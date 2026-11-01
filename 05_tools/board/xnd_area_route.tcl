set taskDir D:/FPGA_PDS/07_runs/development/xnd_area_probe
cd $taskDir
set taskDb [file join $taskDir synthesize pangu_200pro_clocked_board_syn.adf]
set_arch -input_db_file $taskDb
add_constraint D:/FPGA_PDS/06_pango_active/pangu_200pro_board.fdc
dev_map -input_db_file $taskDb -force_to_run
pnr -force_to_run
report_timing
gen_bit_stream -scbv {High Voltage} -compress_bitstream true -force_to_run
