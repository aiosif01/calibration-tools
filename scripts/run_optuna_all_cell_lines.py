#!/usr/bin/env python3
"""Run Optuna control calibration for all configured cell lines."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.calibration_config import CELL_LINES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Run Optuna control calibration for all cell lines.")
    ap.add_argument("--n-trials", type=int, default=None)
    ap.add_argument("--replicates", type=int, default=None)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--cell-lines", default=",".join(CELL_LINES))
    args = ap.parse_args()

    lines = [x.strip() for x in args.cell_lines.split(",") if x.strip()]
    script = ROOT / "scripts" / "run_optuna_control.py"

    for cell_line in lines:
        cmd = [sys.executable, str(script), "--cell-line", cell_line, "--use-config"]
        if args.n_trials is not None:
            cmd.extend(["--n-trials", str(args.n_trials)])
        if args.replicates is not None:
            cmd.extend(["--replicates", str(args.replicates)])
        if args.mock:
            cmd.append("--mock")
        print(f"\n=== {cell_line} ===", flush=True)
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
