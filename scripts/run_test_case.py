#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.abm_runner import ABMRunConfig, calibration_input_overrides, run_abm_once
from abmcal.calibration_params import (
    CONTROL_CAP_OVERRIDES,
    CONTROL_PROLIFERATION_OVERRIDES,
    CONTROL_RUNTIME_OVERRIDES,
)
from abmcal.data_loader import exposure_pretty, read_cap_excel_long, select_target_vector


def parse_float_list(s: str):
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def parse_int_list(s: str):
    return [int(float(x.strip())) for x in s.split(",") if x.strip()]


def parse_csv_values(s: str, cast=str):
    return [cast(x.strip()) for x in s.split(",") if x.strip()]


def read_template_parameter(template_path: str | Path, parameter_name: str) -> str | None:
    template_path = Path(template_path)
    with template_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            if str(row[0]).strip() == parameter_name:
                value = str(row[2]).strip()
                return value or None
    return None


def read_template_time_step_hours(template_path: str | Path, default: float = 1.0) -> float:
    raw = read_template_parameter(template_path, "time_step")
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


MECHANISM12_PROBABILITY_KEYS = (
    "cancer_cell/can_apoptose/probability",
    "cancer_cell/can_grow/probability",
    "cancer_cell/can_divide/probability",
)
MECHANISM11_PROBABILITY_KEYS = (
    "normoxic_CC/can_apoptose/OH_/probability",
    "normoxic_CC/can_grow/probability",
    "normoxic_CC/can_divide/probability",
)


def read_template_probability_params(template_path: str | Path) -> list[float] | None:
    template_path = Path(template_path)
    for keys in (MECHANISM12_PROBABILITY_KEYS, MECHANISM11_PROBABILITY_KEYS):
        values: list[float] = []
        for key in keys:
            raw = read_template_parameter(template_path, key)
            if raw is None or raw.startswith("__parameter_"):
                values = []
                break
            try:
                values.append(float(raw))
            except ValueError:
                values = []
                break
        if len(values) == 3:
            return values
    return None


def build_row_overrides(
    params: list[float],
    parameter_keys: list[str] | None,
    exposure_seconds: int,
    time_step_h: float,
    set_cap_duration: bool,
) -> dict[str, object]:
    row_overrides: dict[str, object] = {}
    if parameter_keys:
        if len(parameter_keys) != len(params):
            raise ValueError(
                f"parameter key count ({len(parameter_keys)}) does not match parameter vector length ({len(params)})"
            )
        row_overrides.update({key: value for key, value in zip(parameter_keys, params)})
    if set_cap_duration:
        exposure_h = float(exposure_seconds) / 3600.0
        duration_steps = 0 if exposure_seconds == 0 else max(1, int(round(exposure_h / max(time_step_h, 1e-12))))
        row_overrides.update({
            "CAP/enabled": bool(exposure_seconds > 0),
            "CAP/start_step": 0,
            "CAP/start_time_h": 0.0,
            "CAP/duration_h": exposure_h,
            "CAP/duration_steps": duration_steps,
        })
    return row_overrides


def abm_results_dir(run_dir: Path) -> Path | None:
    input_csv = run_dir / "input.csv"
    if not input_csv.exists():
        return None
    output_dir_name = read_template_parameter(input_csv, "output_directory") or "results"
    results_dir = run_dir / output_dir_name
    return results_dir if results_dir.is_dir() else None


