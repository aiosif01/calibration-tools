#!/usr/bin/env python3
"""Generate ABM4bio simulation dataset for ANN surrogate training."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._ann_common import (  # noqa: E402
    build_calibration_context,
    default_ann_paths,
    load_parameter_space,
    load_targets_df,
)
from abmcal.calibration_config import ANN, control_out_dir, get_cell_line_settings, resolve_control_template  # noqa: E402
from abmcal.method.dataset_generator import DatasetRunConfig, generate_ann_dataset  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate ANN training dataset from ABM4bio runs.")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--exposure-seconds", type=int, default=0)
    ap.add_argument("--case-label", default="control")
    ap.add_argument("--xlsx", default=str(ROOT / "data" / "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"))
    ap.add_argument("--targets-csv", default=None)
    ap.add_argument("--template", default=None)
    ap.add_argument("--parameter-space", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--work-root", default=None)
    ap.add_argument("--run-command", default="make")
    ap.add_argument("--copy-file", action="append", default=[])
    ap.add_argument("--n-samples", type=int, default=None)
    ap.add_argument("--seeds-per-sample", type=int, default=None)
    ap.add_argument("--sampling", default=None, choices=["lhs", "random"])
    ap.add_argument("--dataset-seed", type=int, default=None)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--use-abm-seed", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--abm-base-seed", type=int, default=None)
    ap.add_argument("--abm-seed-step", type=int, default=None)
    args = ap.parse_args()

    cell_settings = get_cell_line_settings(args.cell_line)
    paths = default_ann_paths(args.cell_line, args.case_label)
    out_dir = Path(args.out_dir or control_out_dir(args.cell_line))
    work_root = Path(args.work_root or paths["work_root"])
    template_path = Path(args.template or resolve_control_template(args.cell_line))
    parameter_space = load_parameter_space(args, cell_settings)
    target_df = load_targets_df(args)

    ctx = build_calibration_context(
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        template_path=template_path,
        run_command=args.run_command,
        parameter_keys=list(parameter_space.names),
        target_df=target_df,
        target_mode=ANN.target_mode,
        copy_files=[Path(x) for x in args.copy_file if x] or [p for p in cell_settings.copy_files if p.is_file()],
        mock=args.mock,
        quiet=args.quiet,
        use_abm_seed=ANN.use_abm_seed if args.use_abm_seed is None else args.use_abm_seed,
        abm_base_seed=args.abm_base_seed or ANN.abm_base_seed,
        abm_seed_step=args.abm_seed_step or ANN.abm_seed_step,
        control_mode=args.exposure_seconds == 0,
        mechanism=cell_settings.mechanism,
        cell_settings=cell_settings,
        work_root=work_root,
    )

    run_config = DatasetRunConfig(
        n_samples=args.n_samples or (ANN.debug_n_samples if args.mock else ANN.n_samples),
        seeds_per_sample=args.seeds_per_sample or (1 if args.mock else ANN.seeds_per_sample),
        sampling=args.sampling or ANN.sampling,
        seed=args.dataset_seed or ANN.dataset_seed,
        normalize_sim_to_t0=ANN.normalize_sim_to_t0,
        time_points=ANN.time_points,
    )

    if not args.quiet:
        print(
            f"Generating ANN dataset: {args.cell_line} "
            f"({run_config.n_samples} samples × {run_config.seeds_per_sample} seeds, {run_config.sampling})",
            flush=True,
        )

    df = generate_ann_dataset(ctx, parameter_space, out_dir=out_dir, run_config=run_config, verbose=not args.quiet)
    print(f"Dataset saved under {out_dir / 'datasets'} ({len(df)} rows)")


if __name__ == "__main__":
    main()
