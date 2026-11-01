// Integer register file with writeback-to-decode bypass.
// 同一拍写回和译码读同一个寄存器时，译码直接看最新值。
module rv32i_regfile(
  input logic clk, reset, we, input logic [4:0] wa,
  input logic [31:0] wd, input logic [4:0] ra1, ra2,
  output logic [31:0] rd1, rd2
);
  logic [31:0] r[0:31];
  integer i;
  assign rd1 = ra1==0 ? 32'd0 : (we && wa==ra1 ? wd : r[ra1]);
  assign rd2 = ra2==0 ? 32'd0 : (we && wa==ra2 ? wd : r[ra2]);
  always_ff @(posedge clk) begin
    if(reset) for(i=0;i<32;i=i+1) r[i]<=0;
    else if(we && wa!=0) r[wa]<=wd;
  end
endmodule
