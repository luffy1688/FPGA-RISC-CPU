`timescale 1ns/1ps
`default_nettype none
// Purposeful acceptance test: actual DMA, packing, residence and failure paths.
module tb_xnd_engine;
  parameter PREFETCH=1;
  logic clk=0; always #5 clk=~clk;
  logic reset=1, req_valid=0, req_write=0;
  logic [15:0] req_addr=0;
  logic [31:0] req_wdata=0, req_rdata;
  logic [3:0] req_wstrb=0;
  logic req_ready, req_error, mem_valid, mem_write, mem_ready, mem_error, irq;
  logic [31:0] mem_addr,mem_wdata,mem_rdata;
  logic [3:0] mem_wstrb;
  logic [31:0] ram [0:65535];
  logic freeze_dma=0, inject_dma_error=0;
  integer tick=0, j,r,i, index, expected;
  integer original_a[0:18], alternate_a[0:18], weights[0:2][0:18];
  logic [31:0] status, value;
  xnd_engine #(.MAX_COLS(32),.MAX_ROWS(8),.DMA_TIMEOUT(8),.WEIGHT_PREFETCH(PREFETCH)) dut(.*);
  always_ff @(posedge clk) begin
    tick<=tick+1;
    if(mem_valid && mem_ready && mem_write && !mem_error)
      for(integer b=0;b<4;b=b+1)
        if(mem_wstrb[b]) ram[mem_addr[17:2]][b*8 +: 8]<=mem_wdata[b*8 +: 8];
  end
  // The address/data contract is independent of the memory response model.
  // Error/timeout completion may cancel an outstanding request in IDLE.
  logic stalled=0;
  logic [31:0] stalled_addr,stalled_wdata;
  logic [3:0] stalled_wstrb;
  logic stalled_write;
  always_ff @(posedge clk) begin
    if(reset) stalled<=0;
    else begin
      if(stalled && dut.state!=0 &&
         (!mem_valid || mem_addr!==stalled_addr || mem_write!==stalled_write ||
          mem_wstrb!==stalled_wstrb || mem_wdata!==stalled_wdata))
        $fatal(1,"DMA request changed under backpressure");
      stalled<=mem_valid && !mem_ready;
      stalled_addr<=mem_addr;stalled_write<=mem_write;
      stalled_wdata<=mem_wdata;stalled_wstrb<=mem_wstrb;
    end
  end
  always_comb begin
    mem_ready=mem_valid && !freeze_dma && ((tick%3)!=0);
    mem_rdata=ram[mem_addr[17:2]];
    mem_error=inject_dma_error || (mem_addr>32'h0003ffff);
  end

  task automatic wr(input [15:0] off, input [31:0] data,
                    input [3:0] strobes=4'hf, input bit expect_error=0);
    begin
      @(negedge clk);
      req_valid=1; req_write=1; req_addr=off; req_wdata=data; req_wstrb=strobes;
      #1;
      if(!req_ready || req_error!==expect_error)
        $fatal(1,"MMIO write off=%h unexpected error=%b expected=%b",off,req_error,expect_error);
      @(posedge clk); #1;
      @(negedge clk); req_valid=0; req_write=0; req_wstrb=0;
    end
  endtask
  task automatic rd(input [15:0] off, output [31:0] data, input bit expect_error=0);
    begin
      @(negedge clk); req_valid=1; req_write=0; req_addr=off;
      #1;
      if(!req_ready || req_error!==expect_error) $fatal(1,"MMIO read off=%h",off);
      data=req_rdata;
      @(negedge clk); req_valid=0;
    end
  endtask
  task automatic finish(input [7:0] code=0);
    integer limit;
    begin
      limit=0; status=1;
      while(status[0] && limit<2000) begin rd(16'h0000,status); limit=limit+1; end
      if(limit>=2000 || !status[1] || status[2]!=(code!=0))
        $fatal(1,"finish status=%h code=%d",status,code);
      rd(16'h003c,value);
      if(value!=code) $fatal(1,"error code=%d expected=%d",value,code);
      repeat(5) @(posedge clk);
      rd(16'h0000,status);
      if(!status[1]) $fatal(1,"done was not sticky");
      if(!irq) $fatal(1,"completion IRQ missing");
      wr(16'h0000,6);
      rd(16'h0000,status);
      if(status[2:1]!=0 || irq) $fatal(1,"W1C failed");
    end
  endtask
  task automatic set_byte(input integer addr,input integer byte_value);
    begin ram[addr>>2][(addr%4)*8 +: 8]=byte_value[7:0]; end
  endtask
  task automatic check_output(input bit alternate);
    begin
      for(integer row=0;row<3;row=row+1) begin
        expected=0;
        for(integer col=0;col<19;col=col+1)
          expected=expected+(alternate?alternate_a[col]:original_a[col])*weights[row][col];
        if($signed(ram[(32'h22000>>2)+row])!==expected)
          $fatal(1,"GEMV row=%0d got=%0d expected=%0d",row,
                     $signed(ram[(32'h22000>>2)+row]),expected);
      end
    end
  endtask
  initial begin
    for(j=0;j<65536;j=j+1) ram[j]=0;
    repeat(4) @(posedge clk);
    @(negedge clk); reset=0;
    wr(16'h0038,2); // enable IRQ, start with INT8
    wr(16'h0008,32'h7f80017f);
    wr(16'h000c,32'h807fff01);
    wr(16'h0010,1);
    finish();
    rd(16'h0004,value);
    if($signed(value)!=(127*(-128)+(-128)*127+1*(-1)+127*1))
      $fatal(1,"dot4 signed extremes=%0d",$signed(value));

    // Byte-enable update must preserve bytes not selected by the store.
    wr(16'h0008,32'h11223344);
    wr(16'h0008,32'h0000aa00,4'b0010);
    rd(16'h0008,value);
    if(value!=32'h1122aa44) $fatal(1,"byte strobes");
    rd(16'h0018,value,1);

    for(i=0;i<19;i=i+1) begin
      case(i%5)
        0: original_a[i]=-128;
        1: original_a[i]=127;
        2: original_a[i]=-1;
        3: original_a[i]=0;
        4: original_a[i]=13;
      endcase
      alternate_a[i]=127-i*11;
      set_byte(32'h20000+i,original_a[i]);
    end
    wr(16'h0020,32'h20000);
    wr(16'h0024,32'h21000);
    wr(16'h0028,32'h22000);
    wr(16'h002c,19); wr(16'h0030,3); wr(16'h0034,12); wr(16'h0038,3);
    // Cannot GEMV from an unfilled slot.
    wr(16'h0010,3); finish(4);
    // Busy configuration is rejected without damaging an in-flight job.
    freeze_dma=1;
    wr(16'h0010,2);
    wr(16'h002c,5,4'hf,1);
    freeze_dma=0;
    finish();
    rd(16'h0050,value);
    if(value!=19) $fatal(1,"resident length");

    // Signed INT4: low nibble is the smaller column. Tail padding is ignored.
    for(r=0;r<3;r=r+1)
      for(i=0;i<19;i=i+1) begin
        weights[r][i]=((r*3+i)%16)-8;
        index=32'h21000+r*12+(i>>1);
        ram[index>>2][(index%4)*8+(i%2)*4 +: 4]=weights[r][i][3:0];
      end
    wr(16'h0010,3); finish(); check_output(0);
    rd(16'h0040,value);$display("XND_PERF int4 prefetch=%0d cycles=%0d",PREFETCH,value);
    rd(16'h0044,value);
    if(value!=36) $fatal(1,"INT4 DMA bytes=%d",value);
    rd(16'h004c,value);
    if(value!=57) $fatal(1,"INT4 MAC count=%d",value);
    rd(16'h0048,value);
    if(value!=12) $fatal(1,"output write bytes");
    // Overwrite source RAM, but the already resident slot must retain its data.
    for(i=0;i<19;i=i+1) set_byte(32'h20000+i,alternate_a[i]);
    wr(16'h0010,3); finish(); check_output(0);

    // Fill slot 1, leaving slot 0 resident; then run signed INT8 GEMV.
    wr(16'h0010,32'h102); finish();
    wr(16'h0038,2); wr(16'h0034,20); wr(16'h0024,32'h10000);
    for(r=0;r<3;r=r+1)
      for(i=0;i<19;i=i+1) begin
        weights[r][i]=((r*31+i*17)%256)-128;
        set_byte(32'h10000+r*20+i,weights[r][i]);
      end
    wr(16'h0010,32'h103); finish(); check_output(1);
    rd(16'h0040,value);$display("XND_PERF int8 prefetch=%0d cycles=%0d",PREFETCH,value);
    rd(16'h0000,status);
    if(status[9:8]!=2'b11) $fatal(1,"double resident slots");
    rd(16'h0044,value);
    if(value!=60) $fatal(1,"INT8 DMA bytes=%d",value);
    if(PREFETCH) begin
      fork
        begin
          wait(dut.state==4 && mem_valid);
          @(negedge clk);inject_dma_error=1;
          wait(dut.state==0);@(negedge clk);inject_dma_error=0;
        end
        begin wr(16'h0010,32'h103);finish(5);end
      join
      fork
        begin
          wait(dut.state==4 && mem_valid);
          @(negedge clk);freeze_dma=1;
          wait(dut.state==0);@(negedge clk);freeze_dma=0;
        end
        begin wr(16'h0010,32'h103);finish(6);end
      join
      wr(16'h0010,32'h103);finish();check_output(1);
    end
    wr(16'h0028,32'h1fffc); wr(16'h0010,32'h103); finish(3);
    wr(16'h0028,32'h22000);
    wr(16'h0010,32'h104); finish();
    wr(16'h0010,32'h103); finish(4);

    wr(16'h0020,32'h1fffc); wr(16'h0010,2); finish(3);
    wr(16'h0020,32'h20001); wr(16'h0010,2); finish(2);
    wr(16'h0020,32'h3fffc); wr(16'h0010,2); finish(3);
    wr(16'h0020,32'h20000);
    inject_dma_error=1; wr(16'h0010,2); finish(5); inject_dma_error=0;
    freeze_dma=1; wr(16'h0010,2); finish(6); freeze_dma=0;
    wr(16'h0010,99); finish(1);
    $display("PASS XND: signed INT4/INT8, odd tails, DMA stalls, 2 slots, W1C, range/DMA/timeout errors");
    $finish;
  end
  initial begin #2000000; $fatal(1,"global timeout"); end
endmodule
`default_nettype wire
