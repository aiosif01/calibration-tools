from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .time_units import (
    MECHANISM11_FIT_HOURS_KEYS,
    hours_to_steps,
    read_template_time_step_hours,
    template_value_to_optimizer,
)

# ABM4bio reference order (calibrate_control_growth.py / abm_io.py CONTROL_GROWTH_PARAMS)
CONTROL_MECHANISM12_PARAMETER_KEYS: tuple[str, ...] = (
    "cancer_cell/can_divide/probability",
    "cancer_cell/can_apoptose/probability",
    "cancer_cell/can_grow/diameter_rate",
    "cancer_cell/can_grow/probability",
    "cancer_cell/can_divide/time_window",
)

# Default control fit set (matches ABM4bio calibrate_control_growth.py --fit-params ...[:4]).
CONTROL_FIT_PARAMETER_KEYS: tuple[str, ...] = CONTROL_MECHANISM12_PARAMETER_KEYS[:4]

# Mechanism-11 normoxic_CC (config/calibration_settings.py is authoritative; keep in sync)
MECHANISM11_PARAMETER_KEYS: tuple[str, ...] = (
    "normoxic_CC/can_grow/probability",
    "normoxic_CC/can_grow/diameter_rate",
    "normoxic_CC/can_divide/probability",
    "normoxic_CC/can_divide/diameter_cutoff",
    "normoxic_CC/can_divide/O2/threshold",
    "normoxic_CC/diameter/max",
)

MECHANISM11_X0: tuple[float, ...] = (0.17951108, 10.244646, 0.29564496, 18.0, 0.65, 20.0)
MECHANISM11_LB: tuple[float, ...] = (0.0, 0.1, 0.0, 10.0, 0.0, 15.0)
MECHANISM11_UB: tuple[float, ...] = (0.99, 25.0, 0.99, 22.0, 1.0, 30.0)
MECHANISM11_PARAMETER_X_SCALE: tuple[float, ...] = (0.15, 3.0, 0.2, 3.0, 0.1, 2.0)

# Short names for live/summary plots (avoid duplicate "probability" legend entries).
PARAMETER_PLOT_LABELS: dict[str, str] = {
    "normoxic_CC/can_apoptose/probability": "Baseline apoptose probability",
    "normoxic_CC/can_grow/probability": "Grow probability",
    "normoxic_CC/can_grow/diameter_rate": "Grow diameter rate",
    "normoxic_CC/can_divide/probability": "Divide probability",
    "normoxic_CC/phase_dwell/G1": "G1 dwell (h)",
    "normoxic_CC/phase_dwell/Sy": "S-phase dwell (h)",
    "normoxic_CC/phase_dwell/G2": "G2 dwell (h)",
    "normoxic_CC/phase_dwell/Di": "M-phase dwell (h)",
    "normoxic_CC/can_divide/time_window": "Divide maturity (h)",
    "normoxic_CC/can_divide/diameter_cutoff": "Divide diameter cutoff",
    "normoxic_CC/can_divide/O2/threshold": "Divide O2 threshold",
    "normoxic_CC/diameter/max": "Max diameter",
    "cancer_cell/can_apoptose/probability": "Apoptose probability",
    "cancer_cell/can_grow/probability": "Grow probability",
    "cancer_cell/can_grow/diameter_rate": "Grow diameter rate",
    "cancer_cell/can_divide/probability": "Divide probability",
    "cancer_cell/can_divide/time_window": "Divide maturity (h)",
}

PARAMETER_PLOT_COLORS: dict[str, str] = {
    "normoxic_CC/can_apoptose/probability": "#4472C4",
    "normoxic_CC/can_grow/probability": "#ED7D31",
    "normoxic_CC/can_grow/diameter_rate": "#70AD47",
    "normoxic_CC/can_divide/probability": "#FFC000",
    "normoxic_CC/phase_dwell/G1": "#5B9BD5",
    "normoxic_CC/phase_dwell/Sy": "#A5A5A5",
    "normoxic_CC/phase_dwell/G2": "#7030A0",
    "normoxic_CC/phase_dwell/Di": "#264478",
    "normoxic_CC/can_divide/time_window": "#C55A11",
    "normoxic_CC/can_divide/diameter_cutoff": "#264478",
    "normoxic_CC/can_divide/O2/threshold": "#548235",
    "normoxic_CC/diameter/max": "#BF8F00",
}

TREATED_MECHANISM12_PARAMETER_KEYS: tuple[str, ...] = (
    "cancer_cell/can_apoptose/probability",
    "cancer_cell/can_grow/probability",
    "cancer_cell/can_divide/probability",
)

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


