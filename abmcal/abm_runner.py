from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence, Mapping, Any
import os
import shutil
import subprocess
import sys
import time
import csv

import numpy as np
import pandas as pd

from .early_stop import EarlyStopLimits, probe_stats_progress, should_kill_overgrowth, terminate_process_tree
from .input_template import render_template
from .stats_metrics import read_output_vector


def _initial_cell_diameter_range(initial_cells_path: Path) -> tuple[float, float] | None:
    diameters: list[float] = []
    for line in initial_cells_path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            diameters.append(float(parts[3]))
        except ValueError:
            continue
    if not diameters:
        return None
    return min(diameters), max(diameters)


def _validate_initial_cell_diameter_bounds(
    parameter_overrides: Mapping[str, Any] | None,
    initial_cells_path: Path,
    *,
    phenotype_prefix: str = "normoxic_CC",
) -> None:
    """Fail fast when sampled diameter limits exclude cells in initial_cells.dat."""
    if not parameter_overrides or not initial_cells_path.is_file():
        return
    dia_range = _initial_cell_diameter_range(initial_cells_path)
    if dia_range is None:
        return

    cell_dia_min, cell_dia_max = dia_range
    min_key = f"{phenotype_prefix}/diameter/min"
    max_key = f"{phenotype_prefix}/diameter/max"
    if min_key in parameter_overrides:
        dia_min = float(parameter_overrides[min_key])
        if dia_min > cell_dia_min + 1e-6:
            raise RuntimeError(
                f"{min_key}={dia_min} exceeds the smallest initial cell diameter "
                f"({cell_dia_min}) in {initial_cells_path.name}; ABM4bio would abort with "
                "'erroneous diameter'."
            )
    if max_key in parameter_overrides:
        dia_max = float(parameter_overrides[max_key])
        if dia_max < cell_dia_max - 1e-6:
            raise RuntimeError(
                f"{max_key}={dia_max} is below the largest initial cell diameter "
                f"({cell_dia_max}) in {initial_cells_path.name}; ABM4bio would abort with "
                "'erroneous diameter'."
            )


@dataclass
class ABMRunConfig:
    template_path: Path
    work_root: Path
    run_command: str = "make"
    run_dir: Path | None = None
    output_dir_name: str = "results"
    stats_file_relpath: str = "results/stats.csv"
    time_column: str = "current_time"
    output_column: str = "N_cells"
    output_metric: str = "viable_cells"
    cancer_phenotype_id: int = 1
    time_points: Sequence[int] = (0, 24, 48, 72)
    clean_before_run: bool = True
    env: Mapping[str, str] = field(default_factory=dict)
    copy_files: Sequence[Path] = field(default_factory=tuple)
    timeout_s: int | None = None
    mock: bool = False
    remove_results_input_copy: bool = False
    strip_visualization_after_run: bool = False
    stream_stdout: bool = False
    abm_base_seed: int | None = 1234
    abm_seed_step: int = 1
    abm_use_seed: bool = True
    replicates: int = 1
    early_stop_max_cells: int | None = None
    early_stop_required_end_h: float = 72.0
    early_stop_min_sim_hour_fraction: float = 0.15
    early_stop_poll_interval_s: float = 0.25


