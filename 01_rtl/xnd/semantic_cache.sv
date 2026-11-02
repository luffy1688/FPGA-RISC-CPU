// Banked INT8 semantic head with synchronous registered read ports.
// W1 size is INPUTS*HIDDEN bytes; the deployed 2048x64, LANES=8 instance
// uses128KiB. Initial loading uses the32bit request/response bus.
module semantic_cache #(
 parameter integer LANES=4,CACHED=1,SKIP_ZERO=0,
 parameter integer INPUTS=1024,HIDDEN=64,OUTPUTS=16,RAM_BYTES=262144
)(
 input logic clk,reset,
 input logic cfg_valid,input logic[1:0]cfg_target,input logic[15:0]cfg_index,
 input logic[31:0]cfg_wdata,output logic cfg_ready,cfg_error,
 input logic cmd_valid,input logic[1:0]cmd,input logic[31:0]weight_base,
 output logic cmd_ready,done,error,cache_valid,
 output logic[7:0]error_code,
 output logic mem_valid,output logic[31:0]mem_addr,
 input logic mem_ready,input logic[31:0]mem_rdata,
 input logic[3:0]score_index,output logic signed[31:0]score,
 input logic[3:0]hidden_word_index,output logic[31:0]hidden_word,
 output logic[31:0]stat_cycles,stat_external_words,stat_macs,stat_active_groups
);
 localparam integer GROUPS=INPUTS/LANES,WG=HIDDEN*GROUPS,HG=HIDDEN/LANES,W2G=OUTPUTS*HG;
 localparam integer IDLE=0,LOAD=1,PREP=2,ROW_BEGIN=3,CACHE_RUN=4,STREAM_RUN=5,W2_BEGIN=6,W2_RUN=7,W1_POST=8,W2_POST=9,ROUND_ADD=10,ROUND_SHIFT=11,ROUND_SIGN=12,POST_BIAS=13,POST_WRITE=14;
 logic[3:0]state;
 // Separate lane banks provideLANES signed bytes per cycle without claiming
 // that a32bit shared SRAM port can magically feed8 multipliers.
 wire signed[7:0]cached_weight[0:LANES-1];
 wire signed[7:0]activation_read[0:LANES-1],second_weight_read[0:LANES-1];
 logic[INPUTS/4-1:0]a_nonzero;
 logic signed[7:0]hbank[0:LANES-1][0:HG-1];
 logic signed[31:0]bias1[0:HIDDEN-1],bias2[0:OUTPUTS-1],scores[0:OUTPUTS-1];
 // Coverage counters equal the number of set seen bits. Repeated writes
 // do not advance them; completion no longer reduces thousands of bits
 // through the datapath clock-enable network.
 logic[$clog2(INPUTS/4+1)-1:0]a_covered;
 logic[$clog2(OUTPUTS*HIDDEN/4+1)-1:0]v_covered;
 logic[$clog2(HIDDEN+1)-1:0]b1_covered;
 logic[$clog2(OUTPUTS+1)-1:0]b2_covered;
 logic[INPUTS/4-1:0]a_seen;logic[OUTPUTS*HIDDEN/4-1:0]v_seen;
 logic[HIDDEN-1:0]b1_seen;logic[OUTPUTS-1:0]b2_seen;
 logic[31:0]base_reg;
 logic[$clog2(HIDDEN*INPUTS/4)-1:0]load_word;
 logic[$clog2(HIDDEN>OUTPUTS?HIDDEN:OUTPUTS)-1:0]row;
 logic[$clog2(INPUTS)-1:0]col;
 logic[$clog2(GROUPS)-1:0]prep_group;
 logic[$clog2(GROUPS):0]active_count,issue,retire;
 logic[$clog2(GROUPS)-1:0]active_group[0:GROUPS-1];
 localparam integer DOT_LEVELS=$clog2(LANES);
 logic [DOT_LEVELS:0] dot_valid;
 logic signed[31:0] dot_pipe[0:DOT_LEVELS][0:LANES-1];
 logic signed[31:0] post_sum;
 logic post_negative,post_is_w2;
 logic signed[31:0] post_abs,post_added,post_shifted,post_rounded,post_biased,post_bias;
 logic pipe_valid;logic signed[31:0]accumulator,vec_sum,stream_sum;
 logic signed[7:0]wq[0:LANES-1],aq[0:LANES-1];
 logic issue_read;integer selected_group,read_weight_group;
 integer lane,b,idx,bank,offset;
 integer loop_hidden,loop_vec,loop_stream,loop_nonzero,loop_cfg_a,loop_cfg_v,loop_read,loop_stream_reg,loop_load;
 logic cfg_ok,any_nonzero;
 logic[63:0]extent;
 assign cfg_ready=state==IDLE;assign cmd_ready=state==IDLE;
 assign score=scores[score_index];
 // The64B quantizedhidden registerfile is small,notW1BRAM. A packed
 // readonly diagnostic/output port avoids a second CPU recomputation.
 always_comb begin
  hidden_word=0;
  for(loop_hidden=0;loop_hidden<4;loop_hidden++)if(hidden_word_index*4+loop_hidden<HIDDEN)
   hidden_word[loop_hidden*8+:8]=hbank[((hidden_word_index*4+loop_hidden)&(LANES-1))][((hidden_word_index*4+loop_hidden)>>$clog2(LANES))];
 end
 assign extent={32'd0,weight_base}+HIDDEN*INPUTS;
 assign mem_valid=state==LOAD||(!CACHED&&state==STREAM_RUN);
 assign mem_addr=state==LOAD?base_reg+load_word*4:base_reg+row*INPUTS+col;
 always_comb begin
  cfg_ok=0;
  case(cfg_target)
   0:cfg_ok=cfg_index<INPUTS/4;
   1:cfg_ok=cfg_index<OUTPUTS*HIDDEN/4;
   2:cfg_ok=cfg_index<HIDDEN;
   3:cfg_ok=cfg_index<OUTPUTS;
  endcase
  selected_group=SKIP_ZERO?active_group[issue<GROUPS?issue:0]:issue;
  issue_read=state==CACHE_RUN?issue<(SKIP_ZERO?active_count:GROUPS):state==W2_RUN?issue<HG:0;
  read_weight_group=state==W2_RUN?row*HG+issue:row*GROUPS+selected_group;
  vec_sum=0;
  for(loop_vec=0;loop_vec<LANES;loop_vec++)vec_sum=vec_sum+$signed(state==W2_RUN?aq[loop_vec]:activation_read[loop_vec])*$signed(state==W2_RUN?second_weight_read[loop_vec]:cached_weight[loop_vec]);
  stream_sum=0;
  if(!CACHED)for(loop_stream=0;loop_stream<4;loop_stream++)stream_sum=stream_sum+$signed(activation_read[loop_stream])*$signed(mem_rdata[loop_stream*8+:8]);
  any_nonzero=0;
  for(loop_nonzero=0;loop_nonzero<LANES/4;loop_nonzero++)if(a_nonzero[prep_group*(LANES/4)+loop_nonzero])any_nonzero=1;
 end
 function automatic signed[31:0]round6(input signed[31:0]x);
  if(x>=0)round6=(x+32)/64;else round6=-((-x+32)/64);
 endfunction
 function automatic signed[7:0]relu(input signed[31:0]x,input signed[31:0]bias);
  logic signed[31:0]v;begin v=round6(x)+bias;relu=v<0?0:v>127?127:v[7:0];end
 endfunction
 task automatic fail(input[7:0]code);
  begin state<=IDLE;done<=1;error<=1;error_code<=code;pipe_valid<=0;dot_valid<=0;end
 endtask
 task automatic finish_w1(input signed[31:0]sum);
  begin
   hbank[row&(LANES-1)][row>>$clog2(LANES)]<=sum<0?0:sum>127?127:sum[7:0];
   accumulator<=0;pipe_valid<=0;dot_valid<=0;
   if(row==HIDDEN-1)begin row<=0;state<=W2_BEGIN;end
   else begin row<=row+1;state<=CACHED?ROW_BEGIN:STREAM_RUN;col<=0;end
  end
 endtask
 // One syntactic write port per physical byte bank. A dynamic bank
 // subscript in four unrolled stores falsely implies four RAM write ports
 // to ADS,even when byte lanes are mutually exclusive. Constant lane
 // selection preserves identical addresses/data and permits BRAM inference.
 genvar bank_lane;
 generate for(bank_lane=0;bank_lane<LANES;bank_lane=bank_lane+1)begin:bank_write_port
  semantic_weight_ram #(.DEPTH(WG)) u_weight_ram(
   .clk(clk),.write_enable(!reset&&state==LOAD&&mem_ready&&(load_word&((LANES/4)-1))==(bank_lane/4)),
   .write_address((load_word>>$clog2(LANES/4))),.write_data(mem_rdata[(bank_lane%4)*8+:8]),
   .read_enable(issue_read&&state!=W2_RUN),.read_address(read_weight_group),.read_data(cached_weight[bank_lane]));
  // Single-write/synchronous-read activation and W2 banks. Zero-group
  // discovery uses a word bitmap, so it does not add a second RAM read port.
  semantic_weight_ram #(.DEPTH(GROUPS)) u_activation_ram(
   .clk(clk),.write_enable(!reset&&cfg_valid&&cfg_ready&&cfg_ok&&cfg_target==0&&(cfg_index&((LANES/4)-1))==(bank_lane/4)),
   .write_address(cfg_index>>$clog2(LANES/4)),.write_data(cfg_wdata[(bank_lane%4)*8+:8]),
   .read_enable((issue_read&&state!=W2_RUN)||(!CACHED&&state==STREAM_RUN)),
   .read_address(state==STREAM_RUN?col>>$clog2(LANES):selected_group),.read_data(activation_read[bank_lane]));
  semantic_weight_ram #(.DEPTH(W2G)) u_second_weight_ram(
   .clk(clk),.write_enable(!reset&&cfg_valid&&cfg_ready&&cfg_ok&&cfg_target==1&&(cfg_index&((LANES/4)-1))==(bank_lane/4)),
   .write_address(cfg_index>>$clog2(LANES/4)),.write_data(cfg_wdata[(bank_lane%4)*8+:8]),
   .read_enable(issue_read&&state==W2_RUN),.read_address(read_weight_group),.read_data(second_weight_read[bank_lane]));
 end endgenerate
 // Registered products and one registered adder level per stage. The
 // accumulator sees one final sum, not a chain of eight multiply-adds.
 genvar dot_lane,dot_level,dot_node;
 generate for(dot_lane=0;dot_lane<LANES;dot_lane=dot_lane+1)begin:dot_product_stage
  always_ff @(posedge clk)if(pipe_valid&&(state==CACHE_RUN||state==W2_RUN))
   dot_pipe[0][dot_lane]<=$signed(state==W2_RUN?aq[dot_lane]:activation_read[dot_lane])*$signed(state==W2_RUN?second_weight_read[dot_lane]:cached_weight[dot_lane]);
 end
 for(dot_level=1;dot_level<=DOT_LEVELS;dot_level=dot_level+1)begin:dot_reduce_stage
  for(dot_node=0;dot_node<(LANES>>dot_level);dot_node=dot_node+1)begin:dot_reduce_node
   always_ff @(posedge clk)if(dot_valid[dot_level-1])
    dot_pipe[dot_level][dot_node]<=dot_pipe[dot_level-1][2*dot_node]+dot_pipe[dot_level-1][2*dot_node+1];
  end
 end endgenerate
 // No RAMcontents are reset. Valid/configuration bitmaps guard every use.
 always_ff @(posedge clk)begin
  if(reset)begin
   state<=IDLE;cache_valid<=0;done<=0;error<=0;error_code<=0;
   a_seen<=0;v_seen<=0;b1_seen<=0;b2_seen<=0;cfg_error<=0;
   a_covered<=0;v_covered<=0;b1_covered<=0;b2_covered<=0;
   base_reg<=0;load_word<=0;row<=0;col<=0;prep_group<=0;active_count<=0;
   issue<=0;retire<=0;pipe_valid<=0;dot_valid<=0;post_sum<=0;post_negative<=0;post_is_w2<=0;post_abs<=0;post_added<=0;post_shifted<=0;post_rounded<=0;post_biased<=0;post_bias<=0;accumulator<=0;
   stat_cycles<=0;stat_external_words<=0;stat_macs<=0;stat_active_groups<=0;
  end else begin
   done<=0;cfg_error<=0;
   if(state==CACHE_RUN||state==W2_RUN)dot_valid<={dot_valid[DOT_LEVELS-1:0],pipe_valid};else dot_valid<=0;
   if(state!=IDLE)stat_cycles<=stat_cycles+1;
   if(cfg_valid&&cfg_ready)begin
    if(!cfg_ok)cfg_error<=1;
    else case(cfg_target)
     0:begin
      // Per-lane activation write ports below.
      if(!a_seen[cfg_index])a_covered<=a_covered+1'b1;
      a_seen[cfg_index]<=1;a_nonzero[cfg_index]<=|cfg_wdata;
     end
     1:begin
      // Per-lane output-weight write ports below.
      if(!v_seen[cfg_index])v_covered<=v_covered+1'b1;v_seen[cfg_index]<=1;
     end
     2:begin bias1[cfg_index]<=cfg_wdata;if(!b1_seen[cfg_index])b1_covered<=b1_covered+1'b1;b1_seen[cfg_index]<=1;end
     3:begin bias2[cfg_index]<=cfg_wdata;if(!b2_seen[cfg_index])b2_covered<=b2_covered+1'b1;b2_seen[cfg_index]<=1;end
    endcase
   end
   // Lane read registers model synchronous RAMports; MAC consumes the prior
   // cycle's valid data. This pipeline can issue one bank group per cycle.
   if(issue_read)begin
    for(loop_read=0;loop_read<LANES;loop_read++)begin
     if(state==W2_RUN)aq[loop_read]<=hbank[loop_read][issue];
    end
   end
   case(state)
    IDLE:if(cmd_valid)begin
     stat_cycles<=0;stat_external_words<=0;stat_macs<=0;stat_active_groups<=0;
     error<=0;error_code<=0;pipe_valid<=0;
     if(cmd==2)begin cache_valid<=0;done<=1;end
     else if(cmd==0)begin
      cache_valid<=0;
      if(weight_base[1:0]!=0||extent>RAM_BYTES)fail(1);
      else begin base_reg<=weight_base;load_word<=0;if(CACHED)state<=LOAD;else begin cache_valid<=1;done<=1;end end
     end
     else if(cmd==1)begin
      if(!cache_valid)fail(2);
      else if(a_covered!=INPUTS/4||v_covered!=OUTPUTS*HIDDEN/4||b1_covered!=HIDDEN||b2_covered!=OUTPUTS)fail(3);
      else begin
       row<=0;col<=0;accumulator<=0;active_count<=0;prep_group<=0;
       if(CACHED&&SKIP_ZERO)state<=PREP;
       else begin stat_active_groups<=GROUPS;state<=CACHED?ROW_BEGIN:STREAM_RUN;end
      end
     end else fail(4);
    end
    LOAD:if(mem_ready)begin
     stat_external_words<=stat_external_words+1;
     // Per-lane W1 write ports below.
     if(load_word==HIDDEN*INPUTS/4-1)begin cache_valid<=1;state<=IDLE;done<=1;end
     else load_word<=load_word+1;
    end
    PREP:begin
     if(any_nonzero)begin active_group[active_count]<=prep_group;active_count<=active_count+1;end
     if(prep_group==GROUPS-1)begin stat_active_groups<=active_count+(any_nonzero?1:0);state<=ROW_BEGIN;end
     else prep_group<=prep_group+1;
    end
    ROW_BEGIN:begin
     issue<=0;retire<=0;accumulator<=0;pipe_valid<=0;dot_valid<=0;
     if(SKIP_ZERO&&active_count==0)begin post_sum<=0;state<=W1_POST;end else state<=CACHE_RUN;
    end
    CACHE_RUN:begin
     pipe_valid<=issue_read;if(issue_read)issue<=issue+1;
     if(dot_valid[DOT_LEVELS])begin
      stat_macs<=stat_macs+LANES;retire<=retire+1;
      if(retire+1==(SKIP_ZERO?active_count:GROUPS))begin post_sum<=accumulator+dot_pipe[DOT_LEVELS][0];pipe_valid<=0;dot_valid<=0;state<=W1_POST;end
      else accumulator<=accumulator+dot_pipe[DOT_LEVELS][0];
     end
    end
    STREAM_RUN:if(!CACHED&&mem_ready)begin
     stat_external_words<=stat_external_words+1;stat_macs<=stat_macs+4;
     if(col+4==INPUTS)begin post_sum<=accumulator+stream_sum;state<=W1_POST;end
     else begin accumulator<=accumulator+stream_sum;col<=col+4;end
    end
    W2_BEGIN:begin issue<=0;retire<=0;accumulator<=0;pipe_valid<=0;dot_valid<=0;state<=W2_RUN;end
    W2_RUN:begin
     pipe_valid<=issue_read;if(issue_read)issue<=issue+1;
     if(dot_valid[DOT_LEVELS])begin
      stat_macs<=stat_macs+LANES;retire<=retire+1;
      if(retire+1==HG)begin
       post_sum<=accumulator+dot_pipe[DOT_LEVELS][0];pipe_valid<=0;dot_valid<=0;state<=W2_POST;
      end else accumulator<=accumulator+dot_pipe[DOT_LEVELS][0];
     end
    end
    // Preserve signed 32-bit wrap and division toward zero from round6.
    // Each carry chain and the final saturation have a separate register.
    W1_POST,W2_POST:begin
      post_negative<=post_sum[31];post_abs<=post_sum[31]?-post_sum:post_sum;
      post_bias<=state==W2_POST?bias2[row]:bias1[row];post_is_w2<=state==W2_POST;state<=ROUND_ADD;
    end
    ROUND_ADD:begin post_added<=post_abs+32'sd32;state<=ROUND_SHIFT;end
    ROUND_SHIFT:begin
      post_shifted<=($signed(post_added)>>>6)+((post_added[31]&&|post_added[5:0])?32'sd1:32'sd0);
      state<=ROUND_SIGN;
    end
    ROUND_SIGN:begin post_rounded<=post_negative?-post_shifted:post_shifted;state<=POST_BIAS;end
    POST_BIAS:begin post_biased<=post_rounded+post_bias;state<=POST_WRITE;end
    POST_WRITE:begin
      if(post_is_w2)begin
        scores[row]<=post_biased;
        if(row==OUTPUTS-1)begin state<=IDLE;done<=1;end
        else begin row<=row+1;state<=W2_BEGIN;end
      end else finish_w1(post_biased);
    end
    default:fail(5);
   endcase
  end
 end
endmodule

// Explicit simple dual-port byte RAM. The read register is the cache MAC
// pipeline stage; it replaces,rather than adds to,the former wq register.
module semantic_weight_ram #(parameter integer DEPTH=16384)(
 input wire clk,write_enable,read_enable,
 input wire [$clog2(DEPTH)-1:0]write_address,read_address,
 input wire [7:0]write_data,output reg [7:0]read_data);
 reg [7:0] mem[0:DEPTH-1];
 always @(posedge clk)begin
  if(write_enable)mem[write_address]<=write_data;
  if(read_enable)read_data<=mem[read_address];
 end
endmodule
