SHELL := /bin/bash
.SHELLFLAGS := -e -o pipefail -c
ROOT := ../..
TOOLCHAIN ?= /opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-
RUN ?= performance
ITERATIONS ?= 300
CPU_HZ ?= 27000000
OUT := $(ROOT)/07_runs/coremark/$(RUN)
RUN_DEFINE := $(if $(filter validation,$(RUN)),VALIDATION_RUN,PERFORMANCE_RUN)
BASEFLAGS := -march=rv32im_zicsr_zifencei -mabi=ilp32 -O2 -ffreestanding -fno-builtin -fno-common -nostdlib -nostartfiles
CFLAGS := $(BASEFLAGS) -I. -I$(ROOT)/09_refs/coremark -D$(RUN_DEFINE)=1 -DITERATIONS=$(ITERATIONS) -DCPU_HZ=$(CPU_HZ) -DTOTAL_DATA_SIZE=2000 -DFLAGS_STR='"$(BASEFLAGS) -D$(RUN_DEFINE)=1 -DITERATIONS=$(ITERATIONS) -DCPU_HZ=$(CPU_HZ) -DTOTAL_DATA_SIZE=2000"'
CORE := $(addprefix $(ROOT)/09_refs/coremark/,core_main.c core_list_join.c core_matrix.c core_state.c core_util.c)
.PHONY: all clean
all:
	mkdir -p $(ROOT)/07_runs/coremark
	$(TOOLCHAIN)gcc $(CFLAGS) -T ../bringup/linker.ld startup.S $(CORE) core_portme.c core_portme_print.c -Wl,-Map,$(OUT).map -lgcc -o $(OUT).elf
	$(TOOLCHAIN)size $(OUT).elf
	$(TOOLCHAIN)objcopy -O binary $(OUT).elf $(OUT).bin
	python3 $(ROOT)/05_tools/bin_to_memh.py $(OUT).bin $(OUT).mem
clean:
	rm -f $(OUT).elf $(OUT).bin $(OUT).mem $(OUT).map

# Run both mandatory seed configurations with the same CPU/cache/RAM RTL.
.PHONY: simulator simulate
simulator:
	cd $(ROOT) && verilator --cc --exe --build -j 2 --top-module needle_soc -GCLK_HZ=$(CPU_HZ) -GBAUD=9000000 '-GINIT_FILE="07_runs/coremark/current.mem"' -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM -Wno-PINCONNECTEMPTY --Mdir 07_runs/coremark/obj_soc 01_rtl/cpu/*.sv 01_rtl/mem/*.sv 01_rtl/periph/*.sv 01_rtl/xnd/*.sv 01_rtl/soc/needle_soc.sv "$(abspath $(ROOT)/05_tools/sim/soc_run.cpp)"
simulate: simulator
	for run in performance validation; do $(MAKE) RUN=$$run all; cp $(ROOT)/07_runs/coremark/$$run.mem $(ROOT)/07_runs/coremark/current.mem; (cd $(ROOT) && 07_runs/coremark/obj_soc/Vneedle_soc) | tee $(ROOT)/07_runs/coremark/$$run.log; done
	cd $(ROOT) && python3 05_tools/sim/check_coremark.py
