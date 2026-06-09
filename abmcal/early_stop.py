from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from pathlib import Path
import subprocess

import pandas as pd


@dataclass(frozen=True)
class EarlyStopLimits:
    max_cells: int
    required_end_h: float
    min_sim_hour_fraction: float = 0.15


def probe_stats_progress(stats_path: Path) -> tuple[float, int] | None:
    """Return (current_time_h, N_cells) from the last row of stats.csv, or None if unavailable."""
    if not stats_path.is_file() or stats_path.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(stats_path)
    except Exception:
        return None
    if df.empty:
        return None
    df.columns = [str(c).strip() for c in df.columns]
    time_col = "current_time"
    count_col = "N_cells"
    if time_col not in df.columns or count_col not in df.columns:
        return None
    row = df.iloc[-1]
    try:
        return float(row[time_col]), int(round(float(row[count_col])))
    except (TypeError, ValueError):
        return None


def should_kill_overgrowth(
    *,
    current_time_h: float,
    n_cells: int,
    limits: EarlyStopLimits,
) -> bool:
    if n_cells <= limits.max_cells:
        return False
    if limits.required_end_h <= 0:
        return True
    return current_time_h < limits.required_end_h * limits.min_sim_hour_fraction


def terminate_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        proc.wait()


def compute_early_stop_max_cells(
    *,
    initial_population: int,
    target_values: list[float] | tuple[float, ...],
    normalize_sim_to_t0: bool,
    overgrowth_factor: float,
    fallback_initial: int = 100,
) -> int:
    """Upper cell-count guardrail from targets (MATLAB-style runaway rejection)."""
    base = int(initial_population) if initial_population > 0 else fallback_initial
    targets = [float(v) for v in target_values if v is not None]
    if not targets:
        return max(base * 20, 5_000)
    if normalize_sim_to_t0:
        peak = max(targets[1:], default=targets[0])
        return max(int(round(base * peak * overgrowth_factor)), base + 1)
    return max(int(round(max(targets) * overgrowth_factor)), base + 1)