def read_initial_cells_max_diameter(path: str | Path) -> float | None:
    """Largest cell diameter in an ABM4bio initial_cells.dat file (column 4)."""
    p = Path(path)
    if not p.is_file():
        return None
    max_dia: float | None = None
    with p.open(encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        dia = float(parts[3])
        max_dia = dia if max_dia is None else max(max_dia, dia)
    return max_dia


def find_initial_cells_file(copy_files: Sequence[Path]) -> Path | None:
    for path in copy_files:
        if path.name == "initial_cells.dat" and path.is_file():
            return path
    return None


def adjust_mechanism11_lb_for_initial_cells(
    lb: Sequence[float],
    parameter_keys: Sequence[str] | None,
    copy_files: Sequence[Path],
) -> list[float]:
    """Keep fitted diameter/max above pre-placed cells so ABM4bio init does not abort."""
    keys = list(parameter_keys or MECHANISM11_PARAMETER_KEYS)
    key = "normoxic_CC/diameter/max"
    if key not in keys:
        return list(lb)
    idx = keys.index(key)
    initial_path = find_initial_cells_file(copy_files)
    if initial_path is None:
        return list(lb)
    max_dia = read_initial_cells_max_diameter(initial_path)
    if max_dia is None:
        return list(lb)
    out = list(lb)
    out[idx] = max(out[idx], max_dia)
    return out


def mechanism11_fit_vectors(
    keys: Sequence[str],
    *,
    template_path: str | Path | None = None,
    time_step_h: float | None = None,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    lookup = {name: i for i, name in enumerate(MECHANISM11_PARAMETER_KEYS)}
    unknown = [name for name in keys if name not in lookup]
    if unknown:
        raise ValueError(f"Unknown mechanism-11 fit parameters: {unknown}")
    indices = [lookup[name] for name in keys]
    x0_defaults = [MECHANISM11_X0[i] for i in indices]
    dt_h = time_step_h
    if dt_h is None and template_path:
        dt_h = read_template_time_step_hours(template_path, default=1.0)
    if dt_h is None:
        dt_h = 1.0
    if template_path:
        template_vals = read_template_parameter_values(template_path, tuple(keys))
        if template_vals:
            x0 = tuple(
                template_value_to_optimizer(key, val, time_step_h=dt_h)
                for key, val in zip(keys, template_vals)
            )
        else:
            x0 = tuple(x0_defaults)
    else:
        x0 = tuple(x0_defaults)
    lb = tuple(MECHANISM11_LB[i] for i in indices)
    ub = tuple(MECHANISM11_UB[i] for i in indices)
    x_scale = tuple(MECHANISM11_PARAMETER_X_SCALE[i] for i in indices)
    return x0, lb, ub, x_scale


def is_mechanism11_fit_keys(keys: Sequence[str]) -> bool:
    known = set(MECHANISM11_PARAMETER_KEYS)
    return bool(keys) and all(key in known for key in keys)

# LM-calibrated control growth defaults (ABM4bio prepare_control_input.py / input_control.csv)
CONTROL_MECHANISM12_X0: tuple[float, ...] = (
    0.84592981,
    0.0029217516,
    0.4556126,
    0.52025049,
    319.0,
)
CONTROL_MECHANISM12_LB: tuple[float, ...] = (0.30, 0.0001, 0.05, 0.01, 50.0)
CONTROL_MECHANISM12_UB: tuple[float, ...] = (0.99, 0.25, 2.0, 0.99, 500.0)

# Relative LM step scales: smaller => more sensitive (probabilities & growth rate prioritized).
CONTROL_PARAMETER_X_SCALE: tuple[float, ...] = (0.2, 0.002, 0.3, 0.2, 80.0)

# Per-stage residual weights for t>0 (stage1: 24h only; stage2: 24+48h; stage3: 24+48+72h).
# Stage 1 de-emphasized: fitting only 24 h often kills 48–72 h growth.
CONTROL_CALIBRATION_STAGE_TIME_WEIGHTS: tuple[tuple[float, ...], ...] = (
    (0.15,),
    (0.2, 3.0),
    (0.15, 3.0, 6.0),
)

TREATED_MECHANISM12_X0: tuple[float, ...] = (0.0029, 0.52, 0.84)
TREATED_MECHANISM12_LB: tuple[float, ...] = (0.0, 0.0, 0.0)
TREATED_MECHANISM12_UB: tuple[float, ...] = (0.9999, 0.9999, 0.9999)

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

# Backward-compatible alias (mech-10/12 only; workflow selects per mechanism).
CONTROL_RUNTIME_OVERRIDES = CONTROL_FAST_RUNTIME_OVERRIDES

def build_mechanism11_control_overrides(
    time_step_h: float,
    *,
    simulation_hours: float | None = None,
    phase_dwell_h: Sequence[float] | None = None,
    divide_maturity_h: float | None = None,
    apoptosis_aging_onset_h: float | None = None,
    apoptosis_cleanup_h: float | None = None,
) -> dict[str, object]:
    """Build step-quantized ABM overrides from hour-based control defaults."""
    from config.calibration_settings import (
        MECHANISM11_APOPTOSIS_AGING_ONSET_H,
        MECHANISM11_APOPTOSIS_CLEANUP_H,
        MECHANISM11_DIVIDE_MATURITY_H,
        MECHANISM11_PHASE_DWELL_H,
        MECHANISM11_SIMULATION_HOURS,
    )

    dt = max(float(time_step_h), 1.0e-12)
    sim_h = float(simulation_hours if simulation_hours is not None else MECHANISM11_SIMULATION_HOURS)
    dwell = tuple(phase_dwell_h if phase_dwell_h is not None else MECHANISM11_PHASE_DWELL_H)
    g1_h, sy_h, g2_h, di_h = (list(dwell) + [0.0, 0.0, 0.0, 0.0])[:4]
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
        "statistics_interval": 1,
        "visualization_interval": max(1, hours_to_steps(24.0, dt)),
    }


def build_mechanism11_runtime_overrides(time_step_h: float, *, simulation_hours: float | None = None) -> dict[str, object]:
    return {
        **CONTROL_CAP_OVERRIDES,
        **build_mechanism11_control_overrides(time_step_h, simulation_hours=simulation_hours),
        "simulation/early_stop_on_total_cells_exceeded": False,
    }


# Default dt=1 h (72 steps × 1 h). Use build_mechanism11_runtime_overrides(dt) when dt differs.
MECHANISM11_CONTROL_OVERRIDES: dict[str, object] = build_mechanism11_control_overrides(1.0)
MECHANISM11_RUNTIME_OVERRIDES: dict[str, object] = build_mechanism11_runtime_overrides(1.0)

# Per-horizon residual weights for t>0 (de-emphasize 24 h-only fits).
MECHANISM11_CALIBRATION_STAGE_TIME_WEIGHTS: tuple[tuple[float, ...], ...] = (
    (0.15,),
    (0.2, 3.0),
    (0.15, 3.0, 10.0),
)

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

# Sequential warm-start calibration: fit 0–24 h, then 0–48 h, then 0–72 h.
CALIBRATION_HORIZONS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("0-24h", (0, 24)),
    ("0-48h", (0, 24, 48)),
    ("0-72h", (0, 24, 48, 72)),
)

