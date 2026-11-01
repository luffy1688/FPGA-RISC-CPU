// CPU-issued XND GEMV integration smoke. The high-half words model AI workspace.
`timescale 1ns/1ps
`default_nettype none
module tb_needle_soc_xnd;
  logic clk=0, reset=1; always #5 clk=~clk;
  logic uart_rx=1, uart_tx; logic [7:0] gpio_in=0, gpio_led;
  logic uart_tx_valid; logic [7:0] uart_tx_data; logic [31:0] timer_value;
  logic commit_valid; logic [31:0] commit_pc,commit_data,dbg_pc; logic [4:0] commit_rd;
  integer cycles, commit_count;
  needle_soc #(.INIT_FILE("02_tb/system/soc_program_xnd.mem")) dut(
    .clk,.reset,.uart_rx,.gpio_in,.uart_tx,.gpio_led,
    .uart_tx_valid,.uart_tx_data,.gpio_out(),
    .timer_value,.commit_valid,.commit_pc,.commit_data,.commit_rd,.dbg_pc);
  initial begin
    #1;
    // activation = [1..8], packed INT4 weights = eight times +1, result = 36.
    dut.u_ram.mem[16'h8000] = 32'h04030201;
    dut.u_ram.mem[16'h8001] = 32'h08070605;
    dut.u_ram.mem[16'h8002] = 32'h11111111;
    dut.u_ram.mem[16'h8003] = 32'd0;
    repeat(2) @(posedge clk); reset<=0;
    for(cycles=0; cycles<50000; cycles=cycles+1) begin
      @(posedge clk);
      if(gpio_led==8'd36) begin
        $display("PASS CPU-XND GEMV result=%0d cycles=%0d commits=%0d",
                 gpio_led,cycles,commit_count);
        $finish;
      end
    end
    $fatal(1,"CPU-XND TIMEOUT gpio=%0d pc=%08x",gpio_led,dbg_pc);
  end
  always_ff @(posedge clk) begin
    if(reset) commit_count<=0;
    else if(commit_valid) commit_count<=commit_count+1;
  end
endmodule
`default_nettype wire
