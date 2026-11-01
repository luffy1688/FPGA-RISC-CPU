set source_db D:/FPGA_PDS/07_runs/development/xnd_area_probe/synthesize/pangu_200pro_clocked_board_syn.adf
set_arch -input_db_file $source_db
add_fic D:/FPGA_PDS/06_pango_active_ila/pangu_200pro_ila.fic
dev_map -input_db_file $source_db -force_to_run
pnr -force_to_run
report_timing
gen_bit_stream -scbv {High Voltage} -compress_bitstream true -force_to_run
