// Physical 200Pro+ top: only pins confirmed by the manufacturer's examples.
// key is sampled as GPIO bit 0; reset_in on C22 is active low.
`default_nettype none
module pangu_200pro_board #(parameter INIT_FILE="firmware/model_interactive.mem", parameter bit HARD_ADC=1) (
  input wire clk_in, reset_in, key, uart_rx,
  output wire uart_tx,
  output wire [7:0] led
);
  pangu_200pro_top #(.CLK_HZ(27000000), .INIT_FILE(INIT_FILE), .HARD_ADC(HARD_ADC)) u_board (
    .clk_in(clk_in), .reset_in(reset_in), .uart_rx(uart_rx), .uart_tx(uart_tx),
    .gpio_in({7'd0,key}), .led(led), .gpio_out()
  );
endmodule
`default_nettype wire
