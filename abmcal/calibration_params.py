from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .time_units import MECHANISM11_FIT_HOURS_KEYS, hours_to_steps

# Mechanism-11 normoxic_CC (config/calibration_settings.py is authoritative; keep in sync)
MECHANISM11_PARAMETER_KEYS: tuple[str, ...] = (
    "normoxic_CC/can_grow/probability",
    "normoxic_CC/can_grow/diameter_rate",
    "normoxic_CC/can_divide/probability",
    "normoxic_CC/can_divide/diameter_cutoff",
    "normoxic_CC/diameter/max",
    "normoxic_CC/phase_dwell/G1",
    "normoxic_CC/phase_dwell/Sy",
    "normoxic_CC/phase_dwell/G2",
    "normoxic_CC/can_divide/time_window",
    "normoxic_CC/can_divide/probability_increment_with_age",
    "normoxic_CC/can_divide/influence_ratio",
    "normoxic_CC/can_apoptose/probability",
    "normoxic_CC/can_apoptose/time_window",
)
# Short names for live/summary plots (avoid duplicate "probability" legend entries).
PARAMETER_PLOT_LABELS: dict[str, str] = {
    "normoxic_CC/can_apoptose/probability": "Apoptosis probability",
    "normoxic_CC/can_apoptose/time_window": "Apoptosis aging onset (h)",
    "normoxic_CC/can_grow/probability": "Grow probability",
    "normoxic_CC/can_grow/diameter_rate": "Grow diameter rate",
    "normoxic_CC/can_divide/probability": "Divide probability",
    "normoxic_CC/phase_dwell/G1": "G1 dwell (h)",
    "normoxic_CC/phase_dwell/Sy": "S-phase dwell (h)",
    "normoxic_CC/phase_dwell/G2": "G2 dwell (h)",
    "normoxic_CC/phase_dwell/Di": "M-phase dwell (h)",
    "normoxic_CC/can_divide/time_window": "Divide maturity (h)",
    "normoxic_CC/can_divide/probability_increment_with_age": "Divide prob. increment / step",
    "normoxic_CC/can_divide/influence_ratio": "Divide crowding radius",
    "normoxic_CC/can_divide/diameter_cutoff": "Divide diameter cutoff",
    "normoxic_CC/diameter/max": "Max diameter",
    "cancer_cell/can_apoptose/probability": "Apoptose probability",
    "cancer_cell/can_grow/probability": "Grow probability",
    "cancer_cell/can_grow/diameter_rate": "Grow diameter rate",
    "cancer_cell/can_divide/probability": "Divide probability",
    "cancer_cell/can_divide/time_window": "Divide maturity (h)",
}

PARAMETER_PLOT_COLORS: dict[str, str] = {
    "normoxic_CC/can_apoptose/probability": "#4472C4",
    "normoxic_CC/can_apoptose/time_window": "#2F5597",
    "normoxic_CC/can_grow/probability": "#ED7D31",
    "normoxic_CC/can_grow/diameter_rate": "#70AD47",
    "normoxic_CC/can_divide/probability": "#FFC000",
    "normoxic_CC/phase_dwell/G1": "#5B9BD5",
    "normoxic_CC/phase_dwell/Sy": "#A5A5A5",
    "normoxic_CC/phase_dwell/G2": "#7030A0",
    "normoxic_CC/phase_dwell/Di": "#264478",
    "normoxic_CC/can_divide/time_window": "#C55A11",
    "normoxic_CC/can_divide/probability_increment_with_age": "#843C0C",
    "normoxic_CC/can_divide/influence_ratio": "#385723",
    "normoxic_CC/can_divide/diameter_cutoff": "#264478",
    "normoxic_CC/diameter/max": "#BF8F00",
}

INT_PARAMETER_KEYS: frozenset[str] = frozenset({
    "cancer_cell/can_divide/time_window",
    "normoxic_CC/phase_dwell/G1",
    "normoxic_CC/phase_dwell/Sy",
    "normoxic_CC/phase_dwell/G2",
    "normoxic_CC/phase_dwell/Di",
    "normoxic_CC/can_divide/time_window",
})