def run_abm_once(
    params: Sequence[float],
    config: ABMRunConfig,
    *,
    placeholder_names: Sequence[str] = ("parameter_1", "parameter_2", "parameter_3"),
    parameter_overrides: Mapping[str, Any] | None = None,
    run_name: str | None = None,
) -> np.ndarray:
    """Render input.csv, run ABM4bio, and return output at configured time points."""
    if config.mock:
        return mock_abm_curve(params, config.time_points)

    run_name = run_name or f"run_{int(time.time() * 1e6)}"
    run_dir = Path(config.run_dir) if config.run_dir is not None else Path(config.work_root) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Track possible output directories to clean/read stats from.
    template_output_dir = _read_csv_parameter(config.template_path, "output_directory")
    candidate_output_dirs = [config.output_dir_name]
    if template_output_dir and template_output_dir not in candidate_output_dirs:
        candidate_output_dirs.append(template_output_dir)

    # Copy support files such as initial_cells.dat or a Makefile into the isolated run directory.
    for src in config.copy_files:
        src = Path(src)
        if src.exists():
            dst = run_dir / src.name
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    if config.clean_before_run:
        for out_dir_name in candidate_output_dirs:
            results_dir = run_dir / out_dir_name
            if results_dir.exists():
                shutil.rmtree(results_dir)

    _validate_initial_cell_diameter_bounds(parameter_overrides, run_dir / "initial_cells.dat")

    placeholder_values = {name: value for name, value in zip(placeholder_names, params)}
    render_template(
        config.template_path,
        run_dir / "input.csv",
        placeholder_values=placeholder_values,
        parameter_overrides=parameter_overrides,
    )

    rendered_output_dir = _read_csv_parameter(run_dir / "input.csv", "output_directory") or config.output_dir_name

    env = os.environ.copy()
    env.update({str(k): str(v) for k, v in config.env.items()})

    replicate_vectors: list[np.ndarray] = []
    n_reps = max(1, int(config.replicates))
    for rep_index in range(n_reps):
        if rep_index > 0:
            for out_dir_name in candidate_output_dirs:
                results_dir = run_dir / out_dir_name
                if results_dir.exists():
                    shutil.rmtree(results_dir)
        seed = None
        if config.abm_use_seed and config.abm_base_seed is not None:
            seed = int(config.abm_base_seed) + rep_index * int(config.abm_seed_step)
        command = _abm_command_with_seed(config.run_command, seed)
        log_path = run_dir / ("run.log" if n_reps == 1 else f"run_rep{rep_index:02d}.log")
        early_limits = None
        if config.early_stop_max_cells is not None:
            early_limits = EarlyStopLimits(
                max_cells=int(config.early_stop_max_cells),
                required_end_h=float(config.early_stop_required_end_h),
                min_sim_hour_fraction=float(config.early_stop_min_sim_hour_fraction),
            )
        stats_probe_path = run_dir / rendered_output_dir / Path(config.stats_file_relpath).name

        early_stopped = False
        if config.stream_stdout:
            seed_label = "default" if seed is None else str(seed)
            print(f"\n>>> Starting ABM run: {run_name} (seed={seed_label})", flush=True)
            returncode, early_stopped = _run_abm_streaming(
                command,
                cwd=run_dir,
                env=env,
                log_path=log_path,
                timeout_s=config.timeout_s,
                stats_probe_path=stats_probe_path,
                early_limits=early_limits,
                poll_interval_s=config.early_stop_poll_interval_s,
            )
        else:
            returncode, early_stopped = _run_abm_with_optional_early_stop(
                command,
                cwd=run_dir,
                env=env,
                log_path=log_path,
                timeout_s=config.timeout_s,
                stats_probe_path=stats_probe_path,
                early_limits=early_limits,
                poll_interval_s=config.early_stop_poll_interval_s,
            )

        if returncode != 0 and not early_stopped:
            raise RuntimeError(f"ABM command failed with exit code {returncode}. See {log_path}")

        if early_stopped:
            replicate_vectors.append(overgrowth_penalty_vector(config.time_points))
            continue

        stats_filename = Path(config.stats_file_relpath).name
        stats_path = run_dir / rendered_output_dir / stats_filename
        legacy_stats_path = run_dir / config.stats_file_relpath
        if not stats_path.exists() and legacy_stats_path.exists():
            stats_path = legacy_stats_path
        if not stats_path.exists():
            raise FileNotFoundError(f"ABM stats file not found: {stats_path}")

        if config.strip_visualization_after_run or config.remove_results_input_copy:
            purge_abm_visualization_outputs(
                run_dir / rendered_output_dir,
                remove_results_input_copy=config.remove_results_input_copy or config.strip_visualization_after_run,
            )

        replicate_vectors.append(
            read_output_vector(
                stats_path,
                config.time_points,
                time_column=config.time_column,
                output_metric=config.output_metric,
                phenotype_id=config.cancer_phenotype_id,
            )
        )

    if len(replicate_vectors) == 1:
        return replicate_vectors[0]
    return np.mean(np.vstack(replicate_vectors), axis=0)


