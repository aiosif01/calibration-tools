# ABM4bio CAP calibration — Python LM/least-squares workflow

This package recreates the MATLAB Levenberg–Marquardt workflow in Python and adds live calibration plots.

**This repo is calibration-only.** It does not bundle or build ABM4bio. Simulation binaries and BioDynaMo live in a separate checkout (default: `~/Desktop/ABM4bio`).

The original MATLAB workflow did three things:

1. Replace three placeholders in an ABM4bio input CSV:
   - `__parameter_1__` → apoptosis-related probability
   - `__parameter_2__` → growth probability
   - `__parameter_3__` → division probability
2. Run ABM4bio.
3. Read `results/stats.csv` and compare `N_cells` at 0, 24, 48, and 72 h against experimental targets.

This Python version does the same, but also:

- reads the uploaded `Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx` file,
- converts the workbook into a clean long-format target CSV,
- treats `15"` and `30"` as seconds and `1'`, `2'`, ... as minutes,
- can recompute means and SDs from `N=1..N=4`,
- generates MATLAB-style plots A/B/C,
- updates a live `matplotlib` calibration figure while the optimizer evaluates simulations,
- can create the grouped probability bar charts used in the professor-style plot.

## Folder structure

```text
calibration-tools/
  abmcal/                         Python calibration package
  scripts/                        CLI scripts + abm_env.sh path resolver
  executables/<CELL_LINE>/        per-line launchers (calibrate_control.sh, run_treat_*.sh)
  templates/                      ABM input CSV templates (used by calibration)
  data/                           experimental targets
  outputs/                        generated during calibration

~/Desktop/ABM4bio/                external ABM4bio + BioDynaMo (not in this repo)
  build/ABM4bio                   simulation executable
  libs/biodynamo-v1.05.143/       BioDynaMo runtime
```

## External ABM4bio setup

1. Build ABM4bio once in the external repo:

```bash
cd ~/Desktop/ABM4bio
make fresh BUILD_JOBS=4
```

2. Tell calibration-tools where to find it (pick one):

```bash
# Option A — one-time copy (recommended)
cp scripts/abm_paths.local.sh.example scripts/abm_paths.local.sh
# edit ABM4BIO_ROOT if needed

# Option B — per-shell export
export ABM4BIO_ROOT=~/Desktop/ABM4bio
export ABM_BIN=~/Desktop/ABM4bio/build/ABM4bio
```

3. Run calibration:

```bash
./executables/EGI1/calibrate_control.sh
```

### Custom ABM4bio fork (extra parameters / different C++ setup)

Keep a second checkout as a sibling repo, build it separately, then point calibration at it:

```bash
# In scripts/abm_paths.local.sh:
export ABM4BIO_ROOT="${HOME}/Desktop/ABM4bio-custom"
export ABM_BIN="${ABM4BIO_ROOT}/build/ABM4bio"
```

Or use per-cell-line binaries when only some lines need a custom build:

```bash
export ABM_BIN_EGI1="${HOME}/Desktop/ABM4bio-custom/build/ABM4bio"
export ABM_BIN_HuCCT1="${HOME}/Desktop/ABM4bio/build/ABM4bio"
```

Templates and parameter overrides stay in **this** repo (`templates/`, Python calibration code). C++ model changes stay in the **ABM4bio** repo you point at.

### Central configuration

Edit **`config/calibration_settings.py`** to change mechanism, per-cell-line templates, LM budgets (`stage_nfev`, `global_nfev`), early-stop thresholds, and default bounds. Shell launchers read these defaults via `--use-config`.

```bash
python scripts/show_calibration_config.py              # all cell lines
python scripts/show_calibration_config.py --cell-line EGI1
```

### Control vs treated templates

| Workflow | Template (per cell line) | Mechanism |
|---|---|---|
| Control proliferation (`calibrate_control.sh`) | `templates/cell_lines/<CELL_LINE>/input_control_mechanism11.csv` | 11 — normoxic_CC (MATLAB LM parity) |
| CAP-treated cases (`run_treat_*.sh`) | `templates/cell_lines/<CELL_LINE>/input_mechanism12_treated.csv` | 12 — CAP + DNA damage |

Shared base templates live under `templates/` (e.g. `input_control_mechanism11_template.csv`). Copy or customize per line under `templates/cell_lines/`.

Do **not** use the mechanism-12 CAP template for untreated control calibration: mechanism 12 runs a DNA-damage cascade that drives cells into distress/apoptosis even with CAP disabled, producing flat or collapsing growth curves.

