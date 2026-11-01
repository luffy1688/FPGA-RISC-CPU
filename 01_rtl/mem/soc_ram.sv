// soc_ram = the chip-on-chip main memory for the first board build.
// 256 KiB, synchronous instruction read port + data/DMA read/write port.
// Memory bits are NOT reset; only the bus response registers are reset.
`default_nettype none
module soc_ram #(
  parameter integer RAM_WORDS=65536,
  parameter bit FAST_WRITES=0,
  parameter INIT_FILE=""
)(
  input logic clk,reset,
  input logic i_valid,i_burst,
  input logic [31:0] i_addr,
  output logic i_ready,
  output logic [31:0] i_rdata,
  output logic i_error,
  input logic d_valid,d_write,
  input logic [31:0] d_addr,d_wdata,
  input logic [3:0] d_wstrb,
  output logic d_ready,
  output logic [31:0] d_rdata,
  output logic d_error
);
  localparam integer INDEX_BITS=$clog2(RAM_WORDS);
  localparam logic [31:0] RAM_BYTES=RAM_WORDS*4;
  integer b;
  logic i_burst_active, i_burst_bad;
  logic [31:0] i_burst_base;
  logic [2:0] i_burst_word, i_burst_count;
  wire [2:0] i_next_word = i_burst_word + 3'd1;
  wire [31:0] i_next_addr = {i_burst_base[31:5],i_next_word,2'b00};
  logic [31:0] mem [0:RAM_WORDS-1];
  wire i_bad=i_addr>=RAM_BYTES || i_addr[1:0]!=0;
  wire i_stream_next = i_burst_active && i_burst_count!=3'd7;
  wire i_read_enable = i_stream_next || (!i_burst_active && i_valid && !i_ready);
  wire [31:0] i_read_addr = i_stream_next ? i_next_addr : i_addr;
  wire i_read_bad = i_stream_next ? i_burst_bad : i_bad;
  wire d_bad=d_addr>=RAM_BYTES || d_addr[1:0]!=0;
  logic d_ready_q,d_error_q;
  wire fast_write=FAST_WRITES&&d_valid&&d_write;
  assign d_ready=fast_write||d_ready_q;
  assign d_error=fast_write?d_bad:d_error_q;
  wire d_accept=d_valid&&!d_ready_q;


  initial if(INIT_FILE!="") $readmemh(INIT_FILE,mem);

  // Word transactions retain their original two-cycle handshake. Instruction
  // bursts accept one command, then return eight synchronous words at one per
  // cycle, wrapping within the 32-byte line from the requested critical word.
  // The independent data/DMA port is unchanged.
  always_ff @(posedge clk) begin
    if(reset) begin
      i_ready<=0; i_rdata<=0; i_error<=0;
      i_burst_active<=0; i_burst_bad<=0; i_burst_base<=0;
      i_burst_word<=0; i_burst_count<=0;
      d_ready_q<=0; d_rdata<=0; d_error_q<=0;
    end else begin
      i_ready<=0; d_ready_q<=0;
      // One syntactic instruction memory read preserves a true dual-port RAM.
      // Separate mem[] reads for first/stream beats infer an unwanted third
      // read port in ADS, even though their enables are mutually exclusive.
      if(i_read_enable)
        i_rdata<=i_read_bad ? 32'd0 : mem[i_read_addr[2 +: INDEX_BITS]];
      if(i_burst_active) begin
        if(i_burst_count==3'd7) i_burst_active<=0;
        else begin
          i_burst_word<=i_next_word;
          i_burst_count<=i_burst_count+3'd1;
          i_ready<=1; i_error<=i_burst_bad;
        end
      end else if(i_valid && !i_ready) begin
        i_ready<=1; i_error<=i_bad;
        if(i_burst) begin
          i_burst_active<=1; i_burst_bad<=i_bad;
          i_burst_base<={i_addr[31:5],5'b0};
          i_burst_word<=i_addr[4:2]; i_burst_count<=0;
        end
      end
      if(d_accept)begin
        if(!fast_write)begin
          d_ready_q<=1;d_error_q<=d_bad;
          d_rdata<=d_bad?32'd0:mem[d_addr[2+:INDEX_BITS]];
        end
        // A write ACK is the same edge that commits enabled bytes. Read
        // responses retain the registered SRAM latency. There is one data
        // memory write port, shared by both transaction modes.
        if(d_write&&!d_bad)
          for(b=0;b<4;b=b+1)
            if(d_wstrb[b])mem[d_addr[2+:INDEX_BITS]][b*8+:8]<=d_wdata[b*8+:8];
      end
    end
  end
endmodule
`default_nettype wire
