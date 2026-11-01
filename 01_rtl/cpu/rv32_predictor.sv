// Direct indexed BTB + two-bit saturating BHT (default 64 entries).
// 一次分支不成功并不马上改主意：2-bit计数器保留历史。
module rv32_predictor #(parameter integer ENTRIES=64)(
  input logic clk,reset,clear,
  input logic [31:0] query_pc,
  output logic [31:0] predicted_pc,
  input logic update,
  input logic [31:0] resolved_pc,target_pc,
  input logic taken,conditional
);
  localparam integer IW=$clog2(ENTRIES);
  logic valid[0:ENTRIES-1],is_cond[0:ENTRIES-1];
  logic [31-IW-2:0] tag[0:ENTRIES-1];
  logic [31:0] target[0:ENTRIES-1];
  logic [1:0] history[0:ENTRIES-1];
  wire [IW-1:0] qi=query_pc[IW+1:2],ui=resolved_pc[IW+1:2];
  integer i;
  always_comb begin
    predicted_pc=query_pc+4;
    if(valid[qi] && tag[qi]==query_pc[31:IW+2] &&
      (!is_cond[qi]||history[qi][1])) predicted_pc=target[qi];
  end
  always_ff @(posedge clk) begin
    if(reset||clear) begin
      for(i=0;i<ENTRIES;i=i+1) begin valid[i]<=0;history[i]<=2'b01;is_cond[i]<=0;tag[i]<=0;target[i]<=0; end
    end else if(update) begin
      valid[ui]<=1;tag[ui]<=resolved_pc[31:IW+2];target[ui]<=target_pc;is_cond[ui]<=conditional;
      if(!valid[ui] || tag[ui]!=resolved_pc[31:IW+2]) history[ui]<=taken?2'b10:2'b01;
      else if(taken && history[ui]!=3) history[ui]<=history[ui]+1'b1;
      else if(!taken && history[ui]!=0) history[ui]<=history[ui]-1'b1;
    end
  end
endmodule