Control calibration (mechanism 11) uses an **O2-only** microenvironment (`diffusion_grid/biochemicals=O2`; no OH_/RONS). It fits **7 parameters**: grow / divide probabilities, grow diameter rate, **cell-cycle dwell** (`G1`, `Sy`, `G2` in **simulated hours**), and divide maturity (**hours**). Python converts hours → ABM **steps** using `steps = round(hours / time_step)` (`MECHANISM11_TIME_STEP_H` in config; default **1 h** → **72 steps** for a 72 h run). Fixed apoptose aging/cleanup windows are also hour-based (`2500 h` / `5000 h` → steps at runtime). Template CSV stores steps for standalone ABM runs; calibration overrides rescale if `time_step` changes. Sequential warm-start **0–24 h → 0–48 h → 0–72 h** with `HORIZON_GATE`. ABM runs omit RNG seed by default.

## Install

```bash
cd abm4bio_lm_python_calibration
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 1 — Extract targets from the Excel workbook

```bash
python scripts/extract_targets.py \
  --xlsx "data/Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx" \
  --out data/calibration_targets_from_excel.csv
```

Default behaviour is to **recompute mean and SD from the N=1..N=4 replicate columns**. This is safer because some sheet MEAN cells are not exactly equal to the visible replicate average. The package also includes `data/mean_sd_discrepancy_report.csv` so you can inspect those differences.

Use sheet values directly only if you intentionally want to reproduce the workbook cells:

```bash
python scripts/extract_targets.py \
  --xlsx "data/Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx" \
  --out data/calibration_targets_sheet_means.csv \
  --use-sheet-mean
```

## Step 2 — Test without ABM4bio using the mock simulator

This checks the optimizer, Excel parser, and live plots without launching ABM4bio.

```bash
python scripts/calibrate_one_case.py \
  --targets-csv data/calibration_targets_from_excel.csv \
  --cell-line EGI1 \
  --exposure-seconds 30 \
  --mock \
  --live \
  --out-dir outputs/test_EGI1_30s_mock
```

If you want a single fixed-parameter test run before any optimization, use:

```bash
chmod +x scripts/run_test_template_case.sh
scripts/run_test_template_case.sh
```

This defaults to the MATLAB-style template in mock mode and writes:

```text
outputs/test_template_case/rendered_input.csv
outputs/test_template_case/simulation_curve.csv
outputs/test_template_case/simulation_preview.png
outputs/test_template_case/simulation_summary.json
```

Switch to the real ABM executable by overriding the shell variables:

```bash
MOCK_MODE=0 \
RUN_COMMAND="/home/aiwsif/Desktop/ABM4bio/build/ABM4bio input.csv" \
scripts/run_test_template_case.sh
```

For the mechanism-12 template, also override the direct parameter keys and CAP duration handling:

```bash
TEMPLATE_PATH="templates/input_mechanism12_CAP_template.csv" \
PARAMETER_KEYS="cancer_cell/can_apoptose/probability,cancer_cell/can_grow/probability,cancer_cell/can_divide/probability" \
PARAMS="0.0029,0.52,0.84" \
SET_CAP_DURATION=1 \
scripts/run_test_template_case.sh
```

Expected outputs:

```text
outputs/test_EGI1_30s_mock/live_calibration_latest.png
outputs/test_EGI1_30s_mock/lm_pythonA_convergence.png/pdf
outputs/test_EGI1_30s_mock/lm_pythonB_fit.png/pdf
outputs/test_EGI1_30s_mock/lm_pythonC_residual_histogram.png/pdf
outputs/test_EGI1_30s_mock/fit_result.json
outputs/test_EGI1_30s_mock/fit_curve.csv
```

## Step 3 — Run real ABM4bio calibration

Use a real ABM4bio executable in `--run-command`. The command is executed inside a fresh run directory containing `input.csv` and copied support files.

Example:

```bash
python scripts/calibrate_one_case.py \
  --targets-csv data/calibration_targets_from_excel.csv \
  --cell-line EGI1 \
  --exposure-seconds 30 \
  --template templates/input_TEMPLATE_m11_from_matlab_lm.csv \
  --run-command "/home/aiwsif/Desktop/ABM4bio/build/ABM4bio input.csv" \
  --copy-file templates/initial_cells.dat \
  --out-dir outputs/EGI1_30s_real \
  --live
