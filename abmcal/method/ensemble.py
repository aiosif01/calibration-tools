"""Train and use an ensemble of forward ANN surrogates for uncertainty estimation."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import torch

from abmcal.method.inverse_calibration import load_surrogate_model
from abmcal.method.surrogate_dataset import SurrogateMeta, build_input_vector
from abmcal.method.train_forward_surrogate import TrainConfig, train_forward_surrogate


DEFAULT_ENSEMBLE_SEEDS: tuple[int, ...] = (100, 200, 300, 400, 500)


def train_ensemble(
    df: pd.DataFrame,
    meta: SurrogateMeta,
    *,
    models_dir: str | Path,
    ensemble_seeds: Sequence[int] = DEFAULT_ENSEMBLE_SEEDS,
    train_config: TrainConfig | None = None,
) -> list[Path]:
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    meta.save(models_dir / "surrogate_meta.json")
    paths: list[Path] = []
    for seed in ensemble_seeds:
        cfg = train_config or TrainConfig(seed=int(seed))
        cfg = TrainConfig(
            learning_rate=cfg.learning_rate,
            weight_decay=cfg.weight_decay,
            batch_size=cfg.batch_size,
            max_epochs=cfg.max_epochs,
            patience=cfg.patience,
            val_fraction=cfg.val_fraction,
            test_fraction=cfg.test_fraction,
            seed=int(seed),
        )
        out_path = models_dir / f"surrogate_seed{seed}.pt"
        train_forward_surrogate(
            df,
            meta,
            out_path=out_path,
            config=cfg,
            history_path=models_dir / f"training_loss_seed{seed}.csv",
        )
        paths.append(out_path)
    return paths


def ensemble_predict(
    model_paths: Sequence[str | Path],
    *,
    params: Sequence[float],
    cell_line: str,
    exposure_seconds: int,
    meta: SurrogateMeta,
) -> tuple[np.ndarray, np.ndarray]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    x_np = build_input_vector(params, cell_line=cell_line, exposure_seconds=exposure_seconds, meta=meta)
    x = torch.tensor(x_np, dtype=torch.float32, device=device).unsqueeze(0)
    preds = []
    for path in model_paths:
        model = load_surrogate_model(path, meta, device=device)
        with torch.no_grad():
            preds.append(model(x).squeeze(0).cpu().numpy())
    stack = np.vstack(preds)
    return stack.mean(axis=0), stack.std(axis=0)
