from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Sequence
import json

import numpy as np
from scipy.optimize import dual_annealing, least_squares

from .live_plots import LiveCalibrationPlotter


@dataclass
class FitResult:
    x: list[float]
    cost: float
    weighted_sse: float
    success: bool
    message: str
    nfev: int
    r_squared: float | None
    sigma_a: list[float] | None
    corr: list[list[float]] | None
    y_fit: list[float]
    residuals: list[float]
    stage: str | None = None

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))


def _prepare_sigma(sigma: Sequence[float] | float, y_data: np.ndarray) -> np.ndarray:
    if np.isscalar(sigma):
        sigma_arr = np.ones_like(y_data, dtype=float) * float(sigma)
    else:
        sigma_arr = np.asarray(sigma, dtype=float)
        sigma_arr = np.where(np.isfinite(sigma_arr) & (sigma_arr > 0), sigma_arr, 0.45)
    return sigma_arr


def compute_weighted_residuals(
    y_data: np.ndarray,
    y_sim: np.ndarray,
    sigma_arr: np.ndarray,
    *,
    log_space: bool = False,
    exclude_t0: bool = True,
) -> np.ndarray:
    """Weighted residuals for least-squares fitting."""
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    sigma_arr = np.asarray(sigma_arr, dtype=float)

    if log_space:
        eps = 1.0
        if exclude_t0 and len(y_data) > 1:
            y_d = np.maximum(y_data[1:], eps)
            y_s = np.maximum(y_sim[1:], eps)
            sig = sigma_arr[1:]
            log_sigma = np.log1p(sig / y_d)
            log_sigma = np.where(log_sigma > 1.0e-9, log_sigma, 1.0)
            return (np.log(y_s) - np.log(y_d)) / log_sigma
        y_d = np.maximum(y_data, eps)
        y_s = np.maximum(y_sim, eps)
        log_sigma = np.log1p(sigma_arr / y_d)
        log_sigma = np.where(log_sigma > 1.0e-9, log_sigma, 1.0)
        return (np.log(y_s) - np.log(y_d)) / log_sigma

    if exclude_t0 and len(y_data) > 1:
        return (y_data[1:] - y_sim[1:]) / sigma_arr[1:]
    return (y_data - y_sim) / sigma_arr


def normalize_simulation(y_sim: np.ndarray, *, normalize_sim_to_t0: bool) -> np.ndarray:
    y_sim = np.asarray(y_sim, dtype=float)
    if not normalize_sim_to_t0:
        return y_sim
    if y_sim[0] == 0:
        raise ZeroDivisionError("Simulation t0 output is zero; cannot normalize to t0.")
    return y_sim / y_sim[0]


