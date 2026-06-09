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

from .input_template import render_template
from .stats_metrics import read_output_vector


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
    abm_base_seed: int = 1234
    abm_seed_step: int = 1
    replicates: int = 1


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
        seed = int(config.abm_base_seed) + rep_index * int(config.abm_seed_step)
        command = _abm_command_with_seed(config.run_command, seed)
        log_path = run_dir / ("run.log" if n_reps == 1 else f"run_rep{rep_index:02d}.log")
        if config.stream_stdout:
            print(f"\n>>> Starting ABM run: {run_name} (seed={seed})", flush=True)
            returncode = _run_abm_streaming(
                command,
                cwd=run_dir,
                env=env,
                log_path=log_path,
                timeout_s=config.timeout_s,
            )
        else:
            proc = subprocess.run(
                command,
                cwd=run_dir,
                shell=True,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=config.timeout_s,
            )
            log_path.write_text(proc.stdout)
            returncode = proc.returncode

        if returncode != 0:
            raise RuntimeError(f"ABM command failed with exit code {returncode}. See {log_path}")

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


def _abm_command_with_seed(run_command: str, seed: int) -> str:
    """Append ABM4bio RNG seed: `ABM4bio input.csv <seed>`."""
    command = run_command.strip()
    if command.endswith("input.csv"):
        return f"{command} {int(seed)}"
    if "input.csv" in command and str(seed) not in command.split():
        return f"{command} {int(seed)}"
    return f"{command} {int(seed)}"


def _run_abm_streaming(
    command: str,
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    timeout_s: int | None,
) -> int:
    """Run ABM4bio while forwarding stdout live (supports \\r progress bars) and saving run.log."""
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        shell=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout_s if timeout_s is not None else None
    with log_path.open("wb") as log_f:
        while True:
            if deadline is not None and time.monotonic() > deadline:
                proc.kill()
                proc.wait()
                raise subprocess.TimeoutExpired(command, timeout_s)
            byte = proc.stdout.read(1)
            if not byte:
                break
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
    return int(proc.returncode or 0)


def calibration_input_overrides(template_path: str | Path) -> dict[str, object]:
    """Input overrides for calibration runs: disable VTK/PVD and cell-export output."""
    return {
        "export_visualization": False,
        "cell_export/enabled": False,
    }


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
