"""
export_simulation_stats.py
==========================
Reads raw per-cell CSV files produced by ABM4bio (cells_t*.csv) and computes
2D morphological metrics matching the experimental data from the workbook.

Inputs
------
  <run_dir>/cells_t000.csv
  <run_dir>/cells_t012.csv
  ...
  Each file has columns:
    time_h, cell_id, x_um, y_um, radius_um, phase, phenotype,
    is_alive, is_necrotic, is_quiescent, is_proliferative

Outputs
-------
  <run_dir>/simulation_metrics.csv  (one row per time point)

Column definitions
------------------
  condition, seed, time_h,
  shell_area_um2, core_area_um2,
  shell_A_over_A0, core_A_over_A0,
  shell_eq_radius_um, core_eq_radius_um,
  viable_rim_um,
  shell_major_axis_um, shell_minor_axis_um, shell_aspect_ratio, shell_orientation_deg,
  core_major_axis_um,  core_minor_axis_um,  core_aspect_ratio,  core_orientation_deg,
  n_total, n_alive, n_necrotic, n_quiescent, n_proliferative

Usage (standalone)
------------------
  python scripts/export_simulation_stats.py \
      --run_dir results/optuna_runs/run_0001 \
      --condition ISO10 \
      --seed 1234
"""
from __future__ import annotations

import argparse
import math
import sys
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt as _distance_transform_edt

# Optional: scikit-image for accurate regionprops
try:
    from skimage.draw import disk as _sk_disk
    from skimage.filters import gaussian as _sk_gaussian, threshold_otsu as _sk_threshold_otsu
    from skimage.measure import label as _sk_label, regionprops as _sk_regionprops
    from skimage.morphology import (
        binary_closing as _sk_binary_closing,
        convex_hull_image as _sk_convex_hull_image,
        disk as _sk_morph_disk,
        remove_small_objects as _sk_remove_small_objects,
    )
    _HAS_SKIMAGE = True
except ImportError:
    _HAS_SKIMAGE = False

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

PIXEL_SIZE_FOR_RASTER_UM = 1.0      # 1 pixel = 1 µm when we build the mask
SHELL_CLOSING_RADIUS_UM = 8.0       # bridges small gaps between neighboring cells
CORE_MIN_FRACTION = 0.05            # sanity floor for segmented core fraction
CORE_MAX_FRACTION = 0.85            # sanity cap for segmented core fraction
CORE_DISTANCE_QUANTILE = 0.68       # fallback central-core quantile from shell EDT


