THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ABM4BIO_ROOT := $(realpath $(THIS_DIR)/../..)
ABM_BINARY := $(ABM4BIO_ROOT)/build/ABM4bio
BDM_ENV_SCRIPT := $(ABM4BIO_ROOT)/libs/biodynamo-v1.05.143/bin/thisbdm.sh
EXCEL_DATA := $(ABM4BIO_ROOT)/libs/experimental_data/Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx
# Prefer project miniconda python when present, otherwise fallback to system python.
PYTHON ?= $(if $(wildcard /home/aiwsif/miniconda/bin/python3),/home/aiwsif/miniconda/bin/python3,python3)

# --- Fork / EAGAIN safety variables ---
# MAKE_CMD: use a plain variable (not $(MAKE)) so dry-run (-n) does not execute recursive makes.
MAKE_CMD ?= /usr/bin/make
# BUILD_JOBS: default 1 to prevent process explosion during compilation.
BUILD_JOBS ?= 1
# MAX_USER_PROCESSES: refuse to start a build or simulation above this threshold.
MAX_USER_PROCESSES ?= 2000

# Cap BLAS/OpenMP threads for ALL python invocations so numpy import
# never tries to fork 64 threads and exhausts RLIMIT_NPROC.
export OPENBLAS_NUM_THREADS := 1
export MKL_NUM_THREADS := 1
export NUMEXPR_NUM_THREADS := 1
export VECLIB_MAXIMUM_THREADS := 1
export BLIS_NUM_THREADS := 1
export OMP_NUM_THREADS := 1
SCRIPTS := scripts

INPUT_CONTROL ?= input_control.csv
RESULTS_CONTROL ?= results_control
SEED ?= 1234
ABM_INITIAL_CELLS ?= 100
GRID_RESOLUTION ?= 10
VIZ_INTERVAL_H ?= 1
ABM_REPLICATES ?= 1
ABM_REPLICATE_SEED_STEP ?= 1
OMP_THREADS ?= 2
ABM_DA_MAXITER ?= 50
ABM_NM_MAXITER ?= 200
ABM_METHODS ?= bayesian powell
ABM_FIT_PARAMS ?= cancer_cell/can_divide/probability cancer_cell/can_apoptose/probability cancer_cell/can_grow/diameter_rate cancer_cell/can_grow/probability
ABM_OVERGROWTH_FACTOR ?= 4.0
ABM_REPLICATE_TIMEOUT_S ?= 900
ABM_MAX_EVALS ?= 200
ABM_BO_CALLS ?= 80
ABM_BO_INIT ?= 20
ABM_BAND_STD_SCALE ?= 2.0
ABM_OUT_DIR ?= calibration_outputs/EGI1_control_0to72h
CELL_LINE ?= EGI1

CAP_TEMPLATE_INPUT ?= input_mechanism12_CAP_template.csv
CAP_OUT_DIR ?= calibration_outputs/CAP_optuna
CAP_CELL_LINES ?= EGI1,HuCCT1,PANC1,MiaPaCa2
CAP_EXPOSURES_MIN ?= 0,0.5,2,4,5
CAP_N_TRIALS ?= 40
CAP_STARTUP_TRIALS ?= 10
CAP_REPLICATES ?= 1
CAP_OMP_THREADS ?= 4
CAP_TIMEOUT_S ?= 1800
CAP_MECHANISM_ORDER ?= 12
CAP_STORAGE ?=
CAP_UPDATE_TEMPLATE ?= 1
CAP_ENQUEUE_TEMPLATE ?= 1
CAP_STAGE ?= bar_chart
CAP_DATA_CSV ?= data/experimental_targets_t0_normalized_corrected_units.csv
CAP_MANIFEST_CSV ?= data/experimental_case_manifest_corrected_units.csv
CAP_PARAM_SPACE_CSV ?= data/optuna_parameter_space_mechanism12.csv
CAP_BAR_CHART_ONLY ?= 0
CAP_LM_COMPARE ?= 0

.PHONY: help build show-config prepare_input run_control check_trajectory calibrate_control calibrate_control_clean calibrate_cap_optuna calibrate_cap_optuna_all4 calibrate_cap_optuna_cell calibrate_cap_stage1 calibrate_cap_stage2 calibrate_cap_stage3 clean clean_calibration clean_all

