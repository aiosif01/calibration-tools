from __future__ import annotations

from pathlib import Path
from typing import Sequence
import numpy as np
import matplotlib
import matplotlib.pyplot as plt


class LiveCalibrationPlotter:
    def __init__(self, out_dir: str | Path, *, live: bool = True, title: str = "ABM4bio LM calibration"):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.live = bool(live)
        self.title = title
        self.history: list[dict] = []
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
        params_arr = np.asarray(params, dtype=float)
        row = {"eval": int(eval_id), "chi2": float(chi2)}
        if stage:
            row["stage"] = stage
        for i, p in enumerate(params_arr, start=1):
            row[f"p{i}"] = float(p)
        self.history.append(row)

        if self.fig is None or self.axes is None:
            self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 8))
            self.fig.suptitle(self.title)

        ax0, ax1, ax2, ax3 = self.axes.ravel()
        for ax in (ax0, ax1, ax2, ax3):
            ax.clear()

        h = self.history
        evals = [r["eval"] for r in h]
        for i in range(len(params_arr)):
            ax0.plot(evals, [r[f"p{i+1}"] for r in h], marker="o", label=f"p{i+1}")
        ax0.set_xlabel("Function evaluation")
        ax0.set_ylabel("Parameter value")
        ax0.set_title("Parameter convergence")
        ax0.legend()

        ax1.semilogy(evals, [max(r["chi2"], 1e-30) for r in h], marker="o")
        ax1.set_xlabel("Function evaluation")
        ax1.set_ylabel("Weighted SSE")
        ax1.set_title("Objective convergence")

        ax2.plot(t, y_data, "o", label="Experimental target")
        ax2.plot(t, y_fit, "-", label="Simulation")
        ax2.set_xlabel("Time post-treatment [h]")
        ax2.set_ylabel("Target output")
        ax2.set_title("Current fit")
        ax2.legend()

        ax3.axhline(0.0, linewidth=1)
        ax3.plot(t, residuals, "o-")
        ax3.set_xlabel("Time post-treatment [h]")
        ax3.set_ylabel("Weighted residual")
        ax3.set_title("Residuals")

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
        if not hist.empty:
            param_cols = [c for c in hist.columns if c.startswith("p")]
            fig, axes = plt.subplots(2, 1, figsize=(9, 8))
            for c in param_cols:
                axes[0].plot(hist["eval"], hist[c], marker="o", label=c)
            axes[0].set_ylabel("Parameter value")
            axes[0].set_title("Parameter convergence")
            axes[0].legend()
            axes[1].semilogy(hist["eval"], hist["chi2"].clip(lower=1e-30), marker="o")
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