def _abm_command_with_seed(run_command: str, seed: int | None) -> str:
    """Append ABM4bio RNG seed when set (`ABM4bio input.csv <seed>`). MATLAB LM omits seed."""
    command = run_command.strip()
    if seed is None:
        return command
    if command.endswith("input.csv"):
        return f"{command} {int(seed)}"
    if "input.csv" in command and str(seed) not in command.split():
        return f"{command} {int(seed)}"
    return f"{command} {int(seed)}"


def overgrowth_penalty_vector(time_points: Sequence[int], *, initial_cells: float = 100.0) -> np.ndarray:
    """Objective penalty when a run is killed for exceeding the cell-count guardrail."""
    return np.array(
        [initial_cells if int(t) <= 0 else initial_cells * 10_000.0 for t in time_points],
        dtype=float,
    )


def _check_early_stop(
    proc: subprocess.Popen,
    *,
    stats_probe_path: Path,
    early_limits: EarlyStopLimits | None,
) -> bool:
    if early_limits is None or proc.poll() is not None:
        return False
    progress = probe_stats_progress(stats_probe_path)
    if progress is None:
        return False
    current_time_h, n_cells = progress
    if should_kill_overgrowth(
        current_time_h=current_time_h,
        n_cells=n_cells,
        limits=early_limits,
    ):
        print(
            f"\n>>> Early stop: N_cells={n_cells} >> {early_limits.max_cells} "
            f"at t={current_time_h:.1f}h",
            flush=True,
        )
        terminate_process_tree(proc)
        return True
    return False


def _run_abm_streaming(
    command: str,
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    timeout_s: int | None,
    stats_probe_path: Path | None = None,
    early_limits: EarlyStopLimits | None = None,
    poll_interval_s: float = 0.25,
) -> tuple[int, bool]:
    """Run ABM4bio while forwarding stdout live (supports \\r progress bars) and saving run.log."""
    early_stopped = False
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        shell=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout_s if timeout_s is not None else None
    last_probe = 0.0
    with log_path.open("wb") as log_f:
        while True:
            if deadline is not None and time.monotonic() > deadline:
                terminate_process_tree(proc)
                raise subprocess.TimeoutExpired(command, timeout_s)
            now = time.monotonic()
            if (
                stats_probe_path is not None
                and early_limits is not None
                and now - last_probe >= poll_interval_s
            ):
                last_probe = now
                if _check_early_stop(proc, stats_probe_path=stats_probe_path, early_limits=early_limits):
                    early_stopped = True
            if proc.poll() is not None:
                break
            byte = proc.stdout.read(1)
            if not byte:
                if proc.poll() is not None:
                    break
                time.sleep(min(poll_interval_s, 0.05))
                continue
            try:
                sys.stdout.buffer.write(byte)
                sys.stdout.buffer.flush()
            except Exception:
                pass
            log_f.write(byte)
            log_f.flush()
    proc.wait()
    if proc.returncode == 0:
        print(f">>> Finished ABM run ({log_path.parent.name})", flush=True)
    elif early_stopped:
        print(f">>> ABM run early-stopped ({log_path.parent.name})", flush=True)
    return int(proc.returncode or 0), early_stopped


def _run_abm_with_optional_early_stop(
    command: str,
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    timeout_s: int | None,
    stats_probe_path: Path | None,
    early_limits: EarlyStopLimits | None,
    poll_interval_s: float,
) -> tuple[int, bool]:
    if early_limits is None or stats_probe_path is None:
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
        log_path.write_text(proc.stdout)
        return int(proc.returncode or 0), False

    early_stopped = False
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        shell=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout_s if timeout_s is not None else None
    last_probe = 0.0
    output_lines: list[str] = []
    while proc.poll() is None:
        if deadline is not None and time.monotonic() > deadline:
            terminate_process_tree(proc)
            raise subprocess.TimeoutExpired(command, timeout_s)
        now = time.monotonic()
        if now - last_probe >= poll_interval_s:
            last_probe = now
            if _check_early_stop(proc, stats_probe_path=stats_probe_path, early_limits=early_limits):
                early_stopped = True
        time.sleep(min(poll_interval_s, 0.05))
    if proc.stdout is not None:
        output_lines.append(proc.stdout.read() or "")
    log_path.write_text("".join(output_lines))
    return int(proc.returncode or 0), early_stopped


