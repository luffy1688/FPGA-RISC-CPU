// Optional DDR subsystem: core word bus -> safe mailbox CDC -> HMIC_S UI.
// This is synthesizable user logic. The HMIC controller/PHY is external;
// behavioral simulation of its UI does not prove DDR training or bandwidth.
`default_nettype none
module needle_ddr_subsystem #(
  parameter integer HMIC_TIMEOUT_CYCLES=1048576
)(
  input logic clk,ui_clk,reset,controller_init_done,
  input logic req_valid,req_write,
  input logic [31:0] req_addr,req_wdata,
  input logic [3:0] req_wstrb,
  output logic req_ready,req_error,
  output logic [31:0] req_rdata,
  output logic available,fault,busy,
  output logic [27:0] axi_awaddr,axi_araddr,
  output logic axi_awuser_ap,axi_aruser_ap,
  output logic [3:0] axi_awuser_id,axi_awlen,axi_aruser_id,axi_arlen,
  output logic axi_awvalid,axi_arvalid,
  input logic axi_awready,axi_arready,
  output logic [255:0] axi_wdata,
  output logic [31:0] axi_wstrb,
  input logic axi_wready,
  input logic [3:0] axi_wusero_id,
  input logic axi_wusero_last,
  input logic [255:0] axi_rdata,
  input logic [3:0] axi_rid,
  input logic axi_rlast,axi_rvalid
);
  (* ASYNC_REG="TRUE" *) logic init_meta,init_sync,fault_meta,fault_sync;
  logic fault_src;
  logic cdc_valid,cdc_ready,cdc_error,cdc_busy;
  logic [31:0] cdc_rdata;
  logic ui_valid,ui_write,ui_ready,ui_error,ui_busy,ui_fault;
  logic [31:0] ui_addr,ui_wdata,ui_rdata;
  logic [3:0] ui_wstrb;
  // Init/fault are sampled in the CPU domain. No request starts before a stable
  // init flag; an early CPU/XND request returns a local access error.
  always_ff @(posedge clk or posedge reset) begin
    if(reset) begin init_meta<=0;init_sync<=0;fault_meta<=0;fault_sync<=0;fault_src<=0;end
    else begin
      init_meta<=controller_init_done;init_sync<=init_meta;
      fault_meta<=ui_fault;fault_sync<=fault_meta;
      if(fault_sync || (cdc_ready && cdc_error)) fault_src<=1;
    end
  end
  assign fault=fault_src || fault_sync;
  assign available=init_sync && !fault && !reset;
  assign busy=cdc_busy;
  assign cdc_valid=req_valid && available;
  // In-flight responses always take precedence. Once a bridge failure occurs,
  // no new request can cross CDC; late HMIC replies are quarantined by the
  // bridge. Recovery requires common reset of source/CDC/bridge/controller.
  assign req_ready=cdc_ready || (req_valid && !cdc_busy && !available && !reset);
  assign req_error=cdc_ready ? cdc_error : 1'b1;
  assign req_rdata=cdc_ready ? cdc_rdata : 32'd0;
  word_bus_cdc u_cdc(
    .src_clk(clk),.dst_clk(ui_clk),.reset(reset),
    .src_valid(cdc_valid),.src_write(req_write),.src_addr(req_addr),
    .src_wdata(req_wdata),.src_wstrb(req_wstrb),.src_ready(cdc_ready),
    .src_error(cdc_error),.src_rdata(cdc_rdata),.src_busy(cdc_busy),
    .dst_valid(ui_valid),.dst_write(ui_write),.dst_addr(ui_addr),
    .dst_wdata(ui_wdata),.dst_wstrb(ui_wstrb),.dst_ready(ui_ready),
    .dst_error(ui_error),.dst_rdata(ui_rdata));
  hmic_word_bridge #(.TIMEOUT_CYCLES(HMIC_TIMEOUT_CYCLES)) u_bridge(
    .clk(ui_clk),.reset(reset),.ddr_init_done(controller_init_done),
    .req_valid(ui_valid),.req_write(ui_write),.req_addr(ui_addr),
    .req_wdata(ui_wdata),.req_wstrb(ui_wstrb),.req_ready(ui_ready),
    .req_error(ui_error),.req_rdata(ui_rdata),.busy(ui_busy),.fault_latched(ui_fault),
    .axi_awaddr(axi_awaddr),.axi_awuser_ap(axi_awuser_ap),.axi_awuser_id(axi_awuser_id),.axi_awlen(axi_awlen),.axi_awvalid(axi_awvalid),.axi_awready(axi_awready),
    .axi_wdata(axi_wdata),.axi_wstrb(axi_wstrb),.axi_wready(axi_wready),.axi_wusero_id(axi_wusero_id),.axi_wusero_last(axi_wusero_last),
    .axi_araddr(axi_araddr),.axi_aruser_ap(axi_aruser_ap),.axi_aruser_id(axi_aruser_id),.axi_arlen(axi_arlen),.axi_arvalid(axi_arvalid),.axi_arready(axi_arready),
    .axi_rdata(axi_rdata),.axi_rid(axi_rid),.axi_rlast(axi_rlast),.axi_rvalid(axi_rvalid));
endmodule
`default_nettype wire
