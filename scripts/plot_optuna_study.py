#!/usr/bin/env python3
"""Regenerate Optuna study figures from an existing SQLite database."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import optuna

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.method.optuna_importance import plot_parameter_importance, plot_parallel_coordinates  # noqa: E402
from abmcal.method.optuna_reporting import plot_optimization_history  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot figures from an existing Optuna study.")
    ap.add_argument("--storage", required=True)
    ap.add_argument("--study-name", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title", default="")
    args = ap.parse_args()

    out_dir = Path(args.out_dir) / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    study = optuna.load_study(study_name=args.study_name, storage=args.storage)
    title = args.title or args.study_name

    plot_optimization_history(study, out_dir / "optimization_history.png", title=title)
    plot_parameter_importance(study, out_dir / "parameter_importance.png", title=title)
    plot_parallel_coordinates(study, out_dir / "parallel_coordinates.png", title=title)

    print(f"Figures saved to {out_dir}")


if __name__ == "__main__":
    main()
