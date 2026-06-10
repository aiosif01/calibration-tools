#!/usr/bin/env python3
"""Print resolved calibration settings (edit config/calibration_settings.py to change defaults)."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.calibration_config import (  # noqa: E402
    CELL_LINES,
    EARLY_STOP,
    OPTUNA,
    TARGETS_CSV,
    get_cell_line_settings,
    resolve_control_template,
    resolve_treated_template,
)
from abmcal.time_units import format_time_conversion_audit, validate_simulation_clock  # noqa: E402
from config.calibration_settings import (  # noqa: E402
    CAP_EXPOSURE_SECONDS,
    mechanism11_simulation_clock,
    mechanism12_simulation_clock,
)


def _path_str(p: Path | str) -> str:
    path = Path(p) if not isinstance(p, Path) else p
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Show central calibration configuration.")
    ap.add_argument("--cell-line", default=None, help="Show one cell line (default: all)")
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = ap.parse_args()

    lines = args.cell_line.strip() if args.cell_line else list(CELL_LINES)
    if isinstance(lines, str):
        lines = [lines]

    payload = {
        "optuna": asdict(OPTUNA),
        "early_stop": asdict(EARLY_STOP),
        "targets_csv": _path_str(TARGETS_CSV),
        "cell_lines": {},
    }
    path_keys = {
        "parameter_space_control",
        "parameter_space_treatment",
        "objective_control",
        "objective_treatment",
        "studies_dir",
    }
    for key, val in payload["optuna"].items():
        if isinstance(val, Path) or key in path_keys:
            payload["optuna"][key] = _path_str(val)

    for name in lines:
        cfg = get_cell_line_settings(name)
        payload["cell_lines"][name] = {
            "mechanism": cfg.mechanism,
            "control_template": _path_str(resolve_control_template(name)),
            "treated_template": _path_str(resolve_treated_template(name)),
            "parameter_keys": list(cfg.parameter_keys),
            "x0": list(cfg.x0),
            "lb": list(cfg.lb),
            "ub": list(cfg.ub),
            "output_metric": cfg.output_metric,
            "copy_files": [_path_str(p) for p in cfg.copy_files],
        }

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print("Optuna calibration settings (config/calibration_settings.py)")
    print("=" * 60)
    print(
        f"Optuna: n_trials={OPTUNA.n_trials}, n_replicates={OPTUNA.n_replicates}, "
        f"validation_replicates={OPTUNA.validation_replicates}"
    )
    print(f"  sampler_seed={OPTUNA.sampler_seed}, n_startup_trials={OPTUNA.n_startup_trials}")
    print(f"  parameter_space_control: {_path_str(OPTUNA.parameter_space_control)}")
    print(f"  studies_dir: {_path_str(OPTUNA.studies_dir)}")
    print(f"Early stop: enabled={EARLY_STOP.enabled}, overgrowth_factor={EARLY_STOP.overgrowth_factor}")
    print(f"Targets CSV: {_path_str(TARGETS_CSV)}")
    m11_clock = mechanism11_simulation_clock()
    m12_clock = mechanism12_simulation_clock()
    print(f"Mechanism-11 control clock: {m11_clock.describe()}")
    print(f"Mechanism-12 CAP clock:      {m12_clock.describe()}")
    print(f"  CAP exposures (s): {list(CAP_EXPOSURE_SECONDS)}")
    print("  Optuna time-parameter bounds are in simulated HOURS; ABM CSV uses integer steps.")
    print()
    for name in lines:
        entry = payload["cell_lines"][name]
        print(f"[{name}] mechanism {entry['mechanism']}")
        print(f"  control:  {entry['control_template']}")
        print(f"  treated:  {entry['treated_template']}")
        print(f"  params:   {', '.join(entry['parameter_keys'])}")
        tpl = Path(entry["control_template"])
        if tpl.is_file():
            report = validate_simulation_clock(tpl, OPTUNA.time_points, m11_clock)
            print(f"  control template: {m11_clock.describe()}")
            for warning in report.warnings:
                print(f"  TIME WARNING: {warning}")
            audit = format_time_conversion_audit(tpl, entry["parameter_keys"], clock=m11_clock)
            for line in audit.splitlines():
                print(f"  {line}")
        print()


if __name__ == "__main__":
    main()
