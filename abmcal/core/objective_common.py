"""Shared objective functions for comparing ABM4bio output to experimental targets."""
from __future__ import annotations

from typing import Sequence

import numpy as np


def prepare_sigma(sigma: Sequence[float] | float, y_data: np.ndarray) -> np.ndarray:
    if np.isscalar(sigma):
        sigma_arr = np.ones_like(y_data, dtype=float) * float(sigma)
    else:
        sigma_arr = np.asarray(sigma, dtype=float)
        sigma_arr = np.where(np.isfinite(sigma_arr) & (sigma_arr > 0), sigma_arr, 0.45)
    return sigma_arr


def normalize_simulation(y_sim: np.ndarray, *, normalize_sim_to_t0: bool) -> np.ndarray:
    y_sim = np.asarray(y_sim, dtype=float)
    if not normalize_sim_to_t0:
        return y_sim
    if y_sim[0] == 0:
        raise ZeroDivisionError("Simulation t0 output is zero; cannot normalize to t0.")
    return y_sim / y_sim[0]


def compute_weighted_residuals(
    y_data: np.ndarray,
    y_sim: np.ndarray,
    sigma_arr: np.ndarray,
    *,
    log_space: bool = False,
    exclude_t0: bool = True,
    time_weights: Sequence[float] | None = None,
) -> np.ndarray:
    """Weighted residuals used as the curve-matching component of the objective."""
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


def viability_penalty_scalar(y_data: np.ndarray, y_sim: np.ndarray) -> float:
    """Penalize culture collapse and severe undergrowth (ABM4bio-style guardrails)."""
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    penalty = 0.0
    if len(y_sim) >= 2 and y_sim[1] < 0.6 * max(y_data[1], 1.0):
        penalty += 3.0 * (0.6 * y_data[1] - y_sim[1]) ** 2
    if len(y_sim) >= 3 and y_sim[2] < 0.65 * max(y_data[2], 1.0):
        penalty += 10.0 * (0.65 * y_data[2] - y_sim[2]) ** 2
    if len(y_sim) >= 3 and y_sim[-1] < 0.75 * max(y_data[-1], 1.0):
        penalty += 12.0 * (0.75 * y_data[-1] - y_sim[-1]) ** 2
    if len(y_sim) >= 2 and y_sim[-1] <= 0.05:
        penalty += 15.0 ** 2
    return float(penalty)


def biological_penalty(y_data: np.ndarray, y_sim: np.ndarray) -> float:
    return viability_penalty_scalar(y_data, y_sim)


def weighted_curve_error(
    y_sim: np.ndarray,
    y_data: np.ndarray,
    sigma: np.ndarray,
    *,
    log_space: bool = False,
    exclude_t0: bool = True,
    time_weights: Sequence[float] | None = None,
) -> float:
    sigma_arr = prepare_sigma(sigma, np.asarray(y_data, dtype=float))
    residuals = compute_weighted_residuals(
        y_data,
        y_sim,
        sigma_arr,
        log_space=log_space,
        exclude_t0=exclude_t0,
        time_weights=time_weights,
    )
    return float(np.sum(residuals ** 2))


def compute_scalar_objective(
    y_data: np.ndarray,
    y_sim: np.ndarray,
    sigma: Sequence[float] | float,
    *,
    log_space: bool = False,
    exclude_t0: bool = True,
    time_weights: Sequence[float] | None = None,
    include_penalty: bool = True,
) -> float:
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    sigma_arr = prepare_sigma(sigma, y_data)
    curve_score = weighted_curve_error(
        y_sim,
        y_data,
        sigma_arr,
        log_space=log_space,
        exclude_t0=exclude_t0,
        time_weights=time_weights,
    )
    if not include_penalty:
        return curve_score
    return curve_score + biological_penalty(y_data, y_sim)
