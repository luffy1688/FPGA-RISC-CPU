// UART = serial link: one start bit, eight data bits, one stop bit (8N1).
// Sixteen-byte receive FIFO absorbs short CPU CRC/interrupt service gaps.
// Software still observes RX_VALID/data and the sticky overrun indication.
`default_nettype none
module uart #(
  parameter integer CLK_HZ=50000000,
  parameter integer BAUD=115200
)(
  input logic clk,reset,rx,
  output logic tx,
  input logic tx_valid,
  input logic [7:0] tx_data,
  output logic tx_ready,
  output logic rx_valid,
  output logic [7:0] rx_data,
  input logic rx_ready,
  output logic rx_overrun
);
  localparam integer DIV=((CLK_HZ+BAUD/2)/BAUD<2)?2:(CLK_HZ+BAUD/2)/BAUD;
  localparam integer COUNT_BITS=$clog2(DIV+1);
  // Integer constants with explicit slices keep ADS and simulators width-exact.
  localparam integer COUNT_RELOAD=DIV-1;
  localparam integer START_RELOAD=DIV/2-1;
  logic tx_busy;
  logic [9:0] tx_frame;
  logic [3:0] tx_bit;
  logic [COUNT_BITS-1:0] tx_count,rx_count;
  logic rx_meta,rx_sync;
  logic [7:0] rx_shift;
  logic [2:0] rx_bit;
  // ADS subset: explicit constants replace the unsupported enum type.
  localparam logic [1:0] R_IDLE=2'd0, R_START=2'd1, R_DATA=2'd2, R_STOP=2'd3;
  logic [1:0] rx_state;
  logic [7:0] rx_fifo [0:15];
  logic [3:0] rx_head,rx_tail;
  logic [4:0] rx_used;
  wire rx_pop=rx_ready && rx_used!=0;
  wire rx_push=rx_state==R_STOP && rx_count==0 && rx_sync;
  assign rx_valid=rx_used!=0;
  assign rx_data=rx_fifo[rx_head];
  always_ff @(posedge clk) begin
    if(reset) begin rx_head<=0;rx_tail<=0;rx_used<=0;rx_overrun<=0;end
    else begin
      if(rx_pop)rx_head<=rx_head+1'b1;
      if(rx_push && (rx_used<16 || rx_pop)) begin
        rx_fifo[rx_tail]<=rx_shift;rx_tail<=rx_tail+1'b1;
        if(!rx_pop)rx_used<=rx_used+1'b1;
      end else if(rx_pop)rx_used<=rx_used-1'b1;
      if(rx_push && rx_used==16 && !rx_pop)rx_overrun<=1;
    end
  end
  assign tx_ready=!tx_busy;
  assign tx=tx_busy ? tx_frame[tx_bit] : 1'b1;

  always_ff @(posedge clk) begin
    if(reset) begin
      tx_busy<=0; tx_frame<=10'h3ff; tx_bit<=0; tx_count<=0;
    end else if(!tx_busy) begin
      if(tx_valid) begin
        tx_frame<={1'b1,tx_data,1'b0}; tx_bit<=0;
        tx_count<=COUNT_RELOAD[COUNT_BITS-1:0]; tx_busy<=1;
      end
    end else if(tx_count==0) begin
      tx_count<=COUNT_RELOAD[COUNT_BITS-1:0];
      if(tx_bit==9) tx_busy<=0;
      else tx_bit<=tx_bit+1;
    end else tx_count<=tx_count-1;
  end

  // Two flip-flops reduce the chance that an asynchronous RX edge reaches logic.
  always_ff @(posedge clk) begin
    if(reset) begin rx_meta<=1;rx_sync<=1;end
    else begin rx_meta<=rx;rx_sync<=rx_meta;end
  end
  always_ff @(posedge clk) begin
    if(reset) begin
      rx_state<=R_IDLE; rx_count<=0; rx_bit<=0; rx_shift<=0;

    end else begin

      case(rx_state)
        R_IDLE: if(!rx_sync) begin
          rx_count<=START_RELOAD[COUNT_BITS-1:0]; rx_state<=R_START;
        end
        R_START: if(rx_count==0) begin
          if(!rx_sync) begin
            rx_count<=COUNT_RELOAD[COUNT_BITS-1:0]; rx_bit<=0; rx_state<=R_DATA;
          end else rx_state<=R_IDLE;
        end else rx_count<=rx_count-1;
        R_DATA: if(rx_count==0) begin
          rx_shift[rx_bit]<=rx_sync; rx_count<=COUNT_RELOAD[COUNT_BITS-1:0];
          if(rx_bit==7) rx_state<=R_STOP;
          else rx_bit<=rx_bit+1;
        end else rx_count<=rx_count-1;
        R_STOP: if(rx_count==0) begin
          // A bad stop bit discards the malformed frame.
          rx_state<=R_IDLE;
        end else rx_count<=rx_count-1;
        default: rx_state<=R_IDLE;
      endcase
    end
  end
endmodule
`default_nettype wire
