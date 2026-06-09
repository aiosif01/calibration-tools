"""
Central calibration / optimization settings for calibration-tools.

Edit this file to change templates, mechanism, LM budgets, early-stop, and
per-cell-line defaults. CLI flags in calibrate_one_case.py still override these.

MATLAB reference: Levenberg-Marquardt_MATLAB/ (mechanism 11; control is O2-only, no RONS).
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
MECHANISM_10 = 10
MECHANISM_11 = 11
MECHANISM_12 = 12

DEFAULT_MECHANISM = MECHANISM_11

# ---------------------------------------------------------------------------
# MATLAB LM parity (Levenberg-Marquardt_MATLAB/main.m + input~TEMPLATE.csv)
# ---------------------------------------------------------------------------
# O2-only control. Dwell / divide maturity are in simulated HOURS (converted to steps via time_step).
MECHANISM11_TIME_STEP_H = 1.0
MECHANISM11_SIMULATION_HOURS = 72.0
# Fixed cell-cycle timing (EGI1 control calibration 2025-06; not fitted — edit template manually).
MECHANISM11_PHASE_DWELL_H: tuple[float, ...] = (8.2266921, 7.9340755, 4.407848, 0.0)  # G1, Sy, G2, Di [h]
MECHANISM11_DIVIDE_MATURITY_H = 5.403776
MECHANISM11_APOPTOSIS_AGING_ONSET_H = 2500.0
MECHANISM11_APOPTOSIS_CLEANUP_H = 5000.0

# x0/lb/ub: grow prob, diameter rate, divide prob, divide diameter cutoff, divide O2 threshold, diameter max
MECHANISM11_X0: tuple[float, ...] = (0.17951108, 10.244646, 0.29564496, 18.0, 0.65, 20.0)
MECHANISM11_LB: tuple[float, ...] = (0.0, 0.1, 0.0, 10.0, 0.0, 15.0)
MECHANISM11_UB: tuple[float, ...] = (0.99, 25.0, 0.99, 22.0, 1.0, 30.0)
MECHANISM11_PARAMETER_X_SCALE: tuple[float, ...] = (0.15, 3.0, 0.2, 3.0, 0.1, 2.0)

# Legacy 3-parameter MATLAB LM names (superseded by MECHANISM11_* above)
MATLAB_LM_X0: tuple[float, ...] = MECHANISM11_X0[:3]
MATLAB_LM_LB: tuple[float, ...] = MECHANISM11_LB[:3]
MATLAB_LM_UB: tuple[float, ...] = MECHANISM11_UB[:3]
MATLAB_LM_SIGMA = 0.45
MATLAB_LM_MAX_NFEV = 20_000
MATLAB_LM_DIFF_STEP = 0.03
MATLAB_LM_TIME_STEPS = 72
MATLAB_LM_TIME_STEP_H = 1.0

MECHANISM11_PARAMETER_KEYS: tuple[str, ...] = (
    "normoxic_CC/can_grow/probability",
    "normoxic_CC/can_grow/diameter_rate",
    "normoxic_CC/can_divide/probability",
    "normoxic_CC/can_divide/diameter_cutoff",
    "normoxic_CC/can_divide/O2/threshold",
    "normoxic_CC/diameter/max",
)

MECHANISM11_PLACEHOLDERS: tuple[str, ...] = ()

# ---------------------------------------------------------------------------
# Shared optimization defaults (scipy.optimize.least_squares / staged control)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OptimizerSettings:
    method: str = "trf"
    staged: bool = True
    log_space: bool = True
    normalize_sim_to_t0: bool = True
    target_mode: str = "t0_normalized"
    time_points: tuple[int, ...] = (0, 24, 48, 72)
    global_nfev: int = 0
    global_seed: int = 1234
    stage_nfev: tuple[int, ...] = (40, 40, 150)
    use_abm_seed: bool = False
    max_nfev_single: int = 150
    replicates: int = 2
    abm_base_seed: int = 1234
    abm_seed_step: int = 17
    diff_step: float = MATLAB_LM_DIFF_STEP
    xtol: float = 1e-6
    ftol: float = 1e-6
    gtol: float = 1e-6
    sigma: str = "data"


@dataclass(frozen=True)
class EarlyStopSettings:
    """Kill ABM runs that explode far above the experimental envelope."""

    enabled: bool = True
    overgrowth_factor: float = 4.0
    min_sim_hour_fraction: float = 0.15
    poll_interval_s: float = 0.25


@dataclass(frozen=True)
class HorizonGateSettings:
    """Do not advance 0-24h -> 0-48h -> 0-72h unless the current horizon fits."""

    enabled: bool = True
    min_sim_to_target: float = 0.55
    max_sim_to_target: float = 2.5


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
    copy_files: tuple[Path, ...] = (TEMPLATES_DIR / "initial_cells.dat",)
    initial_population: int = 1118


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
        copy_files=(TEMPLATES_DIR / "initial_cells.dat",),
        initial_population=1118,
    )


CELL_LINES: tuple[str, ...] = ("EGI1", "HuCCT1", "PANC1", "MiaPaCa2")

CELL_LINE_SETTINGS: Mapping[str, CellLineSettings] = {
    name: _default_cell_line(name) for name in CELL_LINES
}

OPTIMIZER = OptimizerSettings()
EARLY_STOP = EarlyStopSettings()
HORIZON_GATE = HorizonGateSettings()

TARGETS_CSV = DATA_DIR / "calibration_targets_from_excel.csv"
XLSX_DEFAULT = DATA_DIR / (
    "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"
)

# Legacy / alternate templates (not default)
LEGACY_TEMPLATES = {
    "mechanism10_control": TEMPLATES_DIR / "input_control_mechanism10_template.csv",
    "mechanism11_base": TEMPLATES_DIR / "input_control_mechanism11_template.csv",
    "mechanism12_cap": TEMPLATES_DIR / "input_mechanism12_CAP_template.csv",
    "matlab_lm": REPO_ROOT / "Levenberg-Marquardt_MATLAB" / "input~TEMPLATE.csv",
}


def get_cell_line_settings(cell_line: str) -> CellLineSettings:
    key = cell_line.strip()
    if key not in CELL_LINE_SETTINGS:
        known = ", ".join(CELL_LINE_SETTINGS)
        raise KeyError(f"Unknown cell line {cell_line!r}. Known: {known}")
    return CELL_LINE_SETTINGS[key]


def control_out_dir(cell_line: str) -> Path:
    return EXECUTABLES_DIR / cell_line / "outputs" / "calibration_control"


def resolve_control_template(cell_line: str) -> Path:
    cfg = get_cell_line_settings(cell_line)
    if not cfg.control_template.is_file():
        raise FileNotFoundError(
            f"Control template missing for {cell_line}: {cfg.control_template}"
        )
    return cfg.control_template


def resolve_treated_template(cell_line: str) -> Path:
    cfg = get_cell_line_settings(cell_line)
    if not cfg.treated_template.is_file():
        raise FileNotFoundError(
            f"Treated template missing for {cell_line}: {cfg.treated_template}"
        )
    return cfg.treated_template