def calibration_input_overrides(
    template_path: str | Path,
    *,
    mechanism: int | None = None,
) -> dict[str, object]:
    """Input overrides for ABM runs: no VTK/PVD export; geometry depends on mechanism."""
    from .calibration_config import MECHANISM_11
    from .calibration_params import DOMAIN_2D_OVERRIDES

    overrides: dict[str, object] = {
        "export_visualization": False,
        "cell_export/enabled": False,
        "visualization_interval": 999_999,
    }
    if mechanism == MECHANISM_11:
        # MATLAB LM template: 2D polar dish, resolution stays in template (76).
        overrides["simulation_domain_is_2D"] = True
    else:
        overrides.update(DOMAIN_2D_OVERRIDES)
    return overrides


def skip_visualization_exports(template_path: str | Path) -> dict[str, object]:
    """Backward-compatible alias; prefer calibration_input_overrides()."""
    return calibration_input_overrides(template_path)


def purge_abm_visualization_outputs(
    results_dir: str | Path,
    *,
    remove_results_input_copy: bool = True,
) -> None:
    """Remove VTK/PVD and other non-essential artifacts from an ABM results folder."""
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        return

    for pattern in ("*.pvd", "*.vtu", "*.pvtu"):
        for path in results_dir.glob(pattern):
            path.unlink(missing_ok=True)

    for path in (results_dir / "diffusion_grid.dat",):
        if path.exists():
            path.unlink()

    if remove_results_input_copy:
        duplicate_input = results_dir / "input.csv"
        if duplicate_input.is_file():
            duplicate_input.unlink()

    # Calibration runs should only retain stats.csv; drop VTK subdirs (e.g. simulation_title/).
    for sub in results_dir.iterdir():
        if sub.is_dir():
            shutil.rmtree(sub)


def _read_csv_parameter(csv_path: str | Path, parameter_name: str) -> str | None:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return None
    with csv_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            if str(row[0]).strip() == parameter_name:
                value = str(row[2]).strip()
                return value or None
    return None


def read_stats_vector(
    stats_path: str | Path,
    time_points: Sequence[int] = (0, 24, 48, 72),
    time_column: str = "current_time",
    output_column: str = "N_cells",
) -> np.ndarray:
    df = pd.read_csv(stats_path)
    df.columns = [str(c).strip() for c in df.columns]
    if time_column not in df.columns:
        raise KeyError(f"Missing time column {time_column!r}. Available columns: {list(df.columns)}")
    if output_column not in df.columns:
        raise KeyError(f"Missing output column {output_column!r}. Available columns: {list(df.columns)}")
    out = []
    times = df[time_column].astype(float).to_numpy()
    values = df[output_column].astype(float).to_numpy()
    for t in time_points:
        idx = int(np.argmin(np.abs(times - float(t))))
        out.append(values[idx])
    return np.array(out, dtype=float)


def mock_abm_curve(params: Sequence[float], time_points: Sequence[int]) -> np.ndarray:
    """
    Lightweight stand-in for ABM4bio so the plotting/calibration pipeline can be tested.

    Control parameter order:
    divide_prob, apoptose_prob, diameter_rate, grow_prob, time_window
    """
    p = [float(x) for x in params]
    divide_prob = p[0] if len(p) > 0 else 0.5
    apoptose_prob = p[1] if len(p) > 1 else 0.001
    diameter_rate = p[2] if len(p) > 2 else 0.5
    grow_prob = p[3] if len(p) > 3 else 0.5
    time_window = p[4] if len(p) > 4 else 288.0
    times = np.asarray(time_points, dtype=float)
    n0 = 100.0
    window_factor = min(1.5, max(0.2, time_window / 288.0))
    net_rate = (
        0.01
        + 0.12 * divide_prob
        + 0.08 * grow_prob
        + 0.04 * diameter_rate
        - 0.25 * apoptose_prob
    ) * window_factor
    carrying = 1200.0
    y = carrying / (1.0 + ((carrying - n0) / n0) * np.exp(-net_rate * times))
    return y
