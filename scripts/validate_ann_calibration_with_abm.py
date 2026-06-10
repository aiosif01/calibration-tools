#!/usr/bin/env python3
"""Validate ANN-calibrated parameters with real ABM4bio (standalone)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from abmcal.calibration_config import ANN, control_out_dir, get_cell_line_settings, resolve_control_template  # noqa: E402
from abmcal.method.validate_ann_solution import ValidationConfig, validate_with_abm  # noqa: E402
from scripts._ann_common import build_calibration_context, default_ann_paths, load_targets_df  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate ANN parameters with ABM4bio.")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--exposure-seconds", type=int, default=0)
    ap.add_argument("--params-csv", required=True)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--work-root", default=None)
    ap.add_argument("--run-command", default="make")
    ap.add_argument("--n-replicates", type=int, default=None)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    params_df = pd.read_csv(args.params_csv)
    if "fitted_value" in params_df.columns:
        params = params_df["fitted_value"].tolist()
        keys = params_df["parameter_name"].tolist()
    else:
        raise ValueError("params CSV must have parameter_name and fitted_value columns")

    cell_settings = get_cell_line_settings(args.cell_line)
    paths = default_ann_paths(args.cell_line, "control")
    out_dir = Path(args.out_dir or control_out_dir(args.cell_line))
    template_path = resolve_control_template(args.cell_line)

    ctx = build_calibration_context(
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        template_path=template_path,
        run_command=args.run_command,
        parameter_keys=keys,
        target_df=load_targets_df(args),
        target_mode=ANN.target_mode,
        copy_files=[p for p in cell_settings.copy_files if p.is_file()],
        mock=args.mock,
        quiet=args.quiet,
        use_abm_seed=ANN.use_abm_seed,
        abm_base_seed=ANN.abm_base_seed,
        abm_seed_step=ANN.abm_seed_step,
        control_mode=True,
        mechanism=cell_settings.mechanism,
        cell_settings=cell_settings,
        work_root=Path(args.work_root or paths["work_root"]),
    )

    val = validate_with_abm(
        ctx,
        params,
        out_dir=out_dir,
        config=ValidationConfig(n_replicates=args.n_replicates or ANN.validation_replicates),
    )
    print(f"ABM validation error: {val['abm_validation_error']:.6g}")


if __name__ == "__main__":
    main()
