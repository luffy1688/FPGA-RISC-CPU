// needle_soc = CPU + caches + main RAM + peripherals + XND accelerator.
// The word "SoC" means a complete small computer assembled inside the FPGA.
// Experimental dual accelerator: low128KiB cached, remaining SRAM sharedAI.
`default_nettype none
module needle_soc #(
  parameter INIT_FILE="",
  parameter integer SRAM_BYTES=524288,
  parameter bit SEMANTIC_ENABLE=1,
  parameter integer SEMANTIC_LANES=8,
  parameter integer SEMANTIC_DMA_TIMEOUT=4096,
  parameter integer CLK_HZ=50000000,
  parameter integer BAUD=115200,
  parameter bit CACHE_ENABLE=1,
  parameter bit PREDICT_ENABLE=1,
  parameter bit CPU_FETCH_OVERLAP=1,
  parameter bit CPU_FETCH_PREFETCH=1,
  parameter bit ICACHE_BURST_ENABLE=1,
  parameter bit ICACHE_LOOKAHEAD_ENABLE=1,
  parameter bit XND_ENABLE=1,
  parameter bit XND_WEIGHT_PREFETCH=1,
  parameter bit HARD_ADC=0,
  parameter bit ENABLE_DDR=0,
  parameter logic [31:0] DDR_BASE=32'h80000000,
  parameter integer DDR_BYTES=1048576,
  parameter integer DDR_DMA_TIMEOUT=16777216
)(
  input logic clk,reset,uart_rx,
  input logic [7:0] gpio_in,
  output logic uart_tx,
  output logic [7:0] gpio_led,
  // Byte-level simulation/debug event, emitted only when UART accepts a byte.
  output logic uart_tx_valid,
  output logic [7:0] uart_tx_data,
  output logic [7:0] gpio_out,
  output logic [31:0] timer_value,
  output logic commit_valid,
  output logic [31:0] commit_pc,commit_data,
  output logic [4:0] commit_rd,
  output logic [31:0] dbg_pc,
  // Optional data-only, uncached DDR word bus. Address is relative byte offset.
  output logic ddr_req_valid,ddr_req_write,
  output logic [31:0] ddr_req_addr,ddr_req_wdata,
  output logic [3:0] ddr_req_wstrb,
  input logic ddr_req_ready,ddr_req_error,
  input logic [31:0] ddr_req_rdata,
  input logic ddr_available,ddr_fault,ddr_busy
);
  logic imem_lookahead_valid;logic [31:0] imem_lookahead_addr;
  logic imem_valid,imem_ready,imem_error,dmem_valid,dmem_we,dmem_ready,dmem_error;
  logic [31:0] imem_addr,imem_rdata,dmem_addr,dmem_wdata,dmem_rdata;
  logic [3:0] dmem_wstrb;
  logic ic_valid,ic_write,ic_burst,ic_ready,ic_error,ic_idle,ic_invalidate,ic_miss;
  logic [31:0] ic_addr,ic_wdata,ic_rdata;
  logic [3:0] ic_wstrb;
  logic dc_valid,dc_write,dc_ready,dc_error,dc_miss;
  logic [31:0] dc_addr,dc_wdata,dc_rdata;
  logic [3:0] dc_wstrb;
  logic timer_irq,xnd_irq;
  logic xm_valid,xm_write,xm_ready,xm_error;
  logic [31:0] xm_addr,xm_wdata,xm_rdata;
  logic [3:0] xm_wstrb;
  logic xreq_ready,xreq_error;
  logic [31:0] xreq_rdata;
  logic x0m_valid,x0m_write,x0m_ready,x0m_error,sm_valid,sm_write,sm_ready,sm_error,semantic_irq;
  logic [31:0]x0m_addr,x0m_wdata,x0m_rdata,sm_addr,sm_wdata,sm_rdata;
  logic [3:0]x0m_wstrb,sm_wstrb;
  logic sreq_ready,sreq_error;logic[31:0]sreq_rdata;
  logic ram_valid,ram_write,ram_ready,ram_error;
  logic [31:0] ram_addr,ram_wdata,ram_rdata;
  logic [3:0] ram_wstrb;
  logic ram_pending,ram_owner,prefer_xnd;
  logic chosen_xnd,chosen_ddr,ram_target_ddr,ddr_cancelled;
  logic [31:0] saved_ddr_addr,saved_ddr_wdata;
  logic [3:0] saved_ddr_wstrb;
  logic saved_ddr_write,selected_valid,selected_write,memory_ready,memory_error;
  logic [31:0] selected_addr,selected_wdata,memory_rdata;
  logic [3:0] selected_wstrb;
  // Keep the low BRAM decode before the optional DDR expression. Some
  // simulators require declarations referenced by a continuous assignment to
  // appear earlier in the source; this ordering is also easier to audit.
  wire cpu_ram=dc_addr<SRAM_BYTES;
  wire cpu_ddr=ENABLE_DDR && dc_addr>=DDR_BASE &&
               {32'd0,dc_addr}<({32'd0,DDR_BASE}+{32'd0,DDR_BYTES});
  wire cpu_memory=cpu_ram || cpu_ddr;
  wire xnd_select=XND_ENABLE && dc_addr[31:16]==16'h4000;
  wire semantic_select=SEMANTIC_ENABLE&&dc_addr[31:16]==16'h4001;
  wire periph_select=dc_addr>=32'h10000000 && dc_addr<32'h10000110;

  rv32i_core #(.PREDICT_ENABLE(PREDICT_ENABLE),.FETCH_DECODE_OVERLAP(CPU_FETCH_OVERLAP),.FETCH_PREFETCH_ENABLE(CPU_FETCH_PREFETCH)) u_cpu(
    .clk(clk),.reset(reset),
    .imem_valid(imem_valid),.imem_addr(imem_addr),.imem_ready(imem_ready),.imem_rdata(imem_rdata),.imem_error(imem_error),
    .imem_lookahead_valid(imem_lookahead_valid),.imem_lookahead_addr(imem_lookahead_addr),
    .dmem_valid(dmem_valid),.dmem_we(dmem_we),.dmem_addr(dmem_addr),.dmem_wdata(dmem_wdata),.dmem_wstrb(dmem_wstrb),
    .dmem_ready(dmem_ready),.dmem_rdata(dmem_rdata),.dmem_error(dmem_error),
    .timer_irq(timer_irq),.external_irq(xnd_irq),.ic_miss_event(ic_miss),.dc_miss_event(dc_miss),
    .icache_idle(ic_idle),.icache_invalidate(ic_invalidate),
    .commit_valid(commit_valid),.commit_pc(commit_pc),.commit_data(commit_data),.commit_rd(commit_rd),.dbg_pc(dbg_pc));
  rv32_cache #(.STREAM_REFILL(ICACHE_BURST_ENABLE),.LOOKAHEAD_HIT(ICACHE_LOOKAHEAD_ENABLE)) u_icache(
    .clk(clk),.reset(reset),
    .cpu_valid(imem_valid),.cpu_write(1'b0),
    .cpu_cacheable(CACHE_ENABLE && imem_addr<32'h00020000),
    .cpu_addr(imem_addr),.cpu_wdata(32'd0),.cpu_wstrb(4'd0),
    .lookahead_valid(imem_lookahead_valid),.lookahead_addr(imem_lookahead_addr),
    .lookahead_cacheable(CACHE_ENABLE && imem_lookahead_addr<32'h00020000),
    .cpu_ready(imem_ready),.cpu_rdata(imem_rdata),.cpu_error(imem_error),
    .mem_valid(ic_valid),.mem_write(ic_write),.mem_burst(ic_burst),.mem_addr(ic_addr),
    .mem_wdata(ic_wdata),.mem_wstrb(ic_wstrb),
    .mem_ready(ic_ready),.mem_rdata(ic_rdata),.mem_error(ic_error),
    .invalidate(ic_invalidate),.idle(ic_idle),
    .hit_pulse(),.miss_pulse(ic_miss),.refill_pulse());
  rv32_cache u_dcache(
    .clk(clk),.reset(reset),
    .cpu_valid(dmem_valid),.cpu_write(dmem_we),
    .cpu_cacheable(CACHE_ENABLE && dmem_addr<32'h00020000),
    .cpu_addr(dmem_addr),.cpu_wdata(dmem_wdata),.cpu_wstrb(dmem_wstrb),
    .lookahead_valid(1'b0),.lookahead_addr(32'd0),.lookahead_cacheable(1'b0),
    .cpu_ready(dmem_ready),.cpu_rdata(dmem_rdata),.cpu_error(dmem_error),
    .mem_valid(dc_valid),.mem_write(dc_write),.mem_burst(),.mem_addr(dc_addr),
    .mem_wdata(dc_wdata),.mem_wstrb(dc_wstrb),
    .mem_ready(dc_ready),.mem_rdata(dc_rdata),.mem_error(dc_error),
    .invalidate(1'b0),.idle(),.hit_pulse(),.miss_pulse(dc_miss),.refill_pulse());

  generate
    if (XND_ENABLE) begin : gen_xnd
      xnd_engine #(.RAM_LAST(SRAM_BYTES-1),.WEIGHT_PREFETCH(XND_WEIGHT_PREFETCH),.ENABLE_DDR(ENABLE_DDR),.DDR_BASE(DDR_BASE),.DDR_BYTES(DDR_BYTES),
        .DMA_TIMEOUT(ENABLE_DDR ? DDR_DMA_TIMEOUT : 4096)) u_xnd(
        .clk(clk),.reset(reset),
        .req_valid(dc_valid && xnd_select),.req_write(dc_write),
        .req_addr(dc_addr[15:0]),.req_wdata(dc_wdata),.req_wstrb(dc_wstrb),
        .req_ready(xreq_ready),.req_rdata(xreq_rdata),.req_error(xreq_error),
        .mem_valid(x0m_valid),.mem_write(x0m_write),.mem_addr(x0m_addr),
        .mem_wdata(x0m_wdata),.mem_wstrb(x0m_wstrb),
        .mem_ready(x0m_ready),.mem_rdata(x0m_rdata),.mem_error(x0m_error),.irq(xnd_irq));
    end else begin : gen_no_xnd
      assign xreq_ready=1'b0;
      assign xreq_rdata=32'd0;
      assign xreq_error=1'b1;
      assign x0m_valid=1'b0;
      assign x0m_write=1'b0;
      assign x0m_addr=32'd0;
      assign x0m_wdata=32'd0;
      assign x0m_wstrb=4'd0;
      assign xnd_irq=1'b0;
    end
  endgenerate

  generate
    if(SEMANTIC_ENABLE)begin:gen_semantic
      semantic_cache_mmio #(.RAM_BYTES(SRAM_BYTES),.INPUTS(2048),.HIDDEN(64),.LANES(SEMANTIC_LANES),.TIMEOUT(SEMANTIC_DMA_TIMEOUT)) u_semantic(
        .clk(clk),.reset(reset),.req_valid(dc_valid&&semantic_select),.req_write(dc_write),
        .req_addr(dc_addr[15:0]),.req_wdata(dc_wdata),.req_wstrb(dc_wstrb),
        .req_ready(sreq_ready),.req_rdata(sreq_rdata),.req_error(sreq_error),
        .mem_valid(sm_valid),.mem_write(sm_write),.mem_addr(sm_addr),.mem_wdata(sm_wdata),.mem_wstrb(sm_wstrb),
        .mem_ready(sm_ready),.mem_rdata(sm_rdata),.mem_error(sm_error),.irq(semantic_irq));
    end else begin:gen_no_semantic
      assign sreq_ready=0;assign sreq_rdata=0;assign sreq_error=1;
      assign sm_valid=0;assign sm_write=0;assign sm_addr=0;assign sm_wdata=0;assign sm_wstrb=0;assign semantic_irq=0;
    end
  endgenerate
  dual_dma_arbiter u_dual_dma(
    .clk(clk),.reset(reset),
    .a_valid(x0m_valid),.a_write(x0m_write),.a_addr(x0m_addr),.a_wdata(x0m_wdata),.a_wstrb(x0m_wstrb),
    .a_ready(x0m_ready),.a_rdata(x0m_rdata),.a_error(x0m_error),
    .b_valid(sm_valid),.b_write(sm_write),.b_addr(sm_addr),.b_wdata(sm_wdata),.b_wstrb(sm_wstrb),
    .b_ready(sm_ready),.b_rdata(sm_rdata),.b_error(sm_error),
    .m_valid(xm_valid),.m_write(xm_write),.m_addr(xm_addr),.m_wdata(xm_wdata),.m_wstrb(xm_wstrb),
    .m_ready(xm_ready),.m_rdata(xm_rdata),.m_error(xm_error));

  // Instruction fetch stays BRAM. CPU/XND data share one fair owner-locked
  // transaction. Optional DDR fields are latched so an early XND timeout cannot
  // replace an outstanding payload with the next job's payload.
  always_comb begin
    chosen_xnd=0;
    if(ram_pending) chosen_xnd=ram_owner;
    else if(xm_valid && dc_valid && cpu_memory) chosen_xnd=prefer_xnd;
    else if(xm_valid) chosen_xnd=1;
    selected_valid=chosen_xnd ? xm_valid : (dc_valid && cpu_memory);
    selected_write=chosen_xnd ? xm_write : dc_write;
    selected_addr=chosen_xnd ? xm_addr : dc_addr;
    selected_wdata=chosen_xnd ? xm_wdata : dc_wdata;
    selected_wstrb=chosen_xnd ? xm_wstrb : dc_wstrb;
    chosen_ddr=ENABLE_DDR && selected_addr>=DDR_BASE &&
      {32'd0,selected_addr}<({32'd0,DDR_BASE}+{32'd0,DDR_BYTES});
    if(ram_pending && ram_target_ddr) begin
      selected_valid=1; selected_write=saved_ddr_write;
      selected_addr=saved_ddr_addr;selected_wdata=saved_ddr_wdata;
      selected_wstrb=saved_ddr_wstrb;chosen_ddr=1;
    end
    ram_valid=selected_valid && !chosen_ddr;
    ram_write=selected_write;ram_addr=selected_addr;
    ram_wdata=selected_wdata;ram_wstrb=selected_wstrb;
    ddr_req_valid=ENABLE_DDR && selected_valid && chosen_ddr;
    ddr_req_write=selected_write;ddr_req_addr=selected_addr-DDR_BASE;
    ddr_req_wdata=selected_wdata;ddr_req_wstrb=selected_wstrb;
    memory_ready=ram_target_ddr ? ddr_req_ready : ram_ready;
    memory_rdata=ram_target_ddr ? ddr_req_rdata : ram_rdata;
    memory_error=ram_target_ddr ? ddr_req_error : ram_error;
    xm_ready=ram_pending && ram_owner && memory_ready &&
      (!ram_target_ddr || (xm_valid && !ddr_cancelled));
    xm_rdata=memory_rdata;xm_error=memory_error;
  end
  always_ff @(posedge clk) begin
    if(reset) begin
      ram_pending<=0;ram_owner<=0;prefer_xnd<=0;ram_target_ddr<=0;ddr_cancelled<=0;
      saved_ddr_addr<=0;saved_ddr_wdata<=0;saved_ddr_wstrb<=0;saved_ddr_write<=0;
    end else begin
      if(!ram_pending && selected_valid) begin
        ram_pending<=1;ram_owner<=chosen_xnd;ram_target_ddr<=chosen_ddr;
        ddr_cancelled<=0;
        if(chosen_ddr) begin
          saved_ddr_addr<=selected_addr;saved_ddr_wdata<=selected_wdata;
          saved_ddr_wstrb<=selected_wstrb;saved_ddr_write<=selected_write;
        end
      end
      if(ram_pending && ram_target_ddr && ram_owner && !xm_valid)
        ddr_cancelled<=1;
      // Never release an owner merely because valid was withdrawn. Drain the
      // original response, suppress a cancelled XND reply, then allow the next
      // job. Bridge errors remain quarantined until common reset.
      if(ram_pending && memory_ready) begin
        ram_pending<=0;prefer_xnd<=!ram_owner;ddr_cancelled<=0;
      end
    end
  end
  soc_ram #(.RAM_WORDS(SRAM_BYTES/4),.INIT_FILE(INIT_FILE)) u_ram(
    .clk(clk),.reset(reset),
    .i_valid(ic_valid),.i_burst(ic_burst),.i_addr(ic_addr),.i_ready(ic_ready),.i_rdata(ic_rdata),.i_error(ic_error),
    .d_valid(ram_valid),.d_write(ram_write),.d_addr(ram_addr),
    .d_wdata(ram_wdata),.d_wstrb(ram_wstrb),
    .d_ready(ram_ready),.d_rdata(ram_rdata),.d_error(ram_error));

  logic utx_ready,urx_valid,urx_ready,urx_overrun;
  logic [7:0] urx_data;
  wire utx_valid=dc_valid && periph_select && dc_write &&
                 dc_addr==32'h10000000 && dc_wstrb[0];
  uart #(.CLK_HZ(CLK_HZ),.BAUD(BAUD)) u_uart(
    .clk(clk),.reset(reset),.rx(uart_rx),.tx(uart_tx),
    .tx_valid(utx_valid),.tx_data(dc_wdata[7:0]),.tx_ready(utx_ready),
    .rx_valid(urx_valid),.rx_data(urx_data),.rx_ready(urx_ready),.rx_overrun(urx_overrun));
  assign urx_ready=dc_valid && periph_select && !dc_write && dc_addr==32'h10000010;
  // PWM owns physical LED7 only while enabled; GPIO readback retains its written value.
  logic [31:0] pwm_period,pwm_duty;
  logic pwm_enable,pwm_pin;
  pwm #(.DEFAULT_PERIOD(CLK_HZ/1000)) u_pwm(
    .clk(clk),.reset(reset),.enable(pwm_enable),.period(pwm_period),.duty(pwm_duty),.pin(pwm_pin));
  assign gpio_out={pwm_enable?pwm_pin:gpio_led[7],gpio_led[6:0]};
  logic [63:0] mtime,mtimecmp;
  logic timer_enable;
  assign timer_value=mtime[31:0];
  assign timer_irq=timer_enable && mtime>=mtimecmp;

  wire temp_valid,temp_fault,temp_available,temp_ot;
  wire [11:0] temp_code;
  wire [31:0] temp_samples;
  pango_temperature #(.HARD_ADC(HARD_ADC),.CLK_HZ(CLK_HZ)) u_temperature(
    .clk(clk),.reset(reset),.valid(temp_valid),.fault(temp_fault),.available(temp_available),
    .overtemp(temp_ot),.code(temp_code),.samples(temp_samples));
  logic periph_known,periph_write_ok;
  logic [31:0] periph_rdata;
  always_comb begin
    periph_known=1; periph_write_ok=0; periph_rdata=0;
    case(dc_addr)
      32'h10000000: periph_write_ok=1;
      32'h10000004: begin periph_rdata={24'd0,gpio_led}; periph_write_ok=1; end
      32'h10000008: periph_rdata={24'd0,gpio_in};
      32'h1000000c: periph_rdata={29'd0,urx_overrun,urx_valid,utx_ready};
      32'h10000010: periph_rdata=urx_valid ? {24'd0,urx_data} : 32'd0;
      32'h10000020: begin periph_rdata=mtime[31:0];periph_write_ok=1;end
      32'h10000024: begin periph_rdata=mtime[63:32];periph_write_ok=1;end
      32'h10000028: begin periph_rdata=mtimecmp[31:0];periph_write_ok=1;end
      32'h1000002c: begin periph_rdata=mtimecmp[63:32];periph_write_ok=1;end
      32'h10000030: begin periph_rdata={31'd0,timer_enable};periph_write_ok=1;end
      32'h10000034: begin periph_rdata=pwm_duty;periph_write_ok=1;end
      32'h10000038: begin periph_rdata=pwm_period;periph_write_ok=1;end
      32'h1000003c: begin periph_rdata={31'd0,pwm_enable};periph_write_ok=1;end
      32'h10000100: periph_rdata={28'd0,temp_ot,temp_available,temp_fault,temp_valid};
      32'h10000104: periph_rdata={20'd0,temp_code};
      32'h10000108: periph_rdata=temp_samples;
      32'h1000010c: begin
        periph_known=ENABLE_DDR;
        periph_rdata={29'd0,ddr_busy,ddr_fault,ddr_available};
      end
      default: periph_known=0;
    endcase
    dc_ready=dc_valid; dc_rdata=0; dc_error=dc_valid;
    if(cpu_memory) begin
      dc_ready=ram_pending && !ram_owner && memory_ready;
      dc_rdata=memory_rdata; dc_error=memory_error;
    end else if(xnd_select) begin
      dc_ready=xreq_ready; dc_rdata=xreq_rdata; dc_error=xreq_error;
    end else if(semantic_select)begin
      dc_ready=sreq_ready;dc_rdata=sreq_rdata;dc_error=sreq_error;
    end else if(periph_select) begin
      dc_rdata=periph_rdata;
      dc_error=dc_valid && (!periph_known || (dc_write && !periph_write_ok));
      if(dc_addr==32'h10000000 && dc_write && dc_wstrb[0])
        dc_ready=utx_ready;
    end
  end

  function automatic [31:0] merge_bytes(input [31:0] old_value,new_value,
                                        input [3:0] strobes);
    integer b;
    begin
      merge_bytes=old_value;
      for(b=0;b<4;b=b+1)
        if(strobes[b]) merge_bytes[b*8 +: 8]=new_value[b*8 +: 8];
    end
  endfunction
  always_ff @(posedge clk) begin
    if(reset) begin
      gpio_led<=0; uart_tx_valid<=0; uart_tx_data<=0;
      mtime<=0;mtimecmp<=64'hffffffffffffffff;timer_enable<=0;
      pwm_period<=CLK_HZ/1000;pwm_duty<=0;pwm_enable<=0;
    end else begin
      mtime<=mtime+1;
      uart_tx_valid<=0;
      if(utx_valid && utx_ready) begin uart_tx_valid<=1;uart_tx_data<=dc_wdata[7:0];end
      if(dc_valid && dc_ready && !dc_error && dc_write && periph_select) case(dc_addr)
        32'h10000004: if(dc_wstrb[0]) gpio_led<=dc_wdata[7:0];
        32'h10000020: mtime[31:0]<=merge_bytes(mtime[31:0],dc_wdata,dc_wstrb);
        32'h10000024: mtime[63:32]<=merge_bytes(mtime[63:32],dc_wdata,dc_wstrb);
        32'h10000028: mtimecmp[31:0]<=merge_bytes(mtimecmp[31:0],dc_wdata,dc_wstrb);
        32'h1000002c: mtimecmp[63:32]<=merge_bytes(mtimecmp[63:32],dc_wdata,dc_wstrb);
        32'h10000030: if(dc_wstrb[0]) timer_enable<=dc_wdata[0];
        32'h10000034: pwm_duty<=merge_bytes(pwm_duty,dc_wdata,dc_wstrb);
        32'h10000038: pwm_period<=merge_bytes(pwm_period,dc_wdata,dc_wstrb);
        32'h1000003c: if(dc_wstrb[0]) pwm_enable<=dc_wdata[0];
        default: ;
      endcase
    end
  end
  initial begin
    if(ENABLE_DDR && (DDR_BYTES<32 || DDR_BYTES>1073741824 ||
       DDR_BASE[4:0]!=0 || DDR_BYTES%32!=0 || DDR_DMA_TIMEOUT<4096))
      $fatal(1,"Optional DDR requires aligned 32B..1GiB window and DMA timeout>=4096");
  end
endmodule
`default_nettype wire