def compute_metrics_from_cells_csv(
    csv_path: str | Path,
    time_h: float,
    condition: str,
    seed: int,
    pixel_um: float = PIXEL_SIZE_FOR_RASTER_UM,
) -> dict:
    """
    Read one cells_t*.csv and return a dict of 2D morphological metrics.

    Shell mask  : outer envelope of all living cells (image-style segmentation)
    Core  mask  : central dense core segmented from the shell footprint
                 (image-like, not necrotic-only state labels).
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)

    n_total        = len(df)
    n_alive        = int(df["is_alive"].sum())
    n_necrotic     = int(df["is_necrotic"].sum())
    n_quiescent    = int(df["is_quiescent"].sum())
    n_proliferative = int(df["is_proliferative"].sum())

    # Segmentation base: use all exported cells to match image-derived morphology,
    # where footprint is determined by visible mass rather than only viable states.
    shell_df = df.copy()

    # Remove spatial outliers before morphology segmentation.
    # Outlier cells (e.g. a mis-placed necrotic seed) inflate the convex hull
    # to the entire domain size, destroying all area metrics.
    # Rule: exclude cells whose distance from the cluster median exceeds
    # 3× the 95th-percentile radial distance (with a 50 µm floor).
    if len(shell_df) >= 5:
        cx = float(shell_df["x_um"].median())
        cy = float(shell_df["y_um"].median())
        r_from_center = np.sqrt(
            (shell_df["x_um"].values - cx) ** 2 +
            (shell_df["y_um"].values - cy) ** 2
        )
        r95 = float(np.percentile(r_from_center, 95))
        outlier_r = max(50.0, r95 * 3.0)
        n_before = len(shell_df)
        shell_df = shell_df[r_from_center <= outlier_r].copy()
        if len(shell_df) < n_before:
            import warnings as _warnings
            _warnings.warn(
                f"Removed {n_before - len(shell_df)} outlier cells "
                f"(r > {outlier_r:.1f} µm) from shell/core segmentation."
            )

    shell_props, core_props = _segment_shell_and_core(shell_df, pixel_um)

    shell_area = shell_props["area_um2"]
    core_area  = core_props["area_um2"]

    return {
        "condition":           condition,
        "seed":                seed,
        "time_h":              time_h,
        # Areas
        "shell_area_um2":      shell_area,
        "core_area_um2":       core_area,
        # Normalized (A/A0 computed later by compute_metrics_for_run)
        "shell_A_over_A0":     None,
        "core_A_over_A0":      None,
        # Equivalent radii
        "shell_eq_radius_um":  shell_props["eq_radius_um"],
        "core_eq_radius_um":   core_props["eq_radius_um"],
        "viable_rim_um":       max(0.0, shell_props["eq_radius_um"] - core_props["eq_radius_um"]),
        # Shape descriptors
        "shell_major_axis_um": shell_props["major_axis_um"],
        "shell_minor_axis_um": shell_props["minor_axis_um"],
        "shell_aspect_ratio":  shell_props["aspect_ratio"],
        "shell_orientation_deg": shell_props["orientation_deg"],
        "core_major_axis_um":  core_props["major_axis_um"],
        "core_minor_axis_um":  core_props["minor_axis_um"],
        "core_aspect_ratio":   core_props["aspect_ratio"],
        "core_orientation_deg": core_props["orientation_deg"],
        # Cell counts
        "n_total":             n_total,
        "n_alive":             n_alive,
        "n_necrotic":          n_necrotic,
        "n_quiescent":         n_quiescent,
        "n_proliferative":     n_proliferative,
    }


def compute_metrics_for_run(
    run_dir: str | Path,
    condition: str,
    seed: int,
    time_points_h: list[float] | None = None,
    pixel_um: float = PIXEL_SIZE_FOR_RASTER_UM,
) -> pd.DataFrame:
    """
    Process all cells_t*.csv in *run_dir*, compute metrics, add A/A0 columns,
    and return a DataFrame.  Writes simulation_metrics.csv to *run_dir*.
    """
    run_dir = Path(run_dir)
    if time_points_h is None:
        time_points_h = [0, 12, 24, 36, 48]

    rows = []
    for tp in time_points_h:
        fname = run_dir / f"cells_t{int(round(tp)):03d}.csv"
        if not fname.exists():
            warnings.warn(f"Missing cell CSV: {fname}")
            continue
        row = compute_metrics_from_cells_csv(fname, tp, condition, seed, pixel_um)
        rows.append(row)

    if not rows:
        raise FileNotFoundError(f"No cells_t*.csv found in {run_dir}")

    df = pd.DataFrame(rows)

    # Compute A/A0 relative to t=0
    t0_shell = df.loc[df["time_h"] == 0.0, "shell_area_um2"].values
    t0_core  = df.loc[df["time_h"] == 0.0, "core_area_um2"].values

    shell_a0 = float(t0_shell[0]) if len(t0_shell) > 0 and t0_shell[0] > 0 else float("nan")
    core_a0  = float(t0_core[0])  if len(t0_core)  > 0 and t0_core[0]  > 0 else float("nan")

    df["shell_A_over_A0"] = df["shell_area_um2"] / shell_a0 if shell_a0 > 0 else float("nan")
    # Core A/A0 uses its own t=0 when available; fallback to shell A0 only if needed.
    core_ref = core_a0 if core_a0 > 0 else shell_a0
    df["core_A_over_A0"]  = df["core_area_um2"]  / core_ref if core_ref > 0 else float("nan")

    out_path = run_dir / "simulation_metrics.csv"
    df.to_csv(out_path, index=False)
    return df


# ---------------------------------------------------------------------------
# 2-D region-property computation
# ---------------------------------------------------------------------------

def _segment_shell_and_core(df_alive: pd.DataFrame, pixel_um: float) -> tuple[dict, dict]:
    """
    Segment shell/core using an image-analysis style pipeline.

    Shell: binary closing + convex envelope of all alive-cell disks.
    Core : central dense region from smoothed occupancy map (Otsu threshold),
           with a robust distance-transform fallback.
    """
    if len(df_alive) == 0:
        z = _zero_props()
        return z, z

    shell_mask, density_map, _, _ = _build_maps(df_alive, pixel_um)
    shell_mask = _postprocess_shell_mask(shell_mask, pixel_um)
    shell_props = _props_from_mask(shell_mask, pixel_um)

    core_mask = _segment_core_mask(shell_mask, density_map, pixel_um)
    core_props = _props_from_mask(core_mask, pixel_um) if np.any(core_mask) else _zero_props()

    return shell_props, core_props


def _build_maps(
    df: pd.DataFrame,
    pixel_um: float,
    padding_px: int = 6,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Rasterize cell disks into both binary occupancy and density maps."""
    if len(df) == 0:
        z = np.zeros((1, 1), dtype=np.uint8)
        return z, z.astype(float), 0.0, 0.0

    xs = df["x_um"].values.astype(float)
    ys = df["y_um"].values.astype(float)
    rs = df["radius_um"].values.astype(float)

    x_min = (xs - rs).min() - padding_px * pixel_um
    x_max = (xs + rs).max() + padding_px * pixel_um
    y_min = (ys - rs).min() - padding_px * pixel_um
    y_max = (ys + rs).max() + padding_px * pixel_um

    nx = max(1, int(math.ceil((x_max - x_min) / pixel_um)) + 1)
    ny = max(1, int(math.ceil((y_max - y_min) / pixel_um)) + 1)

    binary = np.zeros((ny, nx), dtype=np.uint8)
    density = np.zeros((ny, nx), dtype=np.float32)

    for x, y, r in zip(xs, ys, rs):
        cx_px = (x - x_min) / pixel_um
        cy_px = (y - y_min) / pixel_um
        r_px = r / pixel_um

        if _HAS_SKIMAGE:
            rr, cc = _sk_disk((cy_px, cx_px), r_px, shape=binary.shape)
            binary[rr, cc] = 1
            density[rr, cc] += 1.0
        else:
            r_int = int(math.ceil(r_px)) + 1
            for dr in range(-r_int, r_int + 1):
                for dc in range(-r_int, r_int + 1):
                    if dr * dr + dc * dc <= r_px * r_px:
                        row = int(round(cy_px)) + dr
                        col = int(round(cx_px)) + dc
                        if 0 <= row < ny and 0 <= col < nx:
                            binary[row, col] = 1
                            density[row, col] += 1.0

    return binary, density, x_min, y_min


