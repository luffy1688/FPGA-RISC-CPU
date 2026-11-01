`timescale 1ns/1ps
`default_nettype none
// Behavioral model of the actual Simplified AXI UI, not DDR PHY/training.
module tb_hmic_word_bridge;
  logic clk=0,reset=1,ddr_init_done=0;
  always #5 clk=~clk;
  logic req_valid=0,req_write=0;
  logic [31:0] req_addr=0,req_wdata=0;
  logic [3:0] req_wstrb=0;
  wire req_ready,req_error,busy,fault_latched;
  wire [31:0] req_rdata;
  wire [27:0] axi_awaddr,axi_araddr;
  wire axi_awuser_ap,axi_aruser_ap,axi_awvalid,axi_arvalid;
  wire [3:0] axi_awuser_id,axi_awlen,axi_aruser_id,axi_arlen;
  wire [255:0] axi_wdata;
  wire [31:0] axi_wstrb;
  logic axi_awready,axi_wready,axi_arready,axi_rvalid,axi_rlast;
  logic [255:0] axi_rdata;
  logic [3:0] axi_wusero_id,axi_rid;
  logic axi_wusero_last;
  hmic_word_bridge #(.TIMEOUT_CYCLES(32)) dut(.*);
  logic [31:0] memory[0:63];
  logic wpending=0,rpending=0;
  logic [27:0] waddr=0,raddr=0;
  logic aw_enable=1,w_enable=1,ar_enable=1,drop_read=0;
  logic same_cycle=0,bad_id=0,bad_last=0,late_response=0;
  integer rdelay=0,read_delay=2,aw_count=0,w_count=0,ar_count=0;
  logic [255:0] saved_wdata;
  logic [31:0] saved_wstrb;
  logic have_waiting_write=0;

  always_comb begin
    axi_awready=aw_enable && !wpending && ddr_init_done;
    axi_arready=ar_enable && !rpending && ddr_init_done;
    axi_wready=w_enable && (wpending ||
      (same_cycle && axi_awvalid && axi_awready));
    axi_wusero_id=bad_id ? 4'd1 : 4'd0;
    axi_wusero_last=!bad_last;
    axi_rvalid=(rpending && rdelay==0 && !drop_read) ||
      (same_cycle && axi_arvalid && axi_arready) || late_response;
    axi_rid=bad_id ? 4'd1 : 4'd0;
    axi_rlast=!bad_last;
    for(integer k=0;k<8;k=k+1)
      axi_rdata[32*k+:32]=memory[(same_cycle && axi_arvalid ? axi_araddr : raddr)+k];
  end
  always @(posedge clk) begin
    if(reset) begin
      wpending<=0; rpending<=0; rdelay<=0;
      aw_count<=0;w_count<=0;ar_count<=0;have_waiting_write<=0;
    end else begin
      if(axi_awvalid && !axi_awready) begin
        if(have_waiting_write &&
           (saved_wdata!==axi_wdata || saved_wstrb!==axi_wstrb))
          $fatal(1,"write payload changed during AW backpressure");
        saved_wdata<=axi_wdata;saved_wstrb<=axi_wstrb;have_waiting_write<=1;
      end
      if(axi_awvalid && axi_awready) begin
        if(axi_awlen!=0 || axi_awuser_id!=0 || axi_awaddr[2:0]!=0)
          $fatal(1,"incorrect native single-beat write command");
        wpending<=1;waddr<=axi_awaddr;aw_count<=aw_count+1;
      end
      if(axi_wready) begin
        for(integer b=0;b<32;b=b+1)
          if(axi_wstrb[b])
            memory[(wpending ? waddr : axi_awaddr)+b/4][8*(b%4)+:8]
              <=axi_wdata[8*b+:8];
        wpending<=0;w_count<=w_count+1;have_waiting_write<=0;
      end
      if(axi_arvalid && axi_arready) begin
        if(axi_arlen!=0 || axi_aruser_id!=0 || axi_araddr[2:0]!=0)
          $fatal(1,"incorrect native single-beat read command");
        rpending<=1;raddr<=axi_araddr;rdelay<=read_delay;ar_count<=ar_count+1;
      end else if(rpending && rdelay!=0) rdelay<=rdelay-1;
      if(axi_rvalid) rpending<=0;
    end
  end

  task automatic request(input bit wr,input logic [31:0] addr,data,
                         input logic [3:0] strobe,input bit error_expected,
                         input logic [31:0] expected);
    integer n;
    begin
      @(negedge clk);req_valid=1;req_write=wr;req_addr=addr;
      req_wdata=data;req_wstrb=strobe;n=0;
      begin : wait_reply
        forever begin
          @(posedge clk);n=n+1;
          if(n>70) $fatal(1,"bridge response timeout addr=%08x",addr);
          if(req_ready) begin
            if(req_error!==error_expected) $fatal(1,"response error mismatch");
            if(!wr && !error_expected && req_rdata!==expected)
              $fatal(1,"lane mismatch addr=%x got=%x expected=%x",addr,req_rdata,expected);
            disable wait_reply;
          end
        end
      end
      @(negedge clk);req_valid=0;
    end
  endtask
  task automatic reset_both;
    begin
      @(negedge clk);reset=1;req_valid=0;
      bad_id=0;bad_last=0;drop_read=0;late_response=0;
      aw_enable=1;w_enable=1;ar_enable=1;same_cycle=0;
      repeat(3) @(negedge clk);reset=0;ddr_init_done=1;
    end
  endtask
  integer old_aw,old_ar,old_w;
  initial begin
    for(integer k=0;k<64;k=k+1) memory[k]=32'ha0000000+32'(k);
    repeat(3) @(negedge clk);reset=0;
    // No address command reaches the IP before DDR initialization finishes.
    fork
      request(0,32'h1c,0,0,0,32'ha0000007);
      begin
        repeat(5) @(negedge clk);
        if(axi_arvalid || axi_awvalid) $fatal(1,"command before initialization");
        ddr_init_done=1;
      end
    join
    // Each 256-bit beat contains eight 32-bit words, including the next beat.
    for(integer k=0;k<16;k=k+1)
      request(0,32'(k*4),0,0,0,32'ha0000000+32'(k));
    ar_enable=0;
    fork
      request(0,32'h8,0,0,0,32'ha0000002);
      begin repeat(4) @(negedge clk);ar_enable=1;end
    join
    // AW and WREADY can be separated by arbitrary backpressure. Exactly one
    // 4-byte word is strobed inside the 32-byte beat, without read-modify-write.
    aw_enable=0;w_enable=0;
    fork
      request(1,32'h14,32'h11223344,4'b0101,0,0);
      begin
        repeat(4) @(negedge clk);aw_enable=1;
        repeat(4) @(negedge clk);w_enable=1;
      end
    join
    request(0,32'h14,0,0,0,32'ha0220044);
    request(0,32'h10,0,0,0,32'ha0000004);
    request(0,32'h18,0,0,0,32'ha0000006);
    if(aw_count!=1 || w_count!=1) $fatal(1,"write duplicate/lost");
    same_cycle=1;
    request(1,32'h20,32'hdeadbeef,4'hf,0,0);
    request(0,32'h20,0,0,0,32'hdeadbeef);
    same_cycle=0;
    // A locally invalid address causes no native request and does not poison
    // subsequent legal accesses. Native 28-bit word space is exactly 1 GiB.
    old_ar=ar_count;
    request(0,32'h1,0,0,1,0);
    request(0,32'h40000000,0,0,1,0);
    if(ar_count!=old_ar || fault_latched) $fatal(1,"local range/alignment error");
    request(0,32'h0,0,0,0,32'ha0000000);
    // Read timeout locks the bridge: a late old response must not be reused.
    drop_read=1;request(0,32'h0,0,0,1,0);
    if(!fault_latched) $fatal(1,"timeout did not latch fault");
    old_ar=ar_count;late_response=1;
    request(0,32'h4,0,0,1,0);
    if(ar_count!=old_ar || axi_arvalid || axi_awvalid || axi_wstrb!=0)
      $fatal(1,"new transaction escaped fault lock");
    reset_both();request(0,32'h0,0,0,0,32'ha0000000);
    bad_id=1;request(0,32'h0,0,0,1,0);
    if(!fault_latched) $fatal(1,"wrong read ID not rejected");
    reset_both();bad_last=1;request(0,32'h0,0,0,1,0);
    if(!fault_latched) $fatal(1,"wrong read LAST not rejected");
    reset_both();bad_last=1;request(1,32'h4,32'h01234567,4'hf,1,0);
    if(!fault_latched) $fatal(1,"wrong write LAST not rejected");
    reset_both();aw_enable=0;request(1,32'h0,0,4'hf,1,0);
    if(!fault_latched) $fatal(1,"AW timeout did not latch fault");
    reset_both();w_enable=0;request(1,32'h0,0,4'hf,1,0);
    if(!fault_latched) $fatal(1,"W window timeout did not latch fault");
    reset_both();
    fork
      request(0,32'h0,0,0,1,0);
      begin
        @(negedge clk);@(negedge clk);ddr_init_done=0;
      end
    join
    if(!fault_latched) $fatal(1,"initialization loss did not latch fault");
    reset_both();ddr_init_done=0;request(0,32'h0,0,0,1,0);
    if(!fault_latched) $fatal(1,"initialization timeout did not latch fault");
    reset_both();request(0,32'h0,0,0,0,32'ha0000000);
    $display("PASS HMIC word bridge: 256-bit lanes, native address, byte strobe, AW/W window, init, timeout lock, ID/LAST, reset");
    $finish;
  end
  initial begin #100000; $fatal(1,"test global timeout");end
endmodule
`default_nettype wire
