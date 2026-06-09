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
    time_weights: Sequence[float] | None = None,
) -> np.ndarray:
    """Weighted residuals for least-squares fitting."""
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    sigma_arr = np.asarray(sigma_arr, dtype=float)

    weights = None
    if time_weights is not None:
        weights = np.asarray(time_weights, dtype=float)
        if weights.ndim != 1:
            raise ValueError("time_weights must be a 1D sequence")

    if log_space:
        eps = 1.0
        if exclude_t0 and len(y_data) > 1:
            y_d = np.maximum(y_data[1:], eps)
            y_s = np.maximum(y_sim[1:], eps)
            sig = sigma_arr[1:]
            log_sigma = np.log1p(sig / y_d)
            log_sigma = np.where(log_sigma > 1.0e-9, log_sigma, 1.0)
            residuals = (np.log(y_s) - np.log(y_d)) / log_sigma
        else:
            y_d = np.maximum(y_data, eps)
            y_s = np.maximum(y_sim, eps)
            log_sigma = np.log1p(sigma_arr / y_d)
            log_sigma = np.where(log_sigma > 1.0e-9, log_sigma, 1.0)
            residuals = (np.log(y_s) - np.log(y_d)) / log_sigma
        if weights is not None:
            if len(weights) != len(residuals):
                raise ValueError(
                    f"time_weights length ({len(weights)}) must match residual count ({len(residuals)})"
                )
            residuals = residuals * weights
        return residuals

    if exclude_t0 and len(y_data) > 1:
        residuals = (y_data[1:] - y_sim[1:]) / sigma_arr[1:]
    else:
        residuals = (y_data - y_sim) / sigma_arr
    if weights is not None:
        if len(weights) != len(residuals):
            raise ValueError(
                f"time_weights length ({len(weights)}) must match residual count ({len(residuals)})"
            )
        residuals = residuals * weights
    return residuals


def evaluate_horizon_acceptance(
    t: Sequence[float],
    y_data: Sequence[float],
    y_sim: Sequence[float],
    *,
    min_sim_to_target: float = 0.55,
    max_sim_to_target: float = 2.5,
) -> tuple[bool, str]:
    """Return whether sim/target at each t>0 is within [min, max] ratios."""
    t_arr = np.asarray(t, dtype=float)
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    if len(y_data) < 2:
        return True, "no post-t0 time points"
    for time_h, target, sim in zip(t_arr[1:], y_data[1:], y_sim[1:]):
        if not np.isfinite(target) or target <= 0:
            continue
        if not np.isfinite(sim):
            return False, f"t={int(time_h)}h simulation is non-finite"
        ratio = float(sim / target)
        if ratio < min_sim_to_target:
            return (
                False,
                f"t={int(time_h)}h sim/target={ratio:.3f} < {min_sim_to_target} "
                f"(sim={sim:.4g}, target={target:.4g})",
            )
        if ratio > max_sim_to_target:
            return (
                False,
                f"t={int(time_h)}h sim/target={ratio:.3f} > {max_sim_to_target} "
                f"(sim={sim:.4g}, target={target:.4g})",
            )
    return True, "accepted"


def viability_penalty_residuals(y_data: np.ndarray, y_sim: np.ndarray) -> np.ndarray:
    """Penalize culture collapse and severe undergrowth (ABM4bio-style guardrails).

    Returns a fixed-length vector so scipy.optimize.least_squares sees stable residual size.
    """
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    p24 = 0.0
    p48 = 0.0
    p72 = 0.0
    p_collapse = 0.0
    if len(y_sim) >= 2 and y_sim[1] < 0.6 * max(y_data[1], 1.0):
        p24 = 3.0 * (0.6 * y_data[1] - y_sim[1])
    if len(y_sim) >= 3 and y_sim[2] < 0.65 * max(y_data[2], 1.0):
        p48 = 10.0 * (0.65 * y_data[2] - y_sim[2])
    if len(y_sim) >= 3 and y_sim[-1] < 0.75 * max(y_data[-1], 1.0):
        p72 = 12.0 * (0.75 * y_data[-1] - y_sim[-1])
    if len(y_sim) >= 2 and y_sim[-1] <= 0.05:
        p_collapse = 15.0
    return np.asarray([p24, p48, p72, p_collapse], dtype=float)