def _postprocess_shell_mask(mask: np.ndarray, pixel_um: float) -> np.ndarray:
    """Build a robust shell footprint from sparse/disconnected occupancy."""
    shell = mask.astype(bool)
    if not np.any(shell):
        return shell

    if _HAS_SKIMAGE:
        close_r = max(1, int(round(SHELL_CLOSING_RADIUS_UM / pixel_um)))
        shell = _sk_binary_closing(shell, _sk_morph_disk(close_r))
        shell = _sk_convex_hull_image(shell)
        shell = _keep_largest_component(shell)
    return shell.astype(bool)


def _segment_core_mask(shell_mask: np.ndarray, density_map: np.ndarray, pixel_um: float) -> np.ndarray:
    """Segment core from shell using density threshold with EDT fallback."""
    if not np.any(shell_mask):
        return np.zeros_like(shell_mask, dtype=bool)

    core = np.zeros_like(shell_mask, dtype=bool)

    if _HAS_SKIMAGE:
        sigma_px = max(1.0, 5.0 / pixel_um)
        smooth = _sk_gaussian(density_map, sigma=sigma_px, preserve_range=True)
        vals = smooth[shell_mask]
        if vals.size > 16 and float(np.nanmax(vals) - np.nanmin(vals)) > 1e-6:
            thr = _sk_threshold_otsu(vals)
            core = (smooth >= thr) & shell_mask
            min_sz = max(16, int(0.01 * float(shell_mask.sum())))
            core = _sk_remove_small_objects(core, min_size=min_sz)
            core = _keep_largest_component(core)

    frac = float(core.sum()) / max(1.0, float(shell_mask.sum()))
    if frac < CORE_MIN_FRACTION or frac > CORE_MAX_FRACTION:
        # Fallback: central region from distance-to-boundary quantile.
        dist = _distance_transform_edt(shell_mask)
        dvals = dist[shell_mask]
        if dvals.size > 0:
            q = np.quantile(dvals, CORE_DISTANCE_QUANTILE)
            core = (dist >= q) & shell_mask
            if _HAS_SKIMAGE:
                core = _keep_largest_component(core)

    return core.astype(bool)


def _keep_largest_component(mask: np.ndarray) -> np.ndarray:
    if not _HAS_SKIMAGE or not np.any(mask):
        return mask.astype(bool)
    lbl = _sk_label(mask.astype(np.uint8))
    props = _sk_regionprops(lbl)
    if not props:
        return np.zeros_like(mask, dtype=bool)
    largest_label = max(props, key=lambda p: p.area).label
    return lbl == largest_label


