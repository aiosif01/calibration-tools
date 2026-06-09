#!/usr/bin/env python3
"""Export best parameters from an existing Optuna SQLite study."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import optuna

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.method.optuna_reporting import export_best_parameters, export_trial_history  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Export best parameters from an Optuna study database.")
    ap.add_argument("--storage", required=True, help="sqlite:///path/to/study.db")
    ap.add_argument("--study-name", required=True)
    ap.add_argument("--parameter-keys", required=True, help="Comma-separated parameter names in order")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = [k.strip() for k in args.parameter_keys.split(",") if k.strip()]

    study = optuna.load_study(study_name=args.study_name, storage=args.storage)
    export_best_parameters(study, keys, out_dir / "calibrated_parameters.csv")
    export_trial_history(study, out_dir / "trials" / "trial_history.csv")

    print(f"Exported best trial {study.best_trial.number} to {out_dir}")
    print(f"  Objective: {study.best_value:.6g}")


if __name__ == "__main__":
    main()