def combine_residuals(base: np.ndarray, y_data: np.ndarray, y_sim: np.ndarray) -> np.ndarray:
    return np.concatenate([base, viability_penalty_residuals(y_data, y_sim)])


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
    parameter_x_scale: Sequence[float] | None = None,
    time_weights: Sequence[float] | None = None,
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
        residuals = combine_residuals(
            compute_weighted_residuals(
                y_data,
                y_sim,
                sigma_arr,
                log_space=log_space,
                exclude_t0=exclude_t0_residuals,
                time_weights=time_weights,
            ),
            y_data,
            y_sim,
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

    x_scale: str | np.ndarray = "jac"
    if parameter_x_scale is not None:
        x_scale = np.asarray(parameter_x_scale, dtype=float)

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
        x_scale=x_scale,
    )

    y_fit = normalize_simulation(simulate(opt.x), normalize_sim_to_t0=normalize_sim_to_t0)
    raw_residuals = y_data - y_fit
    weighted_residuals = compute_weighted_residuals(
        y_data,
        y_fit,
        sigma_arr,
        log_space=log_space,
        exclude_t0=exclude_t0_residuals,
        time_weights=time_weights,
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


def _evaluate_cost(
    simulate: Callable[[Sequence[float]], np.ndarray],
    x: np.ndarray,
    *,
    y_data: np.ndarray,
    sigma_arr: np.ndarray,
    normalize_sim_to_t0: bool,
    log_space: bool,
    exclude_t0_residuals: bool,
    time_weights: Sequence[float] | None = None,
) -> tuple[float, np.ndarray]:
    y_sim = normalize_simulation(simulate(x), normalize_sim_to_t0=normalize_sim_to_t0)
    residuals = combine_residuals(
        compute_weighted_residuals(
            y_data,
            y_sim,
            sigma_arr,
            log_space=log_space,
            exclude_t0=exclude_t0_residuals,
            time_weights=time_weights,
        ),
        y_data,
        y_sim,
    )
    return float(np.sum(residuals ** 2)), y_sim


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
    live_plotter: LiveCalibrationPlotter | None = None,
    verbose: bool = False,
) -> tuple[np.ndarray, float, int]:
    y_data = np.asarray(y_data, dtype=float)
    t_arr = np.asarray(t, dtype=float)
    sigma_arr = _prepare_sigma(sigma, y_data)
    eval_counter = {"n": 0}
    x_start = np.asarray(x0, dtype=float)
    try:
        best_cost, _ = _evaluate_cost(
            simulate,
            x_start,
            y_data=y_data,
            sigma_arr=sigma_arr,
            normalize_sim_to_t0=normalize_sim_to_t0,
            log_space=log_space,
            exclude_t0_residuals=exclude_t0_residuals,
        )
    except Exception:
        best_cost = 1.0e12
    best_x = x_start.copy()

    def objective(x: np.ndarray) -> float:
        nonlocal best_cost, best_x
        eval_counter["n"] += 1
        if verbose:
            print(f"\n=== Global search: evaluation {eval_counter['n']} / up to {max_nfev} ===", flush=True)
        try:
            cost, y_sim = _evaluate_cost(
                simulate,
                x,
                y_data=y_data,
                sigma_arr=sigma_arr,
                normalize_sim_to_t0=normalize_sim_to_t0,
                log_space=log_space,
                exclude_t0_residuals=exclude_t0_residuals,
            )
        except Exception:
            return 1.0e12
        if cost < best_cost:
            best_cost = cost
            best_x = np.asarray(x, dtype=float).copy()
        if live_plotter is not None:
            display_residuals = y_data - y_sim
            live_plotter.update(
                eval_id=eval_counter["n"],
                params=x,
                chi2=cost,
                t=t_arr,
                y_data=y_data,
                y_fit=y_sim,
                residuals=display_residuals,
                stage="global",
            )
        return cost

    dual_annealing(
        objective,
        bounds=list(zip(lb, ub)),
        maxfun=max_nfev,
        x0=x_start,
        seed=seed,
    )
    # Never return a global candidate worse than the starting template point.
    return best_x, float(best_cost), int(eval_counter["n"])


