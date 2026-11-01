// HMIC_S Simplified AXI bridge: one 32-bit word request at a time.
// This interface has NO WVALID, RREADY, B channel, or response-code ports.
// A WREADY edge asks us to provide the already latched write data; the
// controller supplies WUSERO_ID/LAST. It is not a standard AXI write handshake.
`default_nettype none
module hmic_word_bridge #(
  parameter integer MEM_DQ_WIDTH = 32,
  parameter integer CTRL_ADDR_WIDTH = 28,
  parameter integer TIMEOUT_CYCLES = 1048576
)(
  input logic clk, reset, ddr_init_done,
  input logic req_valid, req_write,
  input logic [31:0] req_addr, req_wdata,
  input logic [3:0] req_wstrb,
  output logic req_ready, req_error,
  output logic [31:0] req_rdata,
  output logic busy, fault_latched,
  output logic [CTRL_ADDR_WIDTH-1:0] axi_awaddr,
  output logic axi_awuser_ap,
  output logic [3:0] axi_awuser_id, axi_awlen,
  output logic axi_awvalid,
  input logic axi_awready,
  output logic [MEM_DQ_WIDTH*8-1:0] axi_wdata,
  output logic [MEM_DQ_WIDTH-1:0] axi_wstrb,
  input logic axi_wready,
  input logic [3:0] axi_wusero_id,
  input logic axi_wusero_last,
  output logic [CTRL_ADDR_WIDTH-1:0] axi_araddr,
  output logic axi_aruser_ap,
  output logic [3:0] axi_aruser_id, axi_arlen,
  output logic axi_arvalid,
  input logic axi_arready,
  input logic [MEM_DQ_WIDTH*8-1:0] axi_rdata,
  input logic [3:0] axi_rid,
  input logic axi_rlast, axi_rvalid
);
  localparam integer DATA_BITS = MEM_DQ_WIDTH*8;
  localparam integer BEAT_BYTES = DATA_BITS/8;
  localparam integer BYTE_BITS = $clog2(BEAT_BYTES);
  localparam integer DQ_BYTE_BITS = $clog2(MEM_DQ_WIDTH/8);
  localparam integer LANE_BITS = BYTE_BITS-2;
  localparam integer COUNT_BITS = $clog2(TIMEOUT_CYCLES+1);
  // ADS subset: explicit state constants preserve the enum encoding.
  localparam logic [2:0] IDLE=3'd0, WAIT_INIT=3'd1, WRITE_ADDR=3'd2,
    WRITE_DATA=3'd3, READ_ADDR=3'd4, READ_DATA=3'd5, RESPONSE=3'd6;
  logic [2:0] state;
  logic saved_write;
  logic [31:0] saved_data;
  logic [3:0] saved_strobe;
  logic [LANE_BITS-1:0] saved_lane;
  logic [CTRL_ADDR_WIDTH-1:0] saved_addr;
  logic [COUNT_BITS-1:0] wait_count;
  logic [31:0] response_data;
  logic response_error;
  // Native address is a DDR DQ-width word, not a byte address. Each UI beat
  // transfers DDR burst length 8, so align the column address to eight words.
  wire [31:0] byte_base = req_addr & ~(BEAT_BYTES-1);
  wire [31:0] native_addr = byte_base >> DQ_BYTE_BITS;
  wire address_bad = req_addr[1:0]!=0 ||
    ((native_addr >> CTRL_ADDR_WIDTH)!=0);
  wire active = state!=IDLE && state!=RESPONSE;
  wire read_event = axi_rvalid && (state==READ_DATA ||
    (state==READ_ADDR && axi_arready));
  wire write_event = axi_wready && (state==WRITE_DATA ||
    (state==WRITE_ADDR && axi_awready));

  always_comb begin
    req_ready = state==RESPONSE;
    req_rdata = response_data;
    req_error = response_error;
    busy = state!=IDLE;
    axi_awaddr = saved_addr; axi_araddr = saved_addr;
    axi_awlen = 0; axi_arlen = 0;
    axi_awuser_ap = 0; axi_aruser_ap = 0;
    axi_awuser_id = 0; axi_aruser_id = 0;
    axi_awvalid = state==WRITE_ADDR && ddr_init_done && !fault_latched;
    axi_arvalid = state==READ_ADDR && ddr_init_done && !fault_latched;
    // Present stable data before the command is accepted, including the case
    // where the IP raises AWREADY and its first WREADY on the same clock edge.
    axi_wdata = 0; axi_wstrb = 0;
    if((state==WRITE_ADDR || state==WRITE_DATA) && !fault_latched) begin
      axi_wdata[32*saved_lane +: 32] = saved_data;
      axi_wstrb[4*saved_lane +: 4] = saved_strobe;
    end
  end

  always_ff @(posedge clk) begin
    if(reset) begin
      state<=IDLE; fault_latched<=0; wait_count<=0;
      saved_write<=0; saved_data<=0; saved_strobe<=0;
      saved_lane<=0; saved_addr<=0;
      response_data<=0; response_error<=0;
    end else begin
      if(active) wait_count<=wait_count+1'b1;
      // With no RREADY/B response, abandoning a transaction cannot cancel the
      // controller. Any uncertain failure locks out new native transactions.
      // Reset the bridge AND the DDR controller together before using it again.
      if(active && state!=WAIT_INIT && !ddr_init_done) begin
        fault_latched<=1; response_error<=1; response_data<=0; state<=RESPONSE;
      end else if(read_event) begin
        if(axi_rid!=0 || !axi_rlast) begin
          fault_latched<=1; response_error<=1; response_data<=0;
        end else begin
          response_data<=axi_rdata[32*saved_lane +: 32]; response_error<=0;
        end
        state<=RESPONSE;
      end else if(write_event) begin
        if(axi_wusero_id!=0 || !axi_wusero_last) begin
          fault_latched<=1; response_error<=1;
        end else response_error<=0;
        response_data<=0; state<=RESPONSE;
      end else if(active && wait_count==TIMEOUT_CYCLES-1) begin
        fault_latched<=1; response_error<=1; response_data<=0; state<=RESPONSE;
      end else begin
        case(state)
          IDLE: if(req_valid) begin
            saved_write<=req_write; saved_data<=req_wdata;
            saved_strobe<=req_wstrb;
            saved_lane<=req_addr[2 +: LANE_BITS];
            saved_addr<=native_addr;
            wait_count<=0; response_data<=0; response_error<=0;
            if(fault_latched || address_bad) begin
              response_error<=1; state<=RESPONSE;
            end else if(!ddr_init_done) state<=WAIT_INIT;
            else if(req_write) state<=WRITE_ADDR;
            else state<=READ_ADDR;
          end
          WAIT_INIT: if(ddr_init_done) begin
            if(saved_write) state<=WRITE_ADDR;
            else state<=READ_ADDR;
          end
          WRITE_ADDR: if(axi_awready) state<=WRITE_DATA;
          READ_ADDR: if(axi_arready) state<=READ_DATA;
          WRITE_DATA, READ_DATA: begin end
          RESPONSE: state<=IDLE;
          default: state<=IDLE;
        endcase
      end
    end
  end
  initial begin
    if((MEM_DQ_WIDTH!=16 && MEM_DQ_WIDTH!=32) ||
       CTRL_ADDR_WIDTH<1 || CTRL_ADDR_WIDTH>30 || TIMEOUT_CYCLES<2)
      $fatal(1,"HMIC bridge supports 16/32 DQ bits, 1..30 address bits, timeout>=2");
  end
endmodule
`default_nettype wire
