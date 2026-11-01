`default_nettype none
// Four signed 8-bit products reduced into one signed 32-bit result.
// This is the smallest measurable Needle-inspired low-bit kernel.
module xnd_dot4(
  input logic clk,reset,input logic start,
  input logic [31:0] a_packed,b_packed,
  output logic busy,done,output logic signed [31:0] result);
  logic [31:0] a_reg,b_reg;
  always_ff @(posedge clk) begin
    if(reset) begin busy<=0; done<=0; result<=0; a_reg<=0; b_reg<=0; end
    else begin
      done<=0;
      if(start && !busy) begin a_reg<=a_packed; b_reg<=b_packed; busy<=1; end
      else if(busy) begin
        result <= $signed(a_reg[7:0])*$signed(b_reg[7:0]) +
                  $signed(a_reg[15:8])*$signed(b_reg[15:8]) +
                  $signed(a_reg[23:16])*$signed(b_reg[23:16]) +
                  $signed(a_reg[31:24])*$signed(b_reg[31:24]);
        busy<=0; done<=1;
      end
    end
  end
endmodule
`default_nettype wire
