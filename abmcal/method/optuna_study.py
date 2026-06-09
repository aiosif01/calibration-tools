"""Optuna study creation with TPE sampler, median pruner, and SQLite storage."""
from __future__ import annotations

from pathlib import Path

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner


def create_optuna_study(
    *,
    study_name: str,
    storage: str | None = None,
    direction: str = "minimize",
    n_startup_trials: int = 30,
    sampler_seed: int = 1234,
    pruner_n_startup_trials: int = 30,
    pruner_n_warmup_steps: int = 1,
    load_if_exists: bool = True,
) -> optuna.Study:
    sampler = TPESampler(
        n_startup_trials=n_startup_trials,
        multivariate=True,
        group=True,
        constant_liar=True,
        seed=sampler_seed,
    )
    pruner = MedianPruner(
        n_startup_trials=pruner_n_startup_trials,
        n_warmup_steps=pruner_n_warmup_steps,
    )
    if storage:
        storage_path = storage.replace("sqlite:///", "")
        if storage_path and not storage_path.startswith(":"):
            Path(storage_path).parent.mkdir(parents=True, exist_ok=True)
    return optuna.create_study(
        study_name=study_name,
        direction=direction,
        sampler=sampler,
        pruner=pruner,
        storage=storage,
        load_if_exists=load_if_exists,
    )