def parameter_plot_label(key: str) -> str:
    if key in PARAMETER_PLOT_LABELS:
        return PARAMETER_PLOT_LABELS[key]
    if "/" in key:
        parent, leaf = key.rsplit("/", 1)
        parent_short = parent.rsplit("/", 1)[-1]
        return f"{parent_short} / {leaf}"
    return key


def parameter_plot_color(key: str, index: int = 0) -> str:
    if key in PARAMETER_PLOT_COLORS:
        return PARAMETER_PLOT_COLORS[key]
    palette = ["#4472C4", "#ED7D31", "#FFC000", "#70AD47", "#5B9BD5", "#7030A0", "#C55A11", "#A5A5A5"]
    return palette[index % len(palette)]


CONTROL_CAP_OVERRIDES: dict[str, object] = {
    "CAP/enabled": False,
    "CAP/duration_h": 0.0,
    "CAP/duration_steps": 0,
    "CAP/H2O2/concentration": 0.0,
    "CAP/NO2_/concentration": 0.0,
}

# In-vitro dish geometry: 2D bounded domain (not polar 3D).
DOMAIN_2D_OVERRIDES: dict[str, object] = {
    "simulation_domain_is_2D": True,
    "simulation_domain_is_polar": False,
}

# Fast mech-10/12 control runs (ABM4bio prepare_control_input.py). Do NOT use for mech-11:
# coarse diffusion grid (10 vs 76) distorts O2 fields and proliferation in mechanism 11.
CONTROL_FAST_RUNTIME_OVERRIDES: dict[str, object] = {
    "diffusion_grid/spatial_resolution": 10,
    **DOMAIN_2D_OVERRIDES,
}

def build_mechanism11_control_overrides(
    time_step_h: float,
    *,
    simulation_hours: float | None = None,
    phase_dwell_h: Sequence[float] | None = None,
    divide_maturity_h: float | None = None,
    apoptosis_aging_onset_h: float | None = None,
    apoptosis_cleanup_h: float | None = None,
    statistics_interval_steps: int | None = None,
    visualization_interval_steps: int | None = None,
) -> dict[str, object]:
    """Build step-quantized ABM overrides from hour-based control defaults."""
    from config.calibration_settings import (
        MECHANISM11_APOPTOSIS_AGING_ONSET_H,
        MECHANISM11_APOPTOSIS_CLEANUP_H,
        MECHANISM11_DIVIDE_MATURITY_H,
        MECHANISM11_PHASE_DWELL_H,
        MECHANISM11_SIMULATION_HOURS,
        mechanism11_simulation_clock,
    )

    clock = mechanism11_simulation_clock()
    dt = max(float(time_step_h), 1.0e-12)
    sim_h = float(simulation_hours if simulation_hours is not None else MECHANISM11_SIMULATION_HOURS)
    dwell = tuple(phase_dwell_h if phase_dwell_h is not None else MECHANISM11_PHASE_DWELL_H)
    g1_h, sy_h, g2_h, di_h = (list(dwell) + [0.0, 0.0, 0.0, 0.0])[:4]
    stat_iv = statistics_interval_steps if statistics_interval_steps is not None else clock.statistics_interval_steps
    viz_iv = visualization_interval_steps if visualization_interval_steps is not None else clock.visualization_interval_steps
    return {
        "diffusion_grid/biochemicals": "O2",
        "normoxic_CC/can_apoptose/probability": 0.003,
        "normoxic_CC/can_apoptose/time_window": hours_to_steps(
            apoptosis_aging_onset_h if apoptosis_aging_onset_h is not None else MECHANISM11_APOPTOSIS_AGING_ONSET_H,
            dt,
        ),
        "normoxic_CC/can_apoptose/time_window/to_delete": hours_to_steps(
            apoptosis_cleanup_h if apoptosis_cleanup_h is not None else MECHANISM11_APOPTOSIS_CLEANUP_H,
            dt,
        ),
        "normoxic_CC/intracellular/damage/k_induction": 0.0,
        "normoxic_CC/intracellular/damage/probability": 0.0,
        "normoxic_CC/can_divide/CAP_sensitivity": 0.0,
        "normoxic_CC/phase_dwell/G1": hours_to_steps(g1_h, dt),
        "normoxic_CC/phase_dwell/Sy": hours_to_steps(sy_h, dt),
        "normoxic_CC/phase_dwell/G2": hours_to_steps(g2_h, dt),
        "normoxic_CC/phase_dwell/Di": hours_to_steps(di_h, dt),
        "normoxic_CC/can_divide/time_window": hours_to_steps(
            divide_maturity_h if divide_maturity_h is not None else MECHANISM11_DIVIDE_MATURITY_H,
            dt,
        ),
        "number_of_time_steps": hours_to_steps(sim_h, dt),
        "time_step": dt,
        "statistics_interval": max(1, int(stat_iv)),
        "visualization_interval": max(1, int(viz_iv)),
    }


