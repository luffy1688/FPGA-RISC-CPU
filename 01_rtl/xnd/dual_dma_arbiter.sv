
// Two fair, owner-locked DMA masters into the existing CPU/DMA RAM arbiter.
// Upstream withdraw cancels only the reply; latched payload drains downstream
// so a late response cannot acknowledge another client or a later job.
`default_nettype none
module dual_dma_arbiter(
 input logic clk,reset,
 input logic a_valid,a_write,input logic[31:0]a_addr,a_wdata,input logic[3:0]a_wstrb,
 output logic a_ready,a_error,output logic[31:0]a_rdata,
 input logic b_valid,b_write,input logic[31:0]b_addr,b_wdata,input logic[3:0]b_wstrb,
 output logic b_ready,b_error,output logic[31:0]b_rdata,
 output logic m_valid,m_write,output logic[31:0]m_addr,m_wdata,output logic[3:0]m_wstrb,
 input logic m_ready,m_error,input logic[31:0]m_rdata
);
 logic pending,owner,prefer_b,cancelled,chosen_b,chosen_valid;
 logic saved_write;logic[31:0]saved_addr,saved_wdata;logic[3:0]saved_wstrb;
 // Requests cross one register boundary before reaching the RAM arbiter.
 // Responses retain the owner until the captured downstream request drains.
 assign chosen_b=a_valid&&b_valid?prefer_b:b_valid;
 assign chosen_valid=chosen_b?b_valid:a_valid;
 assign m_valid=pending;
 assign m_write=saved_write;
 assign m_addr=saved_addr;
 assign m_wdata=saved_wdata;
 assign m_wstrb=saved_wstrb;
 assign a_ready=pending&&m_ready&&!owner&&a_valid&&!cancelled;
 assign b_ready=pending&&m_ready&&owner&&b_valid&&!cancelled;
 assign a_rdata=m_rdata;assign b_rdata=m_rdata;
 assign a_error=a_ready&&m_error;assign b_error=b_ready&&m_error;
 always_ff @(posedge clk)begin
  if(reset)begin pending<=0;owner<=0;prefer_b<=0;cancelled<=0;saved_write<=0;saved_addr<=0;saved_wdata<=0;saved_wstrb<=0;end
  else begin
   if(!pending&&chosen_valid)begin
    owner<=chosen_b;cancelled<=0;
    saved_write<=chosen_b?b_write:a_write;
    saved_addr<=chosen_b?b_addr:a_addr;
    saved_wdata<=chosen_b?b_wdata:a_wdata;
    saved_wstrb<=chosen_b?b_wstrb:a_wstrb;
    pending<=1;
   end else if(pending)begin
    if(!(owner?b_valid:a_valid))cancelled<=1;
    if(m_ready)begin pending<=0;prefer_b<=!owner;cancelled<=0;end
   end
  end
 end
endmodule
`default_nettype wire
