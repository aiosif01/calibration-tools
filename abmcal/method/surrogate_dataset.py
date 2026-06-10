"""Dataset encoding: parameters, cell-line one-hot, exposure → ANN input/output tensors."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import json
import numpy as np
import pandas as pd

CELL_LINE_ORDER: tuple[str, ...] = ("EGI1", "HuCCT1", "PANC1", "MiaPaCa2")
TIME_COLUMNS: tuple[str, ...] = ("y_0h", "y_24h", "y_48h", "y_72h")
EXPOSURE_SCALE: float = 300.0


def param_column_name(key: str) -> str:
    return "param__" + key.replace("/", "_").replace(" ", "_")


def param_columns(keys: Sequence[str]) -> list[str]:
    return [param_column_name(k) for k in keys]


@dataclass(frozen=True)
class SurrogateMeta:
    parameter_keys: tuple[str, ...]
    cell_lines: tuple[str, ...]
    exposure_scale: float = EXPOSURE_SCALE
    input_dim: int = 0
    output_dim: int = 4

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({
            "parameter_keys": list(self.parameter_keys),
            "cell_lines": list(self.cell_lines),
            "exposure_scale": self.exposure_scale,
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "param_columns": param_columns(self.parameter_keys),
            "time_columns": list(TIME_COLUMNS),
        }, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> SurrogateMeta:
        raw = json.loads(Path(path).read_text())
        keys = tuple(raw["parameter_keys"])
        cell_lines = tuple(raw.get("cell_lines", CELL_LINE_ORDER))
        input_dim = int(raw.get("input_dim", len(keys) + len(cell_lines) + 1))
        return cls(
            parameter_keys=keys,
            cell_lines=cell_lines,
            exposure_scale=float(raw.get("exposure_scale", EXPOSURE_SCALE)),
            input_dim=input_dim,
            output_dim=int(raw.get("output_dim", 4)),
        )


def cell_line_onehot(cell_line: str, cell_lines: Sequence[str] = CELL_LINE_ORDER) -> np.ndarray:
    vec = np.zeros(len(cell_lines), dtype=float)
    key = cell_line.strip()
    for i, name in enumerate(cell_lines):
        if name.lower() == key.lower():
            vec[i] = 1.0
            return vec
    raise KeyError(f"Unknown cell line {cell_line!r}. Known: {list(cell_lines)}")


def build_input_vector(
    params: Sequence[float],
    *,
    cell_line: str,
    exposure_seconds: int,
    meta: SurrogateMeta,
) -> np.ndarray:
    p = np.asarray(params, dtype=float)
    onehot = cell_line_onehot(cell_line, meta.cell_lines)
    exposure = np.array([float(exposure_seconds) / meta.exposure_scale], dtype=float)
    return np.concatenate([p, onehot, exposure])


def dataframe_to_arrays(
    df: pd.DataFrame,
    meta: SurrogateMeta,
) -> tuple[np.ndarray, np.ndarray]:
    pcols = param_columns(meta.parameter_keys)
    x_rows = []
    y_rows = []
    for _, row in df.iterrows():
        params = [float(row[c]) for c in pcols]
        x_rows.append(
            build_input_vector(
                params,
                cell_line=str(row["cell_line"]),
                exposure_seconds=int(row["exposure_seconds"]),
                meta=meta,
            )
        )
        y_rows.append([float(row[c]) for c in TIME_COLUMNS])
    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=float)


def train_val_test_split(
    n: int,
    *,
    val_fraction: float = 0.2,
    test_fraction: float = 0.1,
    seed: int = 1234,
) -> dict[str, list[int]]:
    rng = np.random.default_rng(seed)
    indices = rng.permutation(n).tolist()
    n_test = max(1, int(round(n * test_fraction))) if n >= 10 else 0
    n_val = max(1, int(round(n * val_fraction))) if n >= 5 else max(0, n // 5)
    test_idx = indices[:n_test]
    val_idx = indices[n_test : n_test + n_val]
    train_idx = indices[n_test + n_val :]
    if not train_idx and indices:
        train_idx = indices[n_test + n_val :] or [indices[-1]]
    return {"train": train_idx, "val": val_idx, "test": test_idx}
