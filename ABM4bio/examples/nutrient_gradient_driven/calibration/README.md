# ABM4bio NIH3T3 Control Calibration

Reproducible 2-D simulation-to-experiment calibration pipeline for
ABM4bio using Optuna.

**Biological scope:** NIH3T3 non-tumoral control spheroids only (ISO 10% and
DeltaC / gradient conditions). No CAPP, no GRNs.

---

## Prerequisites

```bash
# Python environment
pip install optuna pandas numpy openpyxl pyyaml scikit-image matplotlib

# ABM4bio must be built (from repo root)
cd /path/to/ABM4bio
make fresh -j$(nproc)
```

---

## Directory layout

```
calibration/
  configs/
    calibration_config.yaml           # master config
    parameter_bounds.yaml             # parameter search space
    input_NIH3T3_ISO10_template.csv   # ABM4bio input CSV template (ISO10)
    input_NIH3T3_DeltaC_template.csv  # ABM4bio input CSV template (DeltaC) [to add]
  data/
    NIH3T3_control_condition.xlsx     # experimental workbook
  scripts/
    load_experimental_data.py         # Excel → tidy DataFrame
    export_simulation_stats.py        # cells_t*.csv → simulation_metrics.csv
    run_abm4bio.py                    # generate CSV + run ABM4bio
    compute_objective.py              # weighted RMSE objective
    optimize_optuna.py                # Optuna calibration loop
    plot_results.py                   # all diagnostic plots
  results/
    optuna_runs/                      # one sub-dir per trial
    best_runs/                        # copies / links of best trials
    plots/                            # output figures
```

---

## Run the calibration

```bash
cd calibration

# ISO10 condition, 200 trials, in-memory study
python scripts/optimize_optuna.py \
    --config configs/calibration_config.yaml \
    --condition ISO10 \
    --seed 1234 \
    --n_trials 200

# DeltaC condition
python scripts/optimize_optuna.py \
    --config configs/calibration_config.yaml \
    --condition DeltaC \
    --seed 1234 \
    --n_trials 200

# Persist to SQLite (allows resuming / parallel workers)
python scripts/optimize_optuna.py \
    --config configs/calibration_config.yaml \
    --storage sqlite:///results/optuna_runs/study.db \
    --condition ISO10 \
    --n_trials 200

# Note: after optimization, the condition template CSV is auto-updated
# with the best calibrated parameters (backup written as *.bak).
```

Disable this behavior in config if needed:

```yaml
auto_update_template_from_best: false
```

---

## Reproduce final plots

```bash
cd calibration

# Exp vs sim for the best run
python scripts/plot_results.py \
    --run results/best_runs/<run_id> \
    --config configs/calibration_config.yaml \
    --condition ISO10

# Full suite (convergence + importance) from a persistent study
python scripts/plot_results.py \
    --config configs/calibration_config.yaml \
    --storage sqlite:///results/optuna_runs/study.db \
    --condition ISO10
```

Figures are saved in `results/plots/`.

---

## Key files produced per trial

| File | Description |
|---|---|
| `results/optuna_runs/<run_id>/input.csv` | Generated ABM4bio input |
| `results/optuna_runs/<run_id>/cells_t*.csv` | Raw per-cell snapshots |
| `results/optuna_runs/<run_id>/simulation_metrics.csv` | 2-D morphology metrics |
| `results/optuna_runs/<run_id>/metadata.json` | Run metadata & parameters |
| `results/optuna_runs/<run_id>/abm4bio.log` | ABM4bio stdout |
| `results/best_runs/best_params_<cond>.json` | Best parameter set |
| `results/best_runs/trials_summary_<cond>.csv` | All trial results |

---

## Calibrated parameters

