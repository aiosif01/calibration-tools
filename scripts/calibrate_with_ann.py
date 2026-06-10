#!/usr/bin/env python3
"""Inverse calibrate parameters using trained ANN surrogate(s)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from abmcal.calibration_config import ANN, control_out_dir, get_cell_line_settings, resolve_control_template  # noqa: E402
from abmcal.calibration_workflow import load_targets  # noqa: E402
from abmcal.method.ann_reporting import plot_inverse_fit_curve  # noqa: E402
from abmcal.method.ensemble import DEFAULT_ENSEMBLE_SEEDS, ensemble_predict  # noqa: E402
from abmcal.method.inverse_calibration import InverseConfig, inverse_calibrate_ensemble  # noqa: E402
from abmcal.method.surrogate_dataset import SurrogateMeta  # noqa: E402
from abmcal.method.train_forward_surrogate import build_meta_from_parameter_keys  # noqa: E402
from abmcal.method.validate_ann_solution import ValidationConfig, validate_with_abm  # noqa: E402
from scripts._ann_common import (  # noqa: E402
    build_calibration_context,
    default_ann_paths,
    load_parameter_space,
    load_targets_df,
    load_yaml_config,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Calibrate parameters with frozen ANN surrogate.")
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
    ap.add_argument("--models-dir", default=None)
    ap.add_argument("--n-restarts", type=int, default=None)
    ap.add_argument("--inverse-steps", type=int, default=None)
    ap.add_argument("--skip-abm-validation", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    cell_settings = get_cell_line_settings(args.cell_line)
    paths = default_ann_paths(args.cell_line, args.case_label)
    out_dir = Path(args.out_dir or control_out_dir(args.cell_line))
    models_dir = Path(args.models_dir or out_dir / "models")
    meta_path = models_dir / "surrogate_meta.json"
    if meta_path.is_file():
        meta = SurrogateMeta.load(meta_path)
    else:
        parameter_space = load_parameter_space(args, cell_settings)
        meta = build_meta_from_parameter_keys(parameter_space.names)

    model_paths = sorted(models_dir.glob("surrogate_seed*.pt"))
    if not model_paths:
        raise FileNotFoundError(f"No surrogate models in {models_dir}. Run train_ann_surrogate.py first.")

    target_df = load_targets_df(args)
    objective_cfg = load_yaml_config(ROOT / "configs" / "objective_control.yaml")
    target_mode = objective_cfg.get("target_mode", ANN.target_mode)
    template_path = Path(args.template or resolve_control_template(args.cell_line))

    ctx = build_calibration_context(
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        template_path=template_path,
        run_command=args.run_command,
        parameter_keys=list(meta.parameter_keys),
        target_df=target_df,
        target_mode=target_mode,
        copy_files=[p for p in cell_settings.copy_files if p.is_file()],
        mock=args.mock,
        quiet=args.quiet,
        use_abm_seed=ANN.use_abm_seed,
        abm_base_seed=ANN.abm_base_seed,
        abm_seed_step=ANN.abm_seed_step,
        control_mode=args.exposure_seconds == 0,
        mechanism=cell_settings.mechanism,
        cell_settings=cell_settings,
        work_root=Path(args.work_root or paths["work_root"]),
    )

    t, y_target, sigma = load_targets(ctx, ANN.time_points)
    lb = list(cell_settings.lb)
    ub = list(cell_settings.ub)

    inverse_config = InverseConfig(
        n_restarts=3 if args.mock else (args.n_restarts or ANN.inverse_restarts),
        max_steps=500 if args.mock else (args.inverse_steps or ANN.inverse_steps),
        learning_rate=ANN.inverse_lr,
    )

    best, restarts_df = inverse_calibrate_ensemble(
        model_paths,
        meta=meta,
        lb=lb,
        ub=ub,
        y_target=y_target,
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        config=inverse_config,
    )

    cal_dir = out_dir / "calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "parameter_name": meta.parameter_keys,
        "fitted_value": best.params,
    }).to_csv(cal_dir / "ann_inverse_best_parameters.csv", index=False)
    pd.DataFrame({
        "time_h": t,
        "y_target": y_target,
        "y_ann": best.predicted_curve,
        "residual": y_target - best.predicted_curve,
    }).to_csv(cal_dir / "ann_inverse_curve.csv", index=False)
    restarts_df.to_csv(cal_dir / "ann_inverse_restarts.csv", index=False)

    mean_pred, std_pred = ensemble_predict(
        model_paths,
        params=best.params,
        cell_line=args.cell_line,
        exposure_seconds=args.exposure_seconds,
        meta=meta,
    )
    pd.DataFrame({
        "time_h": t,
        "y_mean": mean_pred,
        "y_std": std_pred,
    }).to_csv(cal_dir / "ann_surrogate_uncertainty.csv", index=False)

    fig_dir = out_dir / "figures"
    plot_inverse_fit_curve(
        fig_dir / "inverse_fit_curve.png",
        time_h=t,
        y_target=y_target,
        y_ann=best.predicted_curve,
        sigma=sigma,
        title=f"{args.cell_line} ANN inverse calibration",
    )

    print(f"Best inverse loss: {best.loss:.6g}")
    for key, val in zip(meta.parameter_keys, best.params):
        print(f"  {key}: {val:.8g}")

    if not args.skip_abm_validation:
        val = validate_with_abm(
            ctx,
            best.params,
            out_dir=out_dir,
            config=ValidationConfig(
                n_replicates=ANN.validation_replicates,
                normalize_sim_to_t0=ANN.normalize_sim_to_t0,
                log_space=ANN.log_space,
            ),
        )
        from abmcal.method.ann_reporting import plot_abm_validation_band

        plot_abm_validation_band(
            fig_dir / "final_abm_validation_band.png",
            time_h=t,
            y_target=y_target,
            replicate_curves=val["replicate_curves"],
            title=f"{args.cell_line} ABM validation of ANN fit",
        )
        plot_inverse_fit_curve(
            fig_dir / "ann_vs_abm_validation.png",
            time_h=t,
            y_target=y_target,
            y_ann=best.predicted_curve,
            y_abm=val["mean_curve"],
            title=f"{args.cell_line} ANN vs ABM validation",
        )
        print(f"ABM validation error: {val['abm_validation_error']:.6g}")


if __name__ == "__main__":
    main()