help:
	@echo ""
	@echo "=== CAP in-vitro: untreated control calibration (0–72 h) ==="
	@echo ""
	@echo "  make build              Rebuild ABM4bio"
	@echo "  make prepare_input      Generate $(INPUT_CONTROL) (coarse grid, CAP off)"
	@echo "  make run_control        Single 0–72 h untreated simulation"
	@echo "  make check_trajectory   Print viable counts vs t0 from stats.csv"
	@echo "  make calibrate_control  Fit untreated control vs Excel (clean wrapper)"
	@echo "  make calibrate_cap_optuna       CAP calibration with Optuna + mechanism 12"
	@echo "  make calibrate_cap_optuna_all4  CAP calibration for all workbook cell lines"
	@echo "  make calibrate_cap_optuna_cell  CAP calibration for CELL_LINE only"
	@echo ""
	@echo "Options (examples):"
	@echo "  make prepare_input GRID_RESOLUTION=10 VIZ_INTERVAL_H=1 ABM_INITIAL_CELLS=100"
	@echo "  make run_control OMP_THREADS=8 SEED=1234"
	@echo "  make calibrate_control ABM_BO_CALLS=100 ABM_BO_INIT=30 OMP_THREADS=2"
	@echo "  make calibrate_control ABM_METHODS='bayesian powell' ABM_BO_CALLS=80 ABM_BO_INIT=20"
	@echo ""
	@echo "Calibration pipeline (default: bayesian -> powell):"
	@echo "  ABM_METHODS='$(ABM_METHODS)'"
	@echo "    bayesian  - GP surrogate BO (global, noise-aware); use for exploration"
	@echo "    powell    - Powell refinement from BO best (local); use for polishing"
	@echo "    dual_annealing - optional global search (add if BO budget is large)"
	@echo "    NOTE: differential_evolution needs popsize*n_params*maxiter evals - too"
	@echo "          expensive for small budgets; excluded from default pipeline."
	@echo "  ABM_FIT_PARAMS='$(ABM_FIT_PARAMS)'"
	@echo "    Default 4-parameter set: divide_p, apoptose_p, grow_rate, grow_p"
	@echo "  OMP_THREADS=$(OMP_THREADS)  - Threads per ABM run (keep low to avoid fork exhaustion)"
	@echo "  ABM_OVERGROWTH_FACTOR=$(ABM_OVERGROWTH_FACTOR)  - Kill at N0 x max_viability x factor cells"
	@echo "  ABM_REPLICATE_TIMEOUT_S=$(ABM_REPLICATE_TIMEOUT_S)  - Per-replicate wall-time kill"
	@echo "  ABM_BO_CALLS=$(ABM_BO_CALLS)  - Total BO function evaluations"
	@echo "  ABM_BO_INIT=$(ABM_BO_INIT)     - Random BO initialization points"
	@echo ""
	@echo "  make clean              Remove $(RESULTS_CONTROL)"
	@echo "  make clean_calibration  Remove calibration_outputs/"
	@echo "  make show-config        Print active variables"
	@echo ""

show-config:
	@echo "ABM_BINARY=$(ABM_BINARY)"
	@echo "EXCEL_DATA=$(EXCEL_DATA)"
	@echo "INPUT_CONTROL=$(INPUT_CONTROL)"
	@echo "RESULTS_CONTROL=$(RESULTS_CONTROL)"
	@echo "OMP_THREADS=$(OMP_THREADS)"
	@echo "GRID_RESOLUTION=$(GRID_RESOLUTION)"
	@echo "ABM_INITIAL_CELLS=$(ABM_INITIAL_CELLS)"
	@echo "ABM_FIT_PARAMS=$(ABM_FIT_PARAMS)"
	@echo "ABM_METHODS=$(ABM_METHODS)"
	@echo "ABM_BO_CALLS=$(ABM_BO_CALLS)"
	@echo "ABM_BO_INIT=$(ABM_BO_INIT)"
	@echo "ABM_OVERGROWTH_FACTOR=$(ABM_OVERGROWTH_FACTOR)"
	@echo "ABM_REPLICATE_TIMEOUT_S=$(ABM_REPLICATE_TIMEOUT_S)"
	@echo "ABM_OUT_DIR=$(ABM_OUT_DIR)"
	@echo "CAP_TEMPLATE_INPUT=$(CAP_TEMPLATE_INPUT)"
	@echo "CAP_OUT_DIR=$(CAP_OUT_DIR)"
	@echo "CAP_CELL_LINES=$(CAP_CELL_LINES)"
	@echo "CAP_EXPOSURES_MIN=$(CAP_EXPOSURES_MIN)"
	@echo "CAP_N_TRIALS=$(CAP_N_TRIALS)"
	@echo "CAP_STARTUP_TRIALS=$(CAP_STARTUP_TRIALS)"
	@echo "CAP_REPLICATES=$(CAP_REPLICATES)"
	@echo "CAP_OMP_THREADS=$(CAP_OMP_THREADS)"
	@echo "CAP_TIMEOUT_S=$(CAP_TIMEOUT_S)"
	@echo "CAP_MECHANISM_ORDER=$(CAP_MECHANISM_ORDER)"
	@echo "CAP_STORAGE=$(CAP_STORAGE)"
	@echo "CAP_UPDATE_TEMPLATE=$(CAP_UPDATE_TEMPLATE)"
	@echo "CAP_ENQUEUE_TEMPLATE=$(CAP_ENQUEUE_TEMPLATE)"

