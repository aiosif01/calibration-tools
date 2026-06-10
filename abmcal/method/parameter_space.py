"""Load ABM4bio parameter spaces from YAML or cell-line settings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import yaml


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    type: str = "float"
    low: float = 0.0
    high: float = 1.0
    scale: str = "linear"

    @classmethod
    def from_dict(cls, name: str, raw: Mapping[str, Any]) -> ParameterSpec:
        return cls(
            name=name,
            type=str(raw.get("type", "float")),
            low=float(raw["low"]),
            high=float(raw["high"]),
            scale=str(raw.get("scale", "linear")),
        )


@dataclass(frozen=True)
class ParameterSpace:
    parameters: tuple[ParameterSpec, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.parameters)

    def sample_uniform(self, rng: np.random.Generator, n: int) -> np.ndarray:
        rows = []
        for _ in range(n):
            row = []
            for spec in self.parameters:
                if spec.scale == "log" and spec.low > 0 and spec.high > 0:
                    val = float(np.exp(rng.uniform(np.log(spec.low), np.log(spec.high))))
                else:
                    val = float(rng.uniform(spec.low, spec.high))
                if spec.type == "int":
                    val = float(int(round(val)))
                row.append(val)
            rows.append(row)
        return np.asarray(rows, dtype=float)

    def lhs_sample(self, n: int, *, seed: int = 1234) -> np.ndarray:
        rng = np.random.default_rng(seed)
        dim = len(self.parameters)
        if n <= 0:
            return np.empty((0, dim), dtype=float)
        cut = np.linspace(0.0, 1.0, n + 1)
        u = rng.uniform(cut[:-1], cut[1:])
        rng.shuffle(u)
        samples = np.zeros((n, dim), dtype=float)
        for j, spec in enumerate(self.parameters):
            perm = rng.permutation(n)
            for i, rank in enumerate(perm):
                frac = (rank + rng.random()) / n
                if spec.scale == "log" and spec.low > 0 and spec.high > 0:
                    val = float(np.exp(np.log(spec.low) + frac * (np.log(spec.high) - np.log(spec.low))))
                else:
                    val = float(spec.low + frac * (spec.high - spec.low))
                if spec.type == "int":
                    val = float(int(round(val)))
                samples[i, j] = val
        return samples


def load_parameter_space_yaml(path: str | Path) -> ParameterSpace:
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    params_raw = raw.get("parameters") or {}
    specs = tuple(ParameterSpec.from_dict(name, spec) for name, spec in params_raw.items())
    if not specs:
        raise ValueError(f"No parameters defined in {path}")
    return ParameterSpace(parameters=specs)


def parameter_space_from_bounds(
    names: Sequence[str],
    lb: Sequence[float],
    ub: Sequence[float],
    *,
    scales: Sequence[str] | None = None,
    int_keys: frozenset[str] | None = None,
) -> ParameterSpace:
    int_keys = int_keys or frozenset()
    specs = []
    for i, name in enumerate(names):
        scale = scales[i] if scales is not None else "linear"
        specs.append(
            ParameterSpec(
                name=name,
                type="int" if name in int_keys else "float",
                low=float(lb[i]),
                high=float(ub[i]),
                scale=scale,
            )
        )
    return ParameterSpace(parameters=tuple(specs))
