`default_nettype none
// Isolated secondary hart: private 64KiB RAM, no board actuator or AI access.
module nr_worker_subsystem #(parameter INIT_FILE="",parameter integer RAM_BYTES=65536)(
 input wire clk,reset,req_valid,req_write,input wire[15:0]req_addr,input wire[31:0]req_wdata,input wire[3:0]req_wstrb,
 output wire req_ready,output logic req_error,output logic[31:0]req_rdata,
 output logic busy,done,fault,validated,tx_valid,output logic[7:0]tx_data,output logic[31:0]cycles,iterations,output wire[31:0]span_cycles,output logic[31:0]debug_pc,debug_cause,debug_value);
 logic[31:0]ticks,start_tick,primary_end,worker_end;logic[31:0]crc_seed,crc_list,crc_matrix,crc_state,crc_final;logic[2:0]reset_count;
 wire wm_icmiss,wm_dcmiss;
 wire worker_reset=reset||reset_count!=0;
 wire iv,ir,ie,dv,dw,dr,de,ilv,dlv,dlw,ici,icidle;wire[31:0]ia,idata,da,dd,drdata,ila,dla,dld;wire[3:0]ds,dls;
 wire civ,cib,cir,cie,cdv,cdw,cdr,cde;wire[31:0]cia,cid,cda,cdd,cdrdata;wire[3:0]cds;
 wire ram_dr,ram_de;wire[31:0]ram_data;
 assign req_ready=1;
 assign span_cycles=primary_end>worker_end?primary_end:worker_end;
 always_comb begin
  req_rdata=0;req_error=req_valid&&(req_addr[1:0]!=0);
  case(req_addr)
   16'h0:begin req_rdata=0;end
   16'h4:begin req_rdata=primary_end;end
   16'h8:req_rdata={28'd0,validated,fault,done,busy};
   16'hc:req_rdata=cycles;
   16'h10:req_rdata=iterations;
   16'h14:req_rdata={31'd0,validated};
   16'h18:req_rdata=span_cycles;
   16'h1c:req_rdata=worker_end;
   16'h20:req_rdata=crc_seed;16'h24:req_rdata=crc_list;16'h28:req_rdata=crc_matrix;16'h2c:req_rdata=crc_state;16'h30:req_rdata=crc_final;
   default:req_error=req_valid;
  endcase
  if(req_write&&req_addr!=0&&req_addr!=4)req_error=req_valid;
 end
 wire local_io=cdv&&cda[31:8]==24'h100000;
 wire worker_stat=cdv&&cda[31:8]==24'h100001;
 assign cdr=cda<RAM_BYTES?ram_dr:1'b1;
 assign cdrdata=cda<RAM_BYTES ? ram_data : cda==32'h10000134 ? {31'd0,busy} : 32'd1;
 assign cde=cda<RAM_BYTES?ram_de:!(local_io||worker_stat);
 always_ff @(posedge clk)begin
  if(reset)begin busy<=0;done<=0;fault<=0;validated<=0;cycles<=0;iterations<=0;reset_count<=0;ticks<=0;start_tick<=0;primary_end<=0;worker_end<=0;tx_valid<=0;tx_data<=0;debug_pc<=0;debug_cause<=0;debug_value<=0;crc_seed<=0;crc_list<=0;crc_matrix<=0;crc_state<=0;crc_final<=0;end
  else begin
   ticks<=ticks+1'b1;tx_valid<=0;
`ifdef VERILATOR
   if(!worker_reset&&cpu.trap_fire)begin debug_pc<=cpu.trap_pc;debug_cause<=cpu.trap_cause;debug_value<=cpu.trap_value;end