def fit_lm_like(
    simulate: Callable[[Sequence[float]], np.ndarray],
    *,
    t: Sequence[float],
    y_data: Sequence[float],
    sigma: Sequence[float] | float = 0.45,
    x0: Sequence[float] = (0.0001, 0.15, 0.2),
    lb: Sequence[float] = (0.0, 0.01, 0.01),
    ub: Sequence[float] = (0.9999, 0.5, 0.5),
    method: str = "trf",
    max_nfev: int = 20000,
    live_plotter: LiveCalibrationPlotter | None = None,
    normalize_sim_to_t0: bool = True,
    log_space: bool = False,
    exclude_t0_residuals: bool = True,
    xtol: float = 1e-6,
    ftol: float = 1e-6,
    gtol: float = 1e-6,
    diff_step: float = 0.03,
    verbose: bool = False,
    stage_label: str | None = None,
) -> FitResult:
    t = np.asarray(t, dtype=float)
    y_data = np.asarray(y_data, dtype=float)
    sigma_arr = _prepare_sigma(sigma, y_data)

    bounds = (-np.inf, np.inf) if method == "lm" else (np.asarray(lb, dtype=float), np.asarray(ub, dtype=float))
    eval_counter = {"n": 0}

    def residual_function(x: np.ndarray) -> np.ndarray:
        eval_counter["n"] += 1
        if verbose:
            label = stage_label or "fit"
            print(
                f"\n=== {label}: evaluation {eval_counter['n']} / up to {max_nfev} ===",
                flush=True,
            )
        y_sim = normalize_simulation(simulate(x), normalize_sim_to_t0=normalize_sim_to_t0)
        residuals = compute_weighted_residuals(
            y_data,
            y_sim,
            sigma_arr,
            log_space=log_space,
            exclude_t0=exclude_t0_residuals,
        )
        chi2 = float(np.sum(residuals ** 2))
        if live_plotter is not None:
            live_plotter.update(
                eval_id=eval_counter["n"],
                params=x,
                chi2=chi2,
                t=t,
                y_data=y_data,
                y_fit=y_sim,
                residuals=y_data - y_sim,
                stage=stage_label,
            )
        return residuals

    opt = least_squares(
        residual_function,
        x0=np.asarray(x0, dtype=float),
        bounds=bounds,
        method=method,
        max_nfev=max_nfev,
        xtol=xtol,
        ftol=ftol,
        gtol=gtol,
        diff_step=diff_step,
        x_scale="jac",
    )

    y_fit = normalize_simulation(simulate(opt.x), normalize_sim_to_t0=normalize_sim_to_t0)
    raw_residuals = y_data - y_fit
    weighted_residuals = compute_weighted_residuals(
        y_data,
        y_fit,
        sigma_arr,
        log_space=log_space,
        exclude_t0=exclude_t0_residuals,
    )
    weighted_sse = float(np.sum(weighted_residuals ** 2))

    ss_res = float(np.sum((y_data - y_fit) ** 2))
    ss_tot = float(np.sum((y_data - np.mean(y_data)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else None

    sigma_a = None
    corr = None
    try:
        j = opt.jac
        n_residuals = len(weighted_residuals)
        dof = max(1, n_residuals - len(opt.x))
        s_sq = 2.0 * opt.cost / dof
        cov = np.linalg.pinv(j.T @ j) * s_sq
        diag = np.diag(cov)
        sigma_a_arr = np.sqrt(np.maximum(diag, 0))
        denom = np.outer(sigma_a_arr, sigma_a_arr)
        corr_arr = np.divide(cov, denom, out=np.zeros_like(cov), where=denom != 0)
        sigma_a = sigma_a_arr.tolist()
        corr = corr_arr.tolist()
    except Exception:
        pass

    return FitResult(
        x=[float(v) for v in opt.x],
        cost=float(opt.cost),
        weighted_sse=weighted_sse,
        success=bool(opt.success),
        message=str(opt.message),
        nfev=int(opt.nfev),
        r_squared=r_squared,
        sigma_a=sigma_a,
        corr=corr,
        y_fit=[float(v) for v in y_fit],
        residuals=[float(v) for v in raw_residuals],
        stage=stage_label,
    )


def fit_global_search(
    simulate: Callable[[Sequence[float]], np.ndarray],
    *,
    t: Sequence[float],
    y_data: Sequence[float],
    sigma: Sequence[float] | float = 0.45,
    x0: Sequence[float],
    lb: Sequence[float],
    ub: Sequence[float],
    max_nfev: int = 40,
    normalize_sim_to_t0: bool = True,
    log_space: bool = True,
    exclude_t0_residuals: bool = True,
    seed: int = 1234,
    verbose: bool = False,
) -> tuple[np.ndarray, float, int]:
    y_data = np.asarray(y_data, dtype=float)
    sigma_arr = _prepare_sigma(sigma, y_data)
    eval_counter = {"n": 0}

    def objective(x: np.ndarray) -> float:
        eval_counter["n"] += 1
        if verbose:
            print(f"\n=== Global search: evaluation {eval_counter['n']} / up to {max_nfev} ===", flush=True)
        try:
            y_sim = normalize_simulation(simulate(x), normalize_sim_to_t0=normalize_sim_to_t0)
            residuals = compute_weighted_residuals(
                y_data,
                y_sim,
                sigma_arr,
                log_space=log_space,
                exclude_t0=exclude_t0_residuals,
            )
            return float(np.sum(residuals ** 2))
        except Exception:
            return 1.0e12

    result = dual_annealing(
        objective,
        bounds=list(zip(lb, ub)),
        maxfun=max_nfev,
        x0=np.asarray(x0, dtype=float),
        seed=seed,
    )
    return np.asarray(result.x, dtype=float), float(result.fun), int(eval_counter["n"])


def fit_staged_control(
    simulate_factory: Callable[[Sequence[int], str | None], Callable[[Sequence[float]], np.ndarray]],
    *,
    stages: Sequence[tuple[tuple[int, ...], int]],
    target_loader: Callable[[Sequence[int]], tuple[np.ndarray, np.ndarray, np.ndarray]],
    x0: Sequence[float],
    lb: Sequence[float],
    ub: Sequence[float],
    sigma_default: float = 0.45,
    method: str = "trf",
    global_nfev: int = 40,
    global_seed: int = 1234,
    normalize_sim_to_t0: bool = True,
    log_space: bool = True,
    live_plotter: LiveCalibrationPlotter | None = None,
    diff_step: float = 0.03,
    verbose: bool = False,
) -> FitResult:
    """
    Run optional global search, then staged local fits with expanding time horizons.

    simulate_factory(time_points, stage_label) -> simulate(params) callable.
    target_loader(time_points) -> (t, y_data, sigma).
    """
    x = np.asarray(x0, dtype=float)
    total_nfev = 0
    last_result: FitResult | None = None

    if global_nfev > 0:
        full_time_points = stages[-1][0]
        t_g, y_g, sigma_g = target_loader(full_time_points)
        simulate_global = simulate_factory(full_time_points, "global")
        x, _, n_global = fit_global_search(
            simulate_global,
            t=t_g,
            y_data=y_g,
            sigma=sigma_g if len(np.asarray(sigma_g)) == len(y_g) else sigma_default,
            x0=x,
            lb=lb,
            ub=ub,
            max_nfev=global_nfev,
            normalize_sim_to_t0=normalize_sim_to_t0,
            log_space=log_space,
            seed=global_seed,
            verbose=verbose,
        )
        total_nfev += n_global
        if verbose:
            print(f"Global search complete ({n_global} evals). Best x: {x}", flush=True)

    for stage_idx, (time_points, stage_nfev) in enumerate(stages, start=1):
        stage_label = f"stage{stage_idx}_{'-'.join(str(t) for t in time_points)}h"
        t, y_data, sigma = target_loader(time_points)
        simulate = simulate_factory(time_points, stage_label)
        last_result = fit_lm_like(
            simulate,
            t=t,
            y_data=y_data,
            sigma=sigma,
            x0=x,
            lb=lb,
            ub=ub,
            method=method,
            max_nfev=stage_nfev,
            live_plotter=live_plotter,
            normalize_sim_to_t0=normalize_sim_to_t0,
            log_space=log_space,
            diff_step=diff_step,
            verbose=verbose,
            stage_label=stage_label,
        )
        x = np.asarray(last_result.x, dtype=float)
        total_nfev += last_result.nfev
        if verbose:
            print(
                f"{stage_label} complete: weighted_sse={last_result.weighted_sse:.6g}, "
                f"nfev={last_result.nfev}",
                flush=True,
            )

    assert last_result is not None
    last_result.nfev = total_nfev
    last_result.stage = "staged_final"
    return last_result
