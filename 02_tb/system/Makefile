ROOT := ../..
SIM := $(ROOT)/07_runs/sim
CPU_RTL := $(ROOT)/01_rtl/cpu/*.sv
MEM_RTL := $(ROOT)/01_rtl/mem/*.sv
PERIPH_RTL := $(ROOT)/01_rtl/periph/*.sv
XND_RTL := $(ROOT)/01_rtl/xnd/*.sv
SOC_RTL := $(ROOT)/01_rtl/soc/needle_soc.sv
.PHONY: all cpu soc xnd_soc clean
all: cpu soc xnd_soc
cpu:
	make -C $(ROOT)/03_sw/bringup
	mkdir -p $(SIM)
	iverilog -g2012 -s tb_rv32i_acceptance -o $(SIM)/cpu_acceptance.vvp $(CPU_RTL) tb_rv32i_acceptance.sv
	cd $(ROOT) && vvp 07_runs/sim/cpu_acceptance.vvp | tee 07_runs/sim/cpu_acceptance.log
soc:
	mkdir -p $(SIM)
	iverilog -g2012 -s tb_needle_soc -o $(SIM)/soc.vvp $(CPU_RTL) $(MEM_RTL) $(PERIPH_RTL) $(XND_RTL) $(SOC_RTL) tb_needle_soc.sv
	cd $(ROOT) && vvp 07_runs/sim/soc.vvp | tee 07_runs/sim/soc.log
xnd_soc:
	mkdir -p $(SIM)
	iverilog -g2012 -s tb_needle_soc_xnd -o $(SIM)/soc_xnd.vvp $(CPU_RTL) $(MEM_RTL) $(PERIPH_RTL) $(XND_RTL) $(SOC_RTL) tb_needle_soc_xnd.sv
	cd $(ROOT) && vvp 07_runs/sim/soc_xnd.vvp | tee 07_runs/sim/soc_xnd.log
clean:
	rm -f $(SIM)/soc.vvp $(SIM)/soc.log
