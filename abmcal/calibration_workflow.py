from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from .abm_runner import ABMRunConfig, calibration_input_overrides, run_abm_once
from .calibration_params import (
    CONTROL_CALIBRATION_STAGES,
    CONTROL_CAP_OVERRIDES,
    parameter_overrides_from_vector,
)
from .data_loader import select_target_vector
from .lm_calibrator import FitResult, fit_lm_like, fit_staged_control
from .live_plots import LiveCalibrationPlotter


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
    abm_base_seed: int
    abm_seed_step: int
    replicates: int
    eval_counter: dict[str, int]


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
        config.time_points = tuple(int(t) for t in time_points)

        def simulate(params: Sequence[float]) -> np.ndarray:
            ctx.eval_counter["n"] = ctx.eval_counter.get("n", 0) + 1
            eval_id = ctx.eval_counter["n"]
            row_overrides = dict(ctx.calibration_overrides)
            if ctx.control_mode:
                row_overrides.update(CONTROL_CAP_OVERRIDES)
            row_overrides.update(parameter_overrides_from_vector(ctx.parameter_keys, params))
            if ctx.set_cap_duration:
                exposure_h = float(ctx.exposure_seconds) / 3600.0
                duration_steps = (
                    0
                    if ctx.exposure_seconds == 0
                    else max(1, int(round(exposure_h / max(ctx.time_step_h, 1e-12))))
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
            # Fixed base seed per calibration run; replicates use seed, seed+step, ...
            config.abm_base_seed = ctx.abm_base_seed
            return run_abm_once(
                params,
                config,
                placeholder_names=tuple(),
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
        output_metric="viable_cells",
        replicates=ctx.replicates,
        abm_base_seed=ctx.abm_base_seed,
        abm_seed_step=ctx.abm_seed_step,
    )


def run_control_calibration(
    ctx: CalibrationContext,
    *,
    x0: Sequence[float],
    lb: Sequence[float],
    ub: Sequence[float],
    staged: bool = True,
    global_nfev: int = 40,
    global_seed: int = 1234,
    stage_nfev: Sequence[int] = (40, 50, 60),
    method: str = "trf",
    max_nfev: int = 120,
    log_space: bool = True,
    normalize_sim_to_t0: bool = True,
    diff_step: float = 0.03,
    live_plotter: LiveCalibrationPlotter | None = None,
    verbose: bool = False,
) -> FitResult:
    config = build_abm_config(ctx)
    simulate_factory = make_simulate_factory(ctx, config)

    def target_loader(time_points: Sequence[int]):
        return load_targets(ctx, time_points)

    if staged:
        budgets = list(stage_nfev)
        default_budgets = [40, 50, 60]
        while len(budgets) < len(CONTROL_CALIBRATION_STAGES):
            budgets.append(default_budgets[len(budgets)])
        stages = tuple(
            (tp, int(budgets[i]))
            for i, tp in enumerate(CONTROL_CALIBRATION_STAGES)
        )
        return fit_staged_control(
            simulate_factory,
            stages=stages,
            target_loader=target_loader,
            x0=x0,
            lb=lb,
            ub=ub,
            method=method,
            global_nfev=global_nfev,
            global_seed=global_seed,
            normalize_sim_to_t0=normalize_sim_to_t0,
            log_space=log_space,
            live_plotter=live_plotter,
            diff_step=diff_step,
            verbose=verbose,
        )

    t, y, sigma = target_loader(tuple(config.time_points))
    simulate = simulate_factory(config.time_points, "single")
    return fit_lm_like(
        simulate,
        t=t,
        y_data=y,
        sigma=sigma,
        x0=x0,
        lb=lb,
        ub=ub,
        method=method,
        max_nfev=max_nfev,
        live_plotter=live_plotter,
        normalize_sim_to_t0=normalize_sim_to_t0,
        log_space=log_space,
        diff_step=diff_step,
        verbose=verbose,
        stage_label="single",
    )