| Parameter | Meaning | CSV key |
|---|---|---|
| `initial_necrotic_cells` | Initial necrotic-cell seed count at t=0 | `necrotic_cell/initial_population` |
| `cell_cycle_time_h` | Total cycle dwell (G1+S+G2), in hours | `normoxic_cell/phase_dwell/G1,Sy,G2` |
| `nutrient_uptake_rate` | Per-cell Gluc consumption | `normoxic_cell/Gluc/secretion/net_balance` (−value) |
| `cell_grow_probability` | Growth activation probability | `normoxic_cell/can_grow/probability` |
| `cell_divide_probability` | Division probability gate | `normoxic_cell/can_divide/probability` |
| `necrosis_transform_probability` | Necrotic transformation probability | `normoxic_cell/can_transform/probability` |
| `proliferation_threshold` | Gluc threshold for growth/division | `normoxic_cell/can_grow/Gluc/threshold` |
| `necrosis_threshold` | Gluc below which necrosis starts | `normoxic_cell/can_transform/Gluc/threshold` (−value) |
| `quiescence_threshold` | Gluc below which cells become quiescent | `normoxic_cell/quiescence/nutrient_threshold` |

Constraints enforced: `necrosis_threshold < quiescence_threshold < proliferation_threshold`

---

## Hard Paper Parameters: ABM Mapping

Use literature values as fixed priors, then calibrate only uncertain biology.

### Nature 2024 values (provided)

| Paper parameter | Reported value | Unit |
|---|---:|---|
| `Vmax` | `1e-2` | `mol m^-3 s^-1` |
| `Km` | `8` | `mol m^-3` |
| `C0_high` | `6.94` | `mol m^-3` |
| `C0_low` | `0.694` | `mol m^-3` |
| `D_glucose_water` | `9.25e-6` | `cm^2 s^-1` |
| `D_glucose_collagen` | `7.63e-6` | `cm^2 s^-1` |
| `D_glucose_spheroid` | `1.24e-6` | `cm^2 s^-1` |

### Unit conversions you should apply

1. Diffusion conversion:
`D[um^2/h] = D[cm^2/s] * 3.6e11`

2. Normalized concentration used by ABM templates:
`C_norm = C / C_ref`, with `C_ref = C0_high = 6.94 mol m^-3`

3. Michaelis constant in normalized units:
`Km_norm = Km / C_ref = 8 / 6.94 = 1.153`

### Where these enter ABM4bio config/templates

| ABM field | File | How to set |
|---|---|---|
| `Gluc/diffusion_coefficient` | `configs/input_NIH3T3_ISO10_template.csv` | Set as fixed value from converted diffusion scale used by your solver |
| `Gluc/initial_value/min,max` | `configs/input_NIH3T3_ISO10_template.csv` | `1.0` for high condition, `0.1` for low (normalized from 0.694/6.94) |
| `normoxic_cell/Gluc/secretion/net_balance` | generated from calibration | Keep calibrated unless you build explicit MM uptake in C++ |
| `normoxic_cell/can_grow/Gluc/threshold` | generated from calibration | Should remain in normalized concentration units |
| `normoxic_cell/quiescence/nutrient_threshold` | generated from calibration | Normalized threshold |
| `normoxic_cell/can_transform/Gluc/threshold` | generated from calibration | Negative normalized threshold by ABM convention |

### Important modeling note

Current ABM calibration uses an effective per-step net-balance uptake, not explicit Michaelis-Menten uptake.
If you want direct use of `Vmax` and `Km`, add MM kinetics in the biochemical update layer first, then calibrate fewer effective nutrient parameters.

---

## C++ exporter (added to ABM4bio.h)

The file `src/ABM4bio.h` has been extended with:

- `save_cells_csv()` — writes `cells_t<HHH>.csv` per experimental snapshot.
- Hook in `simulate()` — triggered when `cell_export/enabled = true` in the input CSV.

Activate in any ABM4bio input CSV by adding:

```
cell_export/enabled,bool,true
cell_export/times_h,string,0.0 12.0 24.0 36.0 48.0
```

---

## Pixel calibration

`pixel_scale_um_per_px = 1.21079857960497 µm/px`

All exported simulation metrics are in µm and µm². Areas in the
experimental workbook are converted to µm² using this scale.

---

## Extending to DeltaC condition

1. Copy `configs/input_NIH3T3_ISO10_template.csv` →
   `configs/input_NIH3T3_DeltaC_template.csv`.
2. Add a linear gradient initialisation for Gluc (see `input_inVitro_chemotaxis.csv`
   in `examples/nutrient_gradient_driven/` for reference).
3. Ensure `conditions[1].template_csv` in `calibration_config.yaml` points to
   the new template.
4. Run the optimiser with `--condition DeltaC`.