build:
	@echo "[build] Checking user process count before building..."
	@total=$$(ps -u "$${USER}" --no-headers 2>/dev/null | wc -l | tr -d ' '); \
	 if [ -n "$$total" ] && [ "$$total" -gt "$(MAX_USER_PROCESSES)" ]; then \
	   echo "ERROR: $$total user processes detected (limit $(MAX_USER_PROCESSES)). Refusing build."; \
	   exit 1; \
	 fi
	@for tool in make cmake; do \
	  cnt=$$(pgrep -c -u "$${USER}" -x $$tool 2>/dev/null || echo 0); \
	  if [ "$$cnt" -gt 0 ]; then \
	    echo "ERROR: $$cnt active '$$tool' process(es) found. Wait before building."; \
	    exit 1; \
	  fi; \
	done
	@echo "[build] Process budget OK. Starting build with BUILD_JOBS=$(BUILD_JOBS)."
	cd $(ABM4BIO_ROOT) && $(MAKE_CMD) fresh BUILD_JOBS=$(BUILD_JOBS)

prepare_input:
	cd $(THIS_DIR) && OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 $(PYTHON) $(SCRIPTS)/prepare_control_input.py \
		--base-input input_control_base.csv \
		--output $(INPUT_CONTROL) \
		--initial-cells $(ABM_INITIAL_CELLS) \
		--grid-resolution $(GRID_RESOLUTION) \
		--viz-interval-h $(VIZ_INTERVAL_H)

define REMOVE_RESULTS_DIR
	@dir="$(1)"; \
	if [ -z "$$dir" ] || [ "$$dir" = "/" ]; then echo "refusing unsafe path" >&2; exit 1; fi; \
	if [ ! -e "$$dir" ]; then exit 0; fi; \
	echo "Removing $$dir ..."; \
	chmod -R u+w "$$dir" 2>/dev/null || true; \
	find "$$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true; \
	rm -rf "$$dir" 2>/dev/null || true; \
	for attempt in 1 2 3 4 5; do \
		[ ! -e "$$dir" ] && exit 0; sleep 1; chmod -R u+w "$$dir" 2>/dev/null || true; rm -rf "$$dir" 2>/dev/null || true; \
	done; \
	[ ! -e "$$dir" ] || (echo "ERROR: could not remove $$dir" >&2; exit 1)
endef

run_control: prepare_input
	$(call REMOVE_RESULTS_DIR,$(RESULTS_CONTROL))
	bash -c 'export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1 OMP_NUM_THREADS=$(OMP_THREADS); \
		export BDM_THISBDM_SILENT=true; source "$(BDM_ENV_SCRIPT)"; \
		"$(ABM_BINARY)" $(INPUT_CONTROL) $(SEED)'

check_trajectory:
	cd $(THIS_DIR) && $(PYTHON) $(SCRIPTS)/check_trajectory.py $(RESULTS_CONTROL)/stats.csv

calibrate_control: prepare_input
	$(MAKE) --no-print-directory calibrate_control_clean

