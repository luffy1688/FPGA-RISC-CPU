// pango_temperature = PG2L200H片内ADC硬核与通用读取器的连接。
// HARD_ADC=1 is the physical-board build. Generic simulation keeps valid=0.
`default_nettype none
module pango_temperature #(
  parameter bit HARD_ADC=0,
  parameter integer CLK_HZ=27000000
)(
  input wire clk,reset,
  output wire valid,fault,available,overtemp,
  output wire [11:0] code,
  output wire [31:0] samples
);
  assign available=HARD_ADC;
  generate if(HARD_ADC) begin: physical
    localparam integer ADC_DIV=CLK_HZ>200000000?4:CLK_HZ>100000000?2:1;
    localparam integer ADC_CLK_HZ=CLK_HZ/ADC_DIV;
    // CD=10 selects /32 calibration above the original clock range. Keep
    // the original /16 low-frequency configuration used on the known board.
    localparam [15:0] CAL_CONFIG=CLK_HZ>63000000?16'hd21e:16'hd01e;
    // UG040009 table2-7: DB101 covers150ns>T>=50ns; DB110 covers
    // 50ns>T>=10ns. Exactly20MHz (50ns) therefore uses101.
    // Preserve powerdown/sequential/DCLK/OT-enable bits and OT thresholds.
    localparam [15:0] OT_CONFIG=ADC_CLK_HZ>20000000?16'hb301:16'hb281;
    wire adc_clk,adc_reset;
    wire adc_valid,adc_fault,adc_overtemp;
    wire [11:0]adc_code;
    wire [31:0]adc_samples;
    wire loadsc_n,den,secen,ready,done,ot;
    if(ADC_DIV==1)begin:direct_domain
      assign adc_clk=clk;
      assign adc_reset=reset;
      assign valid=adc_valid;assign fault=adc_fault;assign overtemp=adc_overtemp;
      assign code=adc_code;assign samples=adc_samples;
    end else begin:slow_domain
      // A registered divider, never a LUT-gated clock. The generated clock
      // must be declared at physical.u_adc/DCLK in the top-level FDC.
      (* KEEP="TRUE" *) reg adc_clock_half,adc_clock_quarter;
      always @(posedge clk or posedge reset)begin
        if(reset)begin adc_clock_half<=0;adc_clock_quarter<=0;end
        else begin adc_clock_half<=~adc_clock_half;adc_clock_quarter<=adc_clock_quarter^adc_clock_half;end
      end
      assign adc_clk=ADC_DIV==2?adc_clock_half:adc_clock_quarter;
      (* ASYNC_REG="TRUE" *) reg [1:0]adc_reset_pipe,system_reset_pipe;
      always @(posedge adc_clk or posedge reset)begin
        if(reset)adc_reset_pipe<=2'b11;
        else adc_reset_pipe<={adc_reset_pipe[0],1'b0};
      end
      always @(posedge clk or posedge reset)begin
        if(reset)system_reset_pipe<=2'b11;
        else system_reset_pipe<={system_reset_pipe[0],1'b0};
      end
      assign adc_reset=adc_reset_pipe[1];
      wire system_reset=system_reset_pipe[1];
      wire [46:0]live_payload={adc_samples,adc_code,adc_overtemp,adc_fault,adc_valid};
      // Bundled-data mailbox: payload remains unchanged from request until
      // acknowledged. Only the two single-bit toggles pass synchronizers;
      // the destination captures the whole stable bundle on one edge.
      reg [46:0]source_payload,destination_payload;
      reg request_toggle,acknowledge_toggle;
      (* ASYNC_REG="TRUE" *) reg ack_meta,ack_sync,request_meta,request_sync;
      always @(posedge adc_clk or posedge reset)begin
        if(reset)begin source_payload<=0;request_toggle<=0;ack_meta<=0;ack_sync<=0;end
        else if(adc_reset)begin source_payload<=0;request_toggle<=0;ack_meta<=0;ack_sync<=0;end
        else begin
          ack_meta<=acknowledge_toggle;ack_sync<=ack_meta;
          if(ack_sync==request_toggle && live_payload!=source_payload)begin
            source_payload<=live_payload;request_toggle<=~request_toggle;
          end
        end
      end
      always @(posedge clk or posedge reset)begin
        if(reset)begin destination_payload<=0;acknowledge_toggle<=0;request_meta<=0;request_sync<=0;end
        else if(system_reset)begin destination_payload<=0;acknowledge_toggle<=0;request_meta<=0;request_sync<=0;end
        else begin
          request_meta<=request_toggle;request_sync<=request_meta;
          if(request_sync!=acknowledge_toggle)begin
            destination_payload<=source_payload;acknowledge_toggle<=request_sync;
          end
        end
      end
      assign {samples,code,overtemp,fault,valid}=destination_payload;
    end
    initial begin
      if(ADC_CLK_HZ>100000000 || ADC_CLK_HZ<8000000)
        $fatal(1,"ADC APB DCLK must be8..100MHz");
    end
    wire [15:0] data;
    // Temperature-only sequential scan, internal VREF, offset/gain calibration,
    // 64-sample average, DCLK/32. ADC_B and external channels are disabled.
    GTP_ADC_E2 #(
      .CREG_00H(OT_CONFIG),.CREG_01H(CAL_CONFIG),.CREG_02H(16'h0000),
      .CREG_31H(16'h0000),.CREG_03H(16'h0004),.CREG_04H(16'h0000),
      .CREG_0AH(16'h0000),.CREG_05H(16'h0000),.CREG_06H(16'h0000),
      .CREG_0CH(16'h0000),.CREG_07H(16'h0004),.CREG_08H(16'h0000),
      .CREG_0EH(16'h0000),.CREG_20H(12'h000),.CREG_21H(12'h000),
      .CREG_22H(12'h000),.CREG_23H(12'h000),.CREG_24H(12'h000),
      .CREG_25H(12'h000),.CREG_26H(12'h000),.CREG_27H(12'h000),
      .CREG_28H(12'h000),.CREG_29H(12'h000),.CREG_2AH(12'hcc2),.CREG_2BH(12'ha5b)
    ) u_adc(
      .VAUX(32'd0),.RST_N(~adc_reset),.CONVST(1'b0),.LOADSC_N(loadsc_n),
      .DCLK(adc_clk),.DADDR(8'h40),.DEN(den),.SECEN(secen),.DWE(1'b0),.DI(16'd0),
      .DO(data),.DRDY(ready),.OVER_TEMP(ot),.LOGIC_DONE_A(done),
      .LOGIC_DONE_B(),.ADC_CLK_OUT(),.DMODIFIED(),.ALARM()
    );
    temperature_sampler #(.WARMUP_CYCLES(ADC_CLK_HZ/10),.POLL_CYCLES(ADC_CLK_HZ/10)) u_sample(
      .clk(adc_clk),.reset(adc_reset),.adc_done(done),.adc_ready(ready),.adc_overtemp(ot),.adc_data(data),
      .loadsc_n(loadsc_n),.den(den),.secen(secen),.valid(adc_valid),.fault(adc_fault),.overtemp(adc_overtemp),.code(adc_code),.samples(adc_samples));
  end else begin: no_hardware
    assign valid=0;assign fault=0;assign overtemp=0;assign code=0;assign samples=0;
  end endgenerate
endmodule
`default_nettype wire
