#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import json
import csv

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.abm_runner import ABMRunConfig, calibration_input_overrides, run_abm_once
from abmcal.calibration_params import default_fit_bounds
from abmcal.data_loader import read_cap_excel_long, select_target_vector, exposure_pretty
from abmcal.calibration_plots import make_summary_bar_plots, save_calibration_result_plots
from abmcal.live_plots import LiveCalibrationPlotter
from abmcal.lm_calibrator import fit_lm_like


def parse_csv_values(s: str, cast=str):
    return [cast(x.strip()) for x in s.split(",") if x.strip()]


def parse_floats(s: str):
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def parse_key_value_map(s: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not s:
        return out
    for item in s.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid map entry {item!r}. Expected KEY=VALUE pairs separated by ';'.")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"Invalid map entry {item!r}. Empty key/value is not allowed.")
        out[key] = value
    return out


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
    ap = argparse.ArgumentParser(description="Fit multiple cell-line/exposure cases and create the professor-style bar chart table.")
    ap.add_argument("--xlsx", default=None, help="Input Excel workbook. Required only if --targets-csv is not provided.")
    ap.add_argument("--targets-csv", default=None, help="Optional long-format targets CSV from extract_targets.py")
    ap.add_argument("--cell-lines", default="EGI1,HuCCT1,PANC1,MiaPaCa2")
    ap.add_argument("--exposures-seconds", default="0,30,120,240,300")
    ap.add_argument("--target-mode", choices=["t0_normalized", "raw"], default="t0_normalized")
    ap.add_argument("--template", default=str(ROOT / "templates" / "input_TEMPLATE_m11_from_matlab_lm.csv"))
    ap.add_argument("--work-root", default=str(ROOT / "outputs" / "abm_runs"))
    ap.add_argument("--run-command", default="make")
    ap.add_argument(
        "--run-command-map",
        default=None,
        help=(
            "Optional per-cell-line run command map using ';' separators. "
            "Example: 'EGI1=/path/abm_egi1 input.csv;HuCCT1=/path/abm_hucct1 input.csv'"
        ),
    )
    ap.add_argument("--copy-file", action="append", default=[str(ROOT / "templates" / "initial_cells.dat")])
    ap.add_argument("--out-dir", default=str(ROOT / "outputs" / "batch_fit"))
    ap.add_argument("--x0", default=None, help="Initial values as comma list. If omitted, defaults depend on parameter keys.")
    ap.add_argument("--lb", default=None, help="Lower bounds as comma list. If omitted, defaults depend on parameter keys.")
    ap.add_argument("--ub", default=None, help="Upper bounds as comma list. If omitted, defaults depend on parameter keys.")
    ap.add_argument(
        "--parameter-keys",
        default=None,
        help=(
            "Comma list of ABM parameter names to override directly with fitted values. "
            "Example for mechanism 12: "
            "cancer_cell/can_apoptose/probability,cancer_cell/can_grow/probability,cancer_cell/can_divide/probability"
        ),
    )
    ap.add_argument(
        "--set-cap-duration",
        action="store_true",
        help="Override CAP duration fields from each exposure case (recommended for mechanism 12).",
    )
    ap.add_argument("--max-nfev", type=int, default=20000)
    ap.add_argument("--xtol", type=float, default=1e-8)
    ap.add_argument("--ftol", type=float, default=1e-8)
    ap.add_argument("--gtol", type=float, default=1e-8)
    ap.add_argument("--diff-step", type=float, default=1e-3)
    ap.add_argument("--method", choices=["trf", "dogbox", "lm"], default="trf")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="Suppress per-evaluation progress messages and live ABM stdout.")
    ap.add_argument("--live", action="store_true", help="Live plot each fit. Usually leave off for batch runs.")
    args = ap.parse_args()

    parameter_keys = parse_csv_values(args.parameter_keys, str) if args.parameter_keys else None
    default_x0, default_lb, default_ub = default_fit_bounds(parameter_keys, template_path=args.template)
    x0 = parse_floats(args.x0 if args.x0 is not None else default_x0)
    lb = parse_floats(args.lb if args.lb is not None else default_lb)
    ub = parse_floats(args.ub if args.ub is not None else default_ub)

    if args.targets_csv:
        df = pd.read_csv(args.targets_csv)
    else:
        if not args.xlsx:
            raise ValueError("Provide either --targets-csv or --xlsx")
        df = read_cap_excel_long(args.xlsx, recompute_mean=True)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "calibration_targets_from_excel.csv", index=False)
    time_step_h = read_template_time_step_hours(args.template, default=1.0)
    calibration_overrides = calibration_input_overrides(args.template)

    run_command_map = parse_key_value_map(args.run_command_map)

    summary = []
    for cell_line in parse_csv_values(args.cell_lines, str):
        for exposure_s in parse_csv_values(args.exposures_seconds, int):
            exposure_label = exposure_pretty(exposure_s)
            print(f"Starting {cell_line} {exposure_label} ...")
            case_dir = out_dir / f"{cell_line}_{exposure_label.replace(':','_')}"
            case_dir.mkdir(parents=True, exist_ok=True)
            run_command = run_command_map.get(cell_line, args.run_command)
            config = ABMRunConfig(
                template_path=Path(args.template),
                work_root=Path(args.work_root),
                run_command=run_command,
                copy_files=tuple(Path(x) for x in args.copy_file if x),
                mock=args.mock,
                stream_stdout=not args.mock and not args.quiet,
                strip_visualization_after_run=not args.mock,
                remove_results_input_copy=not args.mock,
            )
            rows, y_data, sigma = select_target_vector(df, cell_line=cell_line, exposure_seconds=exposure_s, mode=args.target_mode)
            t = rows["time_h"].to_numpy(dtype=float)
            y = y_data.to_numpy(dtype=float)
            sig = sigma.to_numpy(dtype=float)
            eval_id = {"n": 0}

            def simulate(params, cell_line=cell_line, exposure_s=exposure_s):
                eval_id["n"] += 1
                row_overrides = dict(calibration_overrides)
                if parameter_keys:
                    if len(parameter_keys) != len(params):
                        raise ValueError(f"parameter key count ({len(parameter_keys)}) does not match parameter vector length ({len(params)})")
                    row_overrides.update({k: v for k, v in zip(parameter_keys, params)})
                if args.set_cap_duration:
                    exposure_h = float(exposure_s) / 3600.0
                    duration_steps = 0 if exposure_s == 0 else max(1, int(round(exposure_h / max(time_step_h, 1e-12))))
                    row_overrides.update({
                        "CAP/enabled": bool(exposure_s > 0),
                        "CAP/start_step": 0,
                        "CAP/start_time_h": 0.0,
                        "CAP/duration_h": exposure_h,
                        "CAP/duration_steps": duration_steps,
                    })
                return run_abm_once(
                    params,
                    config,
                    placeholder_names=("parameter_1", "parameter_2", "parameter_3") if not parameter_keys else tuple(),
                    parameter_overrides=row_overrides or None,
                    run_name=f"{cell_line}_{exposure_s}s_eval_{eval_id['n']:05d}",
                )

            plotter = LiveCalibrationPlotter(case_dir, live=args.live, title=f"{cell_line} {exposure_label}")
            result = fit_lm_like(
                simulate,
                t=t,
                y_data=y,
                sigma=sig,
                x0=x0,
                lb=lb,
                ub=ub,
                method=args.method,
                max_nfev=args.max_nfev,
                live_plotter=plotter,
                normalize_sim_to_t0=True,
                xtol=args.xtol,
                ftol=args.ftol,
                gtol=args.gtol,
                diff_step=args.diff_step,
                verbose=not args.quiet,
            )
            y_raw = np.asarray(simulate(result.x), dtype=float)
            y_comparable = y_raw / max(float(y_raw[0]), 1e-12)

            result.save_json(case_dir / "fit_result.json")
            pd.DataFrame({
                "time_h": t,
                "simulation_raw": y_raw,
                "y_data": y,
                "y_fit": result.y_fit,
                "simulation_comparable": y_comparable,
                "residual": result.residuals,
            }).to_csv(case_dir / "fit_curve.csv", index=False)
            if parameter_keys and len(parameter_keys) >= 3:
                save_calibration_result_plots(
                    case_dir,
                    title=f"{cell_line} {exposure_label}",
                    exposure_label=exposure_label,
                    time_h=t,
                    y_target=y,
                    y_sim_raw=y_raw,
                    y_sim_comparable=y_comparable,
                    sigma_target=sig,
                    parameter_keys=parameter_keys[:3],
                    fitted_values=result.x[:3],
                    parameter_sigmas=result.sigma_a[:3] if result.sigma_a else None,
                )
            plotter.save_final_plots(t, y, result.y_fit, sigma_y=sig, prefix="lm_python")

            summary.append({
                "cell_line": cell_line,
                "exposure_seconds": exposure_s,
                "exposure_label": exposure_label,
                "apoptosis_probability": result.x[0],
                "growth_probability": result.x[1],
                "division_probability": result.x[2],
                "apoptosis_sigma": result.sigma_a[0] if result.sigma_a else np.nan,
                "growth_sigma": result.sigma_a[1] if result.sigma_a else np.nan,
                "division_sigma": result.sigma_a[2] if result.sigma_a else np.nan,
                "weighted_sse": result.weighted_sse,
                "r_squared": result.r_squared,
                "success": result.success,
                "message": result.message,
            })
            print(f"Done {cell_line} {exposure_label}: {result.x}")

    summary_df = pd.DataFrame(summary)
    summary_path = out_dir / "summary_fit_parameters.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"Saved summary to {summary_path}")

    make_summary_bar_plots(summary_df, out_dir)


if __name__ == "__main__":
    main()