calibrate_control_clean:
	@if [ "$(SEED)" -le 0 ]; then echo "SEED must be > 0"; exit 2; fi
	@echo "=== Checking Python environment ==="
	@echo "Using Python: $(PYTHON)"
	@$(PYTHON) -c "import sys; print('Python:', sys.executable)" && $(PYTHON) -c "import skopt; print('scikit-optimize:', skopt.__version__)"
	cd $(THIS_DIR) && PYTHON_BIN=$(PYTHON) BDM_ENV_SCRIPT=$(BDM_ENV_SCRIPT) $(SCRIPTS)/run_control_calibration_clean.sh \
		--excel "$(EXCEL_DATA)" \
		--cell-line $(CELL_LINE) \
		--template-input $(INPUT_CONTROL) \
		--abm-binary "$(ABM_BINARY)" \
		--bdm-env-script "$(BDM_ENV_SCRIPT)" \
		--omp-threads $(OMP_THREADS) \
		--seed $(SEED) \
		--replicates $(ABM_REPLICATES) \
		--replicate-seed-step $(ABM_REPLICATE_SEED_STEP) \
		--fit-params $(ABM_FIT_PARAMS) \
		--methods $(ABM_METHODS) \
		--da-maxiter $(ABM_DA_MAXITER) \
		--nm-maxiter $(ABM_NM_MAXITER) \
		--overgrowth-factor $(ABM_OVERGROWTH_FACTOR) \
		--max-evaluations $(ABM_MAX_EVALS) \
		--population-band-std-scale $(ABM_BAND_STD_SCALE) \
		--replicate-timeout-s $(ABM_REPLICATE_TIMEOUT_S) \
		--bo-calls $(ABM_BO_CALLS) \
		--bo-init $(ABM_BO_INIT) \
		--out-dir $(ABM_OUT_DIR)

calibrate_cap_optuna:
	@echo "=== CAP Optuna calibration: stage=$(CAP_STAGE), mechanism=$(CAP_MECHANISM_ORDER) ==="
	cd $(THIS_DIR) && CAP_ALLOW_ACTIVE_MAKE=2 PYTHON_BIN=$(PYTHON) BDM_ENV_SCRIPT=$(BDM_ENV_SCRIPT) bash $(SCRIPTS)/run_cap_optuna_clean.sh \
		--stage "$(CAP_STAGE)" \
		--data-csv "$(CAP_DATA_CSV)" \
		--manifest-csv "$(CAP_MANIFEST_CSV)" \
		--param-space-csv "$(CAP_PARAM_SPACE_CSV)" \
		--template-input $(CAP_TEMPLATE_INPUT) \
		--abm-binary "$(ABM_BINARY)" \
		--bdm-env-script "$(BDM_ENV_SCRIPT)" \
		--out-dir $(CAP_OUT_DIR) \
		--cell-lines "$(CAP_CELL_LINES)" \
		--exposures-min "$(CAP_EXPOSURES_MIN)" \
		--n-trials $(CAP_N_TRIALS) \
		--n-startup-trials $(CAP_STARTUP_TRIALS) \
		--replicates $(CAP_REPLICATES) \
		--sampler-seed $(SEED) \
		--base-seed $(SEED) \
		--omp-threads $(CAP_OMP_THREADS) \
		--timeout-s $(CAP_TIMEOUT_S) \
		--mechanism-order $(CAP_MECHANISM_ORDER) \
		$(if $(CAP_STORAGE),--storage "$(CAP_STORAGE)",) \
		$(if $(filter 1 true TRUE yes YES,$(CAP_BAR_CHART_ONLY)),--bar-chart-only,) \
		$(if $(filter 1 true TRUE yes YES,$(CAP_LM_COMPARE)),--lm-compare,) \
		$(if $(filter 1 true TRUE yes YES,$(CAP_ENQUEUE_TEMPLATE)),--enqueue-template,--no-enqueue-template) \
		$(if $(filter 1 true TRUE yes YES,$(CAP_UPDATE_TEMPLATE)),--update-template,--no-update-template)

# --- Stage shortcuts ---
calibrate_cap_stage1:
	$(MAKE) --no-print-directory calibrate_cap_optuna \
		CAP_STAGE=control_baseline CAP_EXPOSURES_MIN=0 CAP_BAR_CHART_ONLY=0

calibrate_cap_stage2:
	$(MAKE) --no-print-directory calibrate_cap_optuna \
		CAP_STAGE=bar_chart CAP_BAR_CHART_ONLY=1

calibrate_cap_stage3:
	$(MAKE) --no-print-directory calibrate_cap_optuna \
		CAP_STAGE=mechanistic CAP_BAR_CHART_ONLY=0

calibrate_cap_optuna_all4:
	$(MAKE) --no-print-directory calibrate_cap_optuna CAP_CELL_LINES=all

calibrate_cap_optuna_cell:
	$(MAKE) --no-print-directory calibrate_cap_optuna CAP_CELL_LINES="$(CELL_LINE)"

clean:
	$(call REMOVE_RESULTS_DIR,$(RESULTS_CONTROL))

clean_calibration:
	rm -rf calibration_outputs

clean_all: clean clean_calibration
