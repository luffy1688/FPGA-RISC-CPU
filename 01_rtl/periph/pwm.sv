// pwm = pulse width modulation: a counter sets how long LED7 stays high per period.
// Configuration changes take effect at a period boundary, preventing short glitches.
`default_nettype none
module pwm #(
  parameter integer DEFAULT_PERIOD=27000
)(
  input logic clk,reset,enable,
  input logic [31:0] period,duty,
  output logic pin
);
  logic [31:0] counter,active_period,active_duty;
  wire [31:0] next_period=(period==0)?32'd1:period;
  always_ff @(posedge clk) begin
    if(reset) begin counter<=0;active_period<=DEFAULT_PERIOD;active_duty<=0;end
    else if(!enable) begin
      counter<=0;active_period<=next_period;active_duty<=duty;
    end else if(counter==active_period-1) begin
      counter<=0;active_period<=next_period;active_duty<=duty;
    end else counter<=counter+1;
  end
  assign pin=enable && counter<active_duty;
endmodule
`default_nettype wire
