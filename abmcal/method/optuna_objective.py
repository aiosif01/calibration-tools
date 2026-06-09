"""Optuna trial objective: ABM4bio replicates with median-pruner reporting."""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
import optuna

from abmcal.core.objective_common import biological_penalty, normalize_simulation, weighted_curve_error
from abmcal.method.parameter_space import ParameterSpace


def build_optuna_objective(
    *,
    parameter_space: ParameterSpace,
    simulate_replicate: Callable[[Sequence[float], int], np.ndarray],
    y_data: np.ndarray,
    sigma: np.ndarray,
    normalize_sim_to_t0: bool = True,
    log_space: bool = False,
    time_weights: Sequence[float] | None = None,
    n_replicates: int = 3,
    prune_after_replicates: int = 2,
    on_trial_update: Callable[[int, Sequence[float], float, np.ndarray], None] | None = None,
) -> Callable[[optuna.Trial], float]:
    """Return an Optuna objective that averages replicate ABM curves (one seed per replicate)."""

    def objective(trial: optuna.Trial) -> float:
        param_dict = parameter_space.sample(trial)
        params = parameter_space.vector_from_dict(param_dict)

        replicate_curves: list[np.ndarray] = []
        replicate_scores: list[float] = []

        for r in range(max(1, n_replicates)):
            try:
                y_raw = simulate_replicate(params, r)
                curve = normalize_simulation(y_raw, normalize_sim_to_t0=normalize_sim_to_t0)
            except Exception as exc:
                trial.set_user_attr("error", str(exc))
                raise optuna.TrialPruned() from exc

            score_r = weighted_curve_error(
                curve,
                y_data,
                sigma,
                log_space=log_space,
                exclude_t0=True,
                time_weights=time_weights,
            )
            replicate_curves.append(curve)
            replicate_scores.append(score_r)

            mean_score = float(np.mean(replicate_scores))
            trial.report(mean_score, step=r)
            if on_trial_update is not None:
                on_trial_update(trial.number + 1, params, mean_score, curve)

            if r >= prune_after_replicates - 1 and trial.should_prune():
                raise optuna.TrialPruned()

        mean_curve = np.mean(replicate_curves, axis=0)
        score_curve = weighted_curve_error(
            mean_curve,
            y_data,
            sigma,
            log_space=log_space,
            exclude_t0=True,
            time_weights=time_weights,
        )
        penalty = biological_penalty(y_data, mean_curve)
        total = float(score_curve + penalty)

        trial.set_user_attr("mean_curve", mean_curve.tolist())
        trial.set_user_attr("replicate_scores", replicate_scores)
        trial.set_user_attr("score_curve", float(score_curve))
        trial.set_user_attr("penalty", float(penalty))
        trial.set_user_attr("params_dict", param_dict)
        return total

    return objective
