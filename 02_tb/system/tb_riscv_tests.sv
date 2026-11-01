// One upstream test binary per reset. Periodic wait states exercise handshakes.
// A pass/fail store is observed at the bus, without relying on UART strings.
`timescale 1ns/1ps
`default_nettype none
module tb_riscv_tests;
  logic clk=0, reset=1; always #5 clk=~clk;
  logic imem_valid,imem_ready,imem_error;
  logic [31:0] imem_addr,imem_rdata;
  logic dmem_valid,dmem_we,dmem_ready,dmem_error;
  logic [31:0] dmem_addr,dmem_wdata,dmem_rdata;
  logic [3:0] dmem_wstrb;
  logic [31:0] mem[0:65535];
  logic commit_valid; logic [31:0] commit_pc,commit_data,dbg_pc;
  logic [4:0] commit_rd;
  integer cycles=0, max_cycles=200000, waits=1, words=65536;
  string program_file;
  logic [31:0] last_pc=0, testnum=0, fail_pc=32'hffffffff, failure_branch_pc=0, trap_pc=0;
  assign imem_ready=imem_valid && (!waits || cycles%3!=0);
  assign imem_error=imem_addr>=32'h00040000;
  assign imem_rdata=mem[imem_addr[17:2]];
  assign dmem_ready=dmem_valid && (!waits || cycles%4==1);
  assign dmem_error=dmem_addr>=32'h00040000 && dmem_addr!=32'h100000fc && dmem_addr!=32'h100000f8;
  assign dmem_rdata=dmem_addr<32'h00040000 ? mem[dmem_addr[17:2]]:32'd0;
  initial begin
    if(!$value$plusargs("mem=%s",program_file)) $fatal(1,"missing +mem");
    if($value$plusargs("max_cycles=%d",max_cycles)) begin end
    if($value$plusargs("waits=%d",waits)) begin end
    if($value$plusargs("words=%d",words)) begin end
    if($value$plusargs("fail_pc=%h",fail_pc)) begin end
    for(integer i=0;i<65536;i++) mem[i]=0;
    $readmemh(program_file,mem,0,words-1);
    repeat(2) @(posedge clk); reset<=0;
  end
  always @(posedge clk) if(!reset) begin
    cycles<=cycles+1;
    if(commit_valid) begin
      if(commit_pc==fail_pc) failure_branch_pc<=last_pc;
      last_pc<=commit_pc;
      if(commit_rd==5'd3) testnum<=commit_data;
    end
    if(dmem_valid && dmem_ready && dmem_we) begin
      if(dmem_addr<32'h00040000)
        for(integer b=0;b<4;b++) if(dmem_wstrb[b])
          mem[dmem_addr[17:2]][b*8 +:8]<=dmem_wdata[b*8 +:8];
      if(dmem_addr==32'h100000f8) trap_pc<=dmem_wdata;
      if(dmem_addr==32'h100000fc) begin
        $display("NR_RISCV_RESULT status=%s code=%08x cycles=%0d pc=%08x testnum=%0d waits=%0d failure_branch_pc=%08x trap_pc=%08x",
          dmem_wdata==1?"PASS":"FAIL",dmem_wdata,cycles,last_pc,testnum,waits,failure_branch_pc,trap_pc);
        if(dmem_wdata==1) $finish;
        else $fatal(1,"upstream instruction assertion or unexpected trap");
      end
    end
    if(cycles>=max_cycles) begin
      $display("NR_RISCV_RESULT status=TIMEOUT code=00000000 cycles=%0d pc=%08x testnum=%0d waits=%0d failure_branch_pc=%08x trap_pc=%08x",cycles,last_pc,testnum,waits,failure_branch_pc,trap_pc);
      $fatal(1,"instruction test timeout");
    end
  end
  rv32i_core dut(.clk,.reset,.imem_valid,.imem_addr,.imem_ready,.imem_rdata,.imem_error,
    .dmem_valid,.dmem_we,.dmem_addr,.dmem_wdata,.dmem_wstrb,.dmem_ready,.dmem_rdata,.dmem_error,
    .timer_irq(1'b0),.external_irq(1'b0),.ic_miss_event(1'b0),.dc_miss_event(1'b0),
    .icache_idle(1'b1),.icache_invalidate(),.commit_valid,.commit_pc,.commit_data,.commit_rd,.dbg_pc);
endmodule
`default_nettype wire