`endif
   if(reset_count!=0)reset_count<=reset_count-1'b1;
   if(req_valid&&req_write&&!req_error&&req_wstrb[0])begin
    if(req_addr==0&&req_wdata[0]&&!busy)begin busy<=1;done<=0;fault<=0;validated<=0;cycles<=0;iterations<=0;reset_count<=3;start_tick<=ticks;primary_end<=0;worker_end<=0;end
    if(req_addr==4)primary_end<=ticks-start_tick;
   end
   if(!worker_reset&&cdv&&cdr&&!cde&&cdw)begin
    if(cda==32'h10000000)begin tx_valid<=1;tx_data<=cdd[7:0];end
    if(cda==32'h10000120)cycles<=cdd;
    if(cda==32'h10000124)iterations<=cdd;
    if(cda==32'h10000128)validated<=cdd[0];
    if(cda==32'h10000130)worker_end<=ticks-start_tick;
    if(cda==32'h10000140)crc_seed<=cdd;if(cda==32'h10000144)crc_list<=cdd;if(cda==32'h10000148)crc_matrix<=cdd;if(cda==32'h1000014c)crc_state<=cdd;if(cda==32'h10000150)crc_final<=cdd;
    if(cda==32'h10000004&&(cdd==32'hc0||cdd==32'hee))begin busy<=0;done<=1;fault<=cdd==32'hee;end
   end
  end
 end
 rv32_worker_core #(.PREDICTOR_ENTRIES(64)) cpu(.clk(clk),.reset(worker_reset),.imem_valid(iv),.imem_addr(ia),.imem_ready(ir),.imem_rdata(idata),.imem_error(ie),
 .imem_lookahead_valid(ilv),.imem_lookahead_addr(ila),.dmem_lookahead_valid(dlv),.dmem_lookahead_we(dlw),.dmem_lookahead_addr(dla),.dmem_lookahead_wdata(dld),.dmem_lookahead_wstrb(dls),
 .dmem_valid(dv),.dmem_we(dw),.dmem_addr(da),.dmem_wdata(dd),.dmem_wstrb(ds),.dmem_ready(dr),.dmem_rdata(drdata),.dmem_error(de),
 .timer_irq(1'b0),.external_irq(1'b0),.ic_miss_event(wm_icmiss),.dc_miss_event(wm_dcmiss),.icache_idle(icidle),.icache_invalidate(ici),.commit_valid(),.commit_pc(),.commit_data(),.commit_rd(),.dbg_pc());
 rv32_cache #(.CACHE_BYTES(32768),.STREAM_REFILL(1),.LOOKAHEAD_HIT(1),.PRECOMPARE_TAGS(1))ic(.clk(clk),.reset(worker_reset),.cpu_valid(iv),.cpu_write(1'b0),.cpu_cacheable(ia<RAM_BYTES),.cpu_addr(ia),.cpu_wdata(32'd0),.cpu_wstrb(4'd0),
 .lookahead_valid(ilv),.lookahead_cacheable(ila<RAM_BYTES),.lookahead_write(1'b0),.lookahead_addr(ila),.lookahead_wdata(32'd0),.lookahead_wstrb(4'd0),
 .cpu_ready(ir),.cpu_rdata(idata),.cpu_error(ie),.invalidate(ici),.idle(icidle),.hit_pulse(),.miss_pulse(wm_icmiss),.refill_pulse(),
 .mem_valid(civ),.mem_write(),.mem_burst(cib),.mem_addr(cia),.mem_wdata(),.mem_wstrb(),.mem_ready(cir),.mem_rdata(cid),.mem_error(cie));
 rv32_cache #(.PRECOMPARE_TAGS(1),.LOOKAHEAD_HIT(1),.IDLE_LOAD_LOOKAHEAD(1),.DIRECT_BACKEND_RESPONSE(1),.EARLY_STORE_REQUEST(1))dc(.clk(clk),.reset(worker_reset),.cpu_valid(dv),.cpu_write(dw),.cpu_cacheable(da<RAM_BYTES),.cpu_addr(da),.cpu_wdata(dd),.cpu_wstrb(ds),
 .lookahead_valid(dlv),.lookahead_cacheable(dla<RAM_BYTES),.lookahead_write(dlw),.lookahead_addr(dla),.lookahead_wdata(dld),.lookahead_wstrb(dls),
 .cpu_ready(dr),.cpu_rdata(drdata),.cpu_error(de),.invalidate(1'b0),.idle(),.hit_pulse(),.miss_pulse(wm_dcmiss),.refill_pulse(),
 .mem_valid(cdv),.mem_write(cdw),.mem_burst(),.mem_addr(cda),.mem_wdata(cdd),.mem_wstrb(cds),.mem_ready(cdr),.mem_rdata(cdrdata),.mem_error(cde));
 soc_ram #(.RAM_WORDS(RAM_BYTES/4),.FAST_WRITES(1),.INIT_FILE(INIT_FILE)) ram(.clk(clk),.reset(worker_reset),.i_valid(civ),.i_burst(cib),.i_addr(cia),.i_ready(cir),.i_rdata(cid),.i_error(cie),
 .d_valid(cdv&&cda<RAM_BYTES),.d_write(cdw),.d_addr(cda),.d_wdata(cdd),.d_wstrb(cds),.d_ready(ram_dr),.d_rdata(ram_data),.d_error(ram_de));
endmodule
`default_nettype wire
