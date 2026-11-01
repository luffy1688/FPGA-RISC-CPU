`timescale 1ns/1ps
// Tests protocol with explicit ADC stimulus; these are NOT measured temperatures.
module tb_temperature_sampler;
  logic clk=0,reset=1,adc_done=0,adc_ready=0,adc_overtemp=0;
  logic [15:0] adc_data=0;
  wire loadsc_n,den,secen,valid,fault,overtemp;
  wire [11:0] code;wire [31:0] samples;
  integer low_cycles=0,stable_cycles=0;
  always #5 clk=~clk;
  temperature_sampler #(.WARMUP_CYCLES(12),.POLL_CYCLES(32),.TIMEOUT_CYCLES(16)) dut(.*);
  task automatic conversion;
    @(negedge clk);adc_done=1;
    repeat(3) @(negedge clk);adc_done=0;
  endtask
  task automatic reply(input [15:0] data);
    wait(secen);repeat(7) @(negedge clk);
    if(!den || !secen) $fatal(1,"APB enable dropped before ready");
    adc_data=data;adc_ready=1;@(negedge clk);adc_ready=0;
  endtask
  initial begin
    repeat(2) @(negedge clk);reset=0;
    while(loadsc_n) begin @(negedge clk);stable_cycles++;end
    if(stable_cycles<256) $fatal(1,"LOADSC_N before stable clocks");
    while(!loadsc_n) begin @(negedge clk);low_cycles++;end
    if(low_cycles<2) $fatal(1,"LOADSC_N too short");
    conversion();reply(16'h98d0);
    if(!valid || code!=12'h98d || samples!=1 || fault) $fatal(1,"data format/valid");
    // No further conversion: after one poll period the previous value is stale.
    repeat(34) @(negedge clk);
    if(valid || den) $fatal(1,"stale temperature remained valid");
    conversion();reply(16'hb7a0);
    if(!valid || code!=12'hb7a || samples!=2) $fatal(1,"second sample");
    adc_overtemp=1;repeat(3) @(negedge clk);
    if(!overtemp) $fatal(1,"OT synchronization");
    conversion();wait(secen);repeat(18) @(negedge clk);
    if(valid || !fault || den || secen) $fatal(1,"bounded APB timeout");
    // Late completion cannot clear a timeout or publish a false new sample.
    adc_ready=1;adc_data=16'ha000;repeat(4) @(negedge clk);
    if(valid || samples!=2 || !fault) $fatal(1,"late response after fault");
    reset=1;@(negedge clk);reset=0;adc_ready=0;adc_overtemp=0;
    if(valid || fault || samples) $fatal(1,"reset did not clear sampler");
    $display("PASS ADC controller: config loading, APB wait, raw format, freshness, timeout");$finish;
  end
  initial begin #20000;$fatal(1,"test timeout");end
endmodule
