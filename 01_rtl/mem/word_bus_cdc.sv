// word_bus_cdc: one word request crosses between unrelated clock domains.
// "CDC" means clock-domain crossing. Only request/acknowledgment toggles pass
// through two flip-flop synchronizers. Multi-bit data is a held mailbox: the
// sender locks it BEFORE its toggle and keeps it fixed until acknowledgment.
// Both domains must share reset. A source-only or destination-only reset is
// unsupported, because it can destroy knowledge of an outstanding request.
`default_nettype none
module word_bus_cdc(
  input logic src_clk, dst_clk, reset,
  input logic src_valid, src_write,
  input logic [31:0] src_addr, src_wdata,
  input logic [3:0] src_wstrb,
  output logic src_ready, src_error,
  output logic [31:0] src_rdata,
  output logic src_busy,
  output logic dst_valid, dst_write,
  output logic [31:0] dst_addr, dst_wdata,
  output logic [3:0] dst_wstrb,
  input logic dst_ready, dst_error,
  input logic [31:0] dst_rdata
);
  // ADS subset: use explicit state constants instead of an enum.
  localparam logic [1:0] SRC_IDLE=2'd0, SRC_WAIT=2'd1, SRC_RESPONSE=2'd2;
  logic [1:0] src_state;
  logic request_toggle, acknowledge_toggle, active_toggle;
  logic held_write;
  logic [31:0] held_addr, held_wdata;
  logic [3:0] held_wstrb;
  logic [31:0] held_rdata;
  logic held_error;
  // Attributes state design intent; actual PDS synchronizer placement and CDC
  // timing constraints must still be verified for the selected device/tool.
  (* ASYNC_REG = "TRUE" *) logic [1:0] src_reset_pipe, dst_reset_pipe;
  (* ASYNC_REG = "TRUE" *) logic ack_meta, ack_sync;
  (* ASYNC_REG = "TRUE" *) logic req_meta, req_sync;

  // Shared reset asserts asynchronously, releases locally after two clocks.
  always_ff @(posedge src_clk or posedge reset)
    if(reset) src_reset_pipe<=2'b11;
    else src_reset_pipe<={src_reset_pipe[0],1'b0};
  always_ff @(posedge dst_clk or posedge reset)
    if(reset) dst_reset_pipe<=2'b11;
    else dst_reset_pipe<={dst_reset_pipe[0],1'b0};

  assign src_ready = src_state==SRC_RESPONSE && !src_reset_pipe[1];
  assign src_busy = src_state!=SRC_IDLE;

  always_ff @(posedge src_clk or posedge reset) begin
    if(reset) begin
      src_state<=SRC_IDLE;request_toggle<=0;
      held_write<=0;held_addr<=0;held_wdata<=0;held_wstrb<=0;
      ack_meta<=0;ack_sync<=0;src_error<=0;src_rdata<=0;
    end else if(!src_reset_pipe[1]) begin
      ack_meta<=acknowledge_toggle;
      ack_sync<=ack_meta;
      case(src_state)
        SRC_IDLE: if(src_valid) begin
          held_write<=src_write;held_addr<=src_addr;
          held_wdata<=src_wdata;held_wstrb<=src_wstrb;
          request_toggle<=!request_toggle;
          src_state<=SRC_WAIT;
        end
        SRC_WAIT: if(ack_sync==request_toggle) begin
          // The response mailbox has been stable throughout ACK synchronization.
          src_rdata<=held_rdata;src_error<=held_error;
          src_state<=SRC_RESPONSE;
        end
        SRC_RESPONSE: src_state<=SRC_IDLE;
        default: src_state<=SRC_IDLE;
      endcase
    end
  end

  always_ff @(posedge dst_clk or posedge reset) begin
    if(reset) begin
      req_meta<=0;req_sync<=0;acknowledge_toggle<=0;active_toggle<=0;
      dst_valid<=0;dst_write<=0;dst_addr<=0;dst_wdata<=0;dst_wstrb<=0;
      held_rdata<=0;held_error<=0;
    end else if(!dst_reset_pipe[1]) begin
      req_meta<=request_toggle;
      req_sync<=req_meta;
      if(!dst_valid && req_sync!=acknowledge_toggle) begin
        // All request bits were latched before request_toggle changed and have
        // stayed fixed for the synchronizer delay. Capture them together.
        dst_write<=held_write;dst_addr<=held_addr;
        dst_wdata<=held_wdata;dst_wstrb<=held_wstrb;
        active_toggle<=req_sync;dst_valid<=1;
      end else if(dst_valid && dst_ready) begin
        held_rdata<=dst_rdata;held_error<=dst_error;
        acknowledge_toggle<=active_toggle;dst_valid<=0;
      end
    end
  end
endmodule
`default_nettype wire
