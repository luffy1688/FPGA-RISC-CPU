`timescale 1ns/1ps
`default_nettype none
// Minimal system smoke: firmware is loaded through soc_ram's INIT_FILE path.
// This keeps the testbench independent of RTL internal memory names.
module tb_needle_soc;
  logic clk=0, reset=1, uart_rx=1;
  logic [7:0] gpio_in=0;
  logic uart_tx, uart_tx_valid;
  logic [7:0] uart_tx_data, gpio_led, gpio_out;
  logic [31:0] timer_value, commit_pc, commit_data, dbg_pc;
  logic commit_valid; logic [4:0] commit_rd;
  integer commits=0;
  always #5 clk=~clk;
  needle_soc #(.INIT_FILE("02_tb/system/soc_program.mem"), .CACHE_ENABLE(1'b0)) dut(
    .clk,.reset,.uart_rx,.gpio_in,.uart_tx,.gpio_led,.uart_tx_valid,
    .uart_tx_data,.gpio_out,.timer_value,.commit_valid,.commit_pc,
    .commit_data,.commit_rd,.dbg_pc);
  always @(posedge clk) begin
    if (commit_valid) commits <= commits + 1;
    if (uart_tx_valid) $display("UART_ACCEPT t=%0t byte=0x%02x", $time, uart_tx_data);
  end
  initial begin
    repeat (4) @(posedge clk);
    reset <= 1'b0;
    repeat (220) @(posedge clk);
    if (gpio_led !== 8'h5a) $fatal(1, "GPIO smoke failed: got %02x", gpio_led);
    if (commits < 4) $fatal(1, "CPU made too few commits: %0d", commits);
    $display("PASS SoC gpio=%02x commits=%0d timer=%0d", gpio_led, commits, timer_value);
    $finish;
  end
endmodule
`default_nettype wire
