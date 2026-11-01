`timescale 1ns/1ps
`default_nettype none
// Checks real serial bits with BOTH caches and the predictor enabled.
module tb_pangu_200pro_board;
  logic clk_in=0, reset_in=1, key=1, uart_rx=1;
  wire uart_tx; wire [7:0] led;
  logic [7:0] received;
  integer frames=0;
  localparam integer BIT_CYCLES=27000000/115200;
  always #18.5185 clk_in=~clk_in;
  pangu_200pro_board #(.INIT_FILE("06_pango/firmware/board_smoke.mem"), .HARD_ADC(0)) dut(.clk_in,.reset_in,.key,.uart_rx,.uart_tx,.led);
  task automatic receive_frame;
    begin
      @(negedge uart_tx);
      repeat(BIT_CYCLES/2) @(posedge clk_in);
      if(uart_tx!==0) $fatal(1,"UART start bit");
      for(integer b=0;b<8;b=b+1) begin
        repeat(BIT_CYCLES) @(posedge clk_in);
        received[b]=uart_tx;
      end
      repeat(BIT_CYCLES) @(posedge clk_in);
      if(uart_tx!==1) $fatal(1,"UART stop bit");
      if(received!==8'h41) $fatal(1,"UART byte %x",received);
      frames=frames+1;
    end
  endtask
  initial begin
    // No manual reset on first power-up: startup reset must initialize the CPU.
    receive_frame();
    if(led!==8'h5a) $fatal(1,"LED pattern %x",led);
    key=0;
    repeat(5) @(posedge clk_in);
    if(dut.u_board.gpio_sync!==0) $fatal(1,"key synchronization");
    // Assert the KEY0 reset away from a clock edge, then repeat the full frame.
    @(negedge clk_in); #2 reset_in=0;
    repeat(6) @(posedge clk_in);
    if(led!==0 || uart_tx!==1) $fatal(1,"reset outputs");
    @(negedge clk_in); #2 reset_in=1;
    receive_frame();
    if(led!==8'h5a || frames!=2) $fatal(1,"reset recovery");
    $display("PASS BOARD: power-on/reset, 27MHz UART 8N1 byte=41, LED=5a, caches+predictor enabled");
    $finish;
  end
  initial begin repeat(15000) @(posedge clk_in); $fatal(1,"board simulation timeout"); end
endmodule
`default_nettype wire
