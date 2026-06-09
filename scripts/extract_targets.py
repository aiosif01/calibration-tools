#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abmcal.data_loader import read_cap_excel_long


def main() -> None:
    p = argparse.ArgumentParser(description="Extract long-format CAP calibration targets from the Gorjet Excel workbook.")
    p.add_argument("--xlsx", required=True, help="Input Excel workbook")
    p.add_argument("--out", default=str(ROOT / "data" / "calibration_targets_from_excel.csv"))
    p.add_argument("--use-sheet-mean", action="store_true", help="Use sheet MEAN/SD cells instead of recomputing from N=1..N=4")
    args = p.parse_args()

    df = read_cap_excel_long(args.xlsx, recompute_mean=not args.use_sheet_mean)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")
    print(df.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