# Backward-compatible alias.
CONTROL_CALIBRATION_STAGES: tuple[tuple[int, ...], ...] = tuple(
    horizon for _, horizon in CALIBRATION_HORIZONS
)


def format_parameter_value(key: str, value: float, *, time_step_h: float = 1.0) -> object:
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


def _slice_control_vectors(keys: tuple[str, ...]) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    lookup = {name: index for index, name in enumerate(CONTROL_MECHANISM12_PARAMETER_KEYS)}
    unknown = [name for name in keys if name not in lookup]
    if unknown:
        raise ValueError(f"Unknown control fit parameters: {unknown}")
    indices = [lookup[name] for name in keys]
    x0 = tuple(CONTROL_MECHANISM12_X0[i] for i in indices)
    lb = tuple(CONTROL_MECHANISM12_LB[i] for i in indices)
    ub = tuple(CONTROL_MECHANISM12_UB[i] for i in indices)
    return x0, lb, ub


def default_fit_bounds(
    parameter_keys: list[str] | None,
    *,
    template_path: str | Path | None = None,
    control_mode: bool = False,
    mechanism: int | None = None,
) -> tuple[str, str, str]:
    keys = tuple(parameter_keys or ())
    if mechanism == 11 or is_mechanism11_fit_keys(keys):
        fit_keys = keys or MECHANISM11_PARAMETER_KEYS
        dt_h = read_template_time_step_hours(template_path, default=1.0) if template_path else 1.0
        x0, lb, ub, _ = mechanism11_fit_vectors(fit_keys, template_path=template_path, time_step_h=dt_h)
        return comma(x0), comma(lb), comma(ub)
    if control_mode or keys in (CONTROL_MECHANISM12_PARAMETER_KEYS, CONTROL_FIT_PARAMETER_KEYS) or (
        control_mode and not keys
    ):
        fit_keys = keys or CONTROL_FIT_PARAMETER_KEYS
        x0, lb, ub = _slice_control_vectors(fit_keys)
        # Control proliferation uses LM growth defaults, not mechanism-12 CAP template values.
        return comma(x0), comma(lb), comma(ub)
    if keys == TREATED_MECHANISM12_PARAMETER_KEYS or (
        parameter_keys and all("probability" in k for k in parameter_keys) and len(parameter_keys) == 3
    ):
        return comma(TREATED_MECHANISM12_X0), comma(TREATED_MECHANISM12_LB), comma(TREATED_MECHANISM12_UB)
    return comma(MECHANISM11_X0), comma(MECHANISM11_LB), comma(MECHANISM11_UB)
