#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.calibration_plots import make_summary_bar_plots


def make_bar_plots(summary_df: pd.DataFrame, out_dir: str | Path) -> None:
    make_summary_bar_plots(summary_df, out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description="Create grouped bar charts from summary_fit_parameters.csv")
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    summary = pd.read_csv(args.summary)
    out_dir = Path(args.out_dir) if args.out_dir else Path(args.summary).parent
    make_bar_plots(summary, out_dir)
    print(f"Saved bar plots to {out_dir}")


if __name__ == "__main__":
    main()
