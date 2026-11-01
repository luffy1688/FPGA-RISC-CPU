
`timescale 1ns/1ps
module tb_cache_mmio_full;
 logic clk=0;always #5 clk=~clk;
 logic reset=1,req_valid=0,req_write=0;logic[15:0]req_addr=0;logic[31:0]req_wdata=0,req_rdata;logic[3:0]req_wstrb=0;
 logic req_ready,req_error,mem_valid,mem_write,mem_ready,mem_error,irq;logic[31:0]mem_addr,mem_wdata,mem_rdata;logic[3:0]mem_wstrb;
 logic freeze_dma=0,inject_error=0,last_word_error=0,last_word_stall=0;integer ticks=0,j;
 logic[31:0]status,value;logic[31:0]ram[0:131071],inputword[0:511],weight2word[0:255],bias1[0:63],bias2[0:15],hiddenpack[0:15],golden[0:15];
 semantic_cache_mmio #(.RAM_BYTES(524288),.INPUTS(2048),.HIDDEN(64),.LANES(8),.TIMEOUT(16))dut(.*);
 always_comb begin
  mem_ready=mem_valid&&!freeze_dma&&!(last_word_stall&&mem_addr==32'h0003fffc);
  mem_rdata=ram[mem_addr[18:2]];
  mem_error=mem_valid&&(inject_error||(last_word_error&&mem_addr==32'h0003fffc));
 end
 always @(posedge clk)begin ticks<=ticks+1;if(mem_write||mem_wstrb||irq)$fatal(1,"unexpected writer/IRQ");end
 task automatic wr(input[15:0]off,input[31:0]data,input[3:0]strobe=15,input bit expect_error=0);
  @(negedge clk);req_valid=1;req_write=1;req_addr=off;req_wdata=data;req_wstrb=strobe;
  #1;if(!req_ready||req_error!==expect_error)$fatal(1,"WR off%h err%b expected%b",off,req_error,expect_error);
  @(posedge clk);#1;@(negedge clk);req_valid=0;req_write=0;req_wstrb=0;
 endtask
 task automatic rd(input[15:0]off,output[31:0]data,input bit expect_error=0);
  @(negedge clk);req_valid=1;req_write=0;req_addr=off;
  #1;if(!req_ready||req_error!==expect_error)$fatal(1,"RD off%h err%b expected%b",off,req_error,expect_error);
  data=req_rdata;@(negedge clk);req_valid=0;
 endtask
 task automatic finish(input[7:0]code=0);
  integer limit;
  begin
   limit=0;status=1;
   while(status[0]&&limit<200000)begin rd(0,status);limit++;end
   repeat(3)@(posedge clk);rd(0,status);rd(48,value);
   if(limit>=200000||!status[1]||status[2]!=(code!=0)||value!=code)$fatal(1,"FIN status%h code%0d want%0d",status,value,code);
   repeat(3)@(posedge clk);rd(0,status);if(!status[1]||status[2]!=(code!=0))$fatal(1,"stickyflags");
   wr(0,6);rd(0,status);rd(48,value);if(status[2:1]!=0||value!=0)$fatal(1,"W1C");
  end
 endtask
 task automatic cfg(input[1:0]target,input[15:0]idx,input[31:0]data);
  wr(16,target);wr(20,idx);wr(24,data);
 endtask
 task automatic aux;
  begin
   for(integer i=0;i<512;i++)cfg(0,i,inputword[i]);
   for(integer i=0;i<256;i++)cfg(1,i,weight2word[i]);
   for(integer i=0;i<64;i++)cfg(2,i,bias1[i]);
   for(integer i=0;i<16;i++)cfg(3,i,bias2[i]);
  end
 endtask
 task automatic scores;
  begin
   rd(0,status);if(!status[9])$fatal(1,"resultnotvalidaftersuccess");
   for(integer i=0;i<16;i++)begin rd(256+i*4,value);if(value!==golden[i])$fatal(1,"score i%0d got%0d want%0d",i,$signed(value),$signed(golden[i]));
    rd(512+i*4,value);if(value!==hiddenpack[i])$fatal(1,"hiddenpack i%0d got%h want%h",i,value,hiddenpack[i]);end
  end
 endtask
 task automatic load;
  wr(8,131072);wr(4,0);finish();rd(0,status);if(status[9])$fatal(1,"LOADmadeResultValid");rd(256,value,1);rd(512,value,1);
 endtask
 initial begin
  `include "full_fixture.svh"
  $readmemh("/work/LUO/NeedleRV-X/07_runs/development/resource_trials/integrated/full_model/tb/full_weight.mem",ram);
  repeat(4)@(posedge clk);@(negedge clk);reset=0;
  rd(0,status);if(status!=0)$fatal(1,"resetstatus");rd(256,value,1);rd(512,value,1);
  wr(8,512,4'h7,1);rd(8,value);if(value!=0)$fatal(1,"partialstrobemutatedbase");
  wr(9,0,15,1);rd(9,value,1);wr(12,0,15,1);rd(12,value,1);wr(320,0,15,1);rd(320,value,1);
  wr(4,1);finish(2); // unconfigured cache
  load();wr(4,1);finish(3); // loadedweights but incomplete aux
  aux();
  freeze_dma=1;wr(4,0);wr(16,1,15,1);wr(20,77,15,1);wr(24,0,15,1);wr(8,512,15,1);wr(4,1,15,1);freeze_dma=0;finish();
  rd(8,value);if(value!=131072)$fatal(1,"busybasemutated");wr(4,1);rd(256,value,1);rd(512,value,1);finish();scores();
  cfg(0,512,0);rd(0,status);rd(48,value);if(!status[2]||value!=7)$fatal(1,"invalidcfgnotreported");wr(0,4);rd(0,status);if(status[2])$fatal(1,"cfgW1C");
  wr(4,1);rd(256,value,1);rd(512,value,1);finish();scores();
  $display("MMIO_PREVIOUS_GUARDS_PASS");
  inject_error=1;wr(4,0);finish(5);inject_error=0;rd(0,status);if(status[8]||status[9])$fatal(1,"DMAerrorcachevalid");rd(256,value,1);rd(512,value,1);
  wr(4,1);finish(2);aux();load();wr(4,1);rd(256,value,1);rd(512,value,1);finish();scores();
  $display("MMIO_DMA_ERROR_RECOVERY_PASS");
  freeze_dma=1;wr(4,0);finish(6);freeze_dma=0;rd(0,status);if(status[8]||status[9])$fatal(1,"timeoutcachevalid");rd(256,value,1);rd(512,value,1);
  aux();load();wr(4,1);rd(256,value,1);rd(512,value,1);finish();scores();
  $display("MMIO_TIMEOUT_RECOVERY_PASS");
  last_word_error=1;wr(4,0);wait(dut.abort_core);wr(4,1,15,1);finish(5);last_word_error=0;rd(0,status);if(status[8])$fatal(1,"lastwordDMAerrorcachevalid");
  aux();load();wr(4,1);rd(256,value,1);rd(512,value,1);finish();scores();
  $display("MMIO_LASTWORD_DMAERROR_ABORTCMD_PASS");
  last_word_stall=1;wr(4,0);wait(dut.abort_core);wr(24,32'h12345678,15,1);finish(6);last_word_stall=0;
  rd(0,status);if(status[8])$fatal(1,"lastwordtimeoutcachevalid");
  aux();load();wr(4,1);rd(256,value,1);rd(512,value,1);finish();scores();
  $display("MMIO_LASTWORD_TIMEOUT_ABORTCFG_PASS");
  wr(4,2);finish();rd(0,status);if(status[8]||status[9])$fatal(1,"invalidatekeptresult");rd(256,value,1);rd(512,value,1);
  load();wr(4,1);rd(256,value,1);rd(512,value,1);finish();scores();
  $display("CACHE_MMIO_FULL_HIDDEN64_GUARDS_PASS ticks=%0d",ticks);$finish;
 end
 initial begin #20000000;$fatal(1,"timeout");end
endmodule
