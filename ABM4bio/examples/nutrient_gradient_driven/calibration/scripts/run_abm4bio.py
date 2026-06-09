"""
run_abm4bio.py
==============
Generates a simulation input CSV from the template, runs ABM4bio, and
returns the path to the run directory.

Usage (standalone):
    python scripts/run_abm4bio.py \
        --config configs/calibration_config.yaml \
        --params '{"cell_cycle_time_h": 24, "nutrient_uptake_rate": 0.05, \
                   "proliferation_threshold": 0.3, "necrosis_threshold": 0.1, \
                   "quiescence_threshold": 0.2}' \
        --condition ISO10 \
        --seed 1234 \
        --run_id run_0001

The function ``run_simulation`` is the main entry point for the Optuna loop.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import yaml

# Ensure scripts/ is importable from calibration/
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from load_experimental_data import (
    load_config,
    load_experimental_data,
    estimate_initial_cells_from_area,
    estimate_initial_sphere_radius_from_area,
    get_t0_shell_area_um2,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_simulation(
    params_dict: dict[str, Any],
    condition: str,
    seed: int,
    run_id: str,
    config: dict,
    config_dir: Path,
    bounds_config: Optional[dict] = None,
    dry_run: bool = False,
) -> Path:
    """
    Generate input CSV, run ABM4bio, return run directory Path.

    Parameters
    ----------
    params_dict    : calibrated parameters (float values)
    condition      : 'ISO10' or 'DeltaC'
    seed           : integer random seed
    run_id         : unique run identifier string (e.g. 'trial_0042')
    config         : dict loaded from calibration_config.yaml
    config_dir     : directory containing the config file (for relative paths)
    bounds_config  : dict loaded from parameter_bounds.yaml (for transform rules)
    dry_run        : if True, generate CSV but do not execute ABM4bio

    Returns
    -------
    Path to the run output directory
    """
    # ---- resolve paths -----------------------------------------------------
    results_dir = (config_dir.parent / config["results_dir"]).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    run_dir = (results_dir / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    executable = str(
        (config_dir.parent / config["abm4bio_executable"]).resolve()
    )

    # ---- locate condition info in config -----------------------------------
    condition_cfg = _get_condition_cfg(config, condition)
    template_path = config_dir.parent / condition_cfg["template_csv"]
    if not template_path.exists():
        raise FileNotFoundError(f"Template CSV not found: {template_path}")

    # ---- load experimental data for t=0 initial conditions -----------------
    excel_path = config_dir.parent / config["excel_file"]
    exp_df = load_experimental_data(excel_path, config, condition)
    t0_shell_area = get_t0_shell_area_um2(exp_df, condition)
    n0_total = estimate_initial_cells_from_area(
        t0_shell_area,
        config.get("cell_diameter_max_um", 18.0),
    )
    initial_necrotic_cells = int(round(
        params_dict.get(
            "initial_necrotic_cells",
            config.get("initial_necrotic_cells", 0),
        )
    ))
    initial_necrotic_cells = max(0, initial_necrotic_cells)
    max_nec_fraction = float(config.get("initial_necrotic_max_fraction", 0.35))
    min_normoxic_cells = int(config.get("initial_necrotic_min_normoxic_cells", 30))
    max_by_fraction = int(round(n0_total * max(0.0, min(1.0, max_nec_fraction))))
    max_by_viable = max(0, n0_total - max(1, min_normoxic_cells))
    max_allowed_necrotic = max(0, min(max_by_fraction, max_by_viable))
    initial_necrotic_cells = min(initial_necrotic_cells, max_allowed_necrotic)
    n0 = max(1, n0_total - initial_necrotic_cells)
    sphere_radius_um = estimate_initial_sphere_radius_from_area(t0_shell_area)
    # Clamp sphere radius: at least one cell diameter, at most half the domain
    min_r = config.get("cell_diameter_max_um", 18.0)
    max_r = (config.get("domain_max_um", 600.0) -
             config.get("domain_min_um", -600.0)) * 0.4
    sphere_radius_um = max(min_r, min(sphere_radius_um, max_r))

    # ---- compute necrotic core radius for initial placement ----------------
    # Necrotic cells should be seeded near the center of the spheroid, not
    # randomly throughout the domain. Use a fixed fraction of sphere_radius.
    necrotic_core_fraction = float(config.get("initial_necrotic_core_fraction", 0.40))
    necrotic_core_radius_um = max(5.0, sphere_radius_um * necrotic_core_fraction)

    input_csv_path = results_dir / f"{run_id}_input.csv"
    _generate_input_csv(
        template_path=template_path,
        output_path=input_csv_path,
        run_dir_name=str(run_dir),
        simulation_title=condition_cfg.get("simulation_title", f"NIH3T3_{condition}"),
        params_dict=params_dict,
        bounds_config=bounds_config,
        config=config,
        n0=n0,
        necrotic_n0=initial_necrotic_cells,
        sphere_radius_um=sphere_radius_um,
        necrotic_core_radius_um=necrotic_core_radius_um,
    )

    # ---- write metadata JSON ----------------------------------------------
    metadata = {
        "run_id":           run_id,
        "condition":        condition,
        "seed":             seed,
        "parameters":       params_dict,
        "n0_cells":         n0,
        "n0_total_cells":   n0_total,
        "n0_necrotic_cells": initial_necrotic_cells,
        "sphere_radius_um": sphere_radius_um,
        "t0_shell_area_um2": t0_shell_area,
        "simulation_duration_h": config.get("simulation_duration_h", 48.0),
        "time_step_h":      config.get("time_step_h", 0.1),
        "domain_min_um":    config.get("domain_min_um", -600.0),
        "domain_max_um":    config.get("domain_max_um",  600.0),
        "pixel_scale_um_per_px": config.get("pixel_scale_um_per_px",
                                            1.21079857960497),
        "executable":       executable,
        "run_status":       "pending",
        "abm4bio_commit":   _get_git_commit(config_dir.parent / config["abm4bio_dir"]),
        "timestamp":        time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(run_dir / "metadata.json", "w") as fh:
        json.dump(metadata, fh, indent=2)

    if dry_run:
        print(f"[dry_run] Would execute: {executable} {input_csv_path} {seed}")
        return run_dir

    # ---- run ABM4bio -------------------------------------------------------
    omp_threads = config.get("omp_num_threads", 4)
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(omp_threads)

    cmd = [executable, str(input_csv_path), str(seed)]
    if config.get("verbose", False):
        print(f"[ABM4bio] Running: {' '.join(shlex.quote(c) for c in cmd)}")

    t_start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(run_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=3600,       # 1-hour hard limit
        )
        elapsed = time.time() - t_start
        status = "ok" if result.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t_start
        status = "timeout"
        result = None

    # Append stdout log
    log_path = run_dir / "abm4bio.log"
    with open(log_path, "w") as fh:
        if result is not None:
            fh.write(result.stdout.decode("utf-8", errors="replace"))
        else:
            fh.write("TIMEOUT\n")

    # Update metadata
    metadata["run_status"]  = status
    metadata["elapsed_s"]   = round(elapsed, 2)
    with open(run_dir / "metadata.json", "w") as fh:
        json.dump(metadata, fh, indent=2)

    if status != "ok":
        raise RuntimeError(
            f"ABM4bio exited with status '{status}' "
            f"(returncode={result.returncode if result else 'N/A'}). "
            f"Log: {log_path}"
        )

    return run_dir


# ---------------------------------------------------------------------------
# CSV generation helpers
# ---------------------------------------------------------------------------

def _generate_input_csv(
    template_path: Path,
    output_path: Path,
    run_dir_name: str,
    simulation_title: str,
    params_dict: dict[str, Any],
    bounds_config: Optional[dict],
    config: dict,
    n0: int,
    necrotic_n0: int,
    sphere_radius_um: float,
    necrotic_core_radius_um: float = 40.0,
) -> None:
    """
    Read template CSV and substitute PLACEHOLDER_* tokens with real values,
    then apply calibrated parameter values.
    """
    time_step = config.get("time_step_h", 0.1)

    # Build CSV overrides from calibrated parameters
    csv_overrides: dict[str, tuple[str, Any]] = {}  # key → (type_str, value)
    if bounds_config:
        for param_name, param_val in params_dict.items():
            if param_name not in bounds_config.get("parameters", {}):
                continue
            p_cfg = bounds_config["parameters"][param_name]
            for csv_key_spec in p_cfg.get("csv_keys", []):
                key     = csv_key_spec["key"]
                ptype   = csv_key_spec.get("type", "float")
                transform = csv_key_spec.get("transform", "identity")
                val = _apply_transform(param_val, transform, time_step)
                csv_overrides[key] = (ptype, val)

    # Read template
    lines = template_path.read_text().splitlines(keepends=True)

    with open(output_path, "w") as fh:
        for line in lines:
            # Skip comment lines (start with #)
            if line.lstrip().startswith("#"):
                # ABM4bio CSV parser expects exactly 3 columns per row.
                fh.write("#,#,#\n")
                continue

                # Handle placeholder substitutions first
            line = line.replace("PLACEHOLDER_OUTPUT_DIR", run_dir_name)
            line = line.replace("PLACEHOLDER_N0", str(n0))
            line = line.replace(
                "PLACEHOLDER_SPHERE_RADIUS",
                f"{sphere_radius_um:.2f}",
            )
            line = line.replace(
                "PLACEHOLDER_NECROTIC_CORE_RADIUS",
                f"{necrotic_core_radius_um:.2f}",
            )
            # PLACEHOLDER_VMAX: handled via csv_overrides (nutrient_vmax → neg transform)
            # but also support the old PLACEHOLDER_UPTAKE_RATE text if present
            vmax_raw = params_dict.get("nutrient_vmax",
                       params_dict.get("nutrient_uptake_rate", 0.02))
            line = line.replace(
                "PLACEHOLDER_VMAX",
                f"{-abs(vmax_raw):.6f}",
            )
            line = line.replace(
                "PLACEHOLDER_PROLIF_THRESHOLD",
                f"{params_dict.get('proliferation_threshold', 0.35):.4f}",
            )
            # Mechanism-11 phase dwell placeholders
            # Support both new (phase_G1_h / phase_S_h / phase_G2_h) and
            # legacy (cell_cycle_time_h) parameter names.
            if "phase_G1_h" in params_dict:
                g1_h = params_dict["phase_G1_h"]
                sy_h = params_dict.get("phase_S_h", 6.0)
                g2_h = params_dict.get("phase_G2_h", 3.0)
            else:
                # backward compat: fixed 80:70:40 split
                cct = params_dict.get("cell_cycle_time_h", 19.0)
                g1_h = cct * 80 / 190
                sy_h = cct * 70 / 190
                g2_h = cct * 40 / 190
            total_h = g1_h + sy_h + g2_h
            line = line.replace(
                "PLACEHOLDER_G1_DWELL",
                str(max(1, int(round(g1_h / time_step)))),
            )
            line = line.replace(
                "PLACEHOLDER_SY_DWELL",
                str(max(1, int(round(sy_h / time_step)))),
            )
            line = line.replace(
                "PLACEHOLDER_G2_DWELL",
                str(max(1, int(round(g2_h / time_step)))),
            )
            line = line.replace(
                "PLACEHOLDER_DIVIDE_TIME_WINDOW",
                str(max(1, int(round(total_h / time_step)))),
            )
            line = line.replace(
                "PLACEHOLDER_QUIESCENCE_THRESHOLD",
                f"{params_dict.get('quiescence_threshold', 0.15):.4f}",
            )
            necrosis_raw = params_dict.get("necrosis_threshold", 0.10)
            line = line.replace(
                "PLACEHOLDER_NECROSIS_THRESHOLD_NEG",
                f"{-abs(necrosis_raw):.4f}",
            )
            uptake_raw = params_dict.get("nutrient_uptake_rate", 0.02)
            line = line.replace(
                "PLACEHOLDER_UPTAKE_RATE",
                f"{-abs(uptake_raw):.6f}",
            )

            # Parse the line and apply CSV overrides
            stripped = line.rstrip("\n\r")
            parts = [p.strip() for p in stripped.split(",")]
            if len(parts) == 3 and parts[0] in csv_overrides:
                ptype, val = csv_overrides[parts[0]]
                if ptype == "int":
                    parts[2] = str(int(round(val)))
                else:
                    parts[2] = f"{float(val):.6g}"
                line = ",".join(parts) + "\n"

            # Overwrite simulation title and output_directory after template
            if len(parts) == 3:
                if parts[0] == "simulation_title":
                    parts[2] = simulation_title
                    line = ",".join(parts) + "\n"
                elif parts[0] == "output_directory":
                    parts[2] = run_dir_name
                    line = ",".join(parts) + "\n"
                elif parts[0] == "normoxic_cell/initial_population":
                    parts[2] = str(int(n0))
                    line = ",".join(parts) + "\n"
                elif parts[0] == "necrotic_cell/initial_population":
                    parts[2] = str(int(necrotic_n0))
                    line = ",".join(parts) + "\n"

            fh.write(line)


def _apply_transform(value: float, transform: str, time_step: float) -> Any:
    if transform == "identity":
        return value
    if transform == "neg":
        return -abs(value)
    if transform == "round_div_dt":
        return max(1, int(round(value / time_step)))
    if transform == "neg_round_div_dt":
        return -max(1, int(round(value / time_step)))
    # Mechanism-11 phase dwell transforms: distribute total cycle time at fixed ratio 80:70:40
    total_steps = max(3, int(round(value / time_step)))
    if transform == "phase_dwell_G1":
        return max(1, int(round(total_steps * 80 / 190)))
    if transform == "phase_dwell_Sy":
        return max(1, int(round(total_steps * 70 / 190)))
    if transform == "phase_dwell_G2":
        return max(1, int(round(total_steps * 40 / 190)))
    raise ValueError(f"Unknown transform: '{transform}'")


# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------

def _get_condition_cfg(config: dict, condition: str) -> dict:
    for cond in config.get("conditions", []):
        if cond["name"] == condition:
            return cond
    raise ValueError(f"Condition '{condition}' not found in config.")


def _get_git_commit(repo_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a single ABM4bio calibration simulation."
    )
    parser.add_argument(
        "--config", default="configs/calibration_config.yaml",
        help="Path to calibration_config.yaml"
    )
    parser.add_argument(
        "--bounds", default="configs/parameter_bounds.yaml",
        help="Path to parameter_bounds.yaml"
    )
    parser.add_argument(
        "--params", required=True,
        help='JSON dict of parameter values, e.g. \'{"cell_cycle_time_h": 24.0, ...}\''
    )
    parser.add_argument("--condition", default="ISO10")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--run_id", default="run_test")
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    config      = load_config(config_path)
    bounds_cfg  = load_config(args.bounds) if Path(args.bounds).exists() else None
    params_dict = json.loads(args.params)

    run_dir = run_simulation(
        params_dict=params_dict,
        condition=args.condition,
        seed=args.seed,
        run_id=args.run_id,
        config=config,
        config_dir=config_path.parent,
        bounds_config=bounds_cfg,
        dry_run=args.dry_run,
    )
    print(f"\nRun directory: {run_dir}")


if __name__ == "__main__":
    main()
