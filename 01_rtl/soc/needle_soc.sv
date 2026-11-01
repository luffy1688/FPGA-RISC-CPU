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
  input logic ddr_available,ddr_fault,ddr_busy,
 output wire worker_busy,worker_done,worker_fault,worker_validated,worker_tx_valid,output wire[7:0]worker_tx_data,output wire[31:0]worker_cycles,worker_iterations,dual_span_cycles,worker_debug_pc,worker_debug_cause,worker_debug_value
);
 wire w_req_valid,w_req_write,w_req_ready,w_req_error;wire[15:0]w_req_addr;wire[31:0]w_req_wdata,w_req_rdata;wire[3:0]w_req_wstrb;
 needle_primary_soc #(.INIT_FILE(INIT_FILE),.SRAM_BYTES(SRAM_BYTES),.CLK_HZ(CLK_HZ),.BAUD(BAUD),.HARD_ADC(HARD_ADC),
 .SEMANTIC_ENABLE(SEMANTIC_ENABLE),.SEMANTIC_LANES(SEMANTIC_LANES),.SEMANTIC_DMA_TIMEOUT(SEMANTIC_DMA_TIMEOUT),
 .CACHE_ENABLE(CACHE_ENABLE),.PREDICT_ENABLE(PREDICT_ENABLE),.CPU_FETCH_OVERLAP(CPU_FETCH_OVERLAP),.CPU_FETCH_PREFETCH(CPU_FETCH_PREFETCH),
 .ICACHE_BURST_ENABLE(ICACHE_BURST_ENABLE),.ICACHE_LOOKAHEAD_ENABLE(ICACHE_LOOKAHEAD_ENABLE),.XND_ENABLE(XND_ENABLE),.XND_WEIGHT_PREFETCH(XND_WEIGHT_PREFETCH),
 .ENABLE_DDR(ENABLE_DDR),.DDR_BASE(DDR_BASE),.DDR_BYTES(DDR_BYTES),.DDR_DMA_TIMEOUT(DDR_DMA_TIMEOUT)) u_primary(.clk(clk),.reset(reset),.uart_rx(uart_rx),.gpio_in(gpio_in),.uart_tx(uart_tx),.gpio_led(gpio_led),.uart_tx_valid(uart_tx_valid),.uart_tx_data(uart_tx_data),.gpio_out(gpio_out),.timer_value(timer_value),.commit_valid(commit_valid),.commit_pc(commit_pc),.commit_data(commit_data),.commit_rd(commit_rd),.dbg_pc(dbg_pc),.ddr_req_valid(ddr_req_valid),.ddr_req_write(ddr_req_write),.ddr_req_addr(ddr_req_addr),.ddr_req_wdata(ddr_req_wdata),.ddr_req_wstrb(ddr_req_wstrb),.ddr_req_ready(ddr_req_ready),.ddr_req_error(ddr_req_error),.ddr_req_rdata(ddr_req_rdata),.ddr_available(ddr_available),.ddr_fault(ddr_fault),.ddr_busy(ddr_busy),.w_req_valid(w_req_valid),.w_req_write(w_req_write),.w_req_addr(w_req_addr),.w_req_wdata(w_req_wdata),.w_req_wstrb(w_req_wstrb),.w_req_ready(w_req_ready),.w_req_error(w_req_error),.w_req_rdata(w_req_rdata));
 nr_worker_subsystem #(.INIT_FILE("firmware/worker.mem"))u_worker(
 .clk(clk),.reset(reset),.req_valid(w_req_valid),.req_write(w_req_write),.req_addr(w_req_addr),.req_wdata(w_req_wdata),.req_wstrb(w_req_wstrb),
 .req_ready(w_req_ready),.req_error(w_req_error),.req_rdata(w_req_rdata),.busy(worker_busy),.done(worker_done),.fault(worker_fault),.validated(worker_validated),
 .tx_valid(worker_tx_valid),.tx_data(worker_tx_data),.cycles(worker_cycles),.iterations(worker_iterations),.span_cycles(dual_span_cycles),.debug_pc(worker_debug_pc),.debug_cause(worker_debug_cause),.debug_value(worker_debug_value));
endmodule
