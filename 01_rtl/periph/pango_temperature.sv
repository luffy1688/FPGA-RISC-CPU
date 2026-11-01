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
    wire loadsc_n,den,secen,ready,done,ot;
    wire [15:0] data;
    // Temperature-only sequential scan, internal VREF, offset/gain calibration,
    // 64-sample average, DCLK/32. ADC_B and external channels are disabled.
    GTP_ADC_E2 #(
      .CREG_00H(16'hb001),.CREG_01H(16'hd01e),.CREG_02H(16'h0000),
      .CREG_31H(16'h0000),.CREG_03H(16'h0004),.CREG_04H(16'h0000),
      .CREG_0AH(16'h0000),.CREG_05H(16'h0000),.CREG_06H(16'h0000),
      .CREG_0CH(16'h0000),.CREG_07H(16'h0004),.CREG_08H(16'h0000),
      .CREG_0EH(16'h0000),.CREG_20H(12'h000),.CREG_21H(12'h000),
      .CREG_22H(12'h000),.CREG_23H(12'h000),.CREG_24H(12'h000),
      .CREG_25H(12'h000),.CREG_26H(12'h000),.CREG_27H(12'h000),
      .CREG_28H(12'h000),.CREG_29H(12'h000),.CREG_2AH(12'hcc2),.CREG_2BH(12'ha5b)
    ) u_adc(
      .VAUX(32'd0),.RST_N(~reset),.CONVST(1'b0),.LOADSC_N(loadsc_n),
      .DCLK(clk),.DADDR(8'h40),.DEN(den),.SECEN(secen),.DWE(1'b0),.DI(16'd0),
      .DO(data),.DRDY(ready),.OVER_TEMP(ot),.LOGIC_DONE_A(done),
      .LOGIC_DONE_B(),.ADC_CLK_OUT(),.DMODIFIED(),.ALARM()
    );
    temperature_sampler #(.WARMUP_CYCLES(CLK_HZ/10),.POLL_CYCLES(CLK_HZ/10)) u_sample(
      .clk(clk),.reset(reset),.adc_done(done),.adc_ready(ready),.adc_overtemp(ot),.adc_data(data),
      .loadsc_n(loadsc_n),.den(den),.secen(secen),.valid(valid),.fault(fault),.overtemp(overtemp),.code(code),.samples(samples));
  end else begin: no_hardware
    assign valid=0;assign fault=0;assign overtemp=0;assign code=0;assign samples=0;
  end endgenerate
endmodule
`default_nettype wire
