.RECIPEPREFIX := >
SHELL := /bin/bash

ABM4bio := $(CURDIR)

BIODYNAMO_VERSION = a9d3c90e97164660d0ce567a357eb1cfe38035aa
BIODYNAMO_FOLDER  = biodynamo-v1.05.143

CC  = /usr/bin/gcc
CXX = /usr/bin/g++

BUILD_JOBS ?= 1
RUN_JOBS   ?= 1
MAKE_CMD ?= /usr/bin/make
MAX_USER_PROCESSES ?= 2000

EXAMPLES := \
  blood_vessel_CTC \
  cancer_angiogenesis \
  cancer_radiation \
  HeLa_cells \
  neuron_astrocyte \
  neuron_bipolar \
  obstacle_demo_1 \
  obstacle_demo_2 \
  tumour_spheroid \
  vasculogenesis \
  wound_assay

.PHONY: all whereami setup_biodynamo install_biodynamo biodynamo source_biodynamo clean fresh tests check_process_budget $(EXAMPLES)

all:
> @echo
> @echo " *** Please provide a specific rule to execute *** "
> @echo
> @echo "Safe examples:"
> @echo "  make fresh BUILD_JOBS=1"
> @echo "  make blood_vessel_CTC RUN_JOBS=1"
> @echo "  make tests"
> @echo

whereami:
> @echo " ...over here: $(ABM4bio)"

check_process_budget:
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
> fi

setup_biodynamo:
> rm -Rf "$(ABM4bio)/libs/biodynamo"
> git clone https://github.com/BioDynaMo/biodynamo.git "$(ABM4bio)/libs/biodynamo"
> cd "$(ABM4bio)/libs/biodynamo" && git checkout "$(BIODYNAMO_VERSION)"

install_biodynamo:
> @set -euo pipefail; \
> lock="/tmp/abm4bio_install_biodynamo_$$USER.lock"; \
> if [ -e "$$lock" ]; then \
>   echo "ERROR: install_biodynamo already active or stale lock exists: $$lock" >&2; \
>   exit 10; \
> fi; \
> trap 'rm -f "$$lock"' EXIT; \
> touch "$$lock"; \
> cd "$(ABM4bio)/libs/biodynamo"; \
> ./prerequisites.sh all; \
> rm -rf build; \
> mkdir -p build; \
> cd build; \
> cmake -DCMAKE_C_COMPILER="$(CC)" -DCMAKE_CXX_COMPILER="$(CXX)" \
>   -Dparaview=on \
>   -DCMAKE_BUILD_TYPE=Release \
>   -DCMAKE_INSTALL_PREFIX="$(ABM4bio)/libs" ..; \
> $(MAKE_CMD) -j"$(BUILD_JOBS)"; \
> $(MAKE_CMD) install

biodynamo:
> $(MAKE_CMD) setup_biodynamo
> $(MAKE_CMD) BUILD_JOBS="$(BUILD_JOBS)" install_biodynamo

source_biodynamo:
> /bin/bash -c 'source "$(ABM4bio)/libs/$(BIODYNAMO_FOLDER)/bin/thisbdm.sh"'

clean:
> rm -rf "$(ABM4bio)/build"

fresh:
> @set -euo pipefail; \
> lock="/tmp/abm4bio_fresh_$$USER.lock"; \
> if [ -e "$$lock" ]; then \
>   echo "ERROR: fresh build already active or stale lock exists: $$lock" >&2; \
>   exit 10; \
> fi; \
> trap 'rm -f "$$lock"' EXIT; \
> touch "$$lock"; \
> rm -rf "$(ABM4bio)/build"; \
> mkdir -p "$(ABM4bio)/build"; \
> bash -lc 'source "$(ABM4bio)/libs/$(BIODYNAMO_FOLDER)/bin/thisbdm.sh" && \
>   cd "$(ABM4bio)/build" && \
>   cmake -DCMAKE_C_COMPILER="$(CC)" \
>         -DCMAKE_CXX_COMPILER="$(CXX)" \
>         -DCMAKE_PREFIX_PATH="$(ABM4bio)/libs/$(BIODYNAMO_FOLDER)/share/cmake" .. && \
>   $(MAKE_CMD) -j"$(BUILD_JOBS)"'

$(EXAMPLES):
> @set -euo pipefail; \
> example="$@"; \
> example_dir="$(ABM4bio)/examples/$$example"; \
> lock="/tmp/abm4bio_example_$${USER}_$${example}.lock"; \
> if [ -e "$$lock" ]; then \
>   echo "ERROR: example run already active or stale lock exists: $$lock" >&2; \
>   exit 10; \
> fi; \
> if [ ! -d "$$example_dir" ]; then \
>   echo "ERROR: missing example directory: $$example_dir" >&2; \
>   exit 11; \
> fi; \
> if [ ! -f "$$example_dir/Makefile" ] && [ ! -f "$$example_dir/makefile" ]; then \
>   echo "ERROR: no Makefile/makefile in $$example_dir" >&2; \
>   exit 12; \
> fi; \
> trap 'rm -f "$$lock"' EXIT; \
> touch "$$lock"; \
> echo; \
> echo "*****************"; \
> echo "*** Running example: $$example"; \
> echo "*****************"; \
> cd "$$example_dir"; \
> rm -rf results; \
> $(MAKE_CMD) -j"$(RUN_JOBS)" run

tests:
> @set -euo pipefail; \
> $(MAKE_CMD) clean; \
> $(MAKE_CMD) --silent BUILD_JOBS=1 fresh 2>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 blood_vessel_CTC 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 cancer_angiogenesis 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 cancer_radiation 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 HeLa_cells 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 neuron_astrocyte 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 neuron_bipolar 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 obstacle_demo_1 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 obstacle_demo_2 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 tumour_spheroid 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 vasculogenesis 2>>errors; \
> $(MAKE_CMD) --silent RUN_JOBS=1 wound_assay 2>>errors; \
> echo; \
> echo "***************************"; \
> echo "*** All tests completed ***"; \
> echo "***************************"
