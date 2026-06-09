from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def viable_counts_from_stats(df: pd.DataFrame, *, phenotype_id: int = 1) -> np.ndarray:
    """
    Non-apoptotic cycling cancer cells (matches ABM4bio calibrate_control_growth.py).

    Prefers G1+Sy+G2+Di+Tr phase columns; falls back to pheno count minus apoptotic.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    base = f"N_cells_pheno_{phenotype_id}"
    phase_cols = [f"{base}_{phase}" for phase in ("G1", "Sy", "G2", "Di", "Tr")]
    if all(column in df.columns for column in phase_cols):
        total = np.zeros(len(df), dtype=float)
        for column in phase_cols:
            total += df[column].to_numpy(dtype=float)
        return np.maximum(0.0, total)
    apoptotic_col = f"{base}_Ap"
    if base in df.columns and apoptotic_col in df.columns:
        return np.maximum(
            0.0,
            df[base].to_numpy(dtype=float) - df[apoptotic_col].to_numpy(dtype=float),
        )
    if "N_cells" in df.columns:
        return df["N_cells"].to_numpy(dtype=float)
    raise ValueError("stats.csv does not contain recognizable cancer-cell count columns.")


def read_output_vector(
    stats_path: str | pd.PathLike,
    time_points: Sequence[int],
    *,
    time_column: str = "current_time",
    output_metric: str = "viable_cells",
    phenotype_id: int = 1,
) -> np.ndarray:
    """Sample simulation output at configured time points (hours)."""
    df = pd.read_csv(stats_path)
    df.columns = [str(c).strip() for c in df.columns]
    if time_column not in df.columns:
        raise KeyError(f"Missing time column {time_column!r}. Available: {list(df.columns)}")

    times = df[time_column].astype(float).to_numpy()
    if output_metric == "viable_cells":
        values = viable_counts_from_stats(df, phenotype_id=phenotype_id)
    elif output_metric == "N_cells":
        if "N_cells" not in df.columns:
            raise KeyError("Missing N_cells column in stats.csv")
        values = df["N_cells"].astype(float).to_numpy()
    else:
        if output_metric not in df.columns:
            raise KeyError(f"Missing output column {output_metric!r}")
        values = df[output_metric].astype(float).to_numpy()

    out: list[float] = []
    for t in time_points:
        idx = int(np.argmin(np.abs(times - float(t))))
        out.append(float(values[idx]))
    return np.array(out, dtype=float)
