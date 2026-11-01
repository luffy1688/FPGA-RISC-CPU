`timescale 1ns/1ps
module tb_icache_burst;
 reg clk=0,reset=1; always #5 clk=~clk;
 reg cv=0,inv=0; reg [31:0] ca=0;
 wire cr,ce,mv,mw,mb,mready,merror,idle;
 wire [31:0] cd,ma,mwd,mrd; wire[3:0] ms;
 reg dv=0; reg[31:0] da=0,dw=0; wire dr;
 reg integer fault_word=-1;
 assign merror=mready && (ram.i_error || ram.i_burst_word==fault_word);
 rv32_cache #(.STREAM_REFILL(1)) c(.clk(clk),.reset(reset),
 .cpu_valid(cv),.cpu_write(1'b0),.cpu_cacheable(1'b1),.cpu_addr(ca),.cpu_wdata(32'b0),.cpu_wstrb(4'b0),
 .cpu_ready(cr),.cpu_rdata(cd),.cpu_error(ce),.invalidate(inv),.idle(idle),
 .mem_valid(mv),.mem_write(mw),.mem_burst(mb),.mem_addr(ma),.mem_wdata(mwd),.mem_wstrb(ms),
 .mem_ready(mready),.mem_rdata(mrd),.mem_error(merror),.hit_pulse(),.miss_pulse(),.refill_pulse());
 soc_ram #(.RAM_WORDS(128)) ram(.clk(clk),.reset(reset),.i_valid(mv),.i_burst(mb),.i_addr(ma),
 .i_ready(mready),.i_rdata(mrd),.i_error(),.d_valid(dv),.d_write(1'b1),.d_addr(da),
 .d_wdata(dw),.d_wstrb(4'hf),.d_ready(dr),.d_rdata(),.d_error());
 integer cycle=0,commands=0,beats=0,acks=0,in_beat=0,last_beat=0,start_word=0;
 reg[31:0] command_addr;
 always @(posedge clk) if(!reset) begin
  cycle=cycle+1;
  if(mv && !ram.i_burst_active && !mready) begin
   commands=commands+1;in_beat=0;command_addr=ma;start_word=ma[4:2];
   if(!mb)$fatal(1,"not a burst");
  end
  if(mv && mready) begin
   if(ma!==command_addr)$fatal(1,"burst address changed");
   if(ram.i_burst_word!==((start_word+in_beat)%8))$fatal(1,"wrap/order error");
   if(in_beat>0 && cycle-last_beat!=1)$fatal(1,"beat gap");
   beats=beats+1;in_beat=in_beat+1;last_beat=cycle;
  end
  if(cv && cr) acks=acks+1;
  if(!cv && cr)$fatal(1,"unsolicited duplicate response");
  if(cycle>2000)$fatal(1,"timeout");
 end
 task read_word(input [31:0] address,expected,input bit exp_error);
  integer t;
  begin
   @(negedge clk);cv=1;ca=address;t=cycle;
   @(posedge clk);while(!cr)@(posedge clk);
   if(ce!==exp_error || (!exp_error && cd!==expected))
    $fatal(1,"read addr=%h got=%h err=%b expected=%h err=%b",address,cd,ce,expected,exp_error);
   if(commands==1 && acks==1 && cycle-t>5)$fatal(1,"critical word not early");
   @(negedge clk);cv=0;
  end
 endtask
 task settle;begin @(negedge clk);while(!idle)@(negedge clk);repeat(2)@(negedge clk);end endtask
 task invalidate;begin @(negedge clk);inv=1;@(negedge clk);inv=0;settle();end endtask
 integer k,before_commands;
 initial begin
  for(k=0;k<128;k=k+1)ram.mem[k]=32'h12340000+k;
  repeat(5)@(negedge clk);reset=0;
  read_word('h54,'h12340015,0);
  read_word('h58,'h12340016,0);read_word('h5c,'h12340017,0);
  settle();
  for(k=0;k<8;k=k+1)read_word('h40+4*k,32'h12340010+k,0);
  if(commands!=1 || beats!=8)$fatal(1,"line not retained commands=%d beats=%d",commands,beats);
  invalidate();fault_word=2;
  read_word('h54,'h12340015,0);settle();
  fault_word=-1;before_commands=commands;
  read_word('h40,'h12340010,0);settle();
  if(commands!=before_commands+1)$fatal(1,"late-error line became valid");
  invalidate();fault_word=5;
  read_word('h54,0,1);settle();fault_word=-1;
  if(in_beat!=8)$fatal(1,"error burst not drained");
  read_word('h54,'h12340015,0);
  // Modify the backing RAM and invalidate while the old line is still filling.
  @(negedge clk);dv=1;da='h54;dw='hfeed1234;inv=1;
  @(posedge clk);while(!dr)@(posedge clk);
  @(negedge clk);dv=0;inv=0;settle();
  before_commands=commands;read_word('h54,'hfeed1234,0);settle();
  if(commands!=before_commands+1)$fatal(1,"busy invalidate lost");
  $display("ICACHE_BURST_PASS commands=%0d beats=%0d acks=%0d cycles=%0d critical_first=1 consecutive_beats=1 errors_drained=1 busy_invalidate=1",commands,beats,acks,cycle);$finish;
 end
endmodule
