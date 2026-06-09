#!/usr/bin/env python3
"""Run Optuna control proliferation calibration for one cell line."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.abm_runner import calibration_input_overrides
from abmcal.calibration_config import (
    EARLY_STOP,
    OPTUNA,
    control_out_dir,
    get_cell_line_settings,
    optuna_study_db,
    resolve_control_template,
)
from abmcal.calibration_params import INT_PARAMETER_KEYS
from abmcal.calibration_plots import save_calibration_result_plots
from abmcal.calibration_workflow import CalibrationContext
from abmcal.core.objective_common import normalize_simulation
from abmcal.data_loader import exposure_pretty, read_cap_excel_long, select_target_vector
from abmcal.early_stop import compute_early_stop_max_cells
from abmcal.live_plots import LiveCalibrationPlotter
from abmcal.method.optuna_engine import OptunaRunConfig, run_optuna_calibration
from abmcal.method.parameter_space import load_parameter_space_yaml, parameter_space_from_bounds
from abmcal.time_units import read_template_time_step_hours


def parse_int_list(s: str) -> list[int]:
    return [int(float(x.strip())) for x in s.split(",") if x.strip()]


def load_yaml_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def apply_config_defaults(args: argparse.Namespace) -> None:
    if not args.use_config:
        return
    cl = get_cell_line_settings(args.cell_line)
    if args.template is None:
        args.template = str(resolve_control_template(args.cell_line))
    if args.out_dir is None:
        args.out_dir = str(control_out_dir(args.cell_line))
    if args.parameter_space is None:
        args.parameter_space = str(OPTUNA.parameter_space_control)
    if args.objective_config is None:
        args.objective_config = str(OPTUNA.objective_control)
    if args.storage is None:
        args.storage = optuna_study_db(args.cell_line, "control")
    if args.n_trials is None:
        args.n_trials = OPTUNA.n_trials
    if args.replicates is None:
        args.replicates = OPTUNA.n_replicates
    if args.validation_replicates is None:
        args.validation_replicates = OPTUNA.validation_replicates
    if args.abm_base_seed is None:
        args.abm_base_seed = OPTUNA.abm_base_seed
    if args.abm_seed_step is None:
        args.abm_seed_step = OPTUNA.abm_seed_step
    if args.use_abm_seed is None:
        args.use_abm_seed = OPTUNA.use_abm_seed
    if args.copy_file == []:
        args.copy_file = [str(p) for p in cl.copy_files if p.is_file()]
    if args.targets_csv is None and (ROOT / "data" / "calibration_targets_from_excel.csv").is_file():
        args.targets_csv = str(ROOT / "data" / "calibration_targets_from_excel.csv")


def main() -> None:
    ap = argparse.ArgumentParser(description="Optuna control proliferation calibration.")
    ap.add_argument("--xlsx", default=str(ROOT / "data" / "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"))
    ap.add_argument("--targets-csv", default=None)
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--template", default=None)
    ap.add_argument("--work-root", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--run-command", default="make")
    ap.add_argument("--copy-file", action="append", default=[])
    ap.add_argument("--parameter-space", default=None, help="YAML parameter space (default: configs/parameter_space_control.yaml)")
    ap.add_argument("--objective-config", default=None)
    ap.add_argument("--storage", default=None, help="Optuna storage URL, e.g. sqlite:///outputs/optuna/studies/EGI1_control.db")
    ap.add_argument("--study-name", default=None)
    ap.add_argument("--n-trials", type=int, default=None)
    ap.add_argument("--replicates", type=int, default=None, help="ABM replicates per Optuna trial")
    ap.add_argument("--validation-replicates", type=int, default=None, help="ABM replicates for final best-parameter validation")
    ap.add_argument("--abm-base-seed", type=int, default=None)
    ap.add_argument("--abm-seed-step", type=int, default=None)
    ap.add_argument("--use-abm-seed", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--use-config", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--log-space", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--normalize-sim-to-t0", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--target-mode", default=None, choices=["t0_normalized", "raw"])
    ap.add_argument("--time-points", default=None)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-early-stop", action="store_true")
    args = ap.parse_args()

    apply_config_defaults(args)

    cell_settings = get_cell_line_settings(args.cell_line)
    objective_cfg = load_yaml_config(Path(args.objective_config or OPTUNA.objective_control))
    target_mode = args.target_mode or objective_cfg.get("target_mode", OPTUNA.target_mode)
    time_points = tuple(
        parse_int_list(args.time_points)
        if args.time_points
        else objective_cfg.get("time_points", OPTUNA.time_points)
    )
    log_space = OPTUNA.log_space if args.log_space is None else args.log_space
    normalize_sim_to_t0 = (
        OPTUNA.normalize_sim_to_t0 if args.normalize_sim_to_t0 is None else args.normalize_sim_to_t0
    )

    if args.targets_csv:
        target_df = pd.read_csv(args.targets_csv)
    else:
        target_df = read_cap_excel_long(args.xlsx, recompute_mean=True)

    template_path = Path(args.template or resolve_control_template(args.cell_line))
    exposure_label = exposure_pretty(0)
    out_dir = Path(args.out_dir or control_out_dir(args.cell_line))
    out_dir.mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work_root) if args.work_root else out_dir / "abm_evals"

    _, y_full, _ = select_target_vector(
        target_df,
        cell_line=args.cell_line,
        exposure_seconds=0,
        mode=target_mode,
        time_points=time_points,
    )

    early_stop_max_cells = None
    if EARLY_STOP.enabled and not args.no_early_stop and not args.mock:
        early_stop_max_cells = compute_early_stop_max_cells(
            initial_population=cell_settings.initial_population,
            target_values=y_full.to_numpy(dtype=float),
            normalize_sim_to_t0=normalize_sim_to_t0,
            overgrowth_factor=EARLY_STOP.overgrowth_factor,
        )
        if not args.quiet:
            print(f"Early stop: kill run if N_cells > {early_stop_max_cells}", flush=True)

    if Path(args.parameter_space).is_file():
        parameter_space = load_parameter_space_yaml(args.parameter_space)
    else:
        parameter_space = parameter_space_from_bounds(
            cell_settings.parameter_keys,
            cell_settings.lb,
            cell_settings.ub,
            int_keys=INT_PARAMETER_KEYS,
        )

    ctx = CalibrationContext(
        cell_line=args.cell_line,
        exposure_seconds=0,
        template_path=template_path,
        work_root=work_root,
        run_command=args.run_command,
        parameter_keys=list(parameter_space.names),
        target_df=target_df,
        target_mode=target_mode,
        calibration_overrides=calibration_input_overrides(template_path, mechanism=cell_settings.mechanism),
        time_step_h=read_template_time_step_hours(template_path, default=1.0),
        control_mode=True,
        set_cap_duration=False,
        copy_files=tuple(Path(x) for x in args.copy_file if x),
        mock=args.mock,
        stream_stdout=not args.mock and not args.quiet,
        strip_visualization=not args.mock,
        abm_use_seed=bool(args.use_abm_seed),
        abm_base_seed=args.abm_base_seed if args.use_abm_seed else None,
        abm_seed_step=args.abm_seed_step or 17,
        replicates=max(1, args.replicates or 1) if not args.mock else 1,
        eval_counter={"n": 0},
        mechanism=cell_settings.mechanism,
        placeholder_names=cell_settings.placeholder_names,
        output_metric=cell_settings.output_metric,
        cancer_phenotype_id=cell_settings.cancer_phenotype_id,
        early_stop_max_cells=early_stop_max_cells,
        early_stop_required_end_h=float(max(time_points)),
        early_stop_min_sim_hour_fraction=EARLY_STOP.min_sim_hour_fraction,
        early_stop_poll_interval_s=EARLY_STOP.poll_interval_s,
    )

    study_name = args.study_name or f"{args.cell_line}_control"
    if not args.quiet and not args.mock:
        print(
            f"Starting Optuna control calibration for {args.cell_line} "
            f"(n_trials={args.n_trials}, replicates={ctx.replicates})...",
            flush=True,
        )
        print(f"  Template: {template_path}", flush=True)
        print(f"  Storage: {args.storage}", flush=True)

    plotter = LiveCalibrationPlotter(
        out_dir,
        live=args.live,
        title=f"{args.cell_line} {exposure_label} Optuna control calibration",
        parameter_names=list(parameter_space.names),
    )

    run_config = OptunaRunConfig(
        n_trials=args.n_trials or OPTUNA.n_trials,
        n_replicates=ctx.replicates,
        validation_replicates=args.validation_replicates or OPTUNA.validation_replicates,
        study_name=study_name,
        storage=args.storage,
        sampler_seed=OPTUNA.sampler_seed,
        n_startup_trials=OPTUNA.n_startup_trials,
        log_space=log_space,
        normalize_sim_to_t0=normalize_sim_to_t0,
        time_points=time_points,
        prune_after_replicates=OPTUNA.prune_after_replicates,
        show_progress=not args.quiet,
    )

    result = run_optuna_calibration(
        ctx,
        parameter_space,
        out_dir=out_dir,
        run_config=run_config,
        live_plotter=plotter,
        verbose=not args.quiet,
    )

    t_rows, y, sigma = select_target_vector(
        target_df,
        cell_line=args.cell_line,
        exposure_seconds=0,
        mode=target_mode,
        time_points=time_points,
    )
    t = t_rows["time_h"].astype(float).to_numpy()
    y_comparable = normalize_simulation(
        result.y_fit,
        normalize_sim_to_t0=normalize_sim_to_t0,
    )

    pd.DataFrame({
        "time_h": t,
        "y_data": y,
        "y_fit": result.y_fit,
        "simulation_comparable": y_comparable,
        "residual": result.residuals,
    }).to_csv(out_dir / "fit_curve.csv", index=False)

    save_calibration_result_plots(
        out_dir,
        title=f"{args.cell_line} {exposure_label}",
        exposure_label=exposure_label,
        time_h=t,
        y_target=y,
        y_sim_raw=result.y_fit,
        y_sim_comparable=y_comparable,
        sigma_target=sigma,
        parameter_keys=list(parameter_space.names),
        fitted_values=result.x,
    )

    print("Optuna calibration completed" if result.success else "Optuna calibration finished with warnings")
    print(f"Output directory: {out_dir}")
    print(f"Best trial: {result.best_trial_number}")
    for key, value in zip(parameter_space.names, result.x):
        print(f"  {key}: {value:.8g}")
    print(f"Objective: {result.cost:.6g}; weighted SSE: {result.weighted_sse:.6g}; R^2: {result.r_squared}")
    print("Saved figures:")
    print(f"  {out_dir / 'figures' / 'optimization_history.png'}")
    print(f"  {out_dir / 'figures' / 'best_fit_curve.png'}")
    print(f"  {out_dir / 'calibration_01_N_cells_vs_time.png'}")


if __name__ == "__main__":
    main()
