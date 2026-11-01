.RECIPEPREFIX := |
SHELL := /bin/bash
.SHELLFLAGS := -e -o pipefail -c
ROOT := ../..
TOOLCHAIN ?= /opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-
OUT := $(ROOT)/07_runs/ddr
CFLAGS := -march=rv32im_zicsr_zifencei -mabi=ilp32 -O2 -std=c99 -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-common -nostdlib -nostartfiles
.PHONY: all
all: $(OUT)/bringup.mem $(OUT)/fault.mem
$(OUT)/%.elf: startup.S main.c ../bringup/linker.ld ../xnd_runtime/xnd_mmio.h Makefile
|mkdir -p $(OUT)
|$(TOOLCHAIN)gcc $(CFLAGS) $(if $(filter fault,$*),-DNR_DDR_FAULT_TEST=1,) -T ../bringup/linker.ld startup.S main.c -Wl,-Map,$(OUT)/$*.map -lgcc -o $@
|$(TOOLCHAIN)size $@
$(OUT)/%.mem: $(OUT)/%.elf
|$(TOOLCHAIN)objcopy -O binary $< $(OUT)/$*.bin
|python3 $(ROOT)/05_tools/bin_to_memh.py $(OUT)/$*.bin $@
.PRECIOUS: $(OUT)/%.elf
