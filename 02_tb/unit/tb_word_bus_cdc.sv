`timescale 1ns/1ps
`default_nettype none
module tb_word_bus_cdc;
  logic src_clk=0,dst_clk=0,reset=1;
  always #18.5185 src_clk=~src_clk; // Approximate the board CPU's 27 MHz.
  real dst_half_period=4.6729;
  initial begin #1.237;forever begin #(dst_half_period);dst_clk=~dst_clk;end end
  logic src_valid=0,src_write=0;
  logic [31:0] src_addr=0,src_wdata=0;
  logic [3:0] src_wstrb=0;
  wire src_ready,src_error,src_busy;
  wire [31:0] src_rdata;
  wire dst_valid,dst_write;
  wire [31:0] dst_addr,dst_wdata;
  wire [3:0] dst_wstrb;
  logic dst_ready,dst_error;
  logic [31:0] dst_rdata;
  word_bus_cdc dut(.*);
  logic [31:0] memory[0:31];
  logic pending=0,blocked=0;
  logic saved_write;
  logic [31:0] saved_addr,saved_data;
  logic [3:0] saved_strobe;
  integer wait_count=0,delay_setting=5,transactions=0;
  always_comb begin
    dst_ready=pending && wait_count==0 && !blocked;
    dst_error=saved_addr==32'hf00;
    dst_rdata=dst_error ? 32'hbadc0de : memory[saved_addr[6:2]];
  end
  always @(posedge dst_clk or posedge reset) begin
    if(reset) begin pending<=0;wait_count<=0;transactions<=0;end
    else if(!pending && dst_valid) begin
      pending<=1;wait_count<=delay_setting;
      saved_write<=dst_write;saved_addr<=dst_addr;
      saved_data<=dst_wdata;saved_strobe<=dst_wstrb;
    end else if(pending) begin
      if(!dst_valid || dst_addr!==saved_addr || dst_write!==saved_write ||
         dst_wdata!==saved_data || dst_wstrb!==saved_strobe)
        $fatal(1,"destination mailbox changed during backpressure");
      if(wait_count!=0) wait_count<=wait_count-1;
      else if(dst_ready) begin
        pending<=0;transactions<=transactions+1;
        if(saved_write && !dst_error)
          for(integer b=0;b<4;b=b+1)
            if(saved_strobe[b]) memory[saved_addr[6:2]][8*b+:8]<=saved_data[8*b+:8];
      end
    end
  end

  task automatic transaction(input bit wr,input logic [31:0] addr,data,
                             input logic [3:0] strobe,input bit error_expected,
                             input logic [31:0] expected,input bit keep_valid);
    integer n;
    begin
      @(negedge src_clk);src_valid=1;src_write=wr;src_addr=addr;
      src_wdata=data;src_wstrb=strobe;n=0;
      begin : wait_reply
        forever begin
          @(posedge src_clk);n=n+1;
          if(n>180) $fatal(1,"source response timeout");
          if(src_ready) begin
            if(src_error!==error_expected) $fatal(1,"source error mismatch");
            if(!wr && src_rdata!==expected)
              $fatal(1,"source data mismatch got=%x expected=%x",src_rdata,expected);
            disable wait_reply;
          end
        end
      end
      if(!keep_valid) begin @(negedge src_clk);src_valid=0;end
    end
  endtask
  task automatic common_reset;
    begin
      // Reset both request transport and the destination endpoint together.
      reset=1;src_valid=0;blocked=0;
      repeat(4) @(negedge src_clk);reset=0;
      repeat(5) @(negedge src_clk);
      if(src_ready || src_busy || dst_valid || transactions!=0)
        $fatal(1,"spurious transaction after shared reset");
    end
  endtask
  integer expected_count;
  initial begin
    for(integer k=0;k<32;k=k+1) memory[k]=32'h12345600+32'(k);
    common_reset();
    transaction(0,32'h4,0,0,0,32'h12345601,0);
    // Keep valid high across neighboring transactions; neither the source nor
    // the destination may confuse an old toggle with a new request.
    transaction(1,32'h8,32'ha1b2c3d4,4'b0101,0,0,1);
    transaction(0,32'h8,0,0,0,32'h12b256d4,1);
    transaction(1,32'hc,32'hfedcba98,4'hf,0,0,1);
    transaction(0,32'hc,0,0,0,32'hfedcba98,0);
    transaction(0,32'hf00,0,0,1,32'h0badc0de,0);
    expected_count=6;
    repeat(10) @(negedge src_clk);
    if(transactions!=expected_count) $fatal(1,"fast destination duplicate/lost request");
    // A slower unrelated destination exercises the opposite clock-rate ratio.
    dst_half_period=41.237;
    transaction(1,32'h10,32'h55aa0ff0,4'b1010,0,0,1);
    transaction(0,32'h10,0,0,0,32'h55340f04,0);
    expected_count=8;
    // Backpressure persists for many source clocks. No source completion is
    // allowed until the destination's actual ready edge produces an ACK.
    blocked=1;
    fork
      transaction(0,32'h4,0,0,0,32'h12345601,0);
      begin
        wait(dst_valid);repeat(12) @(negedge src_clk);
        if(src_ready || !src_busy) $fatal(1,"source acknowledged without destination ACK");
        blocked=0;
      end
    join
    expected_count=9;
    repeat(12) @(negedge src_clk);
    if(transactions!=expected_count) $fatal(1,"slow destination duplicate/lost request");
    // Shared reset aborts the entire endpoint/transport, including a waiting
    // request. No late response from the old epoch is retained by the model.
    blocked=1;
    @(negedge src_clk);src_valid=1;src_write=0;src_addr=32'h8;
    wait(dst_valid);repeat(3) @(negedge src_clk);
    common_reset();
    transaction(0,32'hc,0,0,0,32'hfedcba98,0);
    repeat(12) @(negedge src_clk);
    if(transactions!=1) $fatal(1,"request replayed after shared reset");
    $display("PASS word_bus_cdc: held mailboxes, asynchronous fast/slow clocks, continuous valid, byte strobes, backpressure, error, shared reset");
    $finish;
  end
  initial begin #100000; $fatal(1,"global CDC test timeout");end
endmodule
`default_nettype wire
