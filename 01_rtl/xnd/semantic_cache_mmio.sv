
// Experimental CPU/DMA integration. Production XND/SoC remains unchanged.
module semantic_cache_mmio #(parameter integer RAM_BYTES=524288,INPUTS=2048,HIDDEN=64,LANES=8,TIMEOUT=4096)(
 input logic clk,reset,input logic req_valid,req_write,input logic[15:0]req_addr,input logic[31:0]req_wdata,input logic[3:0]req_wstrb,
 output logic req_ready,output logic[31:0]req_rdata,output logic req_error,
 output logic mem_valid,mem_write,output logic[31:0]mem_addr,mem_wdata,output logic[3:0]mem_wstrb,
 input logic mem_ready,input logic[31:0]mem_rdata,input logic mem_error,output logic irq);
 logic cfg_ready,cfg_error,cmd_ready,done,error,cache_valid,abort_core,sticky_done,sticky_error;
 logic[7:0]error_code,last_error;logic result_valid,result_read;logic[1:0]last_command;logic[31:0]hidden_word;
 logic[1:0]target;logic[15:0]index;logic[31:0]base,cycles,words,macs,groups,score;
 logic cfg_valid,cmd_valid,valid_address;
 logic cfg_range_bad;
 logic cfg_pending;logic[1:0]cfg_target_q;logic[15:0]cfg_index_q;logic[31:0]cfg_wdata_q;logic[31:0]waiting;
 assign valid_address=req_addr==0||req_addr==4||req_addr==8||req_addr==16||req_addr==20||req_addr==24||
   req_addr==32||req_addr==36||req_addr==40||req_addr==44||req_addr==48||(req_addr>=256&&req_addr<320&&req_addr[1:0]==0)||(req_addr>=512&&req_addr<512+HIDDEN&&req_addr[1:0]==0);
 assign result_read=(req_addr>=256&&req_addr<320)||(req_addr>=512&&req_addr<512+HIDDEN);
 assign req_ready=req_valid&&!(cfg_pending&&req_write&&req_addr==4);
 assign req_error=req_valid&&((result_read&&(!result_valid||req_write))||!valid_address||req_addr[1:0]!=0||(req_write&&req_wstrb!=15)||
  (req_write&&req_addr==4&&!cmd_ready)||(abort_core&&req_write&&req_addr!=0)||(req_write&&(req_addr==16||req_addr==20||req_addr==24||req_addr==8)&&!cfg_ready));
 always_comb begin
  case(target)
   0:cfg_range_bad=index>=INPUTS/4;
   1:cfg_range_bad=index>=16*HIDDEN/4;
   2:cfg_range_bad=index>=HIDDEN;
   3:cfg_range_bad=index>=16;
   default:cfg_range_bad=1;
  endcase
 end
 assign cfg_valid=req_ready&&req_write&&!req_error&&req_addr==24;
 assign cmd_valid=req_ready&&req_write&&!req_error&&req_addr==4;
 assign mem_write=0;assign mem_wdata=0;assign mem_wstrb=0;assign irq=0;
 always_comb begin
  req_rdata=0;
  case(req_addr)
   0:req_rdata={22'd0,result_valid,cache_valid,5'd0,sticky_error,sticky_done,(!cmd_ready||cfg_pending)};
   8:req_rdata=base;16:req_rdata={30'd0,target};20:req_rdata={16'd0,index};
   32:req_rdata=cycles;36:req_rdata=words;40:req_rdata=macs;44:req_rdata=groups;48:req_rdata={24'd0,last_error};
   default:if(req_addr>=256&&req_addr<320)req_rdata=score;
     else if(req_addr>=512&&req_addr<512+HIDDEN)req_rdata=hidden_word;
  endcase
 end
 semantic_cache #(.LANES(LANES),.CACHED(1),.SKIP_ZERO(1),.INPUTS(INPUTS),.HIDDEN(HIDDEN),.RAM_BYTES(RAM_BYTES)) core(
 .clk(clk),.reset(reset||abort_core),.cfg_valid(cfg_pending),.cfg_target(cfg_target_q),.cfg_index(cfg_index_q),.cfg_wdata(cfg_wdata_q),.cfg_ready(cfg_ready),.cfg_error(cfg_error),
 .cmd_valid(cmd_valid),.cmd(req_wdata[1:0]),.weight_base(base),.cmd_ready(cmd_ready),.done(done),.error(error),.cache_valid(cache_valid),.error_code(error_code),
 .mem_valid(mem_valid),.mem_addr(mem_addr),.mem_ready(mem_ready&&!mem_error),.mem_rdata(mem_rdata),.score_index(req_addr[5:2]),.score(score),.hidden_word_index(req_addr[5:2]),.hidden_word(hidden_word),
 .stat_cycles(cycles),.stat_external_words(words),.stat_macs(macs),.stat_active_groups(groups));
 // Configuration write data crosses a register boundary before reaching
 // scattered activation/weight RAM write enables. A following command waits
 // until the pending configuration has committed.
 always_ff @(posedge clk)begin
  if(reset)begin cfg_pending<=0;cfg_target_q<=0;cfg_index_q<=0;cfg_wdata_q<=0;end
  else begin
   cfg_pending<=cfg_valid&&!cfg_range_bad;
   if(cfg_valid)begin cfg_target_q<=target;cfg_index_q<=index;cfg_wdata_q<=req_wdata;end
  end
 end
 always_ff @(posedge clk)begin
  if(reset)begin target<=0;index<=0;base<=0;sticky_done<=0;sticky_error<=0;last_error<=0;waiting<=0;abort_core<=0;result_valid<=0;last_command<=0;end
  else begin
   abort_core<=0;
   if(mem_valid&&!mem_ready)waiting<=waiting+1;else waiting<=0;
   if(req_ready&&req_write&&!req_error)case(req_addr)
    0:begin if(req_wdata[1])sticky_done<=0;if(req_wdata[2])begin sticky_error<=0;last_error<=0;end end
    4:begin sticky_done<=0;sticky_error<=0;last_error<=0;result_valid<=0;last_command<=req_wdata[1:0];end
    8:base<=req_wdata;16:target<=req_wdata[1:0];20:index<=req_wdata[15:0];24:result_valid<=0;default:;
   endcase
   if(done&&!abort_core&&!cmd_valid)begin sticky_done<=1;sticky_error<=error;last_error<=error_code;result_valid<=!error&&last_command==1&&!cfg_valid;end
   if(cfg_valid&&cfg_range_bad)begin sticky_error<=1;last_error<=7;result_valid<=0;end
   if(cfg_error)begin sticky_error<=1;last_error<=7;result_valid<=0;end
   if((mem_valid&&mem_ready&&mem_error)||(mem_valid&&!mem_ready&&waiting==TIMEOUT-1))begin
    abort_core<=1;result_valid<=0;sticky_done<=1;sticky_error<=1;last_error<=mem_error?5:6;waiting<=0;
   end
  end
 end
endmodule