def save_plot(
    out_path: Path,
    time_points: list[int],
    sim_values: np.ndarray,
    comparable_sim: np.ndarray,
    target_values: np.ndarray | None,
    target_sigma: np.ndarray | None,
    target_mode: str,
    title: str,
) -> None:
    fig, axes = plt.subplots(1, 2 if target_values is not None else 1, figsize=(12 if target_values is not None else 6, 4.5))
    if not isinstance(axes, np.ndarray):
        axes = np.array([axes])

    axes[0].plot(time_points, sim_values, "o-", label="Simulation")
    axes[0].set_xlabel("Time post-treatment [h]")
    axes[0].set_ylabel("N_cells")
    axes[0].set_title("Raw simulation output")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    if target_values is not None:
        axes[1].plot(time_points, comparable_sim, "o-", label="Simulation")
        axes[1].plot(time_points, target_values, "s--", label="Experimental target")
        if target_sigma is not None:
            axes[1].fill_between(
                time_points,
                target_values - target_sigma,
                target_values + target_sigma,
                alpha=0.2,
                label="Target +/- 1 SD",
            )
        axes[1].set_xlabel("Time post-treatment [h]")
        axes[1].set_ylabel("Normalized output" if target_mode == "t0_normalized" else "Output")
        axes[1].set_title("Simulation vs target")
        axes[1].grid(True, alpha=0.3)
        axes[1].legend()

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one fixed-parameter simulation and plot raw output vs experimental target.")
    ap.add_argument("--xlsx", default=None, help="Optional Excel workbook for target comparison.")
    ap.add_argument("--targets-csv", default=str(ROOT / "data" / "calibration_targets_from_excel.csv"), help="Optional long-format targets CSV.")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--exposure-seconds", type=int, default=30)
    ap.add_argument("--target-mode", choices=["t0_normalized", "raw"], default="t0_normalized")
    ap.add_argument("--time-points", default="0,24,48,72")
    ap.add_argument("--template", default=str(ROOT / "templates" / "input_mechanism12_CAP_template.csv"))
    ap.add_argument("--work-root", default=None, help="Deprecated for test runs; use --out-dir as the sole run directory.")
    ap.add_argument("--out-dir", default=str(ROOT / "outputs" / "test_template_case"))
    ap.add_argument("--run-dir", default=None, help="Directory where input.csv is rendered and ABM4bio runs. Defaults to --out-dir.")
    ap.add_argument("--run-command", default="make", help="Command executed in the isolated run dir for real ABM runs.")
    ap.add_argument("--copy-file", action="append", default=[], help="Optional file or directory copied into the run directory. Repeatable.")
    ap.add_argument("--params", default=None, help="Optional parameter override values as comma list.")
    ap.add_argument(
        "--parameter-keys",
        default=None,
        help=(
            "Optional comma list of ABM parameter names to override directly. "
            "If omitted, the template values are used unchanged."
        ),
    )
    ap.add_argument("--set-cap-duration", action="store_true", help="Override CAP duration rows from --exposure-seconds.")
    ap.add_argument(
        "--control-mode",
        action="store_true",
        help="Untreated control run: mechanism-10 template overrides (ROS off, CAP off).",
    )
    ap.add_argument("--mock", action=argparse.BooleanOptionalAction, default=False, help="Use the built-in mock simulator instead of ABM4bio.")
    ap.add_argument("--quiet", action="store_true", help="Suppress live ABM stdout/progress bar.")
    ap.add_argument(
        "--normalize-sim-to-t0",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Normalize simulation to t=0 before comparison when target mode is t0_normalized.",
    )
    args = ap.parse_args()

    parameter_keys = parse_csv_values(args.parameter_keys, str) if args.parameter_keys else None
    if args.params is not None:
        params = parse_float_list(args.params)
    elif parameter_keys:
        raise ValueError("--params is required when --parameter-keys is set")
    else:
        params = read_template_probability_params(args.template)
        if params is None:
            template_text = Path(args.template).read_text()
            params = [0.0001, 0.15, 0.2] if "__parameter_1__" in template_text else [0.0029, 0.52, 0.84]
    time_points = parse_int_list(args.time_points)
    time_step_h = read_template_time_step_hours(args.template, default=1.0)
    row_overrides = build_row_overrides(params, parameter_keys, args.exposure_seconds, time_step_h, args.set_cap_duration)
    if not args.mock:
        row_overrides.update(calibration_input_overrides(args.template))
        row_overrides.setdefault("export_visualization", False)
        row_overrides.setdefault("visualization_interval", 999_999)
    if args.control_mode or (args.exposure_seconds == 0 and not args.set_cap_duration):
        row_overrides.update(CONTROL_RUNTIME_OVERRIDES)
        row_overrides.update(CONTROL_CAP_OVERRIDES)
        row_overrides.update(CONTROL_PROLIFERATION_OVERRIDES)

    out_dir = Path(args.out_dir)
    run_dir = Path(args.run_dir) if args.run_dir else out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    exposure_label = exposure_pretty(args.exposure_seconds)
    run_name = f"test_{args.cell_line}_{args.exposure_seconds}s"

    use_placeholders = parameter_keys is None and "__parameter_1__" in Path(args.template).read_text()
    placeholder_names = ("parameter_1", "parameter_2", "parameter_3") if use_placeholders else tuple()

    config = ABMRunConfig(
        template_path=Path(args.template),
        work_root=Path(args.work_root or out_dir),
        run_dir=run_dir,
        run_command=args.run_command,
        time_points=time_points,
        copy_files=tuple(Path(x) for x in args.copy_file if x),
        mock=args.mock,
        output_metric="viable_cells",
        remove_results_input_copy=not args.mock,
        strip_visualization_after_run=not args.mock,
        stream_stdout=not args.mock and not args.quiet,
    )
    sim_values = run_abm_once(
        params,
        config,
        placeholder_names=placeholder_names,
        parameter_overrides=row_overrides or None,
        run_name=run_name,
    )
    sim_values = np.asarray(sim_values, dtype=float)

    target_values = None
    target_sigma = None
    if args.targets_csv and Path(args.targets_csv).exists():
        df = pd.read_csv(args.targets_csv)
        _, target_y, sigma_y = select_target_vector(
            df,
            cell_line=args.cell_line,
            exposure_seconds=args.exposure_seconds,
            mode=args.target_mode,
            time_points=time_points,
        )
        target_values = target_y.to_numpy(dtype=float)
        target_sigma = sigma_y.to_numpy(dtype=float)
    elif args.xlsx and Path(args.xlsx).exists():
        df = read_cap_excel_long(args.xlsx, recompute_mean=True)
        _, target_y, sigma_y = select_target_vector(
            df,
            cell_line=args.cell_line,
            exposure_seconds=args.exposure_seconds,
            mode=args.target_mode,
            time_points=time_points,
        )
        target_values = target_y.to_numpy(dtype=float)
        target_sigma = sigma_y.to_numpy(dtype=float)

    comparable_sim = sim_values.copy()
    if args.target_mode == "t0_normalized" and args.normalize_sim_to_t0:
        comparable_sim = comparable_sim / max(float(comparable_sim[0]), 1e-12)

    preview_path = out_dir / "simulation_preview.png"
    save_plot(
        preview_path,
        time_points,
        sim_values,
        comparable_sim,
        target_values,
        target_sigma,
        args.target_mode,
        title=f"{args.cell_line} {exposure_label} test run",
    )

    results_dir = abm_results_dir(run_dir) if not args.mock else None

    print("Single simulation completed")
    print(f"Run directory: {run_dir.resolve()}")
    print(f"Curve plot: {preview_path.resolve()}")
    if results_dir is not None:
        pvd_files = sorted(results_dir.glob("*.pvd"))
        print(f"ABM visualization files: {results_dir.resolve()}")
        for pvd in pvd_files:
            print(f"  - {pvd.name}")
        if (results_dir / "stats.csv").exists():
            print("  - stats.csv")
        print(f"input.csv: {(run_dir / 'input.csv').resolve()}")
    elif args.mock:
        print("ABM visualization files: not produced in mock mode (run without MOCK_MODE=1 for PVD output)")
    else:
        print(f"ABM visualization files: not found under {run_dir.resolve()}")


if __name__ == "__main__":
    main()