"""Load and sample ABM4bio parameter spaces from YAML or cell-line settings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import optuna
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
    load_frozen_control_params: bool = False
    cell_line_specific: bool = False

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.parameters)

    def sample(self, trial: optuna.Trial) -> dict[str, float]:
        values: dict[str, float] = {}
        for spec in self.parameters:
            log = spec.scale == "log"
            if spec.type == "int":
                values[spec.name] = float(
                    trial.suggest_int(spec.name, int(spec.low), int(spec.high), log=log)
                )
            else:
                values[spec.name] = float(
                    trial.suggest_float(spec.name, spec.low, spec.high, log=log)
                )
        return values

    def vector_from_dict(self, params: Mapping[str, float]) -> list[float]:
        return [float(params[name]) for name in self.names]


def load_parameter_space_yaml(path: str | Path) -> ParameterSpace:
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    params_raw = raw.get("parameters") or {}
    specs = tuple(
        ParameterSpec.from_dict(name, spec)
        for name, spec in params_raw.items()
    )
    if not specs:
        raise ValueError(f"No parameters defined in {path}")
    return ParameterSpace(
        parameters=specs,
        load_frozen_control_params=bool(raw.get("load_frozen_control_params", False)),
        cell_line_specific=bool(raw.get("cell_line_specific", False)),
    )


def parameter_space_from_bounds(
    names: Sequence[str],
    lb: Sequence[float],
    ub: Sequence[float],
    *,
    scales: Sequence[str] | None = None,
    int_keys: frozenset[str] | None = None,
) -> ParameterSpace:
    if len(names) != len(lb) or len(names) != len(ub):
        raise ValueError("names, lb, and ub must have the same length")
    int_keys = int_keys or frozenset()
    specs: list[ParameterSpec] = []
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
