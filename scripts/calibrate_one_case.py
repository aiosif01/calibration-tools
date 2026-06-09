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
from abmcal.calibration_config import (
    EARLY_STOP,
    OPTIMIZER,
    control_out_dir,
    get_cell_line_settings,
    resolve_control_template,
)
from abmcal.calibration_params import (
    CONTROL_FIT_PARAMETER_KEYS,
    adjust_mechanism11_lb_for_initial_cells,
    default_fit_bounds,
)
from abmcal.time_units import read_template_time_step_hours
from abmcal.calibration_plots import save_calibration_result_plots
from abmcal.calibration_workflow import CalibrationContext, build_abm_config, load_targets, make_simulate_factory, run_control_calibration
from abmcal.data_loader import read_cap_excel_long, exposure_pretty, select_target_vector
from abmcal.early_stop import compute_early_stop_max_cells
from abmcal.live_plots import LiveCalibrationPlotter
from abmcal.lm_calibrator import fit_lm_like, normalize_simulation


def parse_float_list(s: str):
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def parse_int_list(s: str):
    return [int(float(x.strip())) for x in s.split(",") if x.strip()]


def parse_csv_values(s: str, cast=str):
    return [cast(x.strip()) for x in s.split(",") if x.strip()]


def apply_config_defaults(args: argparse.Namespace) -> None:
    """Fill unset CLI values from config/calibration_settings.py (control mode)."""
    if not args.control_mode or not args.use_config:
        return

    cl = get_cell_line_settings(args.cell_line)
    if args.template is None:
        args.template = str(resolve_control_template(args.cell_line))
    if args.parameter_keys is None:
        args.parameter_keys = ",".join(cl.parameter_keys)
    if args.x0 is None:
        args.x0 = ",".join(f"{v:.12g}" for v in cl.x0)
    if args.lb is None:
        args.lb = ",".join(f"{v:.12g}" for v in cl.lb)
    if args.ub is None:
        args.ub = ",".join(f"{v:.12g}" for v in cl.ub)
    if args.out_dir is None:
        args.out_dir = str(control_out_dir(args.cell_line))
    if args.copy_file == []:
        args.copy_file = [str(p) for p in cl.copy_files if p.is_file()]

    args.target_mode = args.target_mode or OPTIMIZER.target_mode
    args.time_points = args.time_points or ",".join(str(t) for t in OPTIMIZER.time_points)
    args.method = args.method or OPTIMIZER.method
    args.staged = OPTIMIZER.staged if args.staged is None else args.staged
    args.log_space = OPTIMIZER.log_space if args.log_space is None else args.log_space
    args.normalize_sim_to_t0 = (
        OPTIMIZER.normalize_sim_to_t0 if args.normalize_sim_to_t0 is None else args.normalize_sim_to_t0
    )
    args.global_nfev = args.global_nfev if args.global_nfev is not None else OPTIMIZER.global_nfev
    args.global_seed = args.global_seed or OPTIMIZER.global_seed
    args.stage_nfev = args.stage_nfev or ",".join(str(n) for n in OPTIMIZER.stage_nfev)
    args.max_nfev = args.max_nfev or OPTIMIZER.max_nfev_single
    args.replicates = args.replicates or OPTIMIZER.replicates
    args.abm_base_seed = args.abm_base_seed or OPTIMIZER.abm_base_seed
    args.abm_seed_step = args.abm_seed_step or OPTIMIZER.abm_seed_step
    if args.use_abm_seed is None:
        args.use_abm_seed = OPTIMIZER.use_abm_seed
    args.diff_step = args.diff_step or OPTIMIZER.diff_step
    args.xtol = args.xtol or OPTIMIZER.xtol
    args.ftol = args.ftol or OPTIMIZER.ftol
    args.gtol = args.gtol or OPTIMIZER.gtol
    if args.targets_csv is None and OPTIMIZER and (ROOT / "data" / "calibration_targets_from_excel.csv").is_file():
        args.targets_csv = str(ROOT / "data" / "calibration_targets_from_excel.csv")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fit one cell-line/exposure case with staged control calibration.")
    ap.add_argument("--xlsx", default=str(ROOT / "data" / "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"))
    ap.add_argument("--targets-csv", default=None, help="Optional long-format targets CSV from extract_targets.py")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--exposure-seconds", type=int, default=30)
    ap.add_argument("--target-mode", default=None, choices=["t0_normalized", "raw"])
    ap.add_argument("--time-points", default=None)
    ap.add_argument("--template", default=None, help="ABM input template CSV (default: per-cell-line from config)")
    ap.add_argument("--work-root", default=None)
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
        help="Fit control proliferation: CAP off, mechanism-11 params by default, N_cells, staged LM.",
    )
    ap.add_argument(
        "--use-config",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Load template, bounds, and optimizer budgets from config/calibration_settings.py (control-mode).",
    )
    ap.add_argument("--method", default=None, choices=["trf", "dogbox", "lm"])
    ap.add_argument("--sigma", default="data", help="'data' uses Excel SD; otherwise constant numeric value like 0.45")
    ap.add_argument("--max-nfev", type=int, default=None, help="Max evals for non-staged single fit.")
    ap.add_argument("--global-nfev", type=int, default=None, help="Optional global dual_annealing evals before staged local fits (control-mode).")
    ap.add_argument("--global-seed", type=int, default=None)
    ap.add_argument("--stage-nfev", default=None, help="Local fit budget per stage: 24h, 24+48h, full curve.")
    ap.add_argument("--staged", action=argparse.BooleanOptionalAction, default=None, help="Use 24h -> 24+48h -> 72h staged control calibration.")
    ap.add_argument("--log-space", action=argparse.BooleanOptionalAction, default=None, help="Fit log-space residuals for t>0.")
    ap.add_argument("--replicates", type=int, default=None, help="ABM replicates averaged per evaluation.")
    ap.add_argument("--abm-base-seed", type=int, default=None)
    ap.add_argument("--abm-seed-step", type=int, default=None)
    ap.add_argument(
        "--use-abm-seed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Pass RNG seed to ABM4bio (mechanism-11 default: off, matching MATLAB LM).",
    )
    ap.add_argument("--xtol", type=float, default=None)
    ap.add_argument("--ftol", type=float, default=None)
    ap.add_argument("--gtol", type=float, default=None)
    ap.add_argument("--diff-step", type=float, default=None)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--normalize-sim-to-t0", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--no-early-stop", action="store_true", help="Disable ABM overgrowth early termination.")
    args = ap.parse_args()

    if args.control_mode:
        args.exposure_seconds = 0
        args.set_cap_duration = False

    apply_config_defaults(args)

    if args.control_mode:
        args.staged = True if args.staged is None else args.staged
        args.log_space = True if args.log_space is None else args.log_space

    cell_settings = get_cell_line_settings(args.cell_line) if args.control_mode else None
    mechanism = cell_settings.mechanism if cell_settings else None

    parameter_keys = (
        list(cell_settings.parameter_keys)
        if args.control_mode and cell_settings and not args.parameter_keys
        else (parse_csv_values(args.parameter_keys, str) if args.parameter_keys else None)
    )
    if args.control_mode and not parameter_keys:
        parameter_keys = list(CONTROL_FIT_PARAMETER_KEYS)

    template_path = args.template or str(ROOT / "templates" / "input_mechanism12_CAP_template.csv")
    default_x0, default_lb, default_ub = default_fit_bounds(
        parameter_keys,
        template_path=template_path,
        control_mode=args.control_mode,
        mechanism=mechanism,
    )
    x0 = parse_float_list(args.x0 if args.x0 is not None else default_x0)
    copy_files = tuple(Path(x) for x in args.copy_file if x)
    lb = adjust_mechanism11_lb_for_initial_cells(
        parse_float_list(args.lb if args.lb is not None else default_lb),
        parameter_keys,
        copy_files,
    )
    ub = parse_float_list(args.ub if args.ub is not None else default_ub)
    stage_nfev = parse_int_list(args.stage_nfev or "40,40,100")

    if args.targets_csv:
        target_df = pd.read_csv(args.targets_csv)
    else:
        target_df = read_cap_excel_long(args.xlsx, recompute_mean=True)

    exposure_label = exposure_pretty(args.exposure_seconds)
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "outputs" / f"{args.cell_line}_{exposure_label.replace(':', '_')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work_root) if args.work_root else out_dir / "abm_evals"

    time_points = parse_int_list(args.time_points or "0,24,48,72")
    target_rows, y_full, _ = select_target_vector(
        target_df,
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        mode=args.target_mode or "t0_normalized",
        time_points=time_points,
    )
    target_rows.to_csv(out_dir / "target_rows.csv", index=False)

    early_stop_max_cells = None
    if (
        args.control_mode
        and EARLY_STOP.enabled
        and not args.no_early_stop
        and not args.mock
    ):
        initial_pop = cell_settings.initial_population if cell_settings else 0
        early_stop_max_cells = compute_early_stop_max_cells(
            initial_population=initial_pop,
            target_values=y_full.to_numpy(dtype=float),
            normalize_sim_to_t0=bool(args.normalize_sim_to_t0),
            overgrowth_factor=EARLY_STOP.overgrowth_factor,
        )
        if not args.quiet:
            print(f"Early stop: kill run if N_cells > {early_stop_max_cells}", flush=True)

    placeholder_names = cell_settings.placeholder_names if cell_settings else ()
    output_metric = cell_settings.output_metric if cell_settings else "viable_cells"
    cancer_phenotype_id = cell_settings.cancer_phenotype_id if cell_settings else 1

    ctx = CalibrationContext(
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        template_path=Path(template_path),
        work_root=work_root,
        run_command=args.run_command,
        parameter_keys=parameter_keys or [],
        target_df=target_df,
        target_mode=args.target_mode or "t0_normalized",
        calibration_overrides=calibration_input_overrides(template_path, mechanism=mechanism),
        time_step_h=(
            1.0
            if mechanism == 11
            else read_template_time_step_hours(template_path, default=0.01)
        ),
        control_mode=args.control_mode,
        set_cap_duration=args.set_cap_duration,
        copy_files=copy_files,
        mock=args.mock,
        stream_stdout=not args.mock and not args.quiet,
        strip_visualization=not args.mock,
        abm_use_seed=bool(args.use_abm_seed) if args.use_abm_seed is not None else True,
        abm_base_seed=(
            (args.abm_base_seed or 1234)
            if (args.use_abm_seed if args.use_abm_seed is not None else True)
            else None
        ),
        abm_seed_step=args.abm_seed_step or 17,
        replicates=max(1, args.replicates or 1) if not args.mock else 1,
        eval_counter={"n": 0},
        mechanism=mechanism or 11,
        placeholder_names=placeholder_names,
        output_metric=output_metric,
        cancer_phenotype_id=cancer_phenotype_id,
        early_stop_max_cells=early_stop_max_cells,
        early_stop_required_end_h=float(max(time_points)),
        early_stop_min_sim_hour_fraction=EARLY_STOP.min_sim_hour_fraction,
        early_stop_poll_interval_s=EARLY_STOP.poll_interval_s,
    )

    title_suffix = "control proliferation calibration" if args.control_mode else "LM-like calibration"
    if not args.quiet and not args.mock:
        mech_label = f"mechanism {ctx.mechanism}" if args.control_mode else ""
        print(
            f"Starting calibration for {args.cell_line} {exposure_label} "
            f"({mech_label}, horizons=0-24h→0-48h→0-72h, stage_nfev={stage_nfev}, "
            f"abm_seed={'on' if ctx.abm_use_seed else 'off'}, replicates={ctx.replicates})...",
            flush=True,
        )
        print(f"  Template: {template_path}", flush=True)
    plotter = LiveCalibrationPlotter(
        out_dir,
        live=args.live,
        title=f"{args.cell_line} {exposure_label} {title_suffix}",
        parameter_names=parameter_keys or [],
    )

    if args.control_mode and parameter_keys:
        result = run_control_calibration(
            ctx,
            x0=x0,
            lb=lb,
            ub=ub,
            staged=bool(args.staged),
            global_nfev=args.global_nfev if args.staged else 0,
            global_seed=args.global_seed or 1234,
            stage_nfev=stage_nfev,
            method=args.method or "trf",
            max_nfev=args.max_nfev or 150,
            log_space=bool(args.log_space),
            normalize_sim_to_t0=bool(args.normalize_sim_to_t0),
            diff_step=args.diff_step or 0.03,
            live_plotter=plotter,
            verbose=not args.quiet,
            parameter_keys=parameter_keys,
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
            method=args.method or "trf",
            max_nfev=args.max_nfev or 150,
            live_plotter=plotter,
            normalize_sim_to_t0=bool(args.normalize_sim_to_t0),
            log_space=bool(args.log_space),
            diff_step=args.diff_step or 0.03,
            xtol=args.xtol or 1e-6,
            ftol=args.ftol or 1e-6,
            gtol=args.gtol or 1e-6,
            verbose=not args.quiet,
        )

    config = build_abm_config(ctx)
    config.time_points = tuple(time_points)
    final_simulate = make_simulate_factory(ctx, config)(time_points, "final")
    y_raw = np.asarray(final_simulate(result.x), dtype=float)
    y_comparable = normalize_simulation(y_raw, normalize_sim_to_t0=bool(args.normalize_sim_to_t0))
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
    if parameter_keys:
        bar_vals = [float(v) for v in result.x]
        bar_sigmas = None
        if result.sigma_a and len(result.sigma_a) == len(parameter_keys):
            bar_sigmas = [float(s) for s in result.sigma_a]
        save_calibration_result_plots(
            out_dir,
            title=plot_title,
            exposure_label=exposure_label,
            time_h=t,
            y_target=y,
            y_sim_raw=y_raw,
            y_sim_comparable=y_comparable,
            sigma_target=sigma if args.sigma == "data" else None,
            parameter_keys=parameter_keys,
            fitted_values=bar_vals,
            parameter_sigmas=bar_sigmas,
        )
    plotter.save_final_plots(t, y, result.y_fit, sigma_y=sigma if args.sigma == "data" else None, prefix="lm_python")

    if not result.success:
        print(f"WARNING: calibration stopped early — {result.message}", flush=True)
    print("Fit completed" if result.success else "Fit stopped (horizon gate or optimizer failure)")
    print(f"Output directory: {out_dir}")
    if result.stage:
        print(f"Last horizon: {result.stage}")
    if parameter_keys:
        for key, value in zip(parameter_keys, result.x):
            print(f"  {key}: {value:.8g}")
    else:
        print(f"Parameters: {result.x}")
    print(f"Weighted SSE: {result.weighted_sse:.6g}; R^2: {result.r_squared}; nfev: {result.nfev}")
    print("Saved calibration plots:")
    print(f"  {out_dir / 'calibration_01_N_cells_vs_time.png'}")
    print(f"  {out_dir / 'calibration_02_exp_vs_sim.png'}")
    print(f"  {out_dir / 'calibration_03_fitted_parameters.png'} (or calibration_03_probability_bars.png)")


if __name__ == "__main__":
    main()
