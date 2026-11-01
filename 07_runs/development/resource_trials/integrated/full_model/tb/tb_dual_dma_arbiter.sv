
`timescale 1ns/1ps
module tb_dual_dma_arbiter;
 logic clk=0;always #5 clk=~clk;logic reset=1;
 logic a_valid=0,a_write=0,b_valid=0,b_write=0;logic[31:0]a_addr=0,a_wdata=0,b_addr=0,b_wdata=0;logic[3:0]a_wstrb=0,b_wstrb=0;
 logic a_ready,a_error,b_ready,b_error;logic[31:0]a_rdata,b_rdata;
 logic m_valid,m_write;logic[31:0]m_addr,m_wdata;logic[3:0]m_wstrb;logic m_ready=0,m_error=0;logic[31:0]m_rdata=0;integer count=0;
 dual_dma_arbiter dut(.*);
 task automatic hold(input[31:0]addr,input bit write=0,input[31:0]data=0,input[3:0]strobe=0,input integer n=3);
  for(integer i=0;i<n;i++)begin
   #1;if(!m_valid||m_addr!==addr||m_write!==write||m_wdata!==data||m_wstrb!==strobe||a_ready||b_ready)$fatal(1,"heldpayload/ready addr%h want%h",m_addr,addr);
   @(posedge clk);#1;@(negedge clk);
  end
 endtask
 task automatic reply(input integer owner,input[31:0]data,input bit error=0);
  m_ready=1;m_rdata=data;m_error=error;
  #1;if(a_ready!==(owner==0)||b_ready!==(owner==1))$fatal(1,"responseowner gotA%bB%b want%0d",a_ready,b_ready,owner);
  if(owner==0&&(a_rdata!==data||a_error!==error))$fatal(1,"Aresponsecorrupt");
  if(owner==1&&(b_rdata!==data||b_error!==error))$fatal(1,"Bresponsecorrupt");
  if(owner<0&&(a_error||b_error))$fatal(1,"cancellederrorleaked");
  @(posedge clk);#1;@(negedge clk);m_ready=0;m_error=0;count++;
 endtask
 initial begin
  repeat(3)@(posedge clk);@(negedge clk);reset=0;
  // Both masters remain pending: completion-boundary roundrobin is A,B,A,B.
  a_valid=1;a_addr=32'h20000;b_valid=1;b_addr=32'h24000;b_write=1;b_wdata=32'hdeadbeef;b_wstrb=4'h5;
  hold(32'h20000);reply(0,32'h11112222);
  a_addr=32'h20004;hold(32'h24000,1,32'hdeadbeef,5);reply(1,32'h33334444,1);
  b_addr=32'h24004;hold(32'h20004);reply(0,32'h55556666);
  a_addr=32'h20008;hold(32'h24004,1,32'hdeadbeef,5);reply(1,32'h77778888);
  b_valid=0;hold(32'h20008,0,0,0,8); // capturedAthenAwithdraws
  a_valid=0;a_addr=32'h20bad;a_write=1;a_wdata=32'h01020304;a_wstrb=15;
  b_valid=1;b_addr=32'h25000;b_wdata=32'hf0f0f0f0;b_wstrb=15;
  hold(32'h20008,0,0,0,5); // savedpayloadnotreplacedbyB
  a_valid=1;a_addr=32'h21000; // Anewjobreassertedbeforeoldresponse
  hold(32'h20008,0,0,0,3);reply(-1,32'hbad0bad0,1);
  hold(32'h25000,1,32'hf0f0f0f0,15);reply(1,32'habcdef00);
  b_valid=0;hold(32'h21000,1,32'h01020304,15);reply(0,32'habcdef01);
  // SymmetricBwithdrawalwhileAarrives,cancellationmustdrainBfirst.
  a_valid=0;b_valid=1;b_addr=32'h26000;hold(32'h26000,1,32'hf0f0f0f0,15);
  b_valid=0;a_valid=1;a_addr=32'h22000;hold(32'h26000,1,32'hf0f0f0f0,15,9);reply(-1,32'hbad0bad1);
  hold(32'h22000,1,32'h01020304,15);reply(0,32'h99990000);
  a_valid=0;#1;if(m_valid||a_ready||b_ready)$fatal(1,"ghosttransaction");
  // An instantaneousdownstreamresponseisvalidwithoutopeningpendingstate.
  a_valid=1;a_addr=32'h23000;m_ready=1;m_rdata=32'h12345678;#1;
  if(!a_ready||b_ready||a_rdata!=32'h12345678)$fatal(1,"immediatecompletion");
  @(posedge clk);#1;@(negedge clk);a_valid=0;m_ready=0;#1;if(m_valid||dut.pending)$fatal(1,"immediatedrain");
  // Commonresetflushesownership; no stale responseforwardingafterreset.
  b_valid=1;b_addr=32'h27000;hold(32'h27000,1,32'hf0f0f0f0,15);
  reset=1;b_valid=0;repeat(2)@(posedge clk);@(negedge clk);reset=0;m_ready=1;m_error=1;#1;
  if(m_valid||a_ready||b_ready||a_error||b_error)$fatal(1,"resetresponsedispatch");
  $display("DUAL_DMA_OWNER_FAIR_CANCEL_PASS responses=%0d",count);$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
