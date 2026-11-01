ROOT := ../..
TOOLCHAIN := /opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-
CFLAGS := -march=rv32im_zicsr_zifencei -mabi=ilp32 -nostdlib -nostartfiles -ffreestanding -O2
OUT := $(ROOT)/07_runs/sim/cpu_acceptance.elf
SRC := startup.s cpu_acceptance.S main.c linker.ld
.PHONY: all clean
all: $(OUT)
$(OUT): $(SRC)
	mkdir -p $(ROOT)/07_runs/sim
	$(TOOLCHAIN)gcc $(CFLAGS) -T linker.ld startup.s cpu_acceptance.S main.c -o $@
	$(TOOLCHAIN)objcopy -O binary $@ $(ROOT)/07_runs/sim/cpu_acceptance.bin
	python3 $(ROOT)/05_tools/bin_to_memh.py $(ROOT)/07_runs/sim/cpu_acceptance.bin $(ROOT)/07_runs/sim/cpu_acceptance.hex
clean:
	rm -f $(ROOT)/07_runs/sim/cpu_acceptance.elf $(ROOT)/07_runs/sim/cpu_acceptance.bin $(ROOT)/07_runs/sim/cpu_acceptance.hex
