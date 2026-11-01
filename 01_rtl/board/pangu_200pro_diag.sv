// Physical bring-up diagnostic: no CPU, firmware, RAM, cache or XND.
// KEY0 is observed, not used to hold this diagnostic in reset.
// Fixed LEDs prove output routing; LED0 is a clock heartbeat.
// UART reports raw pin states and valid/fault-qualified ADC raw data.
// This is a diagnostic image, never the complete competition implementation.
`default_nettype none
module pangu_200pro_diag #(
  parameter integer CLK_HZ=27000000,
  parameter integer REPORT_CYCLES=27000000,
  parameter integer HEARTBEAT_BIT=24,
  parameter bit HARD_ADC=1
)(
  input wire clk_in,reset_in,key,uart_rx,
  output wire uart_tx,
  output wire [7:0] led
);
  logic [7:0] startup=8'hff;
  wire reset=|startup;
  always_ff @(posedge clk_in)
    if(startup!=0) startup<=startup-1'b1;
  logic reset_meta,reset_sync,key_meta,key_sync,rx_meta,rx_sync;
  logic [26:0] heartbeat;
  always_ff @(posedge clk_in) begin
    if(reset) begin
      reset_meta<=1;reset_sync<=1;key_meta<=1;key_sync<=1;rx_meta<=1;rx_sync<=1;heartbeat<=0;
    end else begin
      reset_meta<=reset_in;reset_sync<=reset_meta;key_meta<=key;key_sync<=key_meta;
      rx_meta<=uart_rx;rx_sync<=rx_meta;heartbeat<=heartbeat+1'b1;
    end
  end
  assign led={1'b0,1'b1,1'b0,1'b1,1'b1,key_sync,reset_sync,heartbeat[HEARTBEAT_BIT]};
  wire temp_valid,temp_fault,temp_available,temp_ot;
  wire [11:0] temp_code;
  wire [31:0] temp_samples;
  pango_temperature #(.HARD_ADC(HARD_ADC),.CLK_HZ(CLK_HZ)) u_temp(
    .clk(clk_in),.reset(reset),.valid(temp_valid),.fault(temp_fault),
    .available(temp_available),.overtemp(temp_ot),.code(temp_code),.samples(temp_samples));
  wire tx_ready,rx_valid,rx_overrun;
  wire [7:0] rx_data;
  logic sending;
  logic [6:0] byte_index;
  logic [31:0] gap;
  logic [7:0] rx_count,last_rx,snap_count,snap_last;
  logic snap_reset,snap_key,snap_rx,snap_valid,snap_fault,snap_ot;
  logic [11:0] snap_code;
  function automatic [7:0] hexchar(input logic [3:0] nibble);
    hexchar=nibble<10 ? 8'h30+{4'd0,nibble} : 8'h61+{4'd0,nibble}-8'd10;
  endfunction
  function automatic [7:0] message_byte(input logic [6:0] index);
    case(index)
      7'd0: message_byte=8'h4e;
      7'd1: message_byte=8'h52;
      7'd2: message_byte=8'h5f;
      7'd3: message_byte=8'h44;
      7'd4: message_byte=8'h49;
      7'd5: message_byte=8'h41;
      7'd6: message_byte=8'h47;
      7'd7: message_byte=8'h20;
      7'd8: message_byte=8'h72;
      7'd9: message_byte=8'h73;
      7'd10: message_byte=8'h74;
      7'd11: message_byte=8'h3d;
      7'd12: message_byte=8'h30+{7'd0,snap_reset};
      7'd13: message_byte=8'h20;
      7'd14: message_byte=8'h6b;
      7'd15: message_byte=8'h65;
      7'd16: message_byte=8'h79;
      7'd17: message_byte=8'h3d;
      7'd18: message_byte=8'h30+{7'd0,snap_key};
      7'd19: message_byte=8'h20;
      7'd20: message_byte=8'h72;
      7'd21: message_byte=8'h78;
      7'd22: message_byte=8'h3d;
      7'd23: message_byte=8'h30+{7'd0,snap_rx};
      7'd24: message_byte=8'h20;
      7'd25: message_byte=8'h74;
      7'd26: message_byte=8'h65;
      7'd27: message_byte=8'h6d;
      7'd28: message_byte=8'h70;
      7'd29: message_byte=8'h3d;
      7'd30: message_byte=hexchar(snap_code[11:8]);
      7'd31: message_byte=hexchar(snap_code[7:4]);
      7'd32: message_byte=hexchar(snap_code[3:0]);
      7'd33: message_byte=8'h20;
      7'd34: message_byte=8'h76;
      7'd35: message_byte=8'h3d;
      7'd36: message_byte=8'h30+{7'd0,snap_valid};
      7'd37: message_byte=8'h20;
      7'd38: message_byte=8'h66;
      7'd39: message_byte=8'h3d;
      7'd40: message_byte=8'h30+{7'd0,snap_fault};
      7'd41: message_byte=8'h20;
      7'd42: message_byte=8'h6f;
      7'd43: message_byte=8'h74;
      7'd44: message_byte=8'h3d;
      7'd45: message_byte=8'h30+{7'd0,snap_ot};
      7'd46: message_byte=8'h20;
      7'd47: message_byte=8'h63;
      7'd48: message_byte=8'h6e;
      7'd49: message_byte=8'h74;
      7'd50: message_byte=8'h3d;
      7'd51: message_byte=hexchar(snap_count[7:4]);
      7'd52: message_byte=hexchar(snap_count[3:0]);
      7'd53: message_byte=8'h20;
      7'd54: message_byte=8'h6c;
      7'd55: message_byte=8'h61;
      7'd56: message_byte=8'h73;
      7'd57: message_byte=8'h74;
      7'd58: message_byte=8'h3d;
      7'd59: message_byte=hexchar(snap_last[7:4]);
      7'd60: message_byte=hexchar(snap_last[3:0]);
      7'd61: message_byte=8'h0d;
      7'd62: message_byte=8'h0a;
      default: message_byte=8'h0a;
    endcase
  endfunction
  uart #(.CLK_HZ(CLK_HZ),.BAUD(115200)) u_uart(
    .clk(clk_in),.reset(reset),.rx(uart_rx),.tx(uart_tx),
    .tx_valid(sending),.tx_data(message_byte(byte_index)),.tx_ready(tx_ready),
    .rx_valid(rx_valid),.rx_data(rx_data),.rx_ready(1'b1),.rx_overrun(rx_overrun));
  always_ff @(posedge clk_in) begin
    if(reset) begin
      sending<=0;byte_index<=0;gap<=0;rx_count<=0;last_rx<=0;
      snap_count<=0;snap_last<=0;snap_reset<=1;snap_key<=1;snap_rx<=1;
      snap_valid<=0;snap_fault<=0;snap_ot<=0;snap_code<=0;
    end else begin
      if(rx_valid) begin rx_count<=rx_count+1'b1;last_rx<=rx_data;end
      if(gap!=0) gap<=gap-1'b1;
      if(!sending && gap==0) begin
        sending<=1;byte_index<=0;gap<=REPORT_CYCLES-1;
        snap_count<=rx_count;snap_last<=last_rx;
        snap_reset<=reset_sync;snap_key<=key_sync;snap_rx<=rx_sync;
        snap_valid<=temp_valid;snap_fault<=temp_fault;snap_ot<=temp_ot;snap_code<=temp_code;
      end else if(sending && tx_ready) begin
        if(byte_index==7'd62) sending<=0;
        else byte_index<=byte_index+1'b1;
      end
    end
  end
endmodule
`default_nettype wire
