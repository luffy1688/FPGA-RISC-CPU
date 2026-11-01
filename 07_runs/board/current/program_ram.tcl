cfg_set_tcl_break -flag true
cfg_connect -ip 127.0.0.1 -port 65420
cfg_set_cable_property -index 0 -freq 1Mhz
cfg_scan_chain
cfg_assign_file -file {D:/FPGA_PDS/06_pango_active/generate_bitstream/production.sbit} -device_index 0
cfg_set_device_property -device_index 0 -program 3
cfg_program -device_index 0
cfg_read_device_property -mode 3 -device_index 0
cfg_disconnect
cfg_close

