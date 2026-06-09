# ABM4bio CAP calibration — Optuna black-box workflow

This branch calibrates ABM4bio parameters using **Optuna only** (TPE sampler, median pruner, SQLite storage). Each trial runs ABM4bio directly and compares simulation output to the same experimental targets used across all methodological branches.

**Method purity:** This branch does not use `scipy.optimize.least_squares`, TRF/LM, `dual_annealing`, or ANN surrogates. Use the `least-squares` branch for local LM fitting and the `ANN` branch for surrogate-assisted calibration.

**This repo is calibration-only.** It does not bundle or build ABM4bio. Simulation binaries and BioDynaMo live in a separate checkout (default: `~/Desktop/ABM4bio`).

## What Optuna does here

For each trial:

1. Sample a parameter vector from the YAML parameter space.
2. Render `input.csv` from the cell-line template.
3. Run ABM4bio with stochastic replicates (one seed per replicate).
4. Extract viability / `N_cells` at 0, 24, 48, 72 h.
5. Compute a scalar objective: weighted curve error + biological penalty.
6. Report intermediate scores for median pruning across replicates.

## Folder structure

```text
calibration-tools/
  abmcal/
    core/                         shared objective functions
    method/                       Optuna engine, objective, reporting
  configs/                        parameter spaces + objective YAML
  scripts/                        run_optuna_control.py, run_optuna_treatment.py
  executables/<CELL_LINE>/        optuna_control.sh, optuna_treat_*.sh
  templates/                      ABM input CSV templates
  data/                           experimental targets
  outputs/optuna/                 studies, best parameters, figures
```

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Mock smoke test (20 trials, no ABM binary required)
MOCK_MODE=1 N_TRIALS=20 ./executables/EGI1/optuna_control.sh

# Real control calibration
./executables/EGI1/optuna_control.sh
```

## Configuration

| File | Purpose |
|------|---------|
| `config/calibration_settings.py` | Trials, replicates, seeds, study paths |
| `configs/parameter_space_control.yaml` | Control proliferation bounds (mechanism 11) |
| `configs/parameter_space_treatment.yaml` | Treatment / CAP / RONS bounds |
| `configs/objective_control.yaml` | Target mode, log-space residuals |
| `configs/runtime_local.yaml` | Local debug vs development budgets |

Override at runtime:

```bash
N_TRIALS=500 REPLICATES=3 ./executables/EGI1/optuna_control.sh
```

## Python entry points

```bash
python scripts/run_optuna_control.py --cell-line EGI1 --n-trials 200 --mock
python scripts/run_optuna_treatment.py --cell-line EGI1 --exposure-seconds 30 --mock
python scripts/export_optuna_best.py --storage sqlite:///outputs/optuna/studies/EGI1_control.db --study-name EGI1_control --parameter-keys "..." --out-dir outputs/optuna/EGI1/control
python scripts/plot_optuna_study.py --storage sqlite:///... --study-name EGI1_control --out-dir outputs/optuna/EGI1/control
```

## Outputs

```text
outputs/optuna/<CELL_LINE>/control/
  calibrated_parameters.csv
  fit_result.json
  fit_curve.csv
  figures/
    optimization_history.png
    parameter_importance.png
    best_fit_curve.png
  trials/trial_history.csv
  reports/optuna_summary.md
  calibration_01_N_cells_vs_time.png
  calibration_02_exp_vs_sim.png
  calibration_03_fitted_parameters.png

outputs/optuna/studies/
  EGI1_control.db
```

## External ABM4bio setup

1. Build ABM4bio in the external repo:

```bash
cd ~/Desktop/ABM4bio
make fresh BUILD_JOBS=4
```

2. Point calibration-tools at it:

```bash
cp scripts/abm_paths.local.sh.example scripts/abm_paths.local.sh
# edit ABM4BIO_ROOT if needed
```

3. Run:

```bash
./executables/EGI1/optuna_control.sh
```

## Staged calibration workflow

1. **Stage A — control:** `./executables/<CELL_LINE>/optuna_control.sh`
2. **Stage B — treatment per exposure:** `./executables/<CELL_LINE>/optuna_treat_30s.sh` (etc.)
3. Export best control parameters before treatment runs (freeze control in template or overrides).

## Branch comparison

| Branch | Calibration engine |
|--------|-------------------|
| `least-squares` | SciPy `least_squares` / TRF / LM |
| `optuna` (this branch) | Optuna TPE + direct ABM objective |
| `ANN` | PyTorch surrogate + inverse calibration |
