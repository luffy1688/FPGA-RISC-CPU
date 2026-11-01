// Direct indexed BTB + two-bit saturating BHT (default 64 entries).
// 一次分支不成功并不马上改主意：2-bit计数器保留历史。
module rv32_predictor #(parameter integer ENTRIES=64,parameter bit REGISTER_QUERY=0)(
  input logic clk,reset,clear,query_enable,
  input logic [31:0] query_pc,
  output logic [31:0] predicted_pc,
  input logic update,
  input logic [31:0] resolved_pc,target_pc,
  input logic[31:0]resolved_insn,
  input logic taken,conditional
);
  localparam integer IW=$clog2(ENTRIES);
  logic valid[0:ENTRIES-1],is_cond[0:ENTRIES-1],is_return[0:ENTRIES-1];
  logic[31:0]return_stack[0:15];logic[3:0]return_sp;logic[4:0]return_count;
  wire resolved_call=(resolved_insn[6:0]==7'h6f || resolved_insn[6:0]==7'h67) &&
    (resolved_insn[11:7]==1 || resolved_insn[11:7]==5);
  wire resolved_return=resolved_insn[6:0]==7'h67 && resolved_insn[14:12]==0 && resolved_insn[11:7]==0 &&
    (resolved_insn[19:15]==1 || resolved_insn[19:15]==5) && resolved_insn[31:20]==0;
  always_ff @(posedge clk)begin
    if(reset||clear)begin return_sp<=0;return_count<=0;end
    else if(update)begin
      if(resolved_call)begin return_stack[return_sp]<=resolved_pc+4;return_sp<=return_sp+1'b1;if(return_count<16)return_count<=return_count+1'b1;end
      else if(resolved_return && return_count!=0)begin return_sp<=return_sp-1'b1;return_count<=return_count-1'b1;end
    end
  end
  logic [31-IW-2:0] tag[0:ENTRIES-1];
  logic [31:0] target[0:ENTRIES-1];
  logic [1:0] history[0:ENTRIES-1];
  wire [IW-1:0] qi=query_pc[IW+1:2],ui=resolved_pc[IW+1:2];
  localparam integer HB=6;
  localparam integer PB=12;
  logic[HB-1:0]branch_history[0:ENTRIES-1];logic[HB-1:0]global_history;
  integer ph;
  wire[1:0]query_pattern_value;
  wire[1:0]pattern_bank_read[0:(1<<(PB-10))-1];
  wire[PB-1:0]query_pattern=((query_pc>>2)<<HB)^branch_history[qi];
  wire[PB-1:0]update_pattern=((resolved_pc>>2)<<HB)^branch_history[ui];
  always_ff @(posedge clk)begin
    if(reset||clear)begin
      global_history<=0;
      for(ph=0;ph<ENTRIES;ph=ph+1)branch_history[ph]<=0;

    end else if(update&&conditional)begin
      global_history<={global_history[HB-2:0],taken};
      branch_history[ui]<={branch_history[ui][HB-2:0],taken};

    end
  end

  // Banked PHT preserves exactly the same index/state/reset semantics while
  // bounding each ADS memory's mux and decoder expansion to 1024 entries.
  genvar pbank;
  generate for(pbank=0;pbank<(1<<(PB-10));pbank=pbank+1)begin:pht_banks
    logic[1:0]counters[0:1023];integer row;
    assign pattern_bank_read[pbank]=counters[query_pattern[9:0]];
    always_ff @(posedge clk)begin
      if(reset||clear)begin
        for(row=0;row<1024;row=row+1)counters[row]<=2'b01;
      end else if(update&&conditional&&update_pattern[PB-1:10]==pbank)begin
        if(taken&&counters[update_pattern[9:0]]!=3)
          counters[update_pattern[9:0]]<=counters[update_pattern[9:0]]+1'b1;
        else if(!taken&&counters[update_pattern[9:0]]!=0)
          counters[update_pattern[9:0]]<=counters[update_pattern[9:0]]-1'b1;
      end
    end
  end endgenerate
  assign query_pattern_value=pattern_bank_read[query_pattern[PB-1:10]];

  integer i;
  generate if(REGISTER_QUERY)begin:registered_lookup
    logic q_valid,q_cond,q_taken;
    logic [31-IW-2:0] q_tag;
    logic [31:0] q_pc,q_target,q_sequential;
    always_ff @(posedge clk)begin
      if(reset||clear)begin q_valid<=0;q_cond<=0;q_taken<=0;q_tag<=0;q_pc<=0;q_target<=0;q_sequential<=4;end
      else if(query_enable)begin
        q_valid<=valid[qi];q_cond<=is_cond[qi];q_taken<=query_pattern_value[1];
        q_tag<=tag[qi];q_pc<=query_pc;q_target<=(is_return[qi]&&return_count!=0)?return_stack[(return_sp-1'b1)&15]:target[qi];q_sequential<=query_pc+4;
      end
    end
    always_comb begin
      predicted_pc=q_sequential;
      if(q_valid&&q_tag==q_pc[31:IW+2]&&(!q_cond||q_taken))predicted_pc=q_target;
    end
  end else begin:combinational_lookup
    always_comb begin
      predicted_pc=query_pc+4;
      if(valid[qi] && tag[qi]==query_pc[31:IW+2] &&
        (!is_cond[qi]||query_pattern_value[1]))predicted_pc=(is_return[qi]&&return_count!=0)?return_stack[(return_sp-1'b1)&15]:target[qi];
    end
  end endgenerate
  always_ff @(posedge clk) begin
    if(reset||clear) begin
      for(i=0;i<ENTRIES;i=i+1) begin valid[i]<=0;history[i]<=2'b01;is_cond[i]<=0;is_return[i]<=0; end
    end else if(update) begin
      valid[ui]<=1;tag[ui]<=resolved_pc[31:IW+2];target[ui]<=target_pc;is_cond[ui]<=conditional;is_return[ui]<=resolved_return;
      if(!valid[ui] || tag[ui]!=resolved_pc[31:IW+2]) history[ui]<=taken?2'b10:2'b01;
      else if(taken && history[ui]!=3) history[ui]<=history[ui]+1'b1;
      else if(!taken && history[ui]!=0) history[ui]<=history[ui]-1'b1;
    end
  end
endmodule