def fit_sequential_horizons(
    simulate_factory: Callable[[Sequence[int], str | None], Callable[[Sequence[float]], np.ndarray]],
    *,
    horizons: Sequence[tuple[str, tuple[int, ...], int]],
    target_loader: Callable[[Sequence[int]], tuple[np.ndarray, np.ndarray, np.ndarray]],
    x0: Sequence[float],
    lb: Sequence[float],
    ub: Sequence[float],
    method: str = "trf",
    normalize_sim_to_t0: bool = True,
    log_space: bool = True,
    live_plotter: LiveCalibrationPlotter | None = None,
    diff_step: float = 0.03,
    parameter_x_scale: Sequence[float] | None = None,
    horizon_time_weights: Sequence[Sequence[float] | None] | None = None,
    horizon_gate_enabled: bool = True,
    horizon_gate_min_sim_to_target: float = 0.55,
    horizon_gate_max_sim_to_target: float = 2.5,
    verbose: bool = False,
) -> FitResult:
    """
    Sequential warm-start calibration:
      1) fit 0–24 h  → best params
      2) fit 0–48 h  starting from (1)
      3) fit 0–72 h  starting from (2)

    Each horizon runs a full 72 h ABM; only the listed time points enter the objective.
    """
    x = np.asarray(x0, dtype=float)
    total_nfev = 0
    last_result: FitResult | None = None
    ran_any = False

    for horizon_index, (label, time_points, horizon_nfev) in enumerate(horizons):
        if int(horizon_nfev) <= 0:
            if verbose:
                print(f"Horizon {label}: skipped (nfev=0)", flush=True)
            continue
        ran_any = True
        time_weights = None
        if horizon_time_weights is not None and horizon_index < len(horizon_time_weights):
            time_weights = horizon_time_weights[horizon_index]
        if verbose:
            print(f"\n=== Calibrating horizon {label} (budget={horizon_nfev}) ===", flush=True)
        t, y_data, sigma = target_loader(time_points)
        simulate = simulate_factory(time_points, label)
        last_result = fit_lm_like(
            simulate,
            t=t,
            y_data=y_data,
            sigma=sigma,
            x0=x,
            lb=lb,
            ub=ub,
            method=method,
            max_nfev=int(horizon_nfev),
            live_plotter=live_plotter,
            normalize_sim_to_t0=normalize_sim_to_t0,
            log_space=log_space,
            diff_step=diff_step,
            parameter_x_scale=parameter_x_scale,
            time_weights=time_weights,
            verbose=verbose,
            stage_label=label,
        )
        x = np.asarray(last_result.x, dtype=float)
        total_nfev += last_result.nfev
        y_fit_horizon = normalize_simulation(simulate(x), normalize_sim_to_t0=normalize_sim_to_t0)
        if verbose:
            print(
                f"Horizon {label} done: weighted_sse={last_result.weighted_sse:.6g}, "
                f"nfev={last_result.nfev}, x={x}",
                flush=True,
            )
        if horizon_gate_enabled:
            accepted, gate_reason = evaluate_horizon_acceptance(
                t,
                y_data,
                y_fit_horizon,
                min_sim_to_target=horizon_gate_min_sim_to_target,
                max_sim_to_target=horizon_gate_max_sim_to_target,
            )
            if not accepted:
                msg = (
                    f"Horizon {label} failed acceptance gate ({gate_reason}). "
                    "Later horizons were not run."
                )
                if verbose:
                    print(f"\n=== STOP: {msg} ===", flush=True)
                last_result.x = [float(v) for v in x]
                last_result.y_fit = [float(v) for v in y_fit_horizon]
                last_result.residuals = [float(v) for v in (y_data - y_fit_horizon)]
                last_result.success = False
                last_result.message = msg
                last_result.stage = label
                last_result.nfev = total_nfev
                return last_result

    if not ran_any or last_result is None:
        raise RuntimeError("No calibration horizon ran (all stage_nfev budgets were 0).")

    full_label, full_time_points, _ = horizons[-1]
    t_full, y_full, sigma_full = target_loader(full_time_points)
    sigma_full_arr = _prepare_sigma(sigma_full, y_full)
    simulate_full = simulate_factory(full_time_points, f"{full_label}_final")
    y_fit = normalize_simulation(simulate_full(x), normalize_sim_to_t0=normalize_sim_to_t0)
    raw_residuals = y_full - y_fit
    weighted_residuals = compute_weighted_residuals(
        y_full,
        y_fit,
        sigma_full_arr,
        log_space=log_space,
        exclude_t0=True,
    )
    ss_res = float(np.sum((y_full - y_fit) ** 2))
    ss_tot = float(np.sum((y_full - np.mean(y_full)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else None

    last_result.x = [float(v) for v in x]
    last_result.cost = float(np.sum(weighted_residuals ** 2))
    last_result.weighted_sse = last_result.cost
    last_result.y_fit = [float(v) for v in y_fit]
    last_result.residuals = [float(v) for v in raw_residuals]
    last_result.r_squared = r_squared
    last_result.nfev = total_nfev
    last_result.stage = full_label
    return last_result


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
    global_nfev: int = 0,
    global_seed: int = 1234,
    normalize_sim_to_t0: bool = True,
    log_space: bool = True,
    live_plotter: LiveCalibrationPlotter | None = None,
    diff_step: float = 0.03,
    parameter_x_scale: Sequence[float] | None = None,
    stage_time_weights: Sequence[Sequence[float]] | None = None,
    full_curve_time_weights: Sequence[float] | None = None,
    verbose: bool = False,
) -> FitResult:
    """Backward-compatible wrapper around fit_sequential_horizons."""
    del sigma_default, global_nfev, global_seed, stage_time_weights, full_curve_time_weights
    horizons = tuple(
        (f"0-{time_points[-1]}h", time_points, int(budget))
        for time_points, budget in stages
    )
    return fit_sequential_horizons(
        simulate_factory,
        horizons=horizons,
        target_loader=target_loader,
        x0=x0,
        lb=lb,
        ub=ub,
        method=method,
        normalize_sim_to_t0=normalize_sim_to_t0,
        log_space=log_space,
        live_plotter=live_plotter,
        diff_step=diff_step,
        parameter_x_scale=parameter_x_scale,
        verbose=verbose,
    )
