"""Shared helpers for ANN calibration scripts."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from abmcal.abm_runner import calibration_input_overrides
from abmcal.calibration_config import ANN, get_cell_line_settings, resolve_control_template
from abmcal.calibration_params import INT_PARAMETER_KEYS
from abmcal.calibration_workflow import CalibrationContext
from abmcal.data_loader import read_cap_excel_long
from abmcal.method.parameter_space import load_parameter_space_yaml, parameter_space_from_bounds
from abmcal.time_units import read_template_time_step_hours

ROOT = Path(__file__).resolve().parents[1]


def load_yaml_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def parse_int_list(s: str) -> list[int]:
    return [int(float(x.strip())) for x in s.split(",") if x.strip()]


def build_calibration_context(
    *,
    cell_line: str,
    exposure_seconds: int,
    template_path: Path,
    run_command: str,
    parameter_keys: list[str],
    target_df: pd.DataFrame,
    target_mode: str,
    copy_files: list[Path],
    mock: bool,
    quiet: bool,
    use_abm_seed: bool,
    abm_base_seed: int,
    abm_seed_step: int,
    control_mode: bool,
    mechanism: int,
    cell_settings,
    work_root: Path,
    set_cap_duration: bool = False,
) -> CalibrationContext:
    return CalibrationContext(
        cell_line=cell_line,
        exposure_seconds=exposure_seconds,
        template_path=template_path,
        work_root=work_root,
        run_command=run_command,
        parameter_keys=parameter_keys,
        target_df=target_df,
        target_mode=target_mode,
        calibration_overrides=calibration_input_overrides(template_path, mechanism=mechanism),
        time_step_h=read_template_time_step_hours(template_path, default=1.0),
        control_mode=control_mode,
        set_cap_duration=set_cap_duration,
        copy_files=tuple(copy_files),
        mock=mock,
        stream_stdout=not mock and not quiet,
        strip_visualization=not mock,
        abm_use_seed=use_abm_seed,
        abm_base_seed=abm_base_seed if use_abm_seed else None,
        abm_seed_step=abm_seed_step,
        replicates=1,
        eval_counter={"n": 0},
        mechanism=mechanism,
        placeholder_names=cell_settings.placeholder_names,
        output_metric=cell_settings.output_metric,
        cancer_phenotype_id=cell_settings.cancer_phenotype_id,
    )


def load_parameter_space(args: argparse.Namespace, cell_settings) -> tuple:
    if args.parameter_space and Path(args.parameter_space).is_file():
        return load_parameter_space_yaml(args.parameter_space)
    return parameter_space_from_bounds(
        cell_settings.parameter_keys,
        cell_settings.lb,
        cell_settings.ub,
        int_keys=INT_PARAMETER_KEYS,
    )


def load_targets_df(args: argparse.Namespace) -> pd.DataFrame:
    if args.targets_csv:
        return pd.read_csv(args.targets_csv)
    return read_cap_excel_long(args.xlsx, recompute_mean=True)


def default_ann_paths(cell_line: str, case_label: str = "control") -> dict[str, Path]:
    base = ANN.outputs_dir / cell_line / case_label
    return {
        "out_dir": base,
        "datasets": base / "datasets",
        "models": base / "models",
        "calibration": base / "calibration",
        "validation": base / "validation",
        "figures": base / "figures",
        "work_root": base / "abm_evals",
    }
