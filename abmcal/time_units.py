"""Convert between simulated hours and ABM4bio step counts (dt = time_step [h])."""
from __future__ import annotations

import csv
from pathlib import Path

# ABM4bio mechanism-11: these parameters count simulation steps, not hours directly.
STEP_QUANTIZED_PARAMETER_KEYS: frozenset[str] = frozenset({
    "normoxic_CC/phase_dwell/G1",
    "normoxic_CC/phase_dwell/Sy",
    "normoxic_CC/phase_dwell/G2",
    "normoxic_CC/phase_dwell/Di",
    "normoxic_CC/phase_dwell/max_arrest_time",
    "normoxic_CC/can_divide/time_window",
    "normoxic_CC/can_apoptose/time_window",
    "normoxic_CC/can_apoptose/time_window/to_delete",
    "cancer_cell/can_divide/time_window",
    "cancer_cell/can_apoptose/time_window",
    "cancer_cell/can_apoptose/time_window/to_delete",
})

# Fitted mechanism-11 keys that the optimizer treats as hours (converted to steps for ABM).
MECHANISM11_FIT_HOURS_KEYS: frozenset[str] = frozenset({
    "normoxic_CC/phase_dwell/G1",
    "normoxic_CC/phase_dwell/Sy",
    "normoxic_CC/phase_dwell/G2",
    "normoxic_CC/can_divide/time_window",
})


def hours_to_steps(hours: float, time_step_h: float) -> int:
    dt = max(float(time_step_h), 1.0e-12)
    return max(0, int(round(float(hours) / dt)))


def steps_to_hours(steps: float, time_step_h: float) -> float:
    return float(steps) * max(float(time_step_h), 1.0e-12)


def read_template_time_step_hours(template_path: str | Path, default: float = 1.0) -> float:
    template_path = Path(template_path)
    with template_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            if str(row[0]).strip() == "time_step":
                try:
                    return float(str(row[2]).strip())
                except ValueError:
                    return default
    return default


def read_template_simulation_hours(
    template_path: str | Path,
    *,
    default_time_step_h: float = 1.0,
) -> float:
    """Return total simulated duration = number_of_time_steps * time_step [h]."""
    template_path = Path(template_path)
    n_steps: int | None = None
    dt_h = default_time_step_h
    with template_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            name = str(row[0]).strip()
            if name == "number_of_time_steps":
                try:
                    n_steps = int(float(str(row[2]).strip()))
                except ValueError:
                    pass
            elif name == "time_step":
                try:
                    dt_h = float(str(row[2]).strip())
                except ValueError:
                    pass
    if n_steps is None:
        return 72.0
    return steps_to_hours(n_steps, dt_h)


def optimizer_value_to_abm(
    key: str,
    value: float,
    *,
    time_step_h: float,
) -> object:
    if key in MECHANISM11_FIT_HOURS_KEYS or key in STEP_QUANTIZED_PARAMETER_KEYS:
        if key in MECHANISM11_FIT_HOURS_KEYS:
            return hours_to_steps(value, time_step_h)
        return int(round(float(value)))
    if key.endswith("/time_window") or key.endswith("/phase_dwell/G1") or "/phase_dwell/" in key:
        return hours_to_steps(value, time_step_h)
    return float(value)


def template_value_to_optimizer(
    key: str,
    value: float,
    *,
    time_step_h: float,
) -> float:
    if key in MECHANISM11_FIT_HOURS_KEYS:
        return steps_to_hours(value, time_step_h)
    return float(value)
