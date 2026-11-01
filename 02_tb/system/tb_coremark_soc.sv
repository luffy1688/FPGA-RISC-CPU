`timescale 1ns/1ps
`default_nettype none
module tb_coremark_soc;
  logic clk=0,reset=1; always #5 clk=~clk;
  wire uart_tx,uart_tx_valid,commit_valid;
  wire [7:0] uart_tx_data,gpio_led,gpio_out;
  wire [31:0] timer_value,commit_pc,commit_data,dbg_pc;
  wire [4:0] commit_rd;
  // Accelerated SERIAL OUTPUT only; timed algorithms use identical CPU/cache/RAM.
  needle_soc #(.INIT_FILE("07_runs/coremark/current.mem"),.CLK_HZ(27000000),.BAUD(9000000)) dut(
    .clk,.reset,.uart_rx(1'b1),.gpio_in(8'd0),.uart_tx,.gpio_led,.uart_tx_valid,.uart_tx_data,
    .gpio_out,.timer_value,.commit_valid,.commit_pc,.commit_data,.commit_rd,.dbg_pc);
  integer cycles=0;
  initial begin repeat(5) @(posedge clk); @(negedge clk); reset=0; end
  always @(posedge clk) if(!reset) begin
    cycles<=cycles+1;
    if(uart_tx_valid) $write("%c",uart_tx_data);
    if(gpio_led==8'hee) $fatal(1,"CoreMark trap pc=%x cause=%x mepc=%x",dbg_pc,dut.u_cpu.csr.mcause,dut.u_cpu.csr.mepc);
    if(gpio_led==8'hc0) begin $display("\nCOREMARK_DONE sim_cycles=%0d",cycles); $finish; end
    if(cycles>=20000000) $fatal(1,"CoreMark timeout pc=%x",dbg_pc);
  end
endmodule
`default_nettype wire