def build_mechanism12_runtime_overrides(
    time_step_h: float,
    *,
    simulation_hours: float | None = None,
) -> dict[str, object]:
    """Mechanism-12 CAP template clock + disabled CAP (enabled per exposure in workflow)."""
    from config.calibration_settings import MECHANISM12_SIMULATION_HOURS, mechanism12_simulation_clock

    clock = mechanism12_simulation_clock()
    dt = max(float(time_step_h), 1.0e-12)
    sim_h = float(simulation_hours if simulation_hours is not None else MECHANISM12_SIMULATION_HOURS)
    return {
        **CONTROL_CAP_OVERRIDES,
        "number_of_time_steps": hours_to_steps(sim_h, dt),
        "time_step": dt,
        "statistics_interval": clock.statistics_interval_steps,
        "visualization_interval": clock.visualization_interval_steps,
        "export_visualization": False,
        "cell_export/enabled": False,
    }


def build_mechanism11_runtime_overrides(time_step_h: float, *, simulation_hours: float | None = None) -> dict[str, object]:
    return {
        **CONTROL_CAP_OVERRIDES,
        **build_mechanism11_control_overrides(time_step_h, simulation_hours=simulation_hours),
        "simulation/early_stop_on_total_cells_exceeded": False,
    }


def _default_mechanism11_dt_h() -> float:
    from config.calibration_settings import MECHANISM11_TIME_STEP_H
    return MECHANISM11_TIME_STEP_H


MECHANISM11_CONTROL_OVERRIDES: dict[str, object] = build_mechanism11_control_overrides(_default_mechanism11_dt_h())
MECHANISM11_RUNTIME_OVERRIDES: dict[str, object] = build_mechanism11_runtime_overrides(_default_mechanism11_dt_h())

# Untreated control calibration must decouple ROS/damage (ABM4bio prepare_control_input.py).
CONTROL_PROLIFERATION_OVERRIDES: dict[str, object] = {
    "cancer_cell/intracellular/uptake/H2O2": 0.0,
    "cancer_cell/intracellular/uptake/NO2_": 0.0,
    "cancer_cell/intracellular/damage/k_induction": 0.0,
    "cancer_cell/intracellular/damage/probability": 0.0,
    "cancer_cell/can_divide/CAP_sensitivity": 0.0,
    "H2O2/initial_value": 0.0,
    "H2O2/diffusion_coefficient": 0.0,
    "H2O2/dissipation_coefficient": 0.0,
    "NO2_/initial_value": 0.0,
    "NO2_/diffusion_coefficient": 0.0,
    "NO2_/dissipation_coefficient": 0.0,
}

def format_parameter_value(key: str, value: float, *, time_step_h: float = 1.0) -> object:
    """Write optimizer value into input.csv (hours → steps for time keys)."""
    if key in MECHANISM11_FIT_HOURS_KEYS:
        return hours_to_steps(value, time_step_h)
    if key in INT_PARAMETER_KEYS:
        return int(round(float(value)))
    return float(value)


def parameter_overrides_from_vector(
    keys: Sequence[str],
    params: Sequence[float],
    *,
    time_step_h: float = 1.0,
) -> dict[str, object]:
    if len(keys) != len(params):
        raise ValueError(f"Expected {len(keys)} parameters, got {len(params)}")
    return {
        key: format_parameter_value(key, value, time_step_h=time_step_h)
        for key, value in zip(keys, params)
    }


