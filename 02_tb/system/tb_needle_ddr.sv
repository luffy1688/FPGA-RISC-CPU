`timescale 1ns/1ps
`default_nettype none
// Optional DDR integration test. The HMIC model below is a 256-bit user
// interface model only; it is not a DDR PHY, training model, or bandwidth
// claim. The CPU/XND requests run through the real SoC owner arbiter, mailbox
// CDC, and hmic_word_bridge before reaching this model.
module tb_needle_ddr #(
  parameter bit FAULT_TEST = 1'b0
);
  logic clk=0, ui_clk=0, reset=1, uart_rx=1;
  // 27 MHz CPU clock: 37.037 ns period. The UI clock is intentionally
  // unrelated and faster (142.857 MHz, 7 ns period) to exercise CDC.
  always #18.5185 clk=~clk;
  always #3.5 ui_clk=~ui_clk;
  logic [7:0] gpio_in=0, gpio_led, gpio_out;
  logic uart_tx,uart_tx_valid; logic [7:0] uart_tx_data;
  logic [31:0] timer_value,commit_pc,commit_data,dbg_pc; logic commit_valid;
  logic [4:0] commit_rd;
  logic ddr_req_valid,ddr_req_write,ddr_req_ready,ddr_req_error;
  logic [31:0] ddr_req_addr,ddr_req_wdata,ddr_req_rdata;
  logic [3:0] ddr_req_wstrb;
  logic ddr_available,ddr_fault,ddr_busy;
  logic controller_init_done=0;
  logic axi_awuser_ap,axi_aruser_ap,axi_awvalid,axi_arvalid;
  logic [27:0] axi_awaddr,axi_araddr;
  logic [3:0] axi_awuser_id,axi_awlen,axi_aruser_id,axi_arlen;
  logic [255:0] axi_wdata,axi_rdata;
  logic [31:0] axi_wstrb;
  logic axi_awready,axi_arready,axi_wready,axi_rvalid,axi_rlast;
  logic [3:0] axi_wusero_id,axi_rid; logic axi_wusero_last;
  // Full 1 MiB memory model. Read data is latched at accepted AR below,
  // avoiding an always_comb sensitivity list over every RAM word.
  logic [31:0] memory [0:262143];
  logic wpending=0,rpending=0,drop_next_read=0,drop_active=0,late_fire=0;
  logic [27:0] waddr=0,raddr=0; integer rdelay=0,late_delay=0;
  integer aw_count=0,w_count=0,ar_count=0,read_count=0,write_count=0;
  integer bad_cmd=0; logic saw_preinit_cmd=0,late_response_seen=0;
  logic seen_20=0,seen_22=0,seen_30=0,seen_40=0;
  integer ui_ticks=0;
  function automatic [31:0] model_read(input integer idx);
    begin
      if(idx<0 || idx>=262144) $fatal(1,"HMIC read index outside 1 MiB: %0d",idx);
      model_read=memory[idx];
    end
  endfunction

  needle_soc #(
    .INIT_FILE(FAULT_TEST ? "07_runs/ddr/fault.mem" : "07_runs/ddr/bringup.mem"),
    .CLK_HZ(27_000_000), .BAUD(115200), .CACHE_ENABLE(1'b0),
    .ENABLE_DDR(1'b1), .DDR_BASE(32'h80000000), .DDR_BYTES(1048576),
    .DDR_DMA_TIMEOUT(4096)
  ) dut (
    .clk,.reset,.uart_rx,.gpio_in,.uart_tx,.gpio_led,.uart_tx_valid,
    .uart_tx_data,.gpio_out,.timer_value,.commit_valid,.commit_pc,
    .commit_data,.commit_rd,.dbg_pc,
    .ddr_req_valid,.ddr_req_write,.ddr_req_addr,.ddr_req_wdata,
    .ddr_req_wstrb,.ddr_req_ready,.ddr_req_error,.ddr_req_rdata,
    .ddr_available,.ddr_fault,.ddr_busy
  );
  needle_ddr_subsystem #(.HMIC_TIMEOUT_CYCLES(48)) ddr (
    .clk,.ui_clk,.reset,.controller_init_done,
    .req_valid(ddr_req_valid),.req_write(ddr_req_write),.req_addr(ddr_req_addr),
    .req_wdata(ddr_req_wdata),.req_wstrb(ddr_req_wstrb),.req_ready(ddr_req_ready),
    .req_error(ddr_req_error),.req_rdata(ddr_req_rdata),.available(ddr_available),
    .fault(ddr_fault),.busy(ddr_busy),
    .axi_awaddr,.axi_araddr,.axi_awuser_ap,.axi_aruser_ap,.axi_awuser_id,
    .axi_awlen,.axi_aruser_id,.axi_arlen,.axi_awvalid,.axi_arvalid,
    .axi_awready,.axi_arready,.axi_wdata,.axi_wstrb,.axi_wready,
    .axi_wusero_id,.axi_wusero_last,.axi_rdata,.axi_rid,.axi_rlast,.axi_rvalid
  );

  // Deliberate UI backpressure is bounded and deterministic.
  assign axi_awready = controller_init_done && !wpending && ((ui_ticks & 3)!=0);
  assign axi_arready = controller_init_done && !rpending && ((ui_ticks & 3)!=1);
  assign axi_wready = controller_init_done && (wpending ||
    (axi_awvalid && axi_awready && ((ui_ticks & 1)==0)));
  assign axi_wusero_id=0; assign axi_wusero_last=1;
  assign axi_rid=0; assign axi_rlast=1;
  assign axi_rvalid = late_fire || (rpending && rdelay==0 && !drop_active);

  // The model's lane storage is 32-bit words indexed by native address. It
  // checks command alignment/metadata and intentionally delays both channels.
  always @(posedge ui_clk) begin
    ui_ticks<=ui_ticks+1;
    late_fire<=0;
    if(reset) begin
      controller_init_done<=0; wpending<=0; rpending<=0; rdelay<=0;
      late_delay<=0; drop_active<=0; late_response_seen<=0;
      axi_rdata<='0;
      aw_count<=0;w_count<=0;ar_count<=0;read_count<=0;write_count<=0;
      bad_cmd<=0;saw_preinit_cmd<=0;
    end else begin
      if(!controller_init_done && ui_ticks>=8) controller_init_done<=1;
      if((axi_awvalid || axi_arvalid) && !controller_init_done) saw_preinit_cmd<=1;
      if(axi_awvalid && axi_awready) begin
        // One HMIC command covers eight 32-bit lanes. Check the complete
        // accepted range before indexing the 1 MiB (262144-word) model.
        if(axi_awlen!=0 || axi_awuser_id!=0 || axi_awaddr[2:0]!=0)
          $fatal(1,"bad HMIC AW metadata addr=%h",axi_awaddr);
        if(axi_awaddr > 28'd262136)
          $fatal(1,"HMIC AW range addr=%h plus 7 exceeds 1 MiB",axi_awaddr);
        wpending<=1; waddr<=axi_awaddr; aw_count<=aw_count+1;
      end
      if(axi_wready) begin
        if((^axi_wdata === 1'bx) || (^axi_wstrb === 1'bx))
          $fatal(1,"X/Z in accepted HMIC write payload");
        for(integer b=0;b<32;b=b+1) begin
          if(axi_wstrb[b]) begin
            memory[(wpending?waddr:axi_awaddr)+b/4][8*(b%4)+:8] <= axi_wdata[8*b+:8];
          end
        end
        if(axi_wusero_id!=0 || !axi_wusero_last) bad_cmd<=bad_cmd+1;
        wpending<=0; w_count<=w_count+1; write_count<=write_count+1;
      end
      if(axi_arvalid && axi_arready) begin
        if(axi_arlen!=0 || axi_aruser_id!=0 || axi_araddr[2:0]!=0)
          $fatal(1,"bad HMIC AR metadata addr=%h",axi_araddr);
        if(axi_araddr > 28'd262136)
          $fatal(1,"HMIC AR range addr=%h plus 7 exceeds 1 MiB",axi_araddr);
        // The response contains a snapshot of the accepted native beat.
        for(integer k=0;k<8;k=k+1)
          axi_rdata[32*k+:32] <= model_read(axi_araddr+k);
        rpending<=1; raddr<=axi_araddr; rdelay<=2; ar_count<=ar_count+1;
        read_count<=read_count+1;
        if(drop_next_read) begin
          drop_next_read<=0; drop_active<=1; late_delay<=64;
        end
      end else if(rpending && rdelay>0) rdelay<=rdelay-1;
      if(drop_active && late_delay>0) begin
        late_delay<=late_delay-1;
        if(late_delay==1) begin late_fire<=1; late_response_seen<=1; drop_active<=0; end
      end
      if(axi_rvalid) begin
        if((^axi_rdata === 1'bx))
          $fatal(1,"X/Z in accepted HMIC read payload addr=%h",raddr);
        rpending<=0;
      end
    end
  end

  // CPU/XND response and marker checks use reduction XOR and case equality so an unknown value
  // cannot accidentally pass a C `if (!ok)` check in the firmware image.
  always @(posedge clk) begin
    if(!reset) begin
      if((^gpio_led === 1'bx)) $fatal(1,"X/Z on CPU GPIO marker");
      if(ddr_req_valid && ddr_req_ready && (^ddr_req_rdata === 1'bx))
        $fatal(1,"X/Z on CPU/XND DDR response");
      if(gpio_led===8'h20) seen_20<=1;
      if(gpio_led===8'h22) seen_22<=1;
      if(gpio_led===8'h30) seen_30<=1;
      if(gpio_led===8'h40) seen_40<=1;
    end
  end

  // Fault firmware marks the point immediately before its intentionally
  // dropped read. Dropping only that next command exercises timeout and late
  // response quarantine without changing the normal successful path.
  always @(posedge clk) if(!reset && FAULT_TEST && gpio_led==8'hd1) drop_next_read<=1;

  initial begin
    for(integer k=0;k<262144;k=k+1) memory[k]=32'd0;
    repeat(5) @(posedge clk); reset=0;
    if(FAULT_TEST) begin
      wait(gpio_led===8'ha6);
      repeat(80) @(posedge ui_clk);
      if(!late_response_seen) $fatal(1,"late response was not generated");
      if(!ddr_fault) $fatal(1,"DDR fault was not latched");
    end else begin
      wait(gpio_led===8'ha5);
      repeat(20) @(posedge clk);
      if(!seen_20 || !seen_22 || !seen_30 || !seen_40)
        $fatal(1,"missing firmware evidence markers 20=%0d 22=%0d 30=%0d 40=%0d",seen_20,seen_22,seen_30,seen_40);
    end
    if(saw_preinit_cmd) $fatal(1,"HMIC command escaped before init");
    if(bad_cmd!=0) $fatal(1,"HMIC command metadata/alignment errors=%0d",bad_cmd);
    if(aw_count==0 || w_count==0 || ar_count==0) $fatal(1,"missing HMIC traffic aw=%0d w=%0d ar=%0d",aw_count,w_count,ar_count);
    $display("PASS DDR integration fault=%0d gpio=%02x aw=%0d w=%0d ar=%0d late=%0d ddr_fault=%0d",FAULT_TEST,gpio_led,aw_count,w_count,ar_count,late_response_seen,ddr_fault);
    $finish;
  end
  initial begin #30000000; $fatal(1,"DDR integration timeout gpio=%02x busy=%0d fault=%0d",gpio_led,ddr_busy,ddr_fault); end
endmodule
`default_nettype wire
