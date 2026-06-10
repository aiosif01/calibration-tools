"""
Central calibration / optimization settings for calibration-tools.

Edit this file to change templates, mechanism, Optuna budgets, early-stop, and
per-cell-line defaults. CLI flags in run_optuna_control.py still override these.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "templates"
DATA_DIR = REPO_ROOT / "data"
EXECUTABLES_DIR = REPO_ROOT / "executables"

# ---------------------------------------------------------------------------
# Mechanism identifiers
# ---------------------------------------------------------------------------
MECHANISM_11 = 11
MECHANISM_12 = 12

DEFAULT_MECHANISM = MECHANISM_11

# ---------------------------------------------------------------------------
# Simulation clocks (ABM4bio time_step is always in hours; see abmcal/time_units.py)
# ---------------------------------------------------------------------------
# Viability assay: 0, 24, 48, 72 h post-treatment (Excel targets). Control = untreated growth.
# Mechanism 11 control: minute resolution (finer cell-cycle than 1 h/step).
MECHANISM11_TIME_STEP_MINUTES = 1.0
MECHANISM11_SIMULATION_HOURS = 72.0
# Mechanism 12 CAP: second resolution for 30 s / 2 / 4 / 5 min plasma exposures.
MECHANISM12_TIME_STEP_SECONDS = 1.0
MECHANISM12_SIMULATION_HOURS = 72.0
CAP_EXPOSURE_SECONDS: tuple[int, ...] = (30, 120, 240, 300)

# Derived ABM time_step [h] (do not edit — use MINUTES/SECONDS above).
MECHANISM11_TIME_STEP_H = MECHANISM11_TIME_STEP_MINUTES / 60.0
MECHANISM12_TIME_STEP_H = MECHANISM12_TIME_STEP_SECONDS / 3600.0
# Fixed cell-cycle timing (EGI1 control calibration 2025-06; not fitted — edit template manually).
MECHANISM11_PHASE_DWELL_H: tuple[float, ...] = (8.2266921, 7.9340755, 4.407848, 0.0)  # G1, Sy, G2, Di [h]
MECHANISM11_DIVIDE_MATURITY_H = 5.403776
MECHANISM11_APOPTOSIS_AGING_ONSET_H = 2500.0
MECHANISM11_APOPTOSIS_CLEANUP_H = 5000.0

# x0/lb/ub: proliferation + size gates + cell cycle [h] + apoptosis (prob, aging onset [h])
MECHANISM11_X0: tuple[float, ...] = (
    0.17951108,
    10.244646,
    0.29564496,
    18.0,
    20.0,
    8.2266921,
    7.9340755,
    4.407848,
    5.403776,
    0.0,
    0.0,
    0.003,
    2500.0,
)
MECHANISM11_LB: tuple[float, ...] = (
    0.0,
    0.1,
    0.0,
    10.0,
    15.0,
    1.0,
    1.0,
    1.0,
    1.0,
    0.0,
    0.0,
    1.0e-5,
    72.0,
)
MECHANISM11_UB: tuple[float, ...] = (
    0.99,
    25.0,
    0.99,
    22.0,
    30.0,
    24.0,
    20.0,
    12.0,
    30.0,
    5.0e-4,
    4.0,
    0.05,
    5000.0,
)
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

MECHANISM11_PLACEHOLDERS: tuple[str, ...] = ()

# ---------------------------------------------------------------------------
# Optuna optimization defaults (optuna branch)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OptunaSettings:
    n_trials: int = 200
    debug_n_trials: int = 20
    n_replicates: int = 3
    validation_replicates: int = 10
    n_startup_trials: int = 30
    sampler_seed: int = 1234
    prune_after_replicates: int = 2
    log_space: bool = True
    normalize_sim_to_t0: bool = True
    target_mode: str = "t0_normalized"
    time_points: tuple[int, ...] = (0, 24, 48, 72)
    use_abm_seed: bool = False
    abm_base_seed: int = 1234
    abm_seed_step: int = 17
    sigma: str = "data"
    parameter_space_control: Path = field(
        default_factory=lambda: REPO_ROOT / "configs" / "parameter_space_control.yaml"
    )
    parameter_space_treatment: Path = field(
        default_factory=lambda: REPO_ROOT / "configs" / "parameter_space_treatment.yaml"
    )
    objective_control: Path = field(
        default_factory=lambda: REPO_ROOT / "configs" / "objective_control.yaml"
    )
    objective_treatment: Path = field(
        default_factory=lambda: REPO_ROOT / "configs" / "objective_treatment.yaml"
    )
    studies_dir: Path = field(default_factory=lambda: REPO_ROOT / "outputs" / "optuna" / "studies")


# Backward-compatible alias (scripts that still reference OPTIMIZER)
OptimizerSettings = OptunaSettings


@dataclass(frozen=True)
class EarlyStopSettings:
    """Kill ABM runs that explode far above the experimental envelope."""

    enabled: bool = True
    overgrowth_factor: float = 4.0
    min_sim_hour_fraction: float = 0.15
    poll_interval_s: float = 0.25


@dataclass(frozen=True)
class CellLineSettings:
    cell_line: str
    mechanism: int = DEFAULT_MECHANISM
    control_template: Path = field(default_factory=Path)
    treated_template: Path = field(default_factory=Path)
    parameter_keys: tuple[str, ...] = MECHANISM11_PARAMETER_KEYS
    placeholder_names: tuple[str, ...] = MECHANISM11_PLACEHOLDERS
    x0: tuple[float, ...] = MECHANISM11_X0
    lb: tuple[float, ...] = MECHANISM11_LB
    ub: tuple[float, ...] = MECHANISM11_UB
    output_metric: str = "N_cells"
    cancer_phenotype_id: int = 2
    copy_files: tuple[Path, ...] = ()
    initial_population: int = 100


def _cell_template(cell_line: str, name: str) -> Path:
    return TEMPLATES_DIR / "cell_lines" / cell_line / name


def _default_cell_line(cell_line: str) -> CellLineSettings:
    return CellLineSettings(
        cell_line=cell_line,
        mechanism=MECHANISM_11,
        control_template=_cell_template(cell_line, "input_control_mechanism11.csv"),
        treated_template=_cell_template(cell_line, "input_mechanism12_treated.csv"),
        parameter_keys=MECHANISM11_PARAMETER_KEYS,
        placeholder_names=MECHANISM11_PLACEHOLDERS,
        x0=MECHANISM11_X0,
        lb=MECHANISM11_LB,
        ub=MECHANISM11_UB,
        output_metric="N_cells",
        cancer_phenotype_id=2,
        copy_files=(),
        initial_population=100,
    )


CELL_LINES: tuple[str, ...] = ("EGI1", "HuCCT1", "PANC1", "MiaPaCa2")

CELL_LINE_SETTINGS: Mapping[str, CellLineSettings] = {
    name: _default_cell_line(name) for name in CELL_LINES
}

OPTUNA = OptunaSettings()
OPTIMIZER = OPTUNA
EARLY_STOP = EarlyStopSettings()

TARGETS_CSV = DATA_DIR / "calibration_targets_from_excel.csv"
XLSX_DEFAULT = DATA_DIR / (
    "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"
)

def get_cell_line_settings(cell_line: str) -> CellLineSettings:
    key = cell_line.strip()
    if key not in CELL_LINE_SETTINGS:
        known = ", ".join(CELL_LINE_SETTINGS)
        raise KeyError(f"Unknown cell line {cell_line!r}. Known: {known}")
    return CELL_LINE_SETTINGS[key]


def control_out_dir(cell_line: str) -> Path:
    return REPO_ROOT / "outputs" / "optuna" / cell_line / "control"


def treatment_out_dir(cell_line: str, exposure_seconds: int) -> Path:
    label = f"treat_{exposure_seconds}s"
    return REPO_ROOT / "outputs" / "optuna" / cell_line / label


def optuna_study_db(cell_line: str, case_label: str) -> str:
    db_path = OPTUNA.studies_dir / f"{cell_line}_{case_label}.db"
    return f"sqlite:///{db_path}"


def resolve_control_template(cell_line: str) -> Path:
    cfg = get_cell_line_settings(cell_line)
    if not cfg.control_template.is_file():
        raise FileNotFoundError(
            f"Control template missing for {cell_line}: {cfg.control_template}"
        )
    return cfg.control_template


def mechanism11_simulation_clock() -> "SimulationClock":
    from abmcal.time_units import SimulationClock, hours_to_steps, minutes_to_time_step_h

    dt_h = minutes_to_time_step_h(MECHANISM11_TIME_STEP_MINUTES)
    return SimulationClock(
        label=f"mech-11 control ({MECHANISM11_TIME_STEP_MINUTES:g} min/step)",
        time_step_h=dt_h,
        simulation_hours=MECHANISM11_SIMULATION_HOURS,
        statistics_interval_steps=max(1, hours_to_steps(1.0, dt_h)),
        visualization_interval_steps=max(1, hours_to_steps(24.0, dt_h)),
    )


def mechanism12_simulation_clock() -> "SimulationClock":
    from abmcal.time_units import SimulationClock, hours_to_steps, seconds_to_time_step_h

    dt_h = seconds_to_time_step_h(MECHANISM12_TIME_STEP_SECONDS)
    return SimulationClock(
        label=f"mech-12 CAP ({MECHANISM12_TIME_STEP_SECONDS:g} s/step)",
        time_step_h=dt_h,
        simulation_hours=MECHANISM12_SIMULATION_HOURS,
        statistics_interval_steps=max(1, hours_to_steps(1.0, dt_h)),
        visualization_interval_steps=max(1, hours_to_steps(24.0, dt_h)),
    )


def resolve_treated_template(cell_line: str) -> Path:
    cfg = get_cell_line_settings(cell_line)
    if not cfg.treated_template.is_file():
        raise FileNotFoundError(
            f"Treated template missing for {cell_line}: {cfg.treated_template}"
        )
    return cfg.treated_template
