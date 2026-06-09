"""
load_experimental_data.py
=========================
Reads 'NIH3T3 control condition.xlsx' and returns a tidy pandas DataFrame
with shell/core area metrics for each condition and time point.

Usage (standalone):
    python scripts/load_experimental_data.py \
        --config configs/calibration_config.yaml

Returns a DataFrame with columns:
    condition, time_h, shell_area_px2, shell_area_um2, shell_A_over_A0,
    shell_SEM, core_area_px2, core_area_um2, core_A_over_A0, core_SEM,
    shell_eq_radius_um, core_eq_radius_um, viable_rim_um
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path) -> dict:
    with open(config_path, "r") as fh:
        return yaml.safe_load(fh)


def load_experimental_data(
    excel_path: str | Path,
    config: dict,
    condition_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Parse the 'Average' sheet of the Excel workbook and return a tidy
    DataFrame.  If *condition_name* is None, all configured conditions
    are loaded and stacked.

    Parameters
    ----------
    excel_path : path to the .xlsx file
    config     : dict loaded from calibration_config.yaml
    condition_name : 'ISO10' | 'DeltaC' | None (all)

    Returns
    -------
    pd.DataFrame with columns:
        condition, time_h,
        shell_area_px2, shell_area_um2, shell_A_over_A0, shell_SEM,
        core_area_px2,  core_area_um2,  core_A_over_A0,  core_SEM,
        shell_eq_radius_um, core_eq_radius_um, viable_rim_um,
        shell_A_over_A0_SEM, core_A_over_A0_SEM, viable_rim_sem_um
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    sheet_name = config.get("excel_sheet_average", "Average")

    # Read raw sheet without a header row so we can slice freely
    raw = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)

    # Column indices within each block
    ci = {
        "time_h":          config.get("excel_col_time_h", 0),
        "shell_area_px2":  config.get("excel_col_shell_area_px2", 1),
        "shell_area_um2":  config.get("excel_col_shell_area_um2", 2),
        "shell_A_over_A0": config.get("excel_col_shell_A_over_A0", 3),
        "shell_SEM":       config.get("excel_col_shell_SEM", 4),
        "core_area_px2":   config.get("excel_col_core_area_px2", 5),
        "core_area_um2":   config.get("excel_col_core_area_um2", 6),
        "core_A_over_A0":  config.get("excel_col_core_A_over_A0", 7),
        "core_SEM":        config.get("excel_col_core_SEM", 8),
    }

    # Condition definitions from config
    condition_map = {
        "ISO10":  config.get("excel_iso10_rows",  [5, 9]),
        "DeltaC": config.get("excel_deltac_rows", [13, 17]),
    }

    names_to_load = (
        [condition_name] if condition_name is not None
        else list(condition_map.keys())
    )

    frames = []
    for cname in names_to_load:
        if cname not in condition_map:
            raise ValueError(
                f"Unknown condition '{cname}'. "
                f"Available: {list(condition_map.keys())}"
            )
        row_start, row_end = condition_map[cname]
        block = raw.iloc[row_start : row_end + 1].reset_index(drop=True)

        rows = []
        t0_shell_area_um2 = _to_float(block.iloc[0, ci["shell_area_um2"]])
        t0_core_area_um2 = _to_float(block.iloc[0, ci["core_area_um2"]])
        core_a0_ref = t0_core_area_um2 if t0_core_area_um2 > 0 else t0_shell_area_um2
        for _, row in block.iterrows():
            time_h          = _to_float(row.iloc[ci["time_h"]])
            shell_area_px2  = _to_float(row.iloc[ci["shell_area_px2"]])
            shell_area_um2  = _to_float(row.iloc[ci["shell_area_um2"]])
            shell_A_over_A0 = _to_float(row.iloc[ci["shell_A_over_A0"]])
            shell_SEM       = _to_float(row.iloc[ci["shell_SEM"]])
            core_area_px2   = _to_float(row.iloc[ci["core_area_px2"]])
            core_area_um2   = _to_float(row.iloc[ci["core_area_um2"]])
            core_A_over_A0  = _to_float(row.iloc[ci["core_A_over_A0"]])
            core_SEM        = _to_float(row.iloc[ci["core_SEM"]])

            # Derived radii & viable rim
            shell_eq_radius_um = (
                math.sqrt(shell_area_um2 / math.pi)
                if shell_area_um2 and shell_area_um2 > 0 else 0.0
            )
            core_eq_radius_um = (
                math.sqrt(core_area_um2 / math.pi)
                if core_area_um2 and core_area_um2 > 0 else 0.0
            )
            viable_rim_um = max(0.0, shell_eq_radius_um - core_eq_radius_um)

            # SEM propagation for normalized and derived metrics
            shell_A_over_A0_sem = (
                shell_SEM / max(t0_shell_area_um2, 1.0e-6)
                if shell_SEM == shell_SEM and t0_shell_area_um2 > 0 else float("nan")
            )
            core_A_over_A0_sem = (
                core_SEM / max(core_a0_ref, 1.0e-6)
                if core_SEM == core_SEM and core_a0_ref > 0 else float("nan")
            )
            shell_r_sem = (
                shell_SEM / (2.0 * math.sqrt(math.pi * max(shell_area_um2, 1.0e-6)))
                if shell_SEM == shell_SEM and shell_area_um2 > 0 else 0.0
            )
            core_r_sem = (
                core_SEM / (2.0 * math.sqrt(math.pi * max(core_area_um2, 1.0e-6)))
                if core_SEM == core_SEM and core_area_um2 > 0 else 0.0
            )
            viable_rim_sem_um = math.sqrt(shell_r_sem ** 2 + core_r_sem ** 2)

            rows.append({
                "condition":         cname,
                "time_h":            time_h,
                "shell_area_px2":    shell_area_px2,
                "shell_area_um2":    shell_area_um2,
                "shell_A_over_A0":   shell_A_over_A0,
                "shell_SEM":         shell_SEM,
                "core_area_px2":     core_area_px2,
                "core_area_um2":     core_area_um2,
                "core_A_over_A0":    core_A_over_A0,
                "core_SEM":          core_SEM,
                "shell_eq_radius_um": shell_eq_radius_um,
                "core_eq_radius_um":  core_eq_radius_um,
                "viable_rim_um":      viable_rim_um,
                "shell_A_over_A0_SEM": shell_A_over_A0_sem,
                "core_A_over_A0_SEM": core_A_over_A0_sem,
                "viable_rim_sem_um": viable_rim_sem_um,
            })

        frames.append(pd.DataFrame(rows))

    df = pd.concat(frames, ignore_index=True)
    df["time_h"] = df["time_h"].astype(float)
    df = df.sort_values(["condition", "time_h"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(val) -> float:
    """Coerce a cell value to float, returning NaN on failure."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return float("nan")


