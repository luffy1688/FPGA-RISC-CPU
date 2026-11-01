// Focused CPU acceptance: same 32-bit RAM feeds instruction and data ports.
`timescale 1ns/1ps
`default_nettype none
module tb_rv32i_acceptance;
  logic clk=0, reset=1; always #5 clk=~clk;
  logic imem_valid, imem_ready, imem_error;
  logic [31:0] imem_addr, imem_rdata;
  logic dmem_valid,dmem_we,dmem_ready,dmem_error;
  logic [31:0] dmem_addr,dmem_wdata,dmem_rdata; logic [3:0] dmem_wstrb;
  logic [31:0] mem[0:65535]; integer i;
  logic [31:0] magic; integer cycles; logic saw_uart;
  assign imem_ready=imem_valid;
  assign imem_error=1'b0;
  assign imem_rdata=mem[imem_addr[17:2]];
  assign dmem_ready=dmem_valid;
  assign dmem_error=(dmem_addr>=32'h00040000);
  assign dmem_rdata=(dmem_addr<32'h00040000)?mem[dmem_addr[17:2]]:32'd0;
  logic commit_valid; logic [31:0] commit_pc,commit_data,dbg_pc; logic [4:0] commit_rd;
  initial begin
    for(i=0;i<65536;i=i+1) mem[i]=0;
    $readmemh("07_runs/sim/cpu_acceptance.hex",mem);
    magic=0; cycles=0; saw_uart=0;
    repeat(2) @(posedge clk); reset<=0;
    repeat(200000) begin
      @(posedge clk); cycles=cycles+1;
      if(magic!=0) begin
        if(magic==32'h600dcafe) begin
          $display("PASS CPU acceptance cycles=%0d magic=%08x",cycles,magic);
          $finish;
        end else begin
          $fatal(1,"CPU acceptance FAIL magic=%08x pc=%08x",magic,dbg_pc);
        end
      end
    end
    $fatal(1,"CPU acceptance TIMEOUT pc=%08x magic=%08x",dbg_pc,magic);
  end
  always_ff @(posedge clk) begin
    if(!reset && dmem_valid && dmem_ready && dmem_we && dmem_addr<32'h00040000)
      for(integer b=0;b<4;b=b+1) if(dmem_wstrb[b])
        mem[dmem_addr[17:2]][b*8 +: 8] <= dmem_wdata[b*8 +: 8];
    if(!reset && dmem_valid && dmem_ready && dmem_we && dmem_addr==32'h100000fc)
      magic <= dmem_wdata;
    if(!reset && dmem_valid && dmem_ready && dmem_we && dmem_addr==32'h10000000) begin
      saw_uart<=1; $write("%c",dmem_wdata[7:0]);
    end
  end
  rv32i_core dut(
    .clk,.reset,
    .imem_valid,.imem_addr,.imem_ready,.imem_rdata,.imem_error,
    .dmem_valid,.dmem_we,.dmem_addr,.dmem_wdata,.dmem_wstrb,
    .dmem_ready,.dmem_rdata,.dmem_error,
    .timer_irq(1'b0),.external_irq(1'b0),.ic_miss_event(1'b0),.dc_miss_event(1'b0),
    .icache_idle(1'b1),.icache_invalidate(),
    .commit_valid,.commit_pc,.commit_data,.commit_rd,.dbg_pc);
endmodule
`default_nettype wire
