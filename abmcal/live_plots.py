from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .calibration_params import parameter_plot_color, parameter_plot_label


class LiveCalibrationPlotter:
    def __init__(
        self,
        out_dir: str | Path,
        *,
        live: bool = True,
        title: str = "ABM4bio LM calibration",
        parameter_names: Sequence[str] | None = None,
    ):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.live = bool(live)
        self.title = title
        self.parameter_names = list(parameter_names or [])
        self.history: list[dict] = []
        self.stage_history: list[dict] = []
        self._current_stage: str | None = None
        self._stage_eval = 0
        self.fig = None
        self.axes = None
        if self.live:
            try:
                plt.ion()
                self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 8))
                self.fig.suptitle(self.title)
            except Exception:
                self.live = False
                plt.ioff()
        if not self.live:
            matplotlib.use("Agg", force=True)

    def _begin_stage(self, stage: str | None) -> None:
        stage_key = stage or "fit"
        if stage_key == self._current_stage:
            return
        self._current_stage = stage_key
        self.stage_history = []
        self._stage_eval = 0

    def update(
        self,
        *,
        eval_id: int,
        params: Sequence[float],
        chi2: float,
        t: Sequence[float],
        y_data: Sequence[float],
        y_fit: Sequence[float],
        residuals: Sequence[float],
        stage: str | None = None,
    ) -> None:
        self._begin_stage(stage)
        self._stage_eval += 1
        params_arr = np.asarray(params, dtype=float)
        row = {
            "eval": int(eval_id),
            "stage_eval": int(self._stage_eval),
            "chi2": float(chi2),
            "stage": self._current_stage,
        }
        for i, p in enumerate(params_arr, start=1):
            row[f"p{i}"] = float(p)
        self.history.append(row)
        self.stage_history.append(row)

        if self.fig is None or self.axes is None:
            self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 8))
            self.fig.suptitle(self.title)

        ax0, ax1, ax2, ax3 = self.axes.ravel()
        for ax in (ax0, ax1, ax2, ax3):
            ax.clear()

        h = self.stage_history
        evals = [r["stage_eval"] for r in h]
        stage_title = self._current_stage or "current stage"
        for i in range(len(params_arr)):
            key = self.parameter_names[i] if i < len(self.parameter_names) else f"p{i+1}"
            label = parameter_plot_label(key) if i < len(self.parameter_names) else f"param {i+1}"
            color = parameter_plot_color(key, i) if i < len(self.parameter_names) else None
            ax0.plot(
                evals,
                [r[f"p{i+1}"] for r in h],
                marker="o",
                label=label,
                color=color,
            )
        ax0.set_xlabel("Evaluation (this stage)")
        ax0.set_ylabel("Parameter value")
        ax0.set_title(f"Parameter convergence — {stage_title}")
        ax0.legend(fontsize=8)

        ax1.semilogy(evals, [max(r["chi2"], 1e-30) for r in h], marker="o")
        ax1.set_xlabel("Evaluation (this stage)")
        ax1.set_ylabel("Weighted SSE")
        ax1.set_title(f"Objective convergence — {stage_title}")

        ax2.plot(t, y_data, "o", label="Experimental target")
        ax2.plot(t, y_fit, "-", label="Simulation")
        ax2.set_xlabel("Time post-treatment [h]")
        ax2.set_ylabel("Target output")
        ax2.set_title(f"Current fit — {stage_title}")
        ax2.legend()

        ax3.axhline(0.0, linewidth=1)
        ax3.plot(t, residuals, "o-")
        ax3.set_xlabel("Time post-treatment [h]")
        ax3.set_ylabel("Residual")
        ax3.set_title(f"Residuals — {stage_title}")

        self.fig.tight_layout()
        self.fig.savefig(self.out_dir / "live_calibration_latest.png", dpi=180)
        if self.live:
            try:
                self.fig.canvas.draw_idle()
                self.fig.canvas.flush_events()
                plt.pause(0.05)
            except Exception:
                pass

    def save_final_plots(
        self,
        t: Sequence[float],
        y_data: Sequence[float],
        y_fit: Sequence[float],
        sigma_y: Sequence[float] | None = None,
        prefix: str = "lm_python",
    ) -> None:
        import pandas as pd

        pd.DataFrame(self.history).to_csv(self.out_dir / f"{prefix}_trace.csv", index=False)

        hist = pd.DataFrame(self.history)
        if not hist.empty and "stage" in hist.columns:
            stages = [s for s in hist["stage"].dropna().unique().tolist() if s]
            if stages:
                n_stages = len(stages)
                fig, axes = plt.subplots(2, n_stages, figsize=(4.5 * n_stages, 8), squeeze=False)
                for col, stage_name in enumerate(stages):
                    stage_df = hist[hist["stage"] == stage_name]
                    if stage_df.empty:
                        continue
                    xvals = stage_df["stage_eval"] if "stage_eval" in stage_df else stage_df["eval"]
                    param_cols = [c for c in stage_df.columns if c.startswith("p")]
                    for j, c in enumerate(param_cols):
                        key = self.parameter_names[j] if j < len(self.parameter_names) else c
                        label = parameter_plot_label(key) if j < len(self.parameter_names) else c
                        color = parameter_plot_color(key, j) if j < len(self.parameter_names) else None
                        axes[0, col].plot(
                            xvals,
                            stage_df[c],
                            marker="o",
                            label=label,
                            color=color,
                        )
                    axes[0, col].set_title(stage_name)
                    axes[0, col].legend(fontsize=7)
                    axes[1, col].semilogy(xvals, stage_df["chi2"].clip(lower=1e-30), marker="o")
                    axes[1, col].set_xlabel("Evaluation (stage)")
                axes[0, 0].set_ylabel("Parameter value")
                axes[1, 0].set_ylabel("Weighted SSE")
                fig.suptitle("Convergence by calibration stage")
                fig.tight_layout()
                fig.savefig(self.out_dir / f"{prefix}A_convergence.pdf")
                fig.savefig(self.out_dir / f"{prefix}A_convergence.png", dpi=180)
                plt.close(fig)
        elif not hist.empty:
            param_cols = [c for c in hist.columns if c.startswith("p")]
            fig, axes = plt.subplots(2, 1, figsize=(9, 8))
            xvals = hist["stage_eval"] if "stage_eval" in hist.columns else hist["eval"]
            for j, c in enumerate(param_cols):
                key = self.parameter_names[j] if j < len(self.parameter_names) else c
                label = parameter_plot_label(key) if j < len(self.parameter_names) else c
                color = parameter_plot_color(key, j) if j < len(self.parameter_names) else None
                axes[0].plot(xvals, hist[c], marker="o", label=label, color=color)
            axes[0].set_ylabel("Parameter value")
            axes[0].set_title("Parameter convergence")
            axes[0].legend()
            axes[1].semilogy(xvals, hist["chi2"].clip(lower=1e-30), marker="o")
            axes[1].set_xlabel("Function evaluation")
            axes[1].set_ylabel("Weighted SSE")
            axes[1].set_title("Objective convergence")
            fig.tight_layout()
            fig.savefig(self.out_dir / f"{prefix}A_convergence.pdf")
            fig.savefig(self.out_dir / f"{prefix}A_convergence.png", dpi=180)
            plt.close(fig)

        t = np.asarray(t, dtype=float)
        y_data = np.asarray(y_data, dtype=float)
        y_fit = np.asarray(y_fit, dtype=float)
        if sigma_y is None:
            sigma_y = np.zeros_like(y_fit)
        sigma_y = np.asarray(sigma_y, dtype=float)

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.fill_between(t, y_fit - 2.58 * sigma_y, y_fit + 2.58 * sigma_y, alpha=0.20, label="99% c.i.")
        ax.fill_between(t, y_fit - 1.96 * sigma_y, y_fit + 1.96 * sigma_y, alpha=0.35, label="95% c.i.")
        ax.plot(t, y_data, "o", label="Experimental target")
        ax.plot(t, y_fit, "-", label="Simulation fit")
        ax.set_xlabel("Time post-treatment [h]")
        ax.set_ylabel("Model output")
        ax.set_title("Data, fit, and confidence interval")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.out_dir / f"{prefix}B_fit.pdf")
        fig.savefig(self.out_dir / f"{prefix}B_fit.png", dpi=180)
        plt.close(fig)

        residuals = y_data - y_fit
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.hist(residuals, bins=min(10, max(3, len(residuals))))
        ax.set_title("Histogram of residuals")
        ax.set_xlabel("Experimental target - simulation fit")
        ax.set_ylabel("Count")
        fig.tight_layout()
        fig.savefig(self.out_dir / f"{prefix}C_residual_histogram.pdf")
        fig.savefig(self.out_dir / f"{prefix}C_residual_histogram.png", dpi=180)
        plt.close(fig)
