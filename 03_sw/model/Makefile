.RECIPEPREFIX := |
SHELL := /bin/bash
.SHELLFLAGS := -e -o pipefail -c
ROOT := /work/LUO/NeedleRV-X
TOOLCHAIN ?= /opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-
OUT ?= $(ROOT)/07_runs/model
CPU_HZ ?= 40500000
UART_BAUD ?= 921600
CORE_ITERATIONS ?= 1200
CFLAGS := -DNR_PLATFORM_CLOCK_HZ=$(CPU_HZ) -DNR_UART_BAUD=$(UART_BAUD) -DNR_COREMARK_ITERATIONS=$(CORE_ITERATIONS) -march=rv32im_zicsr_zifencei -mabi=ilp32 -mstrict-align -O2 -std=c99 -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-common -ffunction-sections -fdata-sections -nostdlib -nostartfiles
MODEL_FLAGS ?= -DNR_OPT_Q_REUSE=1 -DNR_OPT_AV4=1 -DNR_OPT_POST_FUSE=1 -DNR_OPT_SCORE_CACHE=1 -DNR_OPT_V_CACHE=1 -DNR_MODEL_PROFILE=0 -DNR_OPT_XND_POSTPROCESS=1
CORE_DIR := $(ROOT)/09_refs/coremark
CORE_NAMES := core_main core_list_join core_matrix core_state core_util core_portme core_portme_print
CORE_OBJ := $(addprefix $(OUT)/coremark/,$(addsuffix .o,$(CORE_NAMES)))
CORE_FLAGS := $(filter-out -Wall -Wextra -Werror,$(CFLAGS)) -I../coremark -I$(CORE_DIR) -DNR_COREMARK_LIBRARY=1 -DPERFORMANCE_RUN=1 -DITERATIONS=$(CORE_ITERATIONS) -DCPU_HZ=$(CPU_HZ) -DTOTAL_DATA_SIZE=2000 -DFLAGS_STR='"RV32IM O2 library $(CORE_ITERATIONS) iterations"'
SRC := startup.S main.c coremark_tool.c tensor_plan.c byte_tool_model.c byte_tool_xnd.c semantic_xnd.c semantic_cached.c tool_dispatch.c link_protocol.c ../platform/needle_platform.c
.PHONY: all host alignment simulator simulate
all: $(OUT)/selftest.mem $(OUT)/interactive.mem
$(OUT)/coremark/%.o: $(CORE_DIR)/%.c ../coremark/core_portme.h Makefile $(OUT)/build_config
|mkdir -p $(OUT)/coremark
|$(TOOLCHAIN)gcc $(CORE_FLAGS) $(if $(filter core_main,$*),-Dmain=nr_coremark_entry,) -c $< -o $@
$(OUT)/coremark/core_portme.o: ../coremark/core_portme.c ../coremark/core_portme.h ../coremark/fixed_ratio.h ../platform/needle_pmu.h Makefile $(OUT)/build_config
|mkdir -p $(OUT)/coremark
|$(TOOLCHAIN)gcc $(CORE_FLAGS) -c $< -o $@
$(OUT)/coremark/core_portme_print.o: ../coremark/core_portme_print.c ../coremark/core_portme.h Makefile $(OUT)/build_config
|mkdir -p $(OUT)/coremark
|$(TOOLCHAIN)gcc $(CORE_FLAGS) -c $< -o $@
$(OUT)/%.elf: $(CORE_OBJ) $(SRC) byte_tool_model.h byte_tool_xnd.h semantic_xnd.h semantic_cached.h byte_model_data.h byte_engram_data.h byte_engram.c.inc byte_context_data.h byte_semantic_data.h byte_context.c.inc byte_fusion.c.inc tool_dispatch.h ../platform/needle_platform.h ../platform/needle_pmu.h ../bringup/linker.ld ../xnd_runtime/xnd_mmio.h Makefile $(OUT)/build_config
|mkdir -p $(dir $@)
|$(TOOLCHAIN)gcc $(CFLAGS) $(MODEL_FLAGS) $(if $(filter selftest,$*),-DNR_MODEL_SELFTEST=1,) -I../coremark -I$(CORE_DIR) -T ../bringup/linker.ld $(SRC) $(CORE_OBJ) -Wl,--gc-sections,-Map,$(OUT)/$*.map -lgcc -o $@
|$(TOOLCHAIN)size $@
$(OUT)/%.mem: $(OUT)/%.elf
|$(TOOLCHAIN)objcopy -O binary $< $(OUT)/$*.bin
|python3 $(ROOT)/05_tools/bin_to_memh.py $(OUT)/$*.bin $@
.PRECIOUS: $(OUT)/%.elf
.SECONDARY: $(CORE_OBJ)
host:
|gcc -std=c99 -O2 -Wall -Wextra -Werror $(MODEL_FLAGS) byte_tool_model.c host_demo.c -o $(ROOT)/04_model/golden/model_demo
alignment: host
|cd $(ROOT) && python3 04_model/golden/compare_c_reference.py
simulator:
|cd $(ROOT) && verilator --cc --exe --build -j 2 --top-module needle_soc -CFLAGS "-DNR_SIM_CLK_HZ=$(CPU_HZ) -DNR_SIM_BAUD=1000000" -GCLK_HZ=$(CPU_HZ) -GBAUD=1000000 '-GINIT_FILE="07_runs/model/current.mem"' -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM -Wno-PINCONNECTEMPTY --Mdir 07_runs/model/obj_soc 01_rtl/cpu/*.sv 01_rtl/mem/*.sv 01_rtl/periph/*.sv 01_rtl/xnd/*.sv 01_rtl/soc/needle_soc.sv "$(abspath $(ROOT)/05_tools/sim/soc_run.cpp)"
simulate: all simulator host
|cp $(OUT)/selftest.mem $(OUT)/current.mem
|(cd $(ROOT) && 07_runs/model/obj_soc/Vneedle_soc MODEL_DONE 2000000000) | tee $(OUT)/selftest.log
|cd $(ROOT) && python3 05_tools/sim/check_model.py

.PHONY: uart-simulate
uart-simulate: all simulator host
|cp $(OUT)/interactive.mem $(OUT)/current.mem
|(cd $(ROOT) && 07_runs/model/obj_soc/Vneedle_soc MODEL_UART 1000000000) | tee $(OUT)/interactive.log
|cd $(ROOT) && python3 05_tools/sim/check_model_uart.py

.PHONY: host-acceptance board-image
host-acceptance:
|mkdir -p $(OUT)
|gcc -std=c99 -O2 -Wall -Wextra -Werror $(MODEL_FLAGS) byte_tool_model.c host_acceptance.c -o $(OUT)/host_acceptance
|$(OUT)/host_acceptance | tee $(OUT)/host_acceptance.log
board-image: $(OUT)/interactive.mem
|mkdir -p $(ROOT)/06_pango_active/firmware
|cp $(OUT)/interactive.mem $(ROOT)/06_pango_active/firmware/model_interactive.mem

# profile是独立诊断镜像：全关候选开关，只对粗粒度阶段读计数器。
.PHONY: profile
$(OUT)/optimization/profile.elf: MODEL_FLAGS := -DNR_OPT_Q_REUSE=0 -DNR_OPT_AV4=0 -DNR_OPT_POST_FUSE=0 -DNR_MODEL_PROFILE=1 -DNR_MODEL_SELFTEST=1
profile: $(OUT)/optimization/profile.mem
|cp $(OUT)/optimization/profile.mem $(OUT)/current.mem
|(cd $(ROOT) && 07_runs/model/obj_soc/Vneedle_soc MODEL_DONE 2000000000) > $(OUT)/optimization/profile.log
|cat $(OUT)/optimization/profile.log

# Configuration changes must rebuild objects; this is a build dependency,
# not a source-hash audit or duplicate backup.
.PHONY: FORCE_CONFIG
FORCE_CONFIG:
$(OUT)/build_config: FORCE_CONFIG
|mkdir -p $(OUT)
|printf '%s\n' 'CPU_HZ=$(CPU_HZ)' 'UART_BAUD=$(UART_BAUD)' 'CORE_ITERATIONS=$(CORE_ITERATIONS)' 'MODEL_FLAGS=$(MODEL_FLAGS)' > $(OUT)/build_config.tmp
|if cmp -s $(OUT)/build_config.tmp $@; then rm $(OUT)/build_config.tmp; else mv $(OUT)/build_config.tmp $@; fi
