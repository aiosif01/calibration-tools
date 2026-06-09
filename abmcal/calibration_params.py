from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

# ABM4bio reference order (calibrate_control_growth.py / abm_io.py CONTROL_GROWTH_PARAMS)
CONTROL_MECHANISM12_PARAMETER_KEYS: tuple[str, ...] = (
    "cancer_cell/can_divide/probability",
    "cancer_cell/can_apoptose/probability",
    "cancer_cell/can_grow/diameter_rate",
    "cancer_cell/can_grow/probability",
    "cancer_cell/can_divide/time_window",
)

TREATED_MECHANISM12_PARAMETER_KEYS: tuple[str, ...] = (
    "cancer_cell/can_apoptose/probability",
    "cancer_cell/can_grow/probability",
    "cancer_cell/can_divide/probability",
)

INT_PARAMETER_KEYS: frozenset[str] = frozenset({"cancer_cell/can_divide/time_window"})

CONTROL_MECHANISM12_X0: tuple[float, ...] = (
    0.823441629895,
    0.000232465905465,
    1.278261769119,
    0.743507272804,
    288.0,
)
CONTROL_MECHANISM12_LB: tuple[float, ...] = (0.30, 0.0001, 0.05, 0.01, 50.0)
CONTROL_MECHANISM12_UB: tuple[float, ...] = (0.99, 0.25, 1.5, 0.70, 500.0)

TREATED_MECHANISM12_X0: tuple[float, ...] = (0.0029, 0.52, 0.84)
TREATED_MECHANISM12_LB: tuple[float, ...] = (0.0, 0.0, 0.0)
TREATED_MECHANISM12_UB: tuple[float, ...] = (0.9999, 0.9999, 0.9999)

CONTROL_CAP_OVERRIDES: dict[str, object] = {
    "CAP/enabled": False,
    "CAP/duration_h": 0.0,
    "CAP/duration_steps": 0,
}

CONTROL_CALIBRATION_STAGES: tuple[tuple[int, ...], ...] = (
    (0, 24),
    (0, 24, 48),
    (0, 24, 48, 72),
)


def format_parameter_value(key: str, value: float) -> object:
    if key in INT_PARAMETER_KEYS:
        return int(round(float(value)))
    return float(value)


def parameter_overrides_from_vector(
    keys: Sequence[str],
    params: Sequence[float],
) -> dict[str, object]:
    if len(keys) != len(params):
        raise ValueError(f"Expected {len(keys)} parameters, got {len(params)}")
    return {key: format_parameter_value(key, value) for key, value in zip(keys, params)}


def _read_template_parameter(template_path: str | Path, parameter_name: str) -> float | None:
    template_path = Path(template_path)
    with template_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            if str(row[0]).strip() == parameter_name:
                try:
                    return float(str(row[2]).strip())
                except ValueError:
                    return None
    return None


def read_template_parameter_values(template_path: str | Path, keys: tuple[str, ...]) -> list[float] | None:
    values: list[float] = []
    for key in keys:
        raw = _read_template_parameter(template_path, key)
        if raw is None:
            return None
        values.append(raw)
    return values


def comma(values: tuple[float, ...] | list[float]) -> str:
    return ",".join(f"{v:.12g}" for v in values)


def default_fit_bounds(
    parameter_keys: list[str] | None,
    *,
    template_path: str | Path | None = None,
    control_mode: bool = False,
) -> tuple[str, str, str]:
    keys = tuple(parameter_keys or ())
    if control_mode or keys == CONTROL_MECHANISM12_PARAMETER_KEYS:
        x0 = CONTROL_MECHANISM12_X0
        lb = CONTROL_MECHANISM12_LB
        ub = CONTROL_MECHANISM12_UB
        if template_path is not None:
            from_template = read_template_parameter_values(template_path, CONTROL_MECHANISM12_PARAMETER_KEYS)
            if from_template is not None:
                x0 = tuple(from_template)
        return comma(x0), comma(lb), comma(ub)
    if keys == TREATED_MECHANISM12_PARAMETER_KEYS or (
        parameter_keys and all("probability" in k for k in parameter_keys) and len(parameter_keys) == 3
    ):
        return comma(TREATED_MECHANISM12_X0), comma(TREATED_MECHANISM12_LB), comma(TREATED_MECHANISM12_UB)
    return "0.0001,0.15,0.2", "0.0,0.01,0.01", "0.9999,0.5,0.5"
