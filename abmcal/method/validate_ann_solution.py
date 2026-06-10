"""Validate ANN-calibrated parameters with real ABM4bio replicates."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from abmcal.calibration_workflow import CalibrationContext, build_abm_config, load_targets, make_simulate_factory
from abmcal.core.objective_common import compute_scalar_objective, normalize_simulation


@dataclass(frozen=True)
class ValidationConfig:
    n_replicates: int = 10
    normalize_sim_to_t0: bool = True
    log_space: bool = True
    time_points: tuple[int, ...] = (0, 24, 48, 72)


def validate_with_abm(
    ctx: CalibrationContext,
    params: Sequence[float],
    *,
    out_dir: str | Path,
    config: ValidationConfig,
) -> dict:
    out_dir = Path(out_dir)
    validation_dir = out_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    abm_config = build_abm_config(ctx)
    abm_config.time_points = config.time_points
    abm_config.replicates = 1
    simulate_factory = make_simulate_factory(ctx, abm_config)

    curves = []
    rows = []
    for r in range(config.n_replicates):
        if ctx.abm_use_seed and ctx.abm_base_seed is not None:
            abm_config.abm_base_seed = int(ctx.abm_base_seed) + r * int(ctx.abm_seed_step)
        simulate = simulate_factory(config.time_points, f"val_{r}")
        y_raw = simulate(list(params))
        curve = normalize_simulation(y_raw, normalize_sim_to_t0=config.normalize_sim_to_t0)
        curves.append(curve)
        row = {"replicate": r, "seed": abm_config.abm_base_seed}
        for t_h, val in zip(config.time_points, curve):
            row[f"y_{int(t_h)}h"] = float(val)
        rows.append(row)

    rep_df = pd.DataFrame(rows)
    rep_df.to_csv(validation_dir / "abm_validation_replicates.csv", index=False)

    stack = np.vstack(curves)
    mean_curve = stack.mean(axis=0)
    std_curve = stack.std(axis=0)

    t, y_data, sigma = load_targets(ctx, config.time_points)
    ann_error = None
    ann_curve_path = out_dir / "calibration" / "ann_inverse_curve.csv"
    if ann_curve_path.is_file():
        ann_df = pd.read_csv(ann_curve_path)
        if "y_ann" in ann_df.columns:
            y_ann = ann_df["y_ann"].to_numpy(dtype=float)
            ann_error = compute_scalar_objective(y_data, y_ann, sigma, log_space=config.log_space)

    abm_error = compute_scalar_objective(y_data, mean_curve, sigma, log_space=config.log_space)

    summary = pd.DataFrame([{
        "cell_line": ctx.cell_line,
        "exposure_seconds": ctx.exposure_seconds,
        "n_replicates": config.n_replicates,
        "abm_validation_error": abm_error,
        "ann_calibration_error": ann_error,
        "abm_mean_y72": float(mean_curve[-1]),
        "target_y72": float(y_data[-1]),
    }])
    summary.to_csv(validation_dir / "abm_validation_summary.csv", index=False)

    if ann_error is not None:
        pd.DataFrame([{
            "ann_error": ann_error,
            "abm_validation_error": abm_error,
            "error_ratio_abm_over_ann": abm_error / ann_error if ann_error > 0 else np.nan,
        }]).to_csv(validation_dir / "ann_vs_abm_validation_error.csv", index=False)

    return {
        "mean_curve": mean_curve,
        "std_curve": std_curve,
        "abm_validation_error": abm_error,
        "ann_calibration_error": ann_error,
        "time_h": t,
        "y_target": y_data,
        "sigma": sigma,
        "replicate_curves": stack,
    }
