# 独立 IRQ 验收入口：make -f irq.mk irq-simulate；不覆盖 current.mem 或默认镜像。
.RECIPEPREFIX := |
SHELL := /bin/bash
.SHELLFLAGS := -e -o pipefail -c
ROOT := ../..
TOOLCHAIN ?= /opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-
OUT := $(ROOT)/07_runs/model
CPU_HZ ?= 27000000
CORE_ITERATIONS ?= 300
CFLAGS := -DNR_PLATFORM_CLOCK_HZ=$(CPU_HZ) -DNR_COREMARK_ITERATIONS=$(CORE_ITERATIONS) -march=rv32im_zicsr_zifencei -mabi=ilp32 -O2 -std=c99 -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-common -ffunction-sections -fdata-sections -nostdlib -nostartfiles
CORE_DIR := $(ROOT)/09_refs/coremark
CORE_NAMES := core_main core_list_join core_matrix core_state core_util core_portme core_portme_print
CORE_OBJ := $(addprefix $(OUT)/coremark/,$(addsuffix .o,$(CORE_NAMES)))
SRC := irq_startup.S irq_selftest.c coremark_tool.c tensor_plan.c byte_tool_model.c byte_tool_xnd.c tool_dispatch.c ../platform/needle_platform.c
.PHONY: irq-image irq-simulator irq-simulate
irq-image: $(OUT)/irq.mem
$(CORE_OBJ): $(OUT)/build_config
|$(MAKE) -f Makefile OUT=$(OUT) CPU_HZ=$(CPU_HZ) CORE_ITERATIONS=$(CORE_ITERATIONS) $@
$(OUT)/irq.elf: $(CORE_OBJ) $(SRC) byte_tool_model.h byte_tool_xnd.h byte_model_data.h tool_dispatch.h ../platform/needle_platform.h ../platform/needle_pmu.h ../bringup/linker.ld ../xnd_runtime/xnd_mmio.h irq.mk $(OUT)/build_config
|mkdir -p $(OUT)
|$(TOOLCHAIN)gcc $(CFLAGS) -I../coremark -I$(CORE_DIR) -T ../bringup/linker.ld $(SRC) $(CORE_OBJ) -Wl,--gc-sections,-Map,$(OUT)/irq.map -lgcc -o $@
|$(TOOLCHAIN)size $@
$(OUT)/irq.mem: $(OUT)/irq.elf
|$(TOOLCHAIN)objcopy -O binary $< $(OUT)/irq.bin
|python3 $(ROOT)/05_tools/bin_to_memh.py $(OUT)/irq.bin $@
irq-simulator:
|cd $(ROOT) && verilator --cc --exe --build -j 2 --top-module needle_soc -CFLAGS "-DNR_SIM_CLK_HZ=$(CPU_HZ) -DNR_SIM_BAUD=1000000" -GCLK_HZ=$(CPU_HZ) -GBAUD=1000000 '-GINIT_FILE="07_runs/model/irq.mem"' -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM -Wno-PINCONNECTEMPTY --Mdir 07_runs/model/obj_irq 01_rtl/cpu/*.sv 01_rtl/mem/*.sv 01_rtl/periph/*.sv 01_rtl/xnd/*.sv 01_rtl/soc/needle_soc.sv "$(abspath $(ROOT)/05_tools/sim/soc_run.cpp)"
irq-simulate: irq-image irq-simulator
|(cd $(ROOT) && 07_runs/model/obj_irq/Vneedle_soc MODEL_IRQ_DONE 40000000) | tee $(OUT)/irq.log
|cd $(ROOT) && python3 05_tools/sim/check_model_irq.py

.PHONY: FORCE_CONFIG
FORCE_CONFIG:
$(OUT)/build_config: FORCE_CONFIG
|$(MAKE) -f Makefile OUT=$(OUT) CPU_HZ=$(CPU_HZ) CORE_ITERATIONS=$(CORE_ITERATIONS) $(OUT)/build_config
