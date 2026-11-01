// Board-neutral handoff wrapper for the Pangu 200Pro+ carrier.
// The final PDS project must map these logical ports with the official
// PG2L200H-6IFBB676 constraint file. No board pin number is encoded here.
`default_nettype none
module pangu_200pro_top #(
  parameter integer CLK_HZ = 27_000_000,
  parameter integer BAUD = 115_200,
  parameter bit CACHE_ENABLE = 1'b1,
  parameter bit HARD_ADC = 0,
  parameter bit PREDICT_ENABLE = 1'b1,
  parameter bit XND_ENABLE = 1'b1,
  parameter bit RESET_ACTIVE_LOW = 1'b1,
  parameter bit LED_ACTIVE_LOW = 1'b0,
  parameter INIT_FILE = "06_pango/firmware/board_smoke.mem"
)(
  input  logic       clk_in,
  input  logic       reset_in,
  input  logic       uart_rx,
  output logic       uart_tx,
  input  logic [7:0] gpio_in,
  output logic [7:0] led,
  output logic [7:0] gpio_out
);
  logic reset;
  logic [7:0] gpio_led;
  logic [7:0] gpio_out_soc;
  logic uart_tx_valid;
  logic [7:0] uart_tx_data;
  logic [31:0] timer_value, commit_pc, commit_data, dbg_pc;
  logic commit_valid;
  logic [4:0] commit_rd;

  // Optional DDR word bus is intentionally tied off in the default board
  // wrapper. The carrier has no HMIC/PHY port declaration here; a PDS design
  // that owns the vendor controller must provide these six signals explicitly.
  // Keeping the tie-off visible prevents floating inputs from changing the
  // normal BRAM-only board image while ENABLE_DDR remains at its default 0.
  logic ddr_req_valid, ddr_req_write;
  logic [31:0] ddr_req_addr, ddr_req_wdata, ddr_req_rdata;
  logic [3:0] ddr_req_wstrb;
  logic ddr_req_ready, ddr_req_error, ddr_available, ddr_fault, ddr_busy;
  assign ddr_req_ready = 1'b0;
  assign ddr_req_error = 1'b1;
  assign ddr_req_rdata = 32'd0;
  assign ddr_available = 1'b0;
  assign ddr_fault = 1'b0;
  assign ddr_busy = 1'b0;

  // External reset is asynchronous: assert immediately, release after two clocks.
  // The startup hold also guarantees reset when no button is pressed at power-up.
  wire reset_request = RESET_ACTIVE_LOW ? ~reset_in : reset_in;
  logic [1:0] reset_pipe = 2'b11;
  logic [7:0] startup_count = 8'd0;
  logic startup_hold = 1'b1;
  logic [7:0] gpio_meta, gpio_sync;
  always_ff @(posedge clk_in or posedge reset_request) begin
    if (reset_request) reset_pipe <= 2'b11;
    else reset_pipe <= {reset_pipe[0],1'b0};
  end
  always_ff @(posedge clk_in) begin
    if (reset_pipe[1]) begin startup_count <= 0; startup_hold <= 1; end
    else if (startup_hold) begin
      startup_count <= startup_count + 1'b1;
      if (&startup_count) startup_hold <= 0;
    end
    if (reset) begin gpio_meta <= 0; gpio_sync <= 0; end
    else begin gpio_meta <= gpio_in; gpio_sync <= gpio_meta; end
  end
  assign reset = reset_pipe[1] | startup_hold;
  assign led = LED_ACTIVE_LOW ? ~gpio_out_soc : gpio_out_soc;
  assign gpio_out = gpio_out_soc;

  needle_soc #(
    .INIT_FILE(INIT_FILE),
    .CLK_HZ(CLK_HZ),
    .BAUD(BAUD),
    .CACHE_ENABLE(CACHE_ENABLE),
    .PREDICT_ENABLE(PREDICT_ENABLE),
    .XND_ENABLE(XND_ENABLE),
    .HARD_ADC(HARD_ADC)
  ) u_soc (
    .clk(clk_in), .reset(reset), .uart_rx(uart_rx),
    .gpio_in(gpio_sync), .uart_tx(uart_tx), .gpio_led(gpio_led),
    .uart_tx_valid(uart_tx_valid), .uart_tx_data(uart_tx_data),
    .gpio_out(gpio_out_soc), .timer_value(timer_value),
    .commit_valid(commit_valid), .commit_pc(commit_pc),
    .commit_data(commit_data), .commit_rd(commit_rd), .dbg_pc(dbg_pc),
    .ddr_req_valid(ddr_req_valid), .ddr_req_write(ddr_req_write),
    .ddr_req_addr(ddr_req_addr), .ddr_req_wdata(ddr_req_wdata),
    .ddr_req_wstrb(ddr_req_wstrb), .ddr_req_ready(ddr_req_ready),
    .ddr_req_error(ddr_req_error), .ddr_req_rdata(ddr_req_rdata),
    .ddr_available(ddr_available), .ddr_fault(ddr_fault), .ddr_busy(ddr_busy)
  );
endmodule
`default_nettype wire
