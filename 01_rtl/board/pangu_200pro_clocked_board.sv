// Clocked physical top; pin names stay compatible with the carrier constraints.
`default_nettype none
module pangu_200pro_clocked_board #(
 parameter integer CLK_HZ=54000000,
 parameter integer BAUD=921600,
 parameter INIT_FILE="firmware/model_interactive.mem",
 parameter bit HARD_ADC=1
)(input wire clk_in,reset_in,key,uart_rx,output wire uart_tx,output wire [7:0]led);
 wire system_clk,pll_locked;
 nr_board_clock #(.CLK_HZ(CLK_HZ)) u_clock(.clk_27m(clk_in),.reset(~reset_in),
  .clk_system(system_clk),.locked(pll_locked));
 // Loss of lock asserts reset; board wrapper releases through its two-flop
 // reset synchronizer and startup hold only after the generated clock is ready.
 pangu_200pro_top #(.CLK_HZ(CLK_HZ),.BAUD(BAUD),.INIT_FILE(INIT_FILE),.HARD_ADC(HARD_ADC))u_board(
  .clk_in(system_clk),.reset_in(reset_in && pll_locked),.uart_rx(uart_rx),
  .uart_tx(uart_tx),.gpio_in({7'd0,key}),.led(led),.gpio_out());
endmodule
`default_nettype wire
