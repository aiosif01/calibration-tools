"""Differentiable inverse calibration on a frozen forward ANN surrogate."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from abmcal.method.ann_model import ForwardSurrogate
from abmcal.method.surrogate_dataset import SurrogateMeta, build_input_vector
from abmcal.method.train_forward_surrogate import TIME_WEIGHTS, weighted_mse


@dataclass(frozen=True)
class InverseConfig:
    n_restarts: int = 20
    max_steps: int = 5000
    learning_rate: float = 0.03
    prior_weight: float = 0.001
    seed: int = 42


@dataclass
class InverseResult:
    params: list[float]
    loss: float
    predicted_curve: list[float]
    restart_id: int
    n_steps: int


def load_surrogate_model(path: str | Path, meta: SurrogateMeta, device: torch.device | None = None) -> ForwardSurrogate:
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(path, map_location=device, weights_only=False)
    hidden = tuple(ckpt.get("meta", {}).get("hidden", (128, 128, 64)))
    model = ForwardSurrogate(meta.input_dim, meta.output_dim, hidden=hidden).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model


def _curve_tensor(y: Sequence[float], device: torch.device) -> torch.Tensor:
    return torch.tensor(list(y), dtype=torch.float32, device=device)


def inverse_calibrate(
    model: ForwardSurrogate,
    *,
    meta: SurrogateMeta,
    lb: Sequence[float],
    ub: Sequence[float],
    y_target: Sequence[float],
    cell_line: str,
    exposure_seconds: int,
    config: InverseConfig,
) -> InverseResult:
    device = next(model.parameters()).device
    lb_t = torch.tensor(list(lb), dtype=torch.float32, device=device)
    ub_t = torch.tensor(list(ub), dtype=torch.float32, device=device)
    y_t = _curve_tensor(y_target, device)

    best: InverseResult | None = None
    rng = np.random.default_rng(config.seed)

    for restart in range(config.n_restarts):
        z = torch.tensor(rng.normal(size=len(lb)), dtype=torch.float32, device=device, requires_grad=True)
        optimizer = torch.optim.Adam([z], lr=config.learning_rate)

        last_loss = float("inf")
        for step in range(config.max_steps):
            theta = lb_t + torch.sigmoid(z) * (ub_t - lb_t)
            x_np = build_input_vector(
                theta.detach().cpu().numpy(),
                cell_line=cell_line,
                exposure_seconds=exposure_seconds,
                meta=meta,
            )
            x = torch.tensor(x_np, dtype=torch.float32, device=device).unsqueeze(0)
            pred = model(x).squeeze(0)
            loss_curve = weighted_mse(pred.unsqueeze(0), y_t.unsqueeze(0))
            loss_prior = config.prior_weight * torch.mean((theta - (lb_t + ub_t) * 0.5) ** 2)
            loss = loss_curve + loss_prior

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            last_loss = float(loss.item())

        theta_final = (lb_t + torch.sigmoid(z) * (ub_t - lb_t)).detach()
        x_final = torch.tensor(
            build_input_vector(
                theta_final.cpu().numpy(),
                cell_line=cell_line,
                exposure_seconds=exposure_seconds,
                meta=meta,
            ),
            dtype=torch.float32,
            device=device,
        ).unsqueeze(0)
        with torch.no_grad():
            pred_final = model(x_final).squeeze(0).cpu().numpy()

        candidate = InverseResult(
            params=[float(v) for v in theta_final.cpu().numpy()],
            loss=last_loss,
            predicted_curve=[float(v) for v in pred_final],
            restart_id=restart,
            n_steps=config.max_steps,
        )
        if best is None or candidate.loss < best.loss:
            best = candidate

    assert best is not None
    return best


def inverse_calibrate_ensemble(
    model_paths: Sequence[str | Path],
    *,
    meta: SurrogateMeta,
    lb: Sequence[float],
    ub: Sequence[float],
    y_target: Sequence[float],
    cell_line: str,
    exposure_seconds: int,
    config: InverseConfig,
) -> tuple[InverseResult, pd.DataFrame]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    restart_rows = []
    best: InverseResult | None = None

    for model_path in model_paths:
        model = load_surrogate_model(model_path, meta, device=device)
        result = inverse_calibrate(
            model,
            meta=meta,
            lb=lb,
            ub=ub,
            y_target=y_target,
            cell_line=cell_line,
            exposure_seconds=exposure_seconds,
            config=config,
        )
        restart_rows.append({
            "model_path": str(model_path),
            "restart_id": result.restart_id,
            "loss": result.loss,
            **{f"param_{i}": v for i, v in enumerate(result.params)},
        })
        if best is None or result.loss < best.loss:
            best = result

    assert best is not None
    return best, pd.DataFrame(restart_rows)
