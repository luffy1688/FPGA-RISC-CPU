// Low-congestion board image used for first physical bring-up.
// It keeps the RV32I CPU, UART, GPIO/PWM and BRAM image, while disabling
// the optional XND accelerator, cache and ADC so the first .sbit can route
// reliably. The full Needle/XND image remains in pangu_200pro_board.sv.
`default_nettype none
module pangu_200pro_smoke #(parameter INIT_FILE="firmware/board_smoke.mem") (
  input wire clk_in, reset_in, key, uart_rx,
  output wire uart_tx,
  output wire [7:0] led
);
  pangu_200pro_top #(
    .CLK_HZ(27000000), .BAUD(115200), .INIT_FILE(INIT_FILE),
    .CACHE_ENABLE(1'b0), .PREDICT_ENABLE(1'b0),
    .XND_ENABLE(1'b0), .HARD_ADC(1'b0)
  ) u_board (
    .clk_in(clk_in), .reset_in(reset_in), .uart_rx(uart_rx), .uart_tx(uart_tx),
    .gpio_in({7'd0,key}), .led(led), .gpio_out()
  );
endmodule
`default_nettype wire
