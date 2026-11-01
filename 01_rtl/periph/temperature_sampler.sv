// temperature_sampler = 温度寄存器读取器；等待真实ADC转换完成再发布数据。
// APB is held through DRDY. A timeout invalidates data until reset.
`default_nettype none
module temperature_sampler #(
  parameter integer WARMUP_CYCLES=2700000,
  parameter integer POLL_CYCLES=2700000,
  parameter integer TIMEOUT_CYCLES=4096
)(
  input logic clk,reset,
  input logic adc_done,adc_ready,adc_overtemp,
  input logic [15:0] adc_data,
  output logic loadsc_n,den,secen,
  output logic valid,fault,overtemp,
  output logic [11:0] code,
  output logic [31:0] samples
);
  // ADS subset: explicit constants replace the unsupported enum type.
  localparam logic [2:0] STABLE=3'd0, LOAD=3'd1, WARM=3'd2, GAP=3'd3,
    SETUP=3'd4, ACCESS=3'd5, FAULT=3'd6;
  logic [2:0] state;
  logic [31:0] count;
  logic done_meta,done_sync,done_last,seen_done,ot_meta,ot_sync;
  assign loadsc_n=state!=LOAD;
  assign den=(state==SETUP || state==ACCESS);
  assign secen=state==ACCESS;
  assign overtemp=ot_sync;
  always_ff @(posedge clk) begin
    if(reset) begin
      state<=STABLE;count<=0;valid<=0;fault<=0;code<=0;samples<=0;
      done_meta<=0;done_sync<=0;done_last<=0;seen_done<=0;ot_meta<=0;ot_sync<=0;
    end else begin
      done_meta<=adc_done;done_sync<=done_meta;done_last<=done_sync;
      ot_meta<=adc_overtemp;ot_sync<=ot_meta;
      if(done_sync && !done_last) seen_done<=1;
      case(state)
        // UG040009 requires >=256 stable DCLKs, then LOADSC_N low >=2 clocks.
        STABLE: if(count==255) begin state<=LOAD;count<=0;end else count<=count+1;
        LOAD: if(count==3) begin state<=WARM;count<=0;end else count<=count+1;
        WARM: if(count==WARMUP_CYCLES-1) begin state<=GAP;count<=0;end else count<=count+1;
        GAP: if(count==POLL_CYCLES-1) begin
          count<=0;
          // Do not keep displaying an old reading if conversions have stopped.
          if(seen_done) begin state<=SETUP;seen_done<=0;end
          else valid<=0;
        end else count<=count+1;
        SETUP: begin state<=ACCESS;count<=0;end
        ACCESS: begin
          if(adc_ready) begin
            // Register 0x40 stores DATA[11:0] in bits [15:4]; low bits unused.
            code<=adc_data[15:4];
            valid<=adc_data[15:4]!=0 && adc_data[15:4]!=12'hfff;
            samples<=samples+1;state<=GAP;count<=0;
          end else if(count==TIMEOUT_CYCLES-1) begin
            valid<=0;fault<=1;state<=FAULT;count<=0;
          end else count<=count+1;
        end
        FAULT: begin valid<=0;end
        default: begin state<=STABLE;count<=0;valid<=0;end
      endcase
    end
  end
endmodule
`default_nettype wire
