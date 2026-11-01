set_arch -family Logos2 -device PG2L200H -speedgrade -6 -package FBB676
gen_bit_stream -input_db_file {D:\FPGA_PDS\07_runs\development\resource_trials\integrated\full_model\cache_ram\place_route\pangu_200pro_clocked_board_pnr.adf} -scbv {High Voltage} -compress_bitstream true -done_time_slot T3 -gwen_time_slot T2 -grsn_time_slot T2 -gouten_time_slot T1 -force_to_run
