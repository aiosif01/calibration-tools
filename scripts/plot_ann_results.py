#!/usr/bin/env python3
"""Plot ANN training and calibration results."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from abmcal.calibration_config import control_out_dir  # noqa: E402
from abmcal.method.ann_reporting import plot_inverse_fit_curve, plot_training_loss  # noqa: E402
from scripts._ann_common import default_ann_paths  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot ANN results.")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--case-label", default="control")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    out_dir = Path(args.out_dir or control_out_dir(args.cell_line))
    paths = default_ann_paths(args.cell_line, args.case_label)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    for hist in sorted((out_dir / "models").glob("training_loss_seed*.csv")):
        plot_training_loss(hist, fig_dir / f"{hist.stem}.png", title=hist.stem)

    curve_path = out_dir / "calibration" / "ann_inverse_curve.csv"
    if curve_path.is_file():
        df = pd.read_csv(curve_path)
        plot_inverse_fit_curve(
            fig_dir / "inverse_fit_curve.png",
            time_h=df["time_h"],
            y_target=df["y_target"],
            y_ann=df["y_ann"],
            title=f"{args.cell_line} ANN inverse fit",
        )

    print(f"Figures saved to {fig_dir}")


if __name__ == "__main__":
    main()
