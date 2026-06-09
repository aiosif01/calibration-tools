#!/usr/bin/env python3
"""Print resolved calibration settings (edit config/calibration_settings.py to change defaults)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.calibration_config import (  # noqa: E402
    CELL_LINES,
    EARLY_STOP,
    HORIZON_GATE,
    OPTIMIZER,
    TARGETS_CSV,
    get_cell_line_settings,
    resolve_control_template,
    resolve_treated_template,
)
from config.calibration_settings import (  # noqa: E402
    MECHANISM11_SIMULATION_HOURS,
    MECHANISM11_TIME_STEP_H,
)


def _path_str(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def main() -> None:
    ap = argparse.ArgumentParser(description="Show central calibration configuration.")
    ap.add_argument("--cell-line", default=None, help="Show one cell line (default: all)")
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = ap.parse_args()

    lines = args.cell_line.strip() if args.cell_line else list(CELL_LINES)
    if isinstance(lines, str):
        lines = [lines]

    payload = {
        "optimizer": OPTIMIZER.__dict__,
        "early_stop": EARLY_STOP.__dict__,
        "horizon_gate": HORIZON_GATE.__dict__,
        "targets_csv": _path_str(TARGETS_CSV),
        "cell_lines": {},
    }

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

    print("Calibration settings (config/calibration_settings.py)")
    print("=" * 60)
    print(f"Optimizer: method={OPTIMIZER.method}, staged={OPTIMIZER.staged}, stage_nfev={OPTIMIZER.stage_nfev}")
    print(f"  horizons: 0-24h -> 0-48h -> 0-72h, use_abm_seed={OPTIMIZER.use_abm_seed}")
    print(f"  global_nfev={OPTIMIZER.global_nfev}, max_nfev_single={OPTIMIZER.max_nfev_single}, replicates={OPTIMIZER.replicates}")
    print(f"Early stop: enabled={EARLY_STOP.enabled}, overgrowth_factor={EARLY_STOP.overgrowth_factor}")
    print(
        f"Horizon gate: enabled={HORIZON_GATE.enabled}, "
        f"sim/target in [{HORIZON_GATE.min_sim_to_target}, {HORIZON_GATE.max_sim_to_target}]"
    )
    print(f"Targets CSV: {_path_str(TARGETS_CSV)}")
    print(
        f"Mechanism-11 timing: dt={MECHANISM11_TIME_STEP_H} h, "
        f"simulation={MECHANISM11_SIMULATION_HOURS} h "
        f"({int(MECHANISM11_SIMULATION_HOURS / MECHANISM11_TIME_STEP_H)} steps); "
        "cell-cycle dwell/maturity fixed in template; size/O2 gates fitted"
    )
    print()
    for name in lines:
        entry = payload["cell_lines"][name]
        print(f"[{name}] mechanism {entry['mechanism']}")
        print(f"  control:  {entry['control_template']}")
        print(f"  treated:  {entry['treated_template']}")
        print(f"  params:   {', '.join(entry['parameter_keys'])}")
        print(f"  x0:       {entry['x0']}")
        print()


if __name__ == "__main__":
    main()
