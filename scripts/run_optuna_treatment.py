#!/usr/bin/env python3
"""Run Optuna treatment calibration for one cell line and exposure."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_optuna_control import load_yaml_config, parse_int_list  # noqa: E402

from abmcal.abm_runner import calibration_input_overrides  # noqa: E402
from abmcal.calibration_config import (  # noqa: E402
    MECHANISM_12,
    OPTUNA,
    get_cell_line_settings,
    optuna_study_db,
    resolve_treated_template,
    treatment_out_dir,
)
from abmcal.calibration_params import INT_PARAMETER_KEYS  # noqa: E402
from abmcal.calibration_plots import save_calibration_result_plots  # noqa: E402
from abmcal.calibration_workflow import CalibrationContext  # noqa: E402
from abmcal.core.objective_common import normalize_simulation  # noqa: E402
from abmcal.data_loader import exposure_pretty, read_cap_excel_long, select_target_vector  # noqa: E402
from abmcal.live_plots import LiveCalibrationPlotter  # noqa: E402
from abmcal.method.optuna_engine import OptunaRunConfig, run_optuna_calibration  # noqa: E402
from abmcal.method.parameter_space import load_parameter_space_yaml, parameter_space_from_bounds  # noqa: E402
from abmcal.time_units import (  # noqa: E402
    format_time_conversion_audit,
    read_template_time_step_hours,
    validate_simulation_clock,
)
from config.calibration_settings import CAP_EXPOSURE_SECONDS, mechanism12_simulation_clock  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Optuna treatment calibration for one exposure.")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--exposure-seconds", type=int, required=True)
    ap.add_argument("--xlsx", default=str(ROOT / "data" / "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"))
    ap.add_argument("--targets-csv", default=None)
    ap.add_argument("--template", default=None)
    ap.add_argument("--work-root", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--run-command", default="make")
    ap.add_argument("--copy-file", action="append", default=[])
    ap.add_argument("--parameter-space", default=None)
    ap.add_argument("--objective-config", default=None)
    ap.add_argument("--storage", default=None)
    ap.add_argument("--study-name", default=None)
    ap.add_argument("--n-trials", type=int, default=None)
    ap.add_argument("--replicates", type=int, default=None)
    ap.add_argument("--validation-replicates", type=int, default=None)
    ap.add_argument("--abm-base-seed", type=int, default=None)
    ap.add_argument("--abm-seed-step", type=int, default=None)
    ap.add_argument("--use-abm-seed", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--use-config", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--log-space", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--normalize-sim-to-t0", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--target-mode", default=None, choices=["t0_normalized", "raw"])
    ap.add_argument("--time-points", default=None)
    ap.add_argument("--set-cap-duration", action="store_true", default=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.parameter_space is None:
        args.parameter_space = str(OPTUNA.parameter_space_treatment)
    if args.objective_config is None:
        args.objective_config = str(OPTUNA.objective_treatment)
    if args.out_dir is None:
        args.out_dir = str(treatment_out_dir(args.cell_line, args.exposure_seconds))
    if args.storage is None:
        args.storage = optuna_study_db(args.cell_line, f"treat_{args.exposure_seconds}s")
    if args.template is None:
        args.template = str(resolve_treated_template(args.cell_line))
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
    if args.targets_csv is None and (ROOT / "data" / "calibration_targets_from_excel.csv").is_file():
        args.targets_csv = str(ROOT / "data" / "calibration_targets_from_excel.csv")

    cell_settings = get_cell_line_settings(args.cell_line)
    objective_cfg = load_yaml_config(Path(args.objective_config))
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

    template_path = Path(args.template)
    treat_clock = mechanism12_simulation_clock()
    time_step_h = read_template_time_step_hours(template_path, default=treat_clock.time_step_h)
    time_report = validate_simulation_clock(template_path, time_points, treat_clock)
    exposure_label = exposure_pretty(args.exposure_seconds)
    if args.exposure_seconds not in CAP_EXPOSURE_SECONDS and not args.quiet:
        print(
            f"Note: exposure {args.exposure_seconds}s is not in configured CAP_EXPOSURE_SECONDS "
            f"{CAP_EXPOSURE_SECONDS}",
            flush=True,
        )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work_root) if args.work_root else out_dir / "abm_evals"

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
        exposure_seconds=args.exposure_seconds,
        template_path=template_path,
        work_root=work_root,
        run_command=args.run_command,
        parameter_keys=list(parameter_space.names),
        target_df=target_df,
        target_mode=target_mode,
        calibration_overrides=calibration_input_overrides(template_path, mechanism=MECHANISM_12),
        time_step_h=time_step_h,
        control_mode=False,
        set_cap_duration=args.set_cap_duration,
        copy_files=tuple(Path(x) for x in args.copy_file if x),
        mock=args.mock,
        stream_stdout=not args.mock and not args.quiet,
        strip_visualization=not args.mock,
        abm_use_seed=bool(args.use_abm_seed),
        abm_base_seed=args.abm_base_seed if args.use_abm_seed else None,
        abm_seed_step=args.abm_seed_step or 17,
        replicates=max(1, args.replicates or 1) if not args.mock else 1,
        eval_counter={"n": 0},
        mechanism=MECHANISM_12,
        placeholder_names=cell_settings.placeholder_names,
        output_metric=cell_settings.output_metric,
        cancer_phenotype_id=cell_settings.cancer_phenotype_id,
    )

    study_name = args.study_name or f"{args.cell_line}_treat_{args.exposure_seconds}s"
    if not args.quiet and not args.mock:
        print(f"  {treat_clock.describe()}", flush=True)
        print(
            f"  CAP exposure: {args.exposure_seconds} s → "
            f"{treat_clock.cap_duration_steps(args.exposure_seconds)} steps",
            flush=True,
        )
        for warning in time_report.warnings:
            print(f"  TIME WARNING: {warning}", flush=True)
    plotter = LiveCalibrationPlotter(
        out_dir,
        live=args.live,
        title=f"{args.cell_line} {exposure_label} Optuna treatment calibration",
        parameter_names=list(parameter_space.names),
    )

    run_config = OptunaRunConfig(
        n_trials=args.n_trials,
        n_replicates=ctx.replicates,
        validation_replicates=args.validation_replicates,
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
        exposure_seconds=args.exposure_seconds,
        mode=target_mode,
        time_points=time_points,
    )
    t = t_rows["time_h"].astype(float).to_numpy()
    y_comparable = normalize_simulation(result.y_fit, normalize_sim_to_t0=normalize_sim_to_t0)

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

    print(f"Optuna treatment calibration completed: {out_dir}")


if __name__ == "__main__":
    main()
