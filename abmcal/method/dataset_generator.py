"""Generate ABM4bio simulation datasets for ANN surrogate training."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from abmcal.calibration_workflow import CalibrationContext, build_abm_config, make_simulate_factory
from abmcal.core.objective_common import normalize_simulation
from abmcal.method.parameter_space import ParameterSpace
from abmcal.method.surrogate_dataset import TIME_COLUMNS, param_column_name


@dataclass(frozen=True)
class DatasetRunConfig:
    n_samples: int = 100
    seeds_per_sample: int = 1
    sampling: str = "lhs"
    seed: int = 1234
    normalize_sim_to_t0: bool = True
    time_points: tuple[int, ...] = (0, 24, 48, 72)


def generate_ann_dataset(
    ctx: CalibrationContext,
    parameter_space: ParameterSpace,
    *,
    out_dir: str | Path,
    run_config: DatasetRunConfig,
    verbose: bool = False,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    datasets_dir = out_dir / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    if run_config.sampling == "lhs":
        param_matrix = parameter_space.lhs_sample(run_config.n_samples, seed=run_config.seed)
    else:
        rng = np.random.default_rng(run_config.seed)
        param_matrix = parameter_space.sample_uniform(rng, run_config.n_samples)

    samples_df = pd.DataFrame(param_matrix, columns=list(parameter_space.names))
    samples_df.insert(0, "sample_id", np.arange(len(samples_df), dtype=int))
    samples_df["cell_line"] = ctx.cell_line
    samples_df["exposure_seconds"] = ctx.exposure_seconds
    samples_df.to_csv(datasets_dir / "ann_parameter_samples.csv", index=False)

    config = build_abm_config(ctx)
    config.time_points = run_config.time_points
    config.replicates = 1
    simulate_factory = make_simulate_factory(ctx, config)

    rows: list[dict] = []
    for sample_id, params in enumerate(param_matrix):
        for seed_idx in range(run_config.seeds_per_sample):
            t0 = time.perf_counter()
            run_status = "ok"
            try:
                if ctx.abm_use_seed and ctx.abm_base_seed is not None:
                    config.abm_base_seed = int(ctx.abm_base_seed) + seed_idx * int(ctx.abm_seed_step)
                simulate = simulate_factory(run_config.time_points, f"ds_{sample_id:05d}_s{seed_idx}")
                y_raw = simulate(params.tolist())
                curve = normalize_simulation(y_raw, normalize_sim_to_t0=run_config.normalize_sim_to_t0)
            except Exception as exc:
                run_status = f"error:{exc}"
                curve = np.full(len(run_config.time_points), np.nan)

            row = {
                "sample_id": int(sample_id),
                "cell_line": ctx.cell_line,
                "exposure_seconds": int(ctx.exposure_seconds),
                "seed": int((ctx.abm_base_seed or 0) + seed_idx * ctx.abm_seed_step),
                "run_status": run_status,
                "runtime_s": float(time.perf_counter() - t0),
            }
            for key, val in zip(parameter_space.names, params):
                row[param_column_name(key)] = float(val)
            for t_h, col, val in zip(run_config.time_points, TIME_COLUMNS, curve):
                row[col] = float(val)
                row[f"time_{int(t_h)}h"] = float(val)
            rows.append(row)

            if verbose:
                print(f"  sample {sample_id + 1}/{run_config.n_samples} seed {seed_idx}: {run_status}", flush=True)

    raw_df = pd.DataFrame(rows)
    raw_df.to_csv(datasets_dir / "ann_abm_runs_raw.csv", index=False)

    ok_df = raw_df[raw_df["run_status"] == "ok"].copy()
    if ok_df.empty:
        training_df = raw_df
    else:
        group_cols = ["sample_id", "cell_line", "exposure_seconds"] + [
            param_column_name(k) for k in parameter_space.names
        ]
        mean_rows = []
        for _, group in ok_df.groupby("sample_id"):
            mean_row = group.iloc[0].to_dict()
            for col in TIME_COLUMNS:
                mean_row[col] = float(group[col].mean())
            mean_row["seed"] = -1
            mean_row["run_status"] = "mean"
            mean_row["runtime_s"] = float(group["runtime_s"].sum())
            mean_rows.append(mean_row)
        training_df = pd.concat([ok_df, pd.DataFrame(mean_rows)], ignore_index=True)

    training_df.to_csv(datasets_dir / "ann_training_dataset.csv", index=False)
    return training_df
