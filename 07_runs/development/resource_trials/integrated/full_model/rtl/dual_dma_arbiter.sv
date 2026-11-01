
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
 // Separate response assignments avoid an artificial ready->request
 // combinational dependency when nested in the existing CPU/RAM arbiter.
 assign chosen_b=pending?owner:(a_valid&&b_valid?prefer_b:b_valid);
 assign chosen_valid=chosen_b?b_valid:a_valid;
 assign m_valid=pending?1'b1:chosen_valid;
 assign m_write=pending?saved_write:(chosen_b?b_write:a_write);
 assign m_addr=pending?saved_addr:(chosen_b?b_addr:a_addr);
 assign m_wdata=pending?saved_wdata:(chosen_b?b_wdata:a_wdata);
 assign m_wstrb=pending?saved_wstrb:(chosen_b?b_wstrb:a_wstrb);
 assign a_ready=m_valid&&m_ready&&!chosen_b&&a_valid&&!(pending&&cancelled);
 assign b_ready=m_valid&&m_ready&&chosen_b&&b_valid&&!(pending&&cancelled);
 assign a_rdata=m_rdata;assign b_rdata=m_rdata;
 assign a_error=a_ready&&m_error;assign b_error=b_ready&&m_error;
 always_ff @(posedge clk)begin
  if(reset)begin pending<=0;owner<=0;prefer_b<=0;cancelled<=0;saved_write<=0;saved_addr<=0;saved_wdata<=0;saved_wstrb<=0;end
  else begin
   if(!pending&&chosen_valid)begin
    owner<=chosen_b;cancelled<=0;
    saved_write<=m_write;saved_addr<=m_addr;saved_wdata<=m_wdata;saved_wstrb<=m_wstrb;
    if(m_ready)begin pending<=0;prefer_b<=!chosen_b;end else pending<=1;
   end else if(pending)begin
    if(!(owner?b_valid:a_valid))cancelled<=1;
    if(m_ready)begin pending<=0;prefer_b<=!owner;cancelled<=0;end
   end
  end
 end
endmodule
`default_nettype wire
