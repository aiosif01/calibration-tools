"""Shared calibration workflow infrastructure (method-neutral)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from .abm_runner import ABMRunConfig, run_abm_once
from .calibration_config import MECHANISM_11, MECHANISM_12
from .calibration_params import (
    CONTROL_FAST_RUNTIME_OVERRIDES,
    CONTROL_PROLIFERATION_OVERRIDES,
    build_mechanism11_runtime_overrides,
    build_mechanism12_runtime_overrides,
    parameter_overrides_from_vector,
)
from .time_units import seconds_to_steps
from .data_loader import select_target_vector


@dataclass
class CalibrationContext:
    cell_line: str
    exposure_seconds: int
    template_path: Path
    work_root: Path
    run_command: str
    parameter_keys: list[str]
    target_df: pd.DataFrame
    target_mode: str
    calibration_overrides: dict[str, object]
    time_step_h: float
    control_mode: bool
    set_cap_duration: bool
    copy_files: tuple[Path, ...]
    mock: bool
    stream_stdout: bool
    strip_visualization: bool
    abm_base_seed: int | None
    abm_seed_step: int
    abm_use_seed: bool
    replicates: int
    eval_counter: dict[str, int]
    mechanism: int = MECHANISM_11
    placeholder_names: tuple[str, ...] = ()
    output_metric: str = "N_cells"
    cancer_phenotype_id: int = 2
    early_stop_max_cells: int | None = None
    early_stop_required_end_h: float = 72.0
    early_stop_min_sim_hour_fraction: float = 0.15
    early_stop_poll_interval_s: float = 0.25


def control_runtime_overrides(mechanism: int, *, time_step_h: float = 1.0) -> dict[str, object]:
    if mechanism == MECHANISM_11:
        return dict(build_mechanism11_runtime_overrides(time_step_h))
    overrides = dict(CONTROL_FAST_RUNTIME_OVERRIDES)
    if mechanism == MECHANISM_12:
        overrides.update(CONTROL_PROLIFERATION_OVERRIDES)
    return overrides


def treatment_runtime_overrides(mechanism: int, *, time_step_h: float = 1.0) -> dict[str, object]:
    if mechanism == MECHANISM_12:
        return dict(build_mechanism12_runtime_overrides(time_step_h))
    return {}


def load_targets(
    ctx: CalibrationContext,
    time_points: Sequence[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows, y_data, sigma_data = select_target_vector(
        ctx.target_df,
        cell_line=ctx.cell_line,
        exposure_seconds=ctx.exposure_seconds,
        mode=ctx.target_mode,
        time_points=time_points,
    )
    t = rows["time_h"].astype(float).to_numpy()
    y = y_data.to_numpy(dtype=float)
    sigma = sigma_data.to_numpy(dtype=float)
    return t, y, sigma


def make_simulate_factory(ctx: CalibrationContext, config: ABMRunConfig) -> Callable:
    def simulate_factory(
        time_points: Sequence[int],
        stage_label: str | None,
    ) -> Callable[[Sequence[float]], np.ndarray]:
        stage_time_points = tuple(int(t) for t in time_points)

        def simulate(params: Sequence[float]) -> np.ndarray:
            config.time_points = stage_time_points
            ctx.eval_counter["n"] = ctx.eval_counter.get("n", 0) + 1
            eval_id = ctx.eval_counter["n"]
            row_overrides = dict(ctx.calibration_overrides)
            if ctx.control_mode:
                row_overrides.update(control_runtime_overrides(ctx.mechanism, time_step_h=ctx.time_step_h))
            elif ctx.mechanism == MECHANISM_12:
                row_overrides.update(treatment_runtime_overrides(ctx.mechanism, time_step_h=ctx.time_step_h))
            row_overrides.update(
                parameter_overrides_from_vector(
                    ctx.parameter_keys,
                    params,
                    time_step_h=ctx.time_step_h,
                )
            )
            if ctx.set_cap_duration:
                exposure_h = float(ctx.exposure_seconds) / 3600.0
                duration_steps = (
                    0
                    if ctx.exposure_seconds == 0
                    else seconds_to_steps(float(ctx.exposure_seconds), ctx.time_step_h)
                )
                row_overrides.update({
                    "CAP/enabled": bool(ctx.exposure_seconds > 0),
                    "CAP/start_step": 0,
                    "CAP/start_time_h": 0.0,
                    "CAP/duration_h": exposure_h,
                    "CAP/duration_steps": duration_steps,
                })
            stage_tag = stage_label or "eval"
            run_name = f"{ctx.cell_line}_{ctx.exposure_seconds}s_{stage_tag}_{eval_id:05d}"
            config.abm_base_seed = ctx.abm_base_seed
            return run_abm_once(
                params,
                config,
                placeholder_names=ctx.placeholder_names,
                parameter_overrides=row_overrides or None,
                run_name=run_name,
            )

        return simulate

    return simulate_factory


def build_abm_config(ctx: CalibrationContext) -> ABMRunConfig:
    return ABMRunConfig(
        template_path=ctx.template_path,
        work_root=ctx.work_root,
        run_command=ctx.run_command,
        time_points=(0, 24, 48, 72),
        copy_files=ctx.copy_files,
        mock=ctx.mock,
        stream_stdout=ctx.stream_stdout,
        strip_visualization_after_run=ctx.strip_visualization,
        remove_results_input_copy=ctx.strip_visualization,
        output_metric=ctx.output_metric,
        cancer_phenotype_id=ctx.cancer_phenotype_id,
        replicates=ctx.replicates,
        abm_base_seed=ctx.abm_base_seed,
        abm_seed_step=ctx.abm_seed_step,
        abm_use_seed=ctx.abm_use_seed,
        early_stop_max_cells=ctx.early_stop_max_cells,
        early_stop_required_end_h=ctx.early_stop_required_end_h,
        early_stop_min_sim_hour_fraction=ctx.early_stop_min_sim_hour_fraction,
        early_stop_poll_interval_s=ctx.early_stop_poll_interval_s,
    )
