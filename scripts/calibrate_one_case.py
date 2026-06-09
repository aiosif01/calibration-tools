#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import csv

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.abm_runner import calibration_input_overrides
from abmcal.calibration_params import CONTROL_MECHANISM12_PARAMETER_KEYS, default_fit_bounds
from abmcal.calibration_plots import save_calibration_result_plots
from abmcal.calibration_workflow import CalibrationContext, build_abm_config, load_targets, make_simulate_factory, run_control_calibration
from abmcal.data_loader import read_cap_excel_long, exposure_pretty, select_target_vector
from abmcal.live_plots import LiveCalibrationPlotter
from abmcal.lm_calibrator import fit_lm_like, normalize_simulation


def parse_float_list(s: str):
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def parse_int_list(s: str):
    return [int(float(x.strip())) for x in s.split(",") if x.strip()]


def parse_csv_values(s: str, cast=str):
    return [cast(x.strip()) for x in s.split(",") if x.strip()]


def read_template_time_step_hours(template_path: str | Path, default: float = 1.0) -> float:
    template_path = Path(template_path)
    with template_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            name = str(row[0]).strip()
            if name == "time_step":
                try:
                    return float(str(row[2]).strip())
                except ValueError:
                    return default
    return default


def main() -> None:
    ap = argparse.ArgumentParser(description="Fit one cell-line/exposure case with staged control calibration.")
    ap.add_argument("--xlsx", default=str(ROOT / "data" / "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"))
    ap.add_argument("--targets-csv", default=None, help="Optional long-format targets CSV from extract_targets.py")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--exposure-seconds", type=int, default=30)
    ap.add_argument("--target-mode", choices=["t0_normalized", "raw"], default="t0_normalized")
    ap.add_argument("--time-points", default="0,24,48,72")
    ap.add_argument("--template", default=str(ROOT / "templates" / "input_mechanism12_CAP_template.csv"))
    ap.add_argument("--work-root", default=str(ROOT / "outputs" / "abm_runs"))
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--run-command", default="make", help="Command executed in each run dir, e.g. '/path/ABM4bio input.csv'")
    ap.add_argument(
        "--copy-file",
        action="append",
        default=[],
        help="Optional file/dir copied into each isolated run directory. Repeatable.",
    )
    ap.add_argument("--x0", default=None, help="Initial values as comma list. If omitted, defaults depend on parameter keys.")
    ap.add_argument("--lb", default=None, help="Lower bounds as comma list. If omitted, defaults depend on parameter keys.")
    ap.add_argument("--ub", default=None, help="Upper bounds as comma list. If omitted, defaults depend on parameter keys.")
    ap.add_argument("--parameter-keys", default=None)
    ap.add_argument("--set-cap-duration", action="store_true")
    ap.add_argument(
        "--control-mode",
        action="store_true",
        help="Fit control proliferation: CAP off, 5 parameters, viable cells, log-space staged calibration.",
    )
    ap.add_argument("--method", choices=["trf", "dogbox", "lm"], default="trf")
    ap.add_argument("--sigma", default="data", help="'data' uses Excel SD; otherwise constant numeric value like 0.45")
    ap.add_argument("--max-nfev", type=int, default=150, help="Max evals for non-staged single fit.")
    ap.add_argument("--global-nfev", type=int, default=40, help="Global dual_annealing evals before staged local fits (control-mode).")
    ap.add_argument("--global-seed", type=int, default=1234)
    ap.add_argument("--stage-nfev", default="40,50,60", help="Local fit budget per stage: 24h, 24+48h, full curve.")
    ap.add_argument("--staged", action=argparse.BooleanOptionalAction, default=True, help="Use 24h -> 24+48h -> 72h staged control calibration.")
    ap.add_argument("--log-space", action=argparse.BooleanOptionalAction, default=True, help="Fit log-space residuals for t>0.")
    ap.add_argument("--replicates", type=int, default=2, help="ABM replicates averaged per evaluation.")
    ap.add_argument("--abm-base-seed", type=int, default=1234)
    ap.add_argument("--abm-seed-step", type=int, default=17)
    ap.add_argument("--xtol", type=float, default=1e-6)
    ap.add_argument("--ftol", type=float, default=1e-6)
    ap.add_argument("--gtol", type=float, default=1e-6)
    ap.add_argument("--diff-step", type=float, default=0.03)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--normalize-sim-to-t0", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()

    if args.control_mode:
        args.exposure_seconds = 0
        args.set_cap_duration = False
        args.staged = True
        args.log_space = True

    parameter_keys = (
        list(CONTROL_MECHANISM12_PARAMETER_KEYS)
        if args.control_mode and not args.parameter_keys
        else (parse_csv_values(args.parameter_keys, str) if args.parameter_keys else None)
    )
    default_x0, default_lb, default_ub = default_fit_bounds(
        parameter_keys,
        template_path=args.template,
        control_mode=args.control_mode,
    )
    x0 = parse_float_list(args.x0 if args.x0 is not None else default_x0)
    lb = parse_float_list(args.lb if args.lb is not None else default_lb)
    ub = parse_float_list(args.ub if args.ub is not None else default_ub)
    stage_nfev = parse_int_list(args.stage_nfev)

    if args.targets_csv:
        target_df = pd.read_csv(args.targets_csv)
    else:
        target_df = read_cap_excel_long(args.xlsx, recompute_mean=True)

    exposure_label = exposure_pretty(args.exposure_seconds)
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "outputs" / f"{args.cell_line}_{exposure_label.replace(':', '_')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    time_points = parse_int_list(args.time_points)
    target_rows, _, _ = select_target_vector(
        target_df,
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        mode=args.target_mode,
        time_points=time_points,
    )
    target_rows.to_csv(out_dir / "target_rows.csv", index=False)

    ctx = CalibrationContext(
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        template_path=Path(args.template),
        work_root=Path(args.work_root),
        run_command=args.run_command,
        parameter_keys=parameter_keys or [],
        target_df=target_df,
        target_mode=args.target_mode,
        calibration_overrides=calibration_input_overrides(args.template),
        time_step_h=read_template_time_step_hours(args.template, default=0.01),
        control_mode=args.control_mode,
        set_cap_duration=args.set_cap_duration,
        copy_files=tuple(Path(x) for x in args.copy_file if x),
        mock=args.mock,
        stream_stdout=not args.mock and not args.quiet,
        strip_visualization=not args.mock,
        abm_base_seed=args.abm_base_seed,
        abm_seed_step=args.abm_seed_step,
        replicates=max(1, args.replicates) if not args.mock else 1,
        eval_counter={"n": 0},
    )

    title_suffix = "control proliferation calibration" if args.control_mode else "LM-like calibration"
    if not args.quiet and not args.mock:
        print(
            f"Starting calibration for {args.cell_line} {exposure_label} "
            f"(staged={args.staged}, global_nfev={args.global_nfev}, replicates={ctx.replicates})...",
            flush=True,
        )
    plotter = LiveCalibrationPlotter(out_dir, live=args.live, title=f"{args.cell_line} {exposure_label} {title_suffix}")

    if args.control_mode and parameter_keys:
        result = run_control_calibration(
            ctx,
            x0=x0,
            lb=lb,
            ub=ub,
            staged=args.staged,
            global_nfev=args.global_nfev if args.staged else 0,
            global_seed=args.global_seed,
            stage_nfev=stage_nfev,
            method=args.method,
            max_nfev=args.max_nfev,
            log_space=args.log_space,
            normalize_sim_to_t0=args.normalize_sim_to_t0,
            diff_step=args.diff_step,
            live_plotter=plotter,
            verbose=not args.quiet,
        )
    else:
        config = build_abm_config(ctx)
        config.time_points = tuple(time_points)
        simulate = make_simulate_factory(ctx, config)(time_points, "single")
        t, y, sigma = load_targets(ctx, time_points)
        if args.sigma != "data":
            sigma = np.full_like(y, float(args.sigma))
        result = fit_lm_like(
            simulate,
            t=t,
            y_data=y,
            sigma=sigma,
            x0=x0,
            lb=lb,
            ub=ub,
            method=args.method,
            max_nfev=args.max_nfev,
            live_plotter=plotter,
            normalize_sim_to_t0=args.normalize_sim_to_t0,
            log_space=args.log_space,
            diff_step=args.diff_step,
            xtol=args.xtol,
            ftol=args.ftol,
            gtol=args.gtol,
            verbose=not args.quiet,
        )

    config = build_abm_config(ctx)
    config.time_points = tuple(time_points)
    final_simulate = make_simulate_factory(ctx, config)(time_points, "final")
    y_raw = np.asarray(final_simulate(result.x), dtype=float)
    y_comparable = normalize_simulation(y_raw, normalize_sim_to_t0=args.normalize_sim_to_t0)
    t, y, sigma = load_targets(ctx, time_points)

    result.save_json(out_dir / "fit_result.json")
    pd.DataFrame({
        "time_h": t,
        "simulation_raw_viable": y_raw,
        "y_data": y,
        "y_fit": result.y_fit,
        "simulation_comparable": y_comparable,
        "residual": result.residuals,
    }).to_csv(out_dir / "fit_curve.csv", index=False)
    if parameter_keys:
        pd.DataFrame({"parameter_name": parameter_keys, "fitted_value": result.x}).to_csv(
            out_dir / "calibrated_parameters.csv",
            index=False,
        )

    plot_title = f"{args.cell_line} {exposure_label}"
    if parameter_keys and len(parameter_keys) >= 3:
        prob_keys = [k for k in parameter_keys if "probability" in k][:3]
        prob_vals = [result.x[parameter_keys.index(k)] for k in prob_keys]
        prob_sigmas = None
        if result.sigma_a and len(result.sigma_a) == len(parameter_keys):
            prob_sigmas = [result.sigma_a[parameter_keys.index(k)] for k in prob_keys]
        save_calibration_result_plots(
            out_dir,
            title=plot_title,
            exposure_label=exposure_label,
            time_h=t,
            y_target=y,
            y_sim_raw=y_raw,
            y_sim_comparable=y_comparable,
            sigma_target=sigma if args.sigma == "data" else None,
            parameter_keys=prob_keys,
            fitted_values=prob_vals,
            parameter_sigmas=prob_sigmas,
        )
    plotter.save_final_plots(t, y, result.y_fit, sigma_y=sigma if args.sigma == "data" else None, prefix="lm_python")

    print("Fit completed")
    print(f"Output directory: {out_dir}")
    if parameter_keys:
        for key, value in zip(parameter_keys, result.x):
            print(f"  {key}: {value:.8g}")
    else:
        print(f"Parameters: {result.x}")
    print(f"Weighted SSE: {result.weighted_sse:.6g}; R^2: {result.r_squared}; nfev: {result.nfev}")
    print("Saved calibration plots:")
    print(f"  {out_dir / 'calibration_01_N_cells_vs_time.png'}")
    print(f"  {out_dir / 'calibration_02_exp_vs_sim.png'}")
    print(f"  {out_dir / 'calibration_03_probability_bars.png'}")


if __name__ == "__main__":
    main()
