"""PyTorch forward surrogate: parameters + cell line + exposure → viability curve."""
from __future__ import annotations

import torch
import torch.nn as nn


class ForwardSurrogate(nn.Module):
    def __init__(self, input_dim: int, output_dim: int = 4, *, hidden: tuple[int, ...] = (128, 128, 64)):
        super().__init__()
        layers: list[nn.Module] = []
        prev = input_dim
        for i, width in enumerate(hidden):
            layers.extend([
                nn.Linear(prev, width),
                nn.GELU(),
                nn.LayerNorm(width),
            ])
            if i < len(hidden) - 1:
                layers.append(nn.Dropout(0.05))
            prev = width
        layers.append(nn.Linear(prev, output_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def select_hidden_sizes(n_samples: int) -> tuple[int, ...]:
    if n_samples < 1000:
        return (64, 64, 32)
    if n_samples > 10_000:
        return (256, 256, 128, 64)
    return (128, 128, 64)
