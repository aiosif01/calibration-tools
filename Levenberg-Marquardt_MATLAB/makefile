SHELL := /bin/bash
BDM_DIR := /home/aiwsif/Desktop/ABM4bio/libs/biodynamo-v1.05.143
ABM_BIN := /home/aiwsif/Desktop/ABM4bio/build/ABM4bio
all:
	export BDMSYS=$(BDM_DIR) && \
	export BDM_ROOT_DIR=$(BDM_DIR)/third_party/root && \
	export ROOTSYS=$(BDM_DIR)/third_party/root && \
	export OMP_PROC_BIND=true && \
	export PATH=$(BDM_DIR)/bin:$(BDM_DIR)/third_party/root/bin:$$PATH && \
	export LD_LIBRARY_PATH=$(BDM_DIR)/lib:$(BDM_DIR)/third_party/root/lib:$$LD_LIBRARY_PATH && \
	$(ABM_BIN) input.csv
clean:
	rm -rf results/; rm out *.pdf
