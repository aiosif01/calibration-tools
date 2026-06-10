#!/usr/bin/env python3
"""Train forward ANN surrogate ensemble on ABM-generated dataset."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from abmcal.calibration_config import ANN, control_out_dir, get_cell_line_settings  # noqa: E402
from abmcal.method.ensemble import DEFAULT_ENSEMBLE_SEEDS, train_ensemble  # noqa: E402
from abmcal.method.surrogate_dataset import SurrogateMeta  # noqa: E402
from abmcal.method.train_forward_surrogate import TrainConfig, build_meta_from_parameter_keys  # noqa: E402
from scripts._ann_common import default_ann_paths, load_parameter_space  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Train ANN forward surrogate ensemble.")
    ap.add_argument("--cell-line", default="EGI1")
    ap.add_argument("--case-label", default="control")
    ap.add_argument("--dataset", default=None, help="Path to ann_training_dataset.csv")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--parameter-space", default=None)
    ap.add_argument("--ensemble-size", type=int, default=None)
    ap.add_argument("--max-epochs", type=int, default=None)
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    paths = default_ann_paths(args.cell_line, args.case_label)
    out_dir = Path(args.out_dir or control_out_dir(args.cell_line))
    dataset_path = Path(args.dataset or out_dir / "datasets" / "ann_training_dataset.csv")
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Training dataset not found: {dataset_path}. Run generate_ann_dataset.py first.")

    cell_settings = get_cell_line_settings(args.cell_line)
    parameter_space = load_parameter_space(args, cell_settings)
    meta = build_meta_from_parameter_keys(parameter_space.names)

    df = pd.read_csv(dataset_path)
    df = df[df["run_status"].isin(["ok", "mean"])].copy()
    if df.empty:
        raise RuntimeError("No successful ABM runs in training dataset.")

    ensemble_seeds = DEFAULT_ENSEMBLE_SEEDS
    if args.mock:
        ensemble_seeds = (100,)
    elif args.ensemble_size is not None:
        ensemble_seeds = tuple(range(100, 100 + args.ensemble_size * 100, 100))

    train_config = TrainConfig(
        max_epochs=200 if args.mock else (args.max_epochs or ANN.max_epochs),
        patience=30 if args.mock else ANN.patience,
        batch_size=ANN.batch_size,
        learning_rate=ANN.learning_rate,
        weight_decay=ANN.weight_decay,
    )

    models_dir = out_dir / "models"
    model_paths = train_ensemble(
        df,
        meta,
        models_dir=models_dir,
        ensemble_seeds=ensemble_seeds,
        train_config=train_config,
    )
    print(f"Trained {len(model_paths)} surrogate models in {models_dir}")


if __name__ == "__main__":
    main()
