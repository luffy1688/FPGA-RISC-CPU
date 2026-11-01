`timescale 1ns/1ps
`default_nettype none
// Small focused unit test. The memory deliberately waits before each response;
// this catches refill/store requests accidentally executed more than once.
module tb_rv32_cache;
  logic clk=0, reset=1;
  always #5 clk=~clk;
  logic cpu_valid=0,cpu_write=0,cpu_cacheable=1;
  logic [31:0] cpu_addr=0,cpu_wdata=0;
  logic [3:0] cpu_wstrb=0;
  wire cpu_ready,cpu_error;
  wire [31:0] cpu_rdata;
  wire mem_valid,mem_write;
  wire [31:0] mem_addr,mem_wdata;
  wire [3:0] mem_wstrb;
  logic mem_ready,mem_error;
  logic [31:0] mem_rdata;
  logic invalidate=0;
  wire idle,hit_pulse,miss_pulse,refill_pulse;

  logic mem_burst;
  rv32_cache dut(.*);
  logic [31:0] memory [0:8191];
  logic pending=0,saved_write=0;
  logic [31:0] saved_addr=0,saved_data=0;
  logic [3:0] saved_strobe=0;
  integer delay_count=0, delay_setting=2;
  integer reads=0,writes=0,hits=0,misses=0,refills=0;
  logic fault_enable=0;
  logic [31:0] fault_addr=32'h0000200c;
  always_comb begin
    mem_ready=pending && delay_count==0;
    mem_error=mem_ready && fault_enable && saved_addr==fault_addr;
    mem_rdata=memory[saved_addr[14:2]];
  end
  always @(posedge clk) begin
    if (reset) begin
      pending<=0; delay_count<=0;
      reads<=0; writes<=0; hits<=0; misses<=0; refills<=0;
    end else begin
      if(hit_pulse) hits<=hits+1;
      if(miss_pulse) misses<=misses+1;
      if(refill_pulse) refills<=refills+1;
      if (!pending && mem_valid) begin
        pending<=1;
        saved_write<=mem_write;
        saved_addr<=mem_addr;
        saved_data<=mem_wdata;
        saved_strobe<=mem_wstrb;
        delay_count<=delay_setting;
      end else if(pending) begin
        if (!mem_valid || mem_addr!=saved_addr || mem_write!=saved_write ||
            mem_wdata!=saved_data || mem_wstrb!=saved_strobe)
          $fatal(1,"memory request changed while waiting");
        if(delay_count!=0) delay_count<=delay_count-1;
        else begin
          pending<=0;
          if (saved_write) begin
            writes<=writes+1;
            if(!mem_error)
              for(integer b=0;b<4;b=b+1)
                if(saved_strobe[b]) memory[saved_addr[14:2]][8*b+:8]<=saved_data[8*b+:8];
          end else reads<=reads+1;
        end
      end
    end
  end

  integer last_request_cycles=0;
  task automatic request(input bit wr,input bit cacheable,input logic [31:0] addr,
                         input logic [31:0] data,input logic [3:0] strobe,
                         input logic [31:0] expected,input bit expected_error);
    integer timeout_count;
    begin
      @(negedge clk);
      cpu_valid=1; cpu_write=wr; cpu_cacheable=cacheable;
      cpu_addr=addr; cpu_wdata=data; cpu_wstrb=strobe;
      timeout_count=0;
      begin : wait_response
        forever begin
          @(posedge clk);
          timeout_count=timeout_count+1;
          if(timeout_count>200) $fatal(1,"CPU timeout addr=%08x",addr);
          if(cpu_ready) begin
            last_request_cycles=timeout_count;
            if(cpu_error!==expected_error) $fatal(1,"wrong error at %08x",addr);
            if(!wr && !expected_error && cpu_rdata!==expected)
              $fatal(1,"data addr=%08x got=%08x expected=%08x",addr,cpu_rdata,expected);
            disable wait_response;
          end
        end
      end
      @(negedge clk);
      cpu_valid=0;
    end
  endtask
  task automatic expect_counts(input integer wanted_reads,input integer wanted_writes);
    begin
      if(reads!=wanted_reads || writes!=wanted_writes)
        $fatal(1,"transactions got r=%0d w=%0d expected r=%0d w=%0d",
               reads,writes,wanted_reads,wanted_writes);
    end
  endtask

  integer before_reads,before_writes;
  initial begin
    for(integer i=0;i<8192;i=i+1) memory[i]=32'ha0000000+32'(i);
    repeat(3) @(negedge clk);
    reset=0;
    request(0,1,32'h0,0,0,32'ha0000000,0);
    expect_counts(8,0);
    request(0,1,32'h4,0,0,32'ha0000001,0);
    expect_counts(8,0);
    // One acceptance edge plus one synchronous RAM/lookup response edge.
    if(last_request_cycles!=2) $fatal(1,"read hit latency got=%0d expected=2",last_request_cycles);
    // Keeping valid high must not replay the old word after the fast hit.
    @(negedge clk);
    cpu_valid=1; cpu_write=0; cpu_cacheable=1; cpu_addr=32'h4;
    do @(posedge clk); while(!cpu_ready);
    if(cpu_rdata!==32'ha0000001) $fatal(1,"continuous read first word");
    @(negedge clk); cpu_addr=32'h0;
    do @(posedge clk); while(!cpu_ready);
    if(cpu_rdata!==32'ha0000000) $fatal(1,"continuous read next word");
    @(negedge clk); cpu_valid=0;
    expect_counts(8,0);
    // All three addresses share one set; hit 0 makes 0x800 least recent.
    request(0,1,32'h800,0,0,32'ha0000200,0);
    request(0,1,32'h0,0,0,32'ha0000000,0);
    request(0,1,32'h1000,0,0,32'ha0000400,0);
    request(0,1,32'h0,0,0,32'ha0000000,0);
    expect_counts(24,0);
    request(0,1,32'h800,0,0,32'ha0000200,0);
    expect_counts(32,0);

    // Byte-lane write hits the cached line and is forwarded exactly once.
    request(1,1,32'h0,32'h11223344,4'b0101,0,0);
    expect_counts(32,1);
    request(0,1,32'h0,0,0,32'ha0220044,0);
    expect_counts(32,1);
    // A write miss never fetches a line.
    request(1,1,32'h3000,32'hcafebabe,4'hf,0,0);
    expect_counts(32,2);
    request(0,0,32'h3000,0,0,32'hcafebabe,0);
    expect_counts(33,2);
    request(1,0,32'h3004,32'hdeadbeef,4'hf,0,0);
    expect_counts(33,3);

    // Refill aborts on a memory error and does not leave a valid partial line.
    fault_enable=1;
    request(0,1,32'h2000,0,0,0,1);
    expect_counts(37,3);
    fault_enable=0;
    request(0,1,32'h2000,0,0,32'ha0000800,0);
    expect_counts(45,3);
    // FENCE.I clears tags, so the next read fetches the whole line again.
    @(negedge clk); invalidate=1;
    @(negedge clk); invalidate=0;
    while(!idle) @(negedge clk);
    request(0,1,32'h2000,0,0,32'ha0000800,0);
    expect_counts(53,3);

    // Continuous valid carries a NEW request after the previous ready edge.
    before_writes=writes;
    @(negedge clk);
    cpu_valid=1; cpu_write=1; cpu_cacheable=0;
    cpu_addr=32'h3010; cpu_wdata=32'h12345678; cpu_wstrb=4'hf;
    do @(posedge clk); while(!cpu_ready);
    @(negedge clk);
    cpu_addr=32'h3014; cpu_wdata=32'h87654321;
    do @(posedge clk); while(!cpu_ready);
    @(negedge clk); cpu_valid=0;
    if(writes!=before_writes+2 || memory[32'h3010/4]!=32'h12345678 ||
       memory[32'h3014/4]!=32'h87654321)
      $fatal(1,"back-to-back held valid stores failed");
    repeat(4) @(negedge clk);
    if(writes!=before_writes+2) $fatal(1,"store repeated after response");
    $display("PASS rv32_cache: hits=%0d misses=%0d refill_words=%0d reads=%0d writes=%0d",
             hits,misses,refills,reads,writes);
    $finish;
  end
  initial begin
    #100000;
    $fatal(1,"global timeout");
  end
endmodule
`default_nettype wire

