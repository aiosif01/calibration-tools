"""
ABM4bio time conventions for calibration-tools.

ABM4bio (bdm-abm4bio) always stores ``time_step`` in **simulated hours per scheduler step**
(see ABM4bio.h: ``TIME = step_index * time_step``; variable ``dt_h`` in mechanism code).

Integer parameters in input.csv (phase_dwell/*, can_* /time_window) count **scheduler steps**.
Cell age and phase age increment once per step.

Calibration strategy (viability assay: 0–72 h post-treatment, Excel targets):
  - **Mechanism 11 control** (untreated spheroid growth): 1 **minute** per step
    → time_step = 1/60 h, 4320 steps for 72 h. Optuna still samples dwell/maturity in hours.
  - **Mechanism 12 CAP** (30 s / 2 / 4 / 5 min plasma): 1 **second** per step
    → time_step = 1/3600 h, 259200 steps for 72 h. CAP duration_steps = exposure_seconds.

Before each ABM run:  abm_steps = round(duration_hours / time_step_h).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# Simulated clock unit written into ABM4bio input.csv.
ABM_TIME_STEP_UNIT = "h"

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

# Optimizer / Optuna bounds are expressed in simulated hours for these keys.
MECHANISM11_FIT_HOURS_KEYS: frozenset[str] = frozenset({
    "normoxic_CC/phase_dwell/G1",
    "normoxic_CC/phase_dwell/Sy",
    "normoxic_CC/phase_dwell/G2",
    "normoxic_CC/can_divide/time_window",
    "normoxic_CC/can_apoptose/time_window",
})


def minutes_to_time_step_h(minutes: float) -> float:
    """ABM time_step for one simulated minute per scheduler step."""
    return float(minutes) / 60.0


def seconds_to_time_step_h(seconds: float) -> float:
    """ABM time_step for one simulated second per scheduler step."""
    return float(seconds) / 3600.0


def hours_to_steps(hours: float, time_step_h: float) -> int:
    """Convert simulated duration [h] to ABM integer step count."""
    dt = max(float(time_step_h), 1.0e-12)
    return max(0, int(round(float(hours) / dt)))


def seconds_to_steps(seconds: float, time_step_h: float) -> int:
    """Convert exposure or delay in wall-clock seconds to ABM steps."""
    return hours_to_steps(float(seconds) / 3600.0, time_step_h)


def steps_to_hours(steps: float, time_step_h: float) -> float:
    """Convert ABM step count to simulated duration [h]."""
    return float(steps) * max(float(time_step_h), 1.0e-12)


def is_time_parameter_in_hours(key: str) -> bool:
    return key in MECHANISM11_FIT_HOURS_KEYS


def optimizer_hours_to_abm_value(key: str, hours: float, *, time_step_h: float) -> int | float:
    if key in MECHANISM11_FIT_HOURS_KEYS:
        return hours_to_steps(hours, time_step_h)
    return float(hours)


def template_abm_value_to_optimizer_hours(key: str, abm_value: float, *, time_step_h: float) -> float:
    if key in MECHANISM11_FIT_HOURS_KEYS:
        return steps_to_hours(abm_value, time_step_h)
    return float(abm_value)


optimizer_value_to_abm = optimizer_hours_to_abm_value
template_value_to_optimizer = template_abm_value_to_optimizer_hours


@dataclass(frozen=True)
class SimulationClock:
    """Resolved simulation timing for one ABM case."""

    label: str
    time_step_h: float
    simulation_hours: float
    statistics_interval_steps: int
    visualization_interval_steps: int

    @property
    def time_step_minutes(self) -> float:
        return self.time_step_h * 60.0

    @property
    def time_step_seconds(self) -> float:
        return self.time_step_h * 3600.0

    @property
    def number_of_steps(self) -> int:
        return hours_to_steps(self.simulation_hours, self.time_step_h)

    def cap_duration_steps(self, exposure_seconds: float) -> int:
        if exposure_seconds <= 0:
            return 0
        return max(1, seconds_to_steps(exposure_seconds, self.time_step_h))

    def describe(self) -> str:
        if abs(self.time_step_minutes - 1.0) < 1e-9:
            res = "1 min/step"
        elif abs(self.time_step_seconds - 1.0) < 1e-9:
            res = "1 s/step"
        elif abs(self.time_step_minutes - round(self.time_step_minutes)) < 1e-9:
            res = f"{self.time_step_minutes:.0g} min/step"
        elif abs(self.time_step_seconds - round(self.time_step_seconds)) < 1e-9:
            res = f"{self.time_step_seconds:.0g} s/step"
        else:
            res = f"{self.time_step_h:.6g} h/step"
        return (
            f"{self.label}: {self.number_of_steps} steps × {res} "
            f"= {self.simulation_hours:.4g} h simulated"
        )


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


def read_template_number_of_steps(template_path: str | Path, default: int = 72) -> int:
    template_path = Path(template_path)
    with template_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            if str(row[0]).strip() == "number_of_time_steps":
                try:
                    return int(round(float(str(row[2]).strip())))
                except ValueError:
                    return default
    return default


def read_template_simulation_hours(
    template_path: str | Path,
    *,
    default_time_step_h: float = 1.0,
) -> float:
    n_steps = read_template_number_of_steps(template_path, default=72)
    dt_h = read_template_time_step_hours(template_path, default=default_time_step_h)
    return steps_to_hours(n_steps, dt_h)


@dataclass(frozen=True)
class TimeSetupReport:
    time_step_h: float
    number_of_steps: int
    simulation_hours: float
    calibration_time_points_h: tuple[int, ...]
    warnings: tuple[str, ...]
    clock_label: str = ""


def validate_simulation_clock(
    template_path: str | Path,
    calibration_time_points_h: Sequence[int],
    expected_clock: SimulationClock,
) -> TimeSetupReport:
    """Check template matches the configured simulation clock."""
    template_path = Path(template_path)
    dt_h = read_template_time_step_hours(template_path)
    n_steps = read_template_number_of_steps(template_path)
    sim_h = steps_to_hours(n_steps, dt_h)
    targets = tuple(int(t) for t in calibration_time_points_h)
    warnings: list[str] = []

    if abs(dt_h - expected_clock.time_step_h) > 1.0e-9:
        warnings.append(
            f"template time_step={dt_h:.12g} h differs from expected "
            f"{expected_clock.time_step_h:.12g} h ({expected_clock.label})"
        )
    expected_steps = expected_clock.number_of_steps
    if n_steps != expected_steps:
        warnings.append(
            f"template number_of_time_steps={n_steps} differs from expected {expected_steps} "
            f"for {expected_clock.simulation_hours:.4g} h"
        )
    if sim_h + 1.0e-6 < float(max(targets) if targets else 0):
        warnings.append(
            f"simulation covers {sim_h:.4g} h but calibration targets include "
            f"{max(targets)} h"
        )

    return TimeSetupReport(
        time_step_h=dt_h,
        number_of_steps=n_steps,
        simulation_hours=sim_h,
        calibration_time_points_h=targets,
        warnings=tuple(warnings),
        clock_label=expected_clock.label,
    )


# Backward-compatible alias
validate_mechanism11_time_setup = validate_simulation_clock


def format_time_conversion_audit(
    template_path: str | Path,
    parameter_keys: Sequence[str],
    *,
    sample_hours: Sequence[float] | None = None,
    clock: SimulationClock | None = None,
) -> str:
    template_path = Path(template_path)
    dt_h = read_template_time_step_hours(template_path)
    n_steps = read_template_number_of_steps(template_path)
    sim_h = steps_to_hours(n_steps, dt_h)
    lines = [
        "ABM4bio time units (assay horizon: 0–72 h viability):",
    ]
    if clock is not None:
        lines.append(f"  Configured clock: {clock.describe()}")
    lines.extend([
        f"  Template time_step = {dt_h:.12g} h/step",
        f"  Template steps = {n_steps} → {sim_h:.4g} h in stats.csv current_time",
        "  Optuna time parameters [h] → ABM CSV integers: steps = round(hours / time_step_h)",
    ])
    hour_keys = [k for k in parameter_keys if k in MECHANISM11_FIT_HOURS_KEYS]
    if not hour_keys:
        return "\n".join(lines)

    if sample_hours is None:
        from config.calibration_settings import MECHANISM11_PARAMETER_KEYS, MECHANISM11_X0

        lookup = {name: i for i, name in enumerate(MECHANISM11_PARAMETER_KEYS)}
        sample_hours = [
            float(MECHANISM11_X0[lookup[k]]) if k in lookup else 8.0 for k in hour_keys
        ]

    for key, hours in zip(hour_keys, sample_hours):
        steps = hours_to_steps(hours, dt_h)
        lines.append(f"    {key}: {hours:.4g} h → {steps} steps")
    return "\n".join(lines)
