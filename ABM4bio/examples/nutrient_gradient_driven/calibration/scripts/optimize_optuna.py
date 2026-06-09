"""
optimize_optuna.py
==================
Optuna-based calibration loop for ABM4bio NIH3T3 control spheroid model.

Usage
-----
    # From the calibration/ directory:
    python scripts/optimize_optuna.py --config configs/calibration_config.yaml

    # Resume an existing study (with SQLite storage):
    python scripts/optimize_optuna.py \
        --config configs/calibration_config.yaml \
        --storage sqlite:///results/optuna_runs/study.db

    # Override number of trials:
    python scripts/optimize_optuna.py \
        --config configs/calibration_config.yaml \
        --n_trials 50

Pipeline per trial
------------------
    1. Optuna suggests parameter values.
    2. Constraint check (necrosis < quiescence < proliferation).
    3. run_abm4bio.run_simulation → generates CSV + runs ABM4bio.
    4. export_simulation_stats.compute_metrics_for_run → simulation_metrics.csv.
    5. compute_objective.compute_objective → scalar loss.
    6. Optuna stores (params, loss) and updates TPE model.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    print("ERROR: optuna is not installed.  Run:  pip install optuna")
    sys.exit(1)

# Ensure scripts/ is on path
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from load_experimental_data import load_config, load_experimental_data
from run_abm4bio import run_simulation
from export_simulation_stats import compute_metrics_for_run
from compute_objective import (
    compute_objective,
    FALLBACK_LOSS,
    PENALTY_VALUE,
    _check_constraints,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("optimize_optuna")


# ---------------------------------------------------------------------------
# Objective callable for Optuna
# ---------------------------------------------------------------------------

class CalibrationObjective:
    """
    Callable objective passed to ``study.optimize()``.
    Captures all external state via constructor.
    """

    def __init__(
        self,
        config: dict,
        bounds_config: dict,
        config_dir: Path,
        exp_df,            # pd.DataFrame
        condition: str,
        seeds: list[int],
        results_dir: Path,
    ) -> None:
        self.config      = config
        self.bounds_cfg  = bounds_config
        self.config_dir  = config_dir
        self.exp_df      = exp_df
        self.condition   = condition
        self.seeds       = seeds
        self.results_dir = results_dir
        self._trial_counter = 0

    def __call__(self, trial: "optuna.Trial") -> float:
        self._trial_counter += 1
        trial_id  = f"trial_{trial.number:04d}"
        t_start   = time.time()

        # ---- Suggest parameters -------------------------------------------
        params_dict = _suggest_parameters(trial, self.bounds_cfg)

        # ---- Constraint penalty (prune early) -----------------------------
        penalty = _check_constraints(params_dict, self.config)
        if penalty > 0.0:
            trial.set_user_attr("status", "constraint_violated")
            log.info(
                f"Trial {trial.number:4d} PRUNED  constraint penalty={penalty:.3f}"
            )
            raise optuna.exceptions.TrialPruned()

        # ---- Run simulation + objective on each calibration seed ----------
        tps = self.config.get("experimental_time_points_h", [0, 12, 24, 36, 48])
        seed_losses = {}
        seed_run_dirs = {}
        for seed in self.seeds:
            run_id = f"{trial_id}_{self.condition}_s{seed}"
            try:
                run_dir = run_simulation(
                    params_dict=params_dict,
                    condition=self.condition,
                    seed=seed,
                    run_id=run_id,
                    config=self.config,
                    config_dir=self.config_dir,
                    bounds_config=self.bounds_cfg,
                )
            except Exception:
                tb = traceback.format_exc()
                log.warning(f"Trial {trial.number:4d} run FAILED (seed={seed}):\n{tb}")
                trial.set_user_attr("status", "run_failed")
                return FALLBACK_LOSS

            try:
                sim_df = compute_metrics_for_run(
                    run_dir=run_dir,
                    condition=self.condition,
                    seed=seed,
                    time_points_h=tps,
                )
            except Exception:
                tb = traceback.format_exc()
                log.warning(f"Trial {trial.number:4d} metrics FAILED (seed={seed}):\n{tb}")
                trial.set_user_attr("status", "metrics_failed")
                return FALLBACK_LOSS

            loss_seed = compute_objective(
                sim_metrics_df=sim_df,
                exp_df=self.exp_df,
                config=self.config,
                condition=self.condition,
                params_dict=params_dict,
            )
            seed_losses[str(seed)] = float(loss_seed)
            seed_run_dirs[str(seed)] = str(run_dir)

        loss_values = list(seed_losses.values())
        loss = float(sum(loss_values) / max(1, len(loss_values)))
        loss_std = float(np.std(loss_values)) if len(loss_values) > 1 else 0.0

        elapsed = time.time() - t_start
        trial.set_user_attr("status", "ok")
        trial.set_user_attr("elapsed_s", round(elapsed, 1))
        trial.set_user_attr("run_dirs", json.dumps(seed_run_dirs))
        trial.set_user_attr("seed_losses", json.dumps(seed_losses))
        trial.set_user_attr("seed_loss_std", round(loss_std, 6))

        # Per-phase cycle time summary (new params) or legacy cct
        if "phase_G1_h" in params_dict:
            _g1 = params_dict["phase_G1_h"]
            _sy = params_dict.get("phase_S_h", float("nan"))
            _g2 = params_dict.get("phase_G2_h", float("nan"))
            cycle_str = f"G1={_g1:.1f}h S={_sy:.1f}h G2={_g2:.1f}h"
        else:
            cycle_str = f"cct={params_dict.get('cell_cycle_time_h', float('nan')):.1f}h"
        log.info(
            f"Trial {trial.number:4d}  loss={loss:.5f}  "
            f"{cycle_str}  "
            f"vmax={params_dict.get('nutrient_vmax', params_dict.get('nutrient_uptake_rate', float('nan'))):.4f}  "
            f"prl={params_dict.get('proliferation_threshold', float('nan')):.3f}  "
            f"nec={params_dict.get('necrosis_threshold', float('nan')):.3f}  "
            f"qui={params_dict.get('quiescence_threshold', float('nan')):.3f}  "
            f"seeds={len(self.seeds)}  std={loss_std:.4f}  t={elapsed:.0f}s"
        )
        return loss


def _suggest_parameters(trial: "optuna.Trial", bounds_cfg: dict) -> dict:
    """Map bounds_config to Optuna suggestions."""
    params = bounds_cfg.get("parameters", {})
    result: dict[str, float] = {}

    # Sample constrained thresholds in sorted order:
    # necrosis_threshold < quiescence_threshold < proliferation_threshold
    if all(k in params for k in (
        "necrosis_threshold", "quiescence_threshold", "proliferation_threshold"
    )):
        n_spec = params["necrosis_threshold"]
        q_spec = params["quiescence_threshold"]
        p_spec = params["proliferation_threshold"]
        eps = 1e-6

        nec = trial.suggest_float(
            "necrosis_threshold", float(n_spec["min"]), float(n_spec["max"])
        )

        q_min = max(float(q_spec["min"]), nec + eps)
        q_max = float(q_spec["max"])
        qui = trial.suggest_float("quiescence_threshold", q_min, q_max)

        p_min = max(float(p_spec["min"]), qui + eps)
        p_max = float(p_spec["max"])
        prol = trial.suggest_float("proliferation_threshold", p_min, p_max)

        result["necrosis_threshold"] = nec
        result["quiescence_threshold"] = qui
        result["proliferation_threshold"] = prol

    for name, spec in params.items():
        if name in result:
            continue
        lo    = float(spec["min"])
        hi    = float(spec["max"])
        scale = spec.get("scale", "linear")
        if scale == "log":
            result[name] = trial.suggest_float(name, lo, hi, log=True)
        else:
            result[name] = trial.suggest_float(name, lo, hi)
    return result


def _get_condition_cfg(config: dict, condition: str) -> dict:
    for cond in config.get("conditions", []):
        if cond.get("name") == condition:
            return cond
    raise ValueError(f"Condition '{condition}' not found in config.")


def _apply_transform_for_template(value: float, transform: str, time_step: float):
    if transform == "identity":
        return value
    if transform == "neg":
        return -abs(value)
    if transform == "round_div_dt":
        return max(1, int(round(value / time_step)))
    if transform == "neg_round_div_dt":
        return -max(1, int(round(value / time_step)))

    # Mechanism-11 phase dwell transforms (G1:Sy:G2 = 80:70:40)
    total_steps = max(3, int(round(value / time_step)))
    if transform == "phase_dwell_G1":
        return max(1, int(round(total_steps * 80 / 190)))
    if transform == "phase_dwell_Sy":
        return max(1, int(round(total_steps * 70 / 190)))
    if transform == "phase_dwell_G2":
        return max(1, int(round(total_steps * 40 / 190)))

    raise ValueError(f"Unknown transform: '{transform}'")


def _build_csv_overrides_from_params(params_dict: dict, bounds_cfg: dict, time_step: float) -> dict:
    overrides: dict[str, tuple[str, float]] = {}
    for param_name, param_val in params_dict.items():
        spec = bounds_cfg.get("parameters", {}).get(param_name)
        if not spec:
            continue
        for csv_key_spec in spec.get("csv_keys", []):
            key = csv_key_spec["key"]
            ptype = csv_key_spec.get("type", "float")
            transform = csv_key_spec.get("transform", "identity")
            val = _apply_transform_for_template(float(param_val), transform, time_step)
            overrides[key] = (ptype, val)
    return overrides


def _update_template_from_best(
    config: dict,
    bounds_cfg: dict,
    config_dir: Path,
    condition: str,
    best_params: dict,
) -> None:
    cond_cfg = _get_condition_cfg(config, condition)
    template_rel = cond_cfg.get("template_csv")
    if not template_rel:
        log.warning("No template_csv configured for condition '%s'; skipping template update.", condition)
        return

    template_path = (config_dir.parent / template_rel).resolve()
    if not template_path.exists():
        log.warning("Template CSV not found at %s; skipping template update.", template_path)
        return

    time_step = float(config.get("time_step_h", bounds_cfg.get("time_step_h", 0.1)))
    overrides = _build_csv_overrides_from_params(best_params, bounds_cfg, time_step)
    if not overrides:
        log.info("No CSV overrides found from best parameters; template unchanged.")
        return

    lines = template_path.read_text().splitlines(keepends=True)
    updated_lines = []
    n_changes = 0

    for line in lines:
        stripped = line.rstrip("\n\r")
        parts = [p.strip() for p in stripped.split(",")]
        if len(parts) == 3:
            key = parts[0]
            if key in overrides:
                ptype, val = overrides[key]
                new_val = str(int(round(val))) if ptype == "int" else f"{float(val):.6g}"
                if parts[2] != new_val:
                    parts[2] = new_val
                    line = ",".join(parts) + "\n"
                    n_changes += 1
        updated_lines.append(line)

    if n_changes == 0:
        log.info("Template already matches best parameters: %s", template_path)
        return

    backup_path = template_path.with_suffix(template_path.suffix + ".bak")
    backup_path.write_text("".join(lines))
    template_path.write_text("".join(updated_lines))

    log.info(
        "Template updated from best parameters (%d fields): %s (backup: %s)",
        n_changes,
        template_path,
        backup_path,
    )


# ---------------------------------------------------------------------------
# Study setup & run
# ---------------------------------------------------------------------------

def build_study(
    config: dict,
    storage: Optional[str] = None,
) -> "optuna.Study":
    sampler_name = config.get("sampler", "TPESampler")
    pruner_name  = config.get("pruner",  "MedianPruner")

    sampler = getattr(optuna.samplers, sampler_name)()
    pruner  = getattr(optuna.pruners,  pruner_name)()

    study_name = config.get("study_name", "NIH3T3_ctrl_calib")
    db         = storage or config.get("optuna_db") or None

    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
        storage=db,
        load_if_exists=True,
    )
    return study


def run_optimisation(
    config_path: str | Path,
    bounds_path: str | Path,
    n_trials: Optional[int] = None,
    n_jobs: int = 1,
    condition: str = "ISO10",
    seed: int = 1234,
    calibration_seeds: Optional[list[int]] = None,
    storage: Optional[str] = None,
) -> "optuna.Study":
    config_path = Path(config_path)
    bounds_path = Path(bounds_path)
    config_dir  = config_path.parent

    config      = load_config(config_path)
    bounds_cfg  = load_config(bounds_path)

    # Load experimental data
    excel_path = config_path.parent.parent / config["excel_file"]
    log.info(f"Loading experimental data from {excel_path}")
    exp_df = load_experimental_data(excel_path, config, condition)
    log.info(f"  Loaded {len(exp_df)} experimental rows for condition '{condition}'")

    results_dir = config_path.parent.parent / config["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)

    study = build_study(config, storage=storage)

    n_trials_run = n_trials if n_trials is not None else config.get("n_trials", 100)
    n_jobs_run   = n_jobs   if n_jobs   > 0            else config.get("n_jobs",  1)

    objective = CalibrationObjective(
        config=config,
        bounds_config=bounds_cfg,
        config_dir=config_dir,
        exp_df=exp_df,
        condition=condition,
        seeds=calibration_seeds or [seed],
        results_dir=results_dir,
    )

    log.info(
        f"Starting Optuna optimisation: {n_trials_run} trials, "
        f"condition={condition}, seed={seed}"
    )
    log.info(f"Study '{study.study_name}'  storage: {storage or 'in-memory'}")

    study.optimize(
        objective,
        n_trials=n_trials_run,
        n_jobs=n_jobs_run,
        catch=(Exception,),
    )

    best_dir = config_path.parent.parent / config.get("best_runs_dir", "results/best_runs")
    best_dir.mkdir(parents=True, exist_ok=True)

    # ---- Save full trials summary -----------------------------------------
    import pandas as pd
    df = study.trials_dataframe()
    df.to_csv(best_dir / f"trials_summary_{condition}.csv", index=False)

    completed_trials = [t for t in study.trials if t.value is not None]
    if not completed_trials:
        log.warning(
            "No completed trials yet (all trials pruned/failed). "
            "Trials summary was saved; rerun with more trials."
        )
        return study

    # ---- Report best result -----------------------------------------------
    best = study.best_trial
    log.info(
        f"\nBest trial #{best.number}  loss={best.value:.5f}\n"
        + json.dumps(best.params, indent=2)
    )

    # ---- Save best params --------------------------------------------------
    best_params_path = best_dir / f"best_params_{condition}.json"
    with open(best_params_path, "w") as fh:
        json.dump({
            "trial_number": best.number,
            "loss":         best.value,
            "params":       best.params,
            "condition":    condition,
            "calibration_seeds": calibration_seeds or [seed],
        }, fh, indent=2)
    log.info(f"Best parameters saved to {best_params_path}")

    if bool(config.get("auto_update_template_from_best", True)):
        try:
            _update_template_from_best(
                config=config,
                bounds_cfg=bounds_cfg,
                config_dir=config_dir,
                condition=condition,
                best_params=best.params,
            )
        except Exception:
            tb = traceback.format_exc()
            log.warning("Failed to auto-update template from best parameters:\n%s", tb)

    return study


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optuna calibration for ABM4bio NIH3T3 control spheroid."
    )
    parser.add_argument(
        "--config", default="configs/calibration_config.yaml",
        help="Path to calibration_config.yaml"
    )
    parser.add_argument(
        "--bounds", default="configs/parameter_bounds.yaml",
        help="Path to parameter_bounds.yaml"
    )
    parser.add_argument("--n_trials", type=int, default=None)
    parser.add_argument("--n_jobs",   type=int, default=1)
    parser.add_argument("--condition", default="ISO10")
    parser.add_argument("--seed",     type=int, default=1234)
    parser.add_argument(
        "--calibration_seeds",
        default=None,
        help="Optional comma-separated list of seeds used inside each trial objective, e.g. 1234,5678,9012",
    )
    parser.add_argument(
        "--storage", default=None,
        help="Optuna storage URL, e.g. sqlite:///results/optuna_runs/study.db"
    )
    args = parser.parse_args()

    if args.calibration_seeds:
        cal_seeds = [int(x.strip()) for x in args.calibration_seeds.split(",") if x.strip()]
    else:
        cfg = load_config(args.config)
        cal_seeds = cfg.get("calibration_seeds", [args.seed])

    run_optimisation(
        config_path=args.config,
        bounds_path=args.bounds,
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        condition=args.condition,
        seed=args.seed,
        calibration_seeds=cal_seeds,
        storage=args.storage,
    )


if __name__ == "__main__":
    main()