def get_t0_shell_area_um2(df: pd.DataFrame, condition: str) -> float:
    """Return shell area at t=0 for the given condition (µm²)."""
    sub = df[(df["condition"] == condition) & (df["time_h"] == 0.0)]
    if sub.empty:
        raise ValueError(
            f"No t=0 entry found for condition '{condition}' in experimental data."
        )
    return float(sub["shell_area_um2"].iloc[0])


def estimate_initial_cells_from_area(
    shell_area_um2: float,
    cell_diameter_um: float = 18.0,
) -> int:
    """
    Rough estimate of initial cell count by packing circles inside a disc.
    Uses an empirical 2D packing fraction (~0.64 for random packing).
    """
    if shell_area_um2 <= 0:
        return 0
    cell_area_um2 = math.pi * (cell_diameter_um / 2.0) ** 2
    packing_fraction = 0.64
    n_cells = int(shell_area_um2 * packing_fraction / cell_area_um2)
    return max(1, n_cells)


def estimate_initial_sphere_radius_from_area(
    shell_area_um2: float,
) -> float:
    """Return equivalent disc radius (µm) from t=0 shell area."""
    if shell_area_um2 <= 0:
        return 0.0
    return math.sqrt(shell_area_um2 / math.pi)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load NIH3T3 experimental data from Excel workbook."
    )
    parser.add_argument(
        "--config", default="configs/calibration_config.yaml",
        help="Path to calibration_config.yaml"
    )
    parser.add_argument(
        "--condition", default=None,
        help="Condition to load: ISO10 | DeltaC (default: all)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Optional CSV output path"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    excel_path = Path(args.config).parent.parent / config["excel_file"]

    df = load_experimental_data(excel_path, config, args.condition)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print(df.to_string(index=False))

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"\nSaved to {args.output}")

    # Report derived initial conditions
    for cond in df["condition"].unique():
        t0_area = get_t0_shell_area_um2(df, cond)
        n0 = estimate_initial_cells_from_area(t0_area)
        r0 = estimate_initial_sphere_radius_from_area(t0_area)
        print(
            f"\n[{cond}] t=0 shell area = {t0_area:.1f} µm²  "
            f"→ equiv. radius = {r0:.1f} µm,  "
            f"estimated N0 ≈ {n0} cells"
        )


if __name__ == "__main__":
    main()
