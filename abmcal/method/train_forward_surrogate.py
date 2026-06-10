"""Train forward ANN surrogate(s) on ABM-generated datasets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing import Sequence

import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from abmcal.method.ann_model import ForwardSurrogate, select_hidden_sizes
from abmcal.method.surrogate_dataset import (
    CELL_LINE_ORDER,
    SurrogateMeta,
    dataframe_to_arrays,
    train_val_test_split,
)

TIME_WEIGHTS = torch.tensor([0.2, 1.0, 1.0, 1.5], dtype=torch.float32)


@dataclass(frozen=True)
class TrainConfig:
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 64
    max_epochs: int = 2000
    patience: int = 100
    val_fraction: float = 0.2
    test_fraction: float = 0.1
    seed: int = 100


def weighted_mse(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    w = TIME_WEIGHTS.to(device=pred.device, dtype=pred.dtype)
    if pred.shape[-1] != w.shape[0]:
        w = torch.ones(pred.shape[-1], device=pred.device, dtype=pred.dtype)
    return ((pred - target) ** 2 * w).mean()


def train_forward_surrogate(
    df: pd.DataFrame,
    meta: SurrogateMeta,
    *,
    out_path: str | Path,
    config: TrainConfig,
    history_path: str | Path | None = None,
) -> dict:
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)

    x, y = dataframe_to_arrays(df, meta)
    split = train_val_test_split(
        len(x),
        val_fraction=config.val_fraction,
        test_fraction=config.test_fraction,
        seed=config.seed,
    )
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if history_path:
        Path(history_path).parent.mkdir(parents=True, exist_ok=True)
    split_path = Path(out_path).parent / "ann_train_val_test_split.json"
    split_path.write_text(json.dumps(split, indent=2))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    hidden = select_hidden_sizes(len(x))
    model = ForwardSurrogate(meta.input_dim, meta.output_dim, hidden=hidden).to(device)

    def to_loader(idxs: list[int], shuffle: bool) -> DataLoader:
        if not idxs:
            return None
        xt = torch.tensor(x[idxs], dtype=torch.float32)
        yt = torch.tensor(y[idxs], dtype=torch.float32)
        return DataLoader(TensorDataset(xt, yt), batch_size=min(config.batch_size, len(idxs)), shuffle=shuffle)

    train_loader = to_loader(split["train"], True)
    val_loader = to_loader(split["val"], False)
    test_loader = to_loader(split["test"], False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    best_val = float("inf")
    best_state = None
    stale = 0
    history: list[dict] = []

    for epoch in range(config.max_epochs):
        model.train()
        train_loss = 0.0
        n_batches = 0
        if train_loader is not None:
            for xb, yb in train_loader:
                xb, yb = xb.to(device), yb.to(device)
                optimizer.zero_grad()
                pred = model(xb)
                loss = weighted_mse(pred, yb)
                loss.backward()
                optimizer.step()
                train_loss += float(loss.item())
                n_batches += 1
        train_loss = train_loss / max(1, n_batches)

        model.eval()
        val_loss = float("nan")
        with torch.no_grad():
            if val_loader is not None:
                vals = []
                for xb, yb in val_loader:
                    xb, yb = xb.to(device), yb.to(device)
                    vals.append(float(weighted_mse(model(xb), yb).item()))
                val_loss = float(np.mean(vals)) if vals else train_loss
            else:
                val_loss = train_loss

        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})

        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= config.patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    test_loss = float("nan")
    model.eval()
    with torch.no_grad():
        if test_loader is not None:
            tests = []
            for xb, yb in test_loader:
                xb, yb = xb.to(device), yb.to(device)
                tests.append(float(weighted_mse(model(xb), yb).item()))
            test_loss = float(np.mean(tests)) if tests else best_val

    torch.save({
        "state_dict": model.state_dict(),
        "meta": {
            "parameter_keys": list(meta.parameter_keys),
            "cell_lines": list(meta.cell_lines),
            "input_dim": meta.input_dim,
            "output_dim": meta.output_dim,
            "hidden": hidden,
            "exposure_scale": meta.exposure_scale,
        },
        "best_val_loss": best_val,
        "test_loss": test_loss,
        "seed": config.seed,
    }, out_path)

    if history_path:
        pd.DataFrame(history).to_csv(history_path, index=False)

    return {
        "best_val_loss": best_val,
        "test_loss": test_loss,
        "epochs": len(history),
        "model_path": str(out_path),
    }


def build_meta_from_parameter_keys(parameter_keys: Sequence[str]) -> SurrogateMeta:
    keys = tuple(parameter_keys)
    cell_lines = CELL_LINE_ORDER
    input_dim = len(keys) + len(cell_lines) + 1
    return SurrogateMeta(parameter_keys=keys, cell_lines=cell_lines, input_dim=input_dim)
