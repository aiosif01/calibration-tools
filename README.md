# ABM4bio CAP calibration — ANN surrogate workflow

This branch calibrates ABM4bio parameters using a **PyTorch forward surrogate + differentiable inverse search**. It does not use Optuna, SciPy `least_squares`, or direct ABM optimization during calibration.

**Method purity:** Training data comes from Latin-hypercube/random ABM sampling (not Optuna). Calibration minimizes curve error on the frozen ANN. Final parameters are **always validated** with real ABM4bio replicates.

## Workflow

```text
1. Sample parameter space (LHS) → run ABM4bio → build dataset
2. Train forward ANN ensemble: (θ, cell_line, exposure) → [y0, y24, y48, y72]
3. Inverse calibration: Adam on θ through frozen ANN vs experimental curve
4. Validate best θ with real ABM4bio (mandatory)
```

## Quick start

```bash
pip install -r requirements.txt

# Full mock pipeline (100 samples, fast training)
MOCK_MODE=1 N_SAMPLES=100 ./executables/EGI1/ann_generate_dataset.sh
MOCK_MODE=1 ./executables/EGI1/ann_train_surrogate.sh
MOCK_MODE=1 ./executables/EGI1/ann_calibrate_control.sh

# Or all three steps:
MOCK_MODE=1 N_SAMPLES=100 ANN_STEP=all ./executables/_ann_common.sh
# (set CELL_LINE=EGI1 first)
```

## Production run (real ABM)

```bash
cd /home/aiwsif/Desktop/calibration-tools
export PYTHON_BIN="$(which python)"

./executables/EGI1/ann_generate_dataset.sh   # ~1000 samples × 3 seeds
./executables/EGI1/ann_train_surrogate.sh      # 5-model ensemble
./executables/EGI1/ann_calibrate_control.sh    # inverse + ABM validation
```

Run from **repo root** or from `executables/EGI1/` — both work.

## Folder structure

```text
abmcal/core/objective_common.py     shared curve error / normalization
abmcal/method/
  ann_model.py                      ForwardSurrogate (PyTorch)
  dataset_generator.py              ABM dataset generation
  train_forward_surrogate.py        training loop
  inverse_calibration.py            Adam inverse on frozen ANN
  ensemble.py                       5-model uncertainty ensemble
  validate_ann_solution.py          mandatory ABM validation
configs/parameter_space_control.yaml
scripts/generate_ann_dataset.py
scripts/train_ann_surrogate.py
scripts/calibrate_with_ann.py
executables/EGI1/ann_*.sh
```

## Outputs

```text
outputs/ann/<CELL_LINE>/control/
  datasets/
    ann_parameter_samples.csv
    ann_abm_runs_raw.csv
    ann_training_dataset.csv
  models/
    surrogate_seed100.pt … surrogate_seed500.pt
    surrogate_meta.json
  calibration/
    ann_inverse_best_parameters.csv
    ann_inverse_curve.csv
  validation/
    abm_validation_replicates.csv
    abm_validation_summary.csv
    ann_vs_abm_validation_error.csv
  figures/
    inverse_fit_curve.png
    final_abm_validation_band.png
```

## Configuration

| File | Purpose |
|------|---------|
| `config/calibration_settings.py` | `ANNSettings`: samples, ensemble, inverse steps |
| `configs/parameter_space_control.yaml` | Parameter bounds for dataset sampling |
| `configs/runtime_local.yaml` | Debug vs production budgets |

Override:

```bash
N_SAMPLES=2000 ./executables/EGI1/ann_generate_dataset.sh
```

## Branch comparison

| Branch | Engine |
|--------|--------|
| `least-squares` | SciPy TRF/LM |
| `optuna` | Optuna TPE + direct ABM |
| `ANN` (this branch) | PyTorch surrogate + inverse Adam |

## External ABM4bio

Build ABM4bio separately and configure `scripts/abm_paths.local.sh` before real (non-mock) runs.
