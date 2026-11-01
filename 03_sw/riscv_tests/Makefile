ROOT := ../..
.PHONY: all selected
all:
	python3 $(ROOT)/05_tools/sim/run_riscv_tests.py
selected:
	python3 $(ROOT)/05_tools/sim/run_riscv_tests.py --tests $(TESTS)
