"""Optuna calibration engine: orchestrates ABM4bio trials and result export."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import optuna

from abmcal.calibration_workflow import (
    CalibrationContext,
    build_abm_config,
    load_targets,
    make_simulate_factory,
)
from abmcal.core.objective_common import normalize_simulation
from abmcal.live_plots import LiveCalibrationPlotter
from abmcal.method.optuna_objective import build_optuna_objective
from abmcal.method.optuna_reporting import (
    OptunaFitResult,
    export_best_parameters,
    export_failed_trials,
    export_trial_history,
    plot_best_fit_curve,
    plot_optimization_history,
    write_summary_report,
)
from abmcal.method.optuna_importance import plot_parameter_importance, plot_parallel_coordinates
from abmcal.method.optuna_study import create_optuna_study
from abmcal.method.parameter_space import ParameterSpace


@dataclass(frozen=True)
class OptunaRunConfig:
    n_trials: int = 200
    n_replicates: int = 3
    validation_replicates: int = 10
    study_name: str = "optuna_study"
    storage: str | None = None
    sampler_seed: int = 1234
    n_startup_trials: int = 30
    log_space: bool = True
    normalize_sim_to_t0: bool = True
    time_points: tuple[int, ...] = (0, 24, 48, 72)
    prune_after_replicates: int = 2
    show_progress: bool = True


def run_optuna_calibration(
    ctx: CalibrationContext,
    parameter_space: ParameterSpace,
    *,
    out_dir: str | Path,
    run_config: OptunaRunConfig,
    live_plotter: LiveCalibrationPlotter | None = None,
    verbose: bool = False,
) -> OptunaFitResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    trials_dir = out_dir / "trials"
    reports_dir = out_dir / "reports"
    for d in (figures_dir, trials_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)

    config = build_abm_config(ctx)
    config.time_points = run_config.time_points
    simulate_factory = make_simulate_factory(ctx, config)

    def simulate_replicate(params: Sequence[float], replicate_index: int) -> np.ndarray:
        config.replicates = 1
        if ctx.abm_use_seed and ctx.abm_base_seed is not None:
            config.abm_base_seed = int(ctx.abm_base_seed) + replicate_index * int(ctx.abm_seed_step)
        return simulate_factory(run_config.time_points, f"optuna_r{replicate_index}")(params)

    t, y_data, sigma = load_targets(ctx, run_config.time_points)

    def on_update(trial_id: int, params: Sequence[float], score: float, curve: np.ndarray) -> None:
        if live_plotter is not None:
            live_plotter.update(
                eval_id=trial_id,
                params=params,
                chi2=score,
                t=t,
                y_data=y_data,
                y_fit=curve,
                residuals=y_data - curve,
                stage="optuna",
            )
        if verbose:
            print(f"  trial {trial_id}: score={score:.6g}", flush=True)

    objective = build_optuna_objective(
        parameter_space=parameter_space,
        simulate_replicate=simulate_replicate,
        y_data=y_data,
        sigma=sigma,
        normalize_sim_to_t0=run_config.normalize_sim_to_t0,
        log_space=run_config.log_space,
        n_replicates=run_config.n_replicates,
        prune_after_replicates=run_config.prune_after_replicates,
        on_trial_update=on_update,
    )

    study = create_optuna_study(
        study_name=run_config.study_name,
        storage=run_config.storage,
        sampler_seed=run_config.sampler_seed,
        n_startup_trials=run_config.n_startup_trials,
    )

    if verbose:
        print(f"Starting Optuna study '{run_config.study_name}' ({run_config.n_trials} trials)...", flush=True)

    study.optimize(
        objective,
        n_trials=run_config.n_trials,
        show_progress_bar=run_config.show_progress,
    )

    parameter_keys = list(parameter_space.names)
    export_trial_history(study, trials_dir / "trial_history.csv")
    export_failed_trials(study, trials_dir / "failed_trials.csv")
    export_best_parameters(
        study,
        parameter_keys,
        out_dir / "calibrated_parameters.csv",
        time_step_h=ctx.time_step_h,
    )

    best_params = [float(study.best_params[key]) for key in parameter_keys]
    best_trial = study.best_trial

    # Final validation: average validation_replicates separate ABM seeds
    validation_curves: list[np.ndarray] = []
    for r in range(max(1, run_config.validation_replicates)):
        validation_curves.append(simulate_replicate(best_params, r))
    y_raw = np.mean(validation_curves, axis=0)
    y_fit = normalize_simulation(y_raw, normalize_sim_to_t0=run_config.normalize_sim_to_t0)

    raw_residuals = y_data - y_fit
    ss_res = float(np.sum(raw_residuals ** 2))
    ss_tot = float(np.sum((y_data - np.mean(y_data)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else None

    result = OptunaFitResult(
        x=best_params,
        cost=float(best_trial.value) if best_trial.value is not None else float("inf"),
        weighted_sse=float(best_trial.user_attrs.get("score_curve", best_trial.value or 0.0)),
        success=best_trial.state == optuna.trial.TrialState.COMPLETE,
        message=f"Optuna best trial {best_trial.number}",
        n_trials=len(study.trials),
        r_squared=r_squared,
        y_fit=[float(v) for v in y_fit],
        residuals=[float(v) for v in raw_residuals],
        study_name=run_config.study_name,
        best_trial_number=best_trial.number,
    )
    result.save_json(out_dir / "fit_result.json")

    plot_optimization_history(
        study,
        figures_dir / "optimization_history.png",
        title=f"{ctx.cell_line} — optimization history",
    )
    plot_parameter_importance(
        study,
        figures_dir / "parameter_importance.png",
        title=f"{ctx.cell_line} — parameter importance",
    )
    plot_parallel_coordinates(
        study,
        figures_dir / "parallel_coordinates.png",
        title=f"{ctx.cell_line} — parallel coordinates",
    )
    plot_best_fit_curve(
        figures_dir / "best_fit_curve.png",
        time_h=t,
        y_target=y_data,
        y_sim=y_fit,
        sigma=sigma,
        title=f"{ctx.cell_line} — best ABM fit",
    )

    case_label = "control" if ctx.control_mode else f"treat_{ctx.exposure_seconds}s"
    write_summary_report(
        reports_dir / "optuna_summary.md",
        study=study,
        cell_line=ctx.cell_line,
        case_label=case_label,
        parameter_keys=parameter_keys,
        n_replicates=run_config.n_replicates,
    )

    if live_plotter is not None:
        live_plotter.save_final_plots(t, y_data, y_fit, sigma_y=sigma, prefix="optuna")

    return result
