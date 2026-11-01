`timescale 1ns/1ps
`default_nettype none
module tb_xnd_dot4;
  logic clk=0,reset=1,start=0,busy,done; logic [31:0] a,b; logic signed [31:0] result;
  always #5 clk=~clk;
  xnd_dot4 dut(.clk,.reset,.start,.a_packed(a),.b_packed(b),.busy,.done,.result);
  initial begin
    a={8'sd4,8'sd3,8'sd2,8'sd1}; b={8'sd8,8'sd7,8'sd6,8'sd5};
    repeat(2) @(posedge clk); reset<=0; @(posedge clk); start<=1; @(posedge clk); start<=0;
    wait(done); if(result!==32'sd70) $fatal(1,"dot4 failed %0d",result);
    $display("PASS xnd.dot4 result=%0d",result); $finish;
  end
endmodule
`default_nettype wire
