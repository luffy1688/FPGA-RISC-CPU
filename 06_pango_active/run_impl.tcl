set taskRoot D:/FPGA_PDS
set taskDir D:/FPGA_PDS/06_pango_active
cd $taskDir
set_arch -family Logos2 -device PG2L200H -speedgrade -6 -package FBB676
add_design [file join $taskRoot 01_rtl/cpu/rv32i_pkg.sv]
add_design [file join $taskRoot 01_rtl/board/pangu_200pro_clocked_board.sv]
add_design [file join $taskRoot 01_rtl/board/nr_board_clock.sv]
add_design [file join $taskRoot 01_rtl/board/pangu_200pro_top.sv]
add_design [file join $taskRoot 01_rtl/cpu/rv32_divider.sv]
add_design [file join $taskRoot 01_rtl/cpu/rv32_predictor.sv]
add_design [file join $taskRoot 01_rtl/cpu/rv32i_core.sv]
add_design [file join $taskRoot 01_rtl/cpu/rv32i_csr.sv]
add_design [file join $taskRoot 01_rtl/cpu/rv32i_regfile.sv]
add_design [file join $taskRoot 01_rtl/mem/rv32_cache.sv]
add_design [file join $taskRoot 01_rtl/mem/soc_ram.sv]
add_design [file join $taskRoot 01_rtl/periph/pango_temperature.sv]
add_design [file join $taskRoot 01_rtl/periph/pwm.sv]
add_design [file join $taskRoot 01_rtl/periph/temperature_sampler.sv]
add_design [file join $taskRoot 01_rtl/periph/uart.sv]
add_design [file join $taskRoot 01_rtl/soc/needle_soc.sv]
add_design [file join $taskRoot 01_rtl/xnd/xnd_dot4.sv]
add_design [file join $taskRoot 01_rtl/xnd/xnd_engine.sv]
add_design [file join $taskRoot 01_rtl/xnd/postprocess_fusion.sv]
add_design [file join $taskRoot 01_rtl/xnd/xnd_mmio.sv]
add_design [file join $taskRoot 01_rtl/xnd/dual_dma_arbiter.sv]
add_design [file join $taskRoot 01_rtl/xnd/semantic_cache.sv]
add_design [file join $taskRoot 01_rtl/xnd/semantic_cache_mmio.sv]
add_constraint [file join $taskDir pangu_200pro_board.fdc]
compile -system_verilog -top_module pangu_200pro_clocked_board -force_to_run
synthesize -ads -selected_syn_tool_opt 2 -force_to_run
dev_map -force_to_run
pnr -force_to_run
report_timing
gen_bit_stream -scbv {High Voltage} -compress_bitstream true -done_time_slot T3 -gwen_time_slot T2 -grsn_time_slot T2 -gouten_time_slot T1 -force_to_run
