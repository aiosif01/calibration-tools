#!/usr/bin/env python3
"""Print resolved ANN calibration settings."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.calibration_config import ANN, CELL_LINES, TARGETS_CSV, get_cell_line_settings, resolve_control_template  # noqa: E402


def _path_str(p: Path | str) -> str:
    path = Path(p)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Show ANN calibration configuration.")
    ap.add_argument("--cell-line", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    lines = [args.cell_line] if args.cell_line else list(CELL_LINES)
    payload = {"ann": asdict(ANN), "cell_lines": {}}
    for key, val in payload["ann"].items():
        if isinstance(val, Path):
            payload["ann"][key] = _path_str(val)

    for name in lines:
        cfg = get_cell_line_settings(name)
        payload["cell_lines"][name] = {
            "parameter_keys": list(cfg.parameter_keys),
            "lb": list(cfg.lb),
            "ub": list(cfg.ub),
            "control_template": _path_str(resolve_control_template(name)),
        }

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print("ANN calibration settings (config/calibration_settings.py)")
    print("=" * 60)
    print(f"Dataset: n_samples={ANN.n_samples}, seeds_per_sample={ANN.seeds_per_sample}, sampling={ANN.sampling}")
    print(f"Training: max_epochs={ANN.max_epochs}, ensemble={len(ANN.ensemble_seeds)} models")
    print(f"Inverse: restarts={ANN.inverse_restarts}, steps={ANN.inverse_steps}, validation_replicates={ANN.validation_replicates}")
    print(f"Outputs: {_path_str(ANN.outputs_dir)}")
    print(f"Targets: {_path_str(TARGETS_CSV)}")
    for name in lines:
        entry = payload["cell_lines"][name]
        print(f"\n[{name}] params: {', '.join(entry['parameter_keys'])}")


if __name__ == "__main__":
    main()