```

If BioDynaMo environment variables are required, wrap the command in `bash -lc`, e.g.:

```bash
--run-command "bash -lc 'export BDMSYS=/home/aiwsif/Desktop/ABM4bio/libs/biodynamo-v1.05.143 && export BDM_ROOT_DIR=$BDMSYS/third_party/root && export ROOTSYS=$BDMSYS/third_party/root && export PATH=$BDMSYS/bin:$ROOTSYS/bin:$PATH && export LD_LIBRARY_PATH=$BDMSYS/lib:$ROOTSYS/lib:$LD_LIBRARY_PATH && /home/aiwsif/Desktop/ABM4bio/build/ABM4bio input.csv'"
```

## Step 4 — Calibrate the professor-style probability bars

The attached bar chart corresponds to fitting the 3 effective probabilities for cases such as:

```text
Control, Treat:30s, Treat:2min, Treat:4min, Treat:5min
```

Run:

```bash
python scripts/calibrate_all_cases.py \
  --xlsx "data/Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx" \
  --cell-lines EGI1,HuCCT1,PANC1,MiaPaCa2 \
  --exposures-seconds 0,30,120,240,300 \
  --template templates/input_TEMPLATE_m11_from_matlab_lm.csv \
  --run-command "/home/aiwsif/Desktop/ABM4bio/build/ABM4bio input.csv" \
  --copy-file templates/initial_cells.dat \
  --out-dir outputs/batch_probability_fit
```

This writes:

```text
outputs/batch_probability_fit/summary_fit_parameters.csv
outputs/batch_probability_fit/<CELL_LINE>_probability_bar_chart.png/pdf
```

## Mechanism-12 setup for all cases (recommended for your CAP directory)

For mechanism 12, the template usually has fixed numeric values (not `__parameter_*__` tokens).
Use direct row overrides for the three probabilities:

- `cancer_cell/can_apoptose/probability`
- `cancer_cell/can_grow/probability`
- `cancer_cell/can_divide/probability`

and set CAP duration from each exposure case (`0, 30 s, 2 min, 4 min, 5 min`).

### Why these starting values and bounds

- `x0 = 0.0029,0.52,0.84`:
  - matches mechanism-12 baseline values already used in your CAP example,
  - starts the optimizer close to a biologically plausible control point.
- `lb = 0,0,0`, `ub = 0.9999,0.9999,0.9999`:
  - these are probabilities, so `[0,1)` is the correct feasible range,
  - avoids clipping growth/division at `0.5` (which can bias the fit).

### One-command run

```bash
cd /home/aiwsif/Desktop/LM-python
./run_mechanism12_EGI1.sh
./run_mechanism12_HuCCT1.sh
./run_mechanism12_PANC1.sh
./run_mechanism12_MiaPaCa2.sh
```

Optional overrides:

```bash
XLSX_PATH="/path/to/workbook.xlsx" \
ABM_BIN="/home/aiwsif/Desktop/ABM4bio/build/ABM4bio" \
OUT_DIR="/home/aiwsif/Desktop/LM-python/outputs/mechanism12_EGI1" \
./run_mechanism12_EGI1.sh
```

Use different executables per cell line by running each script with its own `ABM_BIN`:

```bash
ABM_BIN="/path/to/ABM4bio_EGI1" ./run_mechanism12_EGI1.sh
ABM_BIN="/path/to/ABM4bio_HuCCT1" ./run_mechanism12_HuCCT1.sh
ABM_BIN="/path/to/ABM4bio_PANC1" ./run_mechanism12_PANC1.sh
ABM_BIN="/path/to/ABM4bio_MiaPaCa2" ./run_mechanism12_MiaPaCa2.sh
```

Outputs:

```text
outputs/mechanism12_all_cases/summary_fit_parameters.csv
outputs/mechanism12_all_cases/<CELL_LINE>_probability_bar_chart.png
```

## Mechanism 11 vs mechanism 12

The file `templates/input_TEMPLATE_m11_from_matlab_lm.csv` is the direct translation of the uploaded MATLAB LM template. It uses `mechanism_order = 11` because that was in the original ZIP.

For mechanism 12, start from:

```text
templates/input_mechanism12_CAP_template.csv
```

Then map the 3 fitted placeholders or explicit ABM parameter names to the mechanism-12 parameters you want to calibrate. The Python renderer supports both placeholder replacement and row-based parameter overrides.

## Important defaults

- Optimizer: `scipy.optimize.least_squares`.
- Default method: `trf`, because SciPy's `lm` method does **not** support bounds.
- Bounds are the same as the MATLAB example by default:
  - apoptosis: `[0.0, 0.9999]`
  - growth: `[0.01, 0.5]`
  - division: `[0.01, 0.5]`
- Target mode: `t0_normalized`, because the uploaded Excel values are assay-like continuous measurements, while ABM4bio returns cell counts. This compares growth/response shape rather than raw units.
- Use `--target-mode raw` only if the simulation output is in the same scale as the experimental targets.

## Live plots

Use `--live` for interactive plots. Even without a GUI, the latest frame is saved after every function evaluation as:

```text
live_calibration_latest.png
```

This replaces MATLAB's `drawnow` behaviour.