def _props_from_mask(mask: np.ndarray, pixel_um: float) -> dict:
    """Compute area/shape descriptors directly from a binary mask."""
    if not np.any(mask):
        return _zero_props()

    if _HAS_SKIMAGE:
        lbl = _sk_label(mask.astype(np.uint8))
        props_list = _sk_regionprops(lbl)
        if not props_list:
            return _zero_props()
        props = max(props_list, key=lambda p: p.area)
        area_px2 = float(props.area)
        area_um2 = area_px2 * pixel_um ** 2
        eq_r_um = math.sqrt(area_um2 / math.pi)
        maj_axis_um = props.major_axis_length * pixel_um
        min_axis_um = props.minor_axis_length * pixel_um
        aspect = maj_axis_um / min_axis_um if min_axis_um > 0 else 1.0
        orient_deg = math.degrees(props.orientation)
        cy_px, cx_px = props.centroid
        return {
            "area_um2": area_um2,
            "eq_radius_um": eq_r_um,
            "major_axis_um": maj_axis_um,
            "minor_axis_um": min_axis_um,
            "aspect_ratio": aspect,
            "orientation_deg": orient_deg,
            "centroid_x_um": cx_px * pixel_um,
            "centroid_y_um": cy_px * pixel_um,
        }

    # Fallback without skimage
    ys, xs = np.where(mask)
    area_um2 = float(mask.sum()) * pixel_um ** 2
    eq_r_um = math.sqrt(area_um2 / math.pi) if area_um2 > 0 else 0.0
    cx = float(xs.mean()) * pixel_um
    cy = float(ys.mean()) * pixel_um
    return {
        "area_um2": area_um2,
        "eq_radius_um": eq_r_um,
        "major_axis_um": 2.0 * eq_r_um,
        "minor_axis_um": 2.0 * eq_r_um,
        "aspect_ratio": 1.0,
        "orientation_deg": 0.0,
        "centroid_x_um": cx,
        "centroid_y_um": cy,
    }

def _region_props_from_cells(
    df: pd.DataFrame,
    pixel_um: float = PIXEL_SIZE_FOR_RASTER_UM,
) -> dict:
    """
    Given a DataFrame with columns [x_um, y_um, radius_um], compute 2D
    region properties using skimage if available, otherwise fall back to
    a pure-numpy implementation.
    """
    if len(df) == 0:
        return _zero_props()

    if _HAS_SKIMAGE:
        return _props_skimage(df, pixel_um)
    else:
        return _props_fallback(df, pixel_um)


def _build_binary_mask(
    df: pd.DataFrame,
    pixel_um: float,
    padding_px: int = 5,
) -> tuple[np.ndarray, float, float]:
    """
    Rasterize circles onto a binary mask.
    Returns (mask, origin_x_um, origin_y_um).
    """
    if len(df) == 0:
        return np.zeros((1, 1), dtype=np.uint8), 0.0, 0.0

    xs = df["x_um"].values.astype(float)
    ys = df["y_um"].values.astype(float)
    rs = df["radius_um"].values.astype(float)

    x_min = (xs - rs).min() - padding_px * pixel_um
    x_max = (xs + rs).max() + padding_px * pixel_um
    y_min = (ys - rs).min() - padding_px * pixel_um
    y_max = (ys + rs).max() + padding_px * pixel_um

    nx = max(1, int(math.ceil((x_max - x_min) / pixel_um)) + 1)
    ny = max(1, int(math.ceil((y_max - y_min) / pixel_um)) + 1)

    mask = np.zeros((ny, nx), dtype=np.uint8)

    for x, y, r in zip(xs, ys, rs):
        # Convert centre and radius to pixel coords
        cx_px = (x - x_min) / pixel_um
        cy_px = (y - y_min) / pixel_um
        r_px  = r / pixel_um

        if _HAS_SKIMAGE:
            rr, cc = _sk_disk((cy_px, cx_px), r_px, shape=mask.shape)
            mask[rr, cc] = 1
        else:
            # Fallback: bounding box rasterisation
            r_int = int(math.ceil(r_px)) + 1
            for dr in range(-r_int, r_int + 1):
                for dc in range(-r_int, r_int + 1):
                    if dr * dr + dc * dc <= r_px * r_px:
                        row = int(round(cy_px)) + dr
                        col = int(round(cx_px)) + dc
                        if 0 <= row < ny and 0 <= col < nx:
                            mask[row, col] = 1

    return mask, x_min, y_min


