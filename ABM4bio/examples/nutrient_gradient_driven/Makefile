.RECIPEPREFIX := >
SHELL := /bin/bash

ABM_ROOT := $(abspath ../..)
BIN := $(ABM_ROOT)/build/ABM4bio

BUILD_JOBS ?= 1
OMP_THREADS ?= 4
SEED ?= 1234
MAX_USER_PROCESSES ?= 2000

.PHONY: help check build run invitro chemotaxis ecm analyze clean clean_build

help:
> @echo "Safe nutrient_gradient_driven targets:"
> @echo "  make build BUILD_JOBS=1"
> @echo "  make invitro OMP_THREADS=4 SEED=1234"
> @echo "  make chemotaxis OMP_THREADS=4 SEED=1234"
> @echo "  make ecm OMP_THREADS=4 SEED=1234"
> @echo "  make clean"
> @echo
> @echo "Current settings:"
> @echo "  ABM_ROOT=$(ABM_ROOT)"
> @echo "  BIN=$(BIN)"
> @echo "  BUILD_JOBS=$(BUILD_JOBS)"
> @echo "  OMP_THREADS=$(OMP_THREADS)"
> @echo "  SEED=$(SEED)"

check:
> @set -euo pipefail; \
> total=$$(/usr/bin/ps -u "$$USER" --no-headers | /usr/bin/wc -l); \
> make_count=$$(/usr/bin/pgrep -c -u "$$USER" -x make || true); \
> cmake_count=$$(/usr/bin/pgrep -c -u "$$USER" -x cmake || true); \
> sh_count=$$(/usr/bin/pgrep -c -u "$$USER" -x sh || true); \
> echo "User processes: $$total"; \
> echo "make processes: $$make_count"; \
> echo "cmake processes: $$cmake_count"; \
> echo "sh processes: $$sh_count"; \
> if [ "$$total" -gt "$(MAX_USER_PROCESSES)" ]; then \
>   echo "ERROR: too many user processes: $$total > $(MAX_USER_PROCESSES)" >&2; \
>   exit 20; \
> fi; \
> if [ ! -x "$(BIN)" ]; then \
>   echo "ERROR: ABM4bio executable not found or not executable: $(BIN)" >&2; \
>   echo "Run: make build BUILD_JOBS=1" >&2; \
>   exit 21; \
> fi

build:
> cd "$(ABM_ROOT)" && $(MAKE) BUILD_JOBS="$(BUILD_JOBS)" fresh

run: invitro

invitro: check
> @set -euo pipefail; \
> lock="/tmp/abm4bio_nutrient_$${USER}_invitro.lock"; \
> if [ -e "$$lock" ]; then \
>   echo "ERROR: invitro run already active or stale lock exists: $$lock" >&2; \
>   exit 10; \
> fi; \
> trap 'rm -f "$$lock"' EXIT; \
> touch "$$lock"; \
> rm -rf results_inVitro; \
> OMP_NUM_THREADS="$(OMP_THREADS)" "$(BIN)" input_inVitro.csv "$(SEED)"

chemotaxis: check
> @set -euo pipefail; \
> lock="/tmp/abm4bio_nutrient_$${USER}_chemotaxis.lock"; \
> if [ -e "$$lock" ]; then \
>   echo "ERROR: chemotaxis run already active or stale lock exists: $$lock" >&2; \
>   exit 10; \
> fi; \
> trap 'rm -f "$$lock"' EXIT; \
> touch "$$lock"; \
> rm -rf results_inVitro_chemotaxis; \
> OMP_NUM_THREADS="$(OMP_THREADS)" "$(BIN)" input_inVitro_chemotaxis.csv "$(SEED)"

ecm: check
> @set -euo pipefail; \
> lock="/tmp/abm4bio_nutrient_$${USER}_ecm.lock"; \
> if [ -e "$$lock" ]; then \
>   echo "ERROR: ecm run already active or stale lock exists: $$lock" >&2; \
>   exit 10; \
> fi; \
> trap 'rm -f "$$lock"' EXIT; \
> touch "$$lock"; \
> rm -rf results_ECM; \
> OMP_NUM_THREADS="$(OMP_THREADS)" "$(BIN)" input_ECM.csv "$(SEED)"

analyze:
> python3 analyze_invivo_tumor.py

clean:
> rm -rf results_inVitro results_inVitro_chemotaxis results_ECM

clean_build:
> rm -rf "$(ABM_ROOT)/build"
