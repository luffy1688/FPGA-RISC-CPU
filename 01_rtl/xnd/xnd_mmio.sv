`default_nettype none
// MMIO shell around xnd_dot4. Offsets: 0x00 status, 0x04 result,
// 0x08 operand A, 0x0c operand B, 0x10 start command.
module xnd_mmio(
  input logic clk,reset,input logic wr_en,rd_en,input logic [5:0] addr,
  input logic [31:0] wdata,output logic [31:0] rdata);
  logic [31:0] op_a,op_b; logic start; logic busy,done; logic signed [31:0] result;
  xnd_dot4 u_dot4(.clk(clk),.reset(reset),.start(start),.a_packed(op_a),.b_packed(op_b),.busy(busy),.done(done),.result(result));
  always_ff @(posedge clk) begin
    if(reset) begin op_a<=0; op_b<=0; start<=0; end
    else begin
      start<=0;
      if(wr_en) case(addr)
        6'h08: op_a<=wdata; 6'h0c: op_b<=wdata; 6'h10: start<=wdata[0]; default: ;
      endcase
    end
  end
  always_comb begin
    rdata=0;
    if(rd_en) case(addr)
      6'h00:rdata={30'd0,done,busy}; 6'h04:rdata=result; 6'h08:rdata=op_a; 6'h0c:rdata=op_b; default:rdata=0;
    endcase
  end
endmodule
`default_nettype wire