def _props_skimage(df: pd.DataFrame, pixel_um: float) -> dict:
    """Use scikit-image regionprops for accurate shape analysis."""
    mask, _, _ = _build_binary_mask(df, pixel_um)
    lbl = _sk_label(mask)
    props_list = _sk_regionprops(lbl)
    if not props_list:
        return _zero_props()

    # Take the largest connected component
    props = max(props_list, key=lambda p: p.area)

    area_px2   = float(props.area)
    area_um2   = area_px2 * pixel_um ** 2
    eq_r_um    = math.sqrt(area_um2 / math.pi)

    maj_axis_um = props.major_axis_length * pixel_um
    min_axis_um = props.minor_axis_length * pixel_um
    aspect      = maj_axis_um / min_axis_um if min_axis_um > 0 else 1.0
    orient_deg  = math.degrees(props.orientation)

    centroid_y_px, centroid_x_px = props.centroid

    return {
        "area_um2":        area_um2,
        "eq_radius_um":    eq_r_um,
        "major_axis_um":   maj_axis_um,
        "minor_axis_um":   min_axis_um,
        "aspect_ratio":    aspect,
        "orientation_deg": orient_deg,
        "centroid_x_um":   centroid_x_px * pixel_um,
        "centroid_y_um":   centroid_y_px * pixel_um,
    }


def _props_fallback(df: pd.DataFrame, pixel_um: float) -> dict:
    """
    Pure-numpy fallback when scikit-image is unavailable.
    Computes area from mask, centroid from coordinates, and major/minor
    axes from covariance eigenvalues.
    """
    mask, ox, oy = _build_binary_mask(df, pixel_um)

    # Area
    area_px2 = float(mask.sum())
    area_um2 = area_px2 * pixel_um ** 2
    eq_r_um  = math.sqrt(area_um2 / math.pi) if area_um2 > 0 else 0.0

    # Centroid and covariance from individual cell positions (fast, approximate)
    xs = df["x_um"].values.astype(float)
    ys = df["y_um"].values.astype(float)
    cx, cy = float(xs.mean()), float(ys.mean())

    if len(xs) > 1:
        dx = xs - cx
        dy = ys - cy
        cov = np.array([[np.dot(dx, dx), np.dot(dx, dy)],
                        [np.dot(dx, dy), np.dot(dy, dy)]]) / (len(xs) - 1)
        eigvals = np.linalg.eigvalsh(cov)
        eigvals = np.sort(np.abs(eigvals))[::-1]  # descending
        # Scale eigenvalues to axis lengths
        maj_axis_um = 4.0 * math.sqrt(max(float(eigvals[0]), 0.0))
        min_axis_um = 4.0 * math.sqrt(max(float(eigvals[1]), 0.0))
    else:
        maj_axis_um = eq_r_um * 2
        min_axis_um = eq_r_um * 2

    aspect     = maj_axis_um / min_axis_um if min_axis_um > 0 else 1.0
    orient_deg = 0.0  # not computable without skimage

    return {
        "area_um2":        area_um2,
        "eq_radius_um":    eq_r_um,
        "major_axis_um":   maj_axis_um,
        "minor_axis_um":   min_axis_um,
        "aspect_ratio":    aspect,
        "orientation_deg": orient_deg,
        "centroid_x_um":   cx,
        "centroid_y_um":   cy,
    }


def _zero_props() -> dict:
    return {
        "area_um2":        0.0,
        "eq_radius_um":    0.0,
        "major_axis_um":   0.0,
        "minor_axis_um":   0.0,
        "aspect_ratio":    1.0,
        "orientation_deg": 0.0,
        "centroid_x_um":   0.0,
        "centroid_y_um":   0.0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute 2D spheroid metrics from ABM4bio cell CSV files."
    )
    parser.add_argument("--run_dir", required=True, help="Path to simulation run dir")
    parser.add_argument("--condition", default="ISO10", help="Condition label")
    parser.add_argument("--seed", type=int, default=0, help="Random seed used")
    parser.add_argument(
        "--time_points", default="0,12,24,36,48",
        help="Comma-separated experimental time points (h)"
    )
    parser.add_argument(
        "--pixel_um", type=float, default=PIXEL_SIZE_FOR_RASTER_UM,
        help="Raster pixel size in µm (default 1.0)"
    )
    args = parser.parse_args()

    tps = [float(t) for t in args.time_points.split(",")]

    print(f"Processing run: {args.run_dir}")
    print(f"  skimage available: {_HAS_SKIMAGE}")

    df = compute_metrics_for_run(
        run_dir=args.run_dir,
        condition=args.condition,
        seed=args.seed,
        time_points_h=tps,
        pixel_um=args.pixel_um,
    )

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 140)
    print(df[["time_h", "shell_area_um2", "core_area_um2",
              "shell_A_over_A0", "core_A_over_A0", "viable_rim_um",
              "n_total", "n_alive", "n_necrotic"]].to_string(index=False))

    out = Path(args.run_dir) / "simulation_metrics.csv"
    print(f"\nMetrics written to: {out}")


if __name__ == "__main__":
    main()
