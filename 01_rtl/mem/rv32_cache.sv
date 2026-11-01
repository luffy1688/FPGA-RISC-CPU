// rv32_cache: "rv32" = 32-bit RISC-V bus, "cache" = a small memory shortcut.
// Two-way cache. Optional instruction SRAM bursts return the critical word
// first, and forward matching in-flight words while finishing the line fill.
// Both instruction and data caches use this module; instruction writes stay 0.
// No Pango-specific primitive is required. Data arrays have synchronous reads
// and are never reset, so FPGA synthesis can infer block RAM.
`default_nettype none
module rv32_cache #(
  parameter integer CACHE_BYTES = 4096,
  parameter integer LINE_BYTES = 32,
  parameter bit STREAM_REFILL = 0,
  parameter bit LOOKAHEAD_HIT = 0,
  parameter bit IDLE_LOAD_LOOKAHEAD = 0,
  parameter bit PRECOMPARE_TAGS = 0,
  parameter bit DIRECT_BACKEND_RESPONSE = 0,
  parameter bit EARLY_STORE_REQUEST = 0
)(
  input  logic clk, reset,
  input  logic cpu_valid, cpu_write, cpu_cacheable,
  input  logic [31:0] cpu_addr, cpu_wdata,
  input  logic [3:0] cpu_wstrb,
  input logic lookahead_valid,lookahead_cacheable,lookahead_write,
  input logic[31:0]lookahead_wdata,input logic[3:0]lookahead_wstrb,
  input logic [31:0] lookahead_addr,
  output logic cpu_ready,
  output logic [31:0] cpu_rdata,
  output logic cpu_error,
  output logic mem_valid, mem_write, mem_burst,
  output logic [31:0] mem_addr, mem_wdata,
  output logic [3:0] mem_wstrb,
  input  logic mem_ready,
  input  logic [31:0] mem_rdata,
  input  logic mem_error,
  input  logic invalidate,
  output logic idle,
  output logic hit_pulse, miss_pulse, refill_pulse
);
  localparam integer SETS = CACHE_BYTES / (2 * LINE_BYTES);
  localparam integer LINE_WORDS = LINE_BYTES / 4;
  localparam integer OFFSET_BITS = $clog2(LINE_BYTES);
  localparam integer SET_BITS = $clog2(SETS);
  localparam integer WORD_BITS = $clog2(LINE_WORDS);
  localparam integer RAM_BITS = SET_BITS + WORD_BITS;
  localparam integer TAG_BITS = 32 - SET_BITS - OFFSET_BITS;
  localparam integer WAY_WORDS = CACHE_BYTES / 8;
  localparam integer LAST_LINE_WORD = LINE_WORDS - 1;
  // ADS does not support enum declarations; preserve the six state values.
  localparam logic [2:0] S_IDLE=3'd0, S_LOOKUP=3'd1, S_WRITE=3'd2,
    S_REFILL=3'd3, S_BYPASS=3'd4, S_RESP=3'd5, S_STREAM_RESP=3'd6;
  logic [2:0] state;

  // Each set holds two candidate lines. Only tags/valid bits are reset.
  logic [TAG_BITS-1:0] tag0 [0:SETS-1], tag1 [0:SETS-1];
  logic valid0 [0:SETS-1], valid1 [0:SETS-1];
  // victim=0 means evict way 0 next; touching way 0 makes way 1 the victim.
  logic victim [0:SETS-1];
  // Keep each byte lane in its own single-port memory.  ADS/PDS can infer a
  // block RAM for this shape, while a 32-bit array that mixes byte writes
  // with full-word refills is otherwise expanded into LUT/FF logic.
  logic [7:0] read0_b0, read0_b1, read0_b2, read0_b3;
  logic [7:0] read1_b0, read1_b1, read1_b2, read1_b3;
  logic [31:0] read0, read1;

  logic [31:0] req_addr, req_wdata, response_data, requested_word;
  logic [3:0] req_wstrb;
  logic req_write, hit_way, req_hit, refill_way;
  logic response_error, pending_invalidate;
  wire accept_lookahead,read_ahead_probe;
  wire request_match,lookup_hit0,lookup_hit1;
  logic [WORD_BITS-1:0] refill_word, refill_count;
  logic early_delivered, refill_failed;
  logic stream_valid,stream_error;
  logic [31:0]stream_addr,stream_data;
  integer set_number;
  wire [SET_BITS-1:0] req_set = req_addr[OFFSET_BITS +: SET_BITS];
  wire [TAG_BITS-1:0] req_tag = req_addr[31 -: TAG_BITS];
  wire [WORD_BITS-1:0] req_word = req_addr[2 +: WORD_BITS];
  wire [RAM_BITS-1:0] req_ram_index = {req_set, req_word};
  wire [RAM_BITS-1:0] incoming_ram_index =
    read_ahead_probe ? lookahead_addr[2 +: RAM_BITS] : cpu_addr[2 +: RAM_BITS];
  wire [RAM_BITS-1:0] refill_index = {req_set, refill_word};
  // Reads and writes are mutually exclusive in the blocking cache FSM.  A
  // bank therefore has exactly one read address and one write address on a
  // clock edge, which preserves the old synchronous-read behavior.
  wire bank_read_enable = ((state == S_IDLE && cpu_valid && cpu_cacheable) ||
                          read_ahead_probe);
  wire bank_refill_write = state == S_REFILL && mem_ready && !mem_error;
  wire early_store=EARLY_STORE_REQUEST&&state==S_LOOKUP&&req_write&&request_match;
  wire bank_hit_write = mem_ready && !mem_error && ((state==S_WRITE&&req_hit)||(early_store&&(lookup_hit0||lookup_hit1)));
  wire bank_write_enable = !reset && (bank_refill_write || bank_hit_write);
  wire [RAM_BITS-1:0] bank_write_addr = bank_refill_write ? refill_index : req_ram_index;
  wire bank_write_way = bank_refill_write ? refill_way : early_store ? lookup_hit1 : hit_way;
  wire [3:0] bank_write_lane_enable = bank_refill_write ? 4'hf : early_store ? cpu_wstrb : req_wstrb;
  wire [31:0] bank_write_data = bank_refill_write ? mem_rdata : early_store ? cpu_wdata : req_wdata;
  logic [TAG_BITS-1:0] read_tag0,read_tag1;
  logic read_valid0,read_valid1;
  wire [SET_BITS-1:0] incoming_set=read_ahead_probe?lookahead_addr[OFFSET_BITS+:SET_BITS]:cpu_addr[OFFSET_BITS+:SET_BITS];
  always_ff @(posedge clk)begin
    if(reset)begin read_valid0<=0;read_valid1<=0;end
    else if(bank_read_enable)begin
      read_valid0<=valid0[incoming_set];read_valid1<=valid1[incoming_set];
    end
    if(bank_read_enable)begin read_tag0<=tag0[incoming_set];read_tag1<=tag1[incoming_set];end
  end
  // Resolve metadata in the request acceptance cycle and register only the
  // hit bits. This trades distributed tag storage for a short CPU-ready path,
  // without adding a cache-hit cycle or changing replacement/write semantics.
  wire[TAG_BITS-1:0]incoming_tag=read_ahead_probe?lookahead_addr[31-:TAG_BITS]:cpu_addr[31-:TAG_BITS];
  logic early_hit0,early_hit1;
  generate if(PRECOMPARE_TAGS)begin:early_tags
    always_ff @(posedge clk)begin
      if(reset)begin early_hit0<=0;early_hit1<=0;end
      else if(bank_read_enable)begin
        early_hit0<=valid0[incoming_set]&&tag0[incoming_set]==incoming_tag;
        early_hit1<=valid1[incoming_set]&&tag1[incoming_set]==incoming_tag;
      end
    end
  end else begin:no_early_tags
    assign early_hit0=0;assign early_hit1=0;
  end endgenerate
  assign lookup_hit0 = PRECOMPARE_TAGS ? early_hit0 : read_valid0 && read_tag0 == req_tag;
  assign lookup_hit1 = PRECOMPARE_TAGS ? early_hit1 : read_valid1 && read_tag1 == req_tag;
  wire read_hit = state == S_LOOKUP && !req_write &&
                  (lookup_hit0 || lookup_hit1);

  // Next-address sideband is a reservation, never a second outstanding miss.
  // RAM reads may be speculative even on a cancellation cycle. State and
  // valid bits still serialize FENCE.I; no speculative read can retire by itself.
  assign read_ahead_probe = LOOKAHEAD_HIT && lookahead_valid && lookahead_cacheable &&
    (read_hit || (EARLY_STORE_REQUEST && early_store && mem_ready) || (IDLE_LOAD_LOOKAHEAD && state==S_IDLE && !cpu_valid));
  assign accept_lookahead = read_ahead_probe && !pending_invalidate && !invalidate;

  // A burst owns the dedicated instruction SRAM port for exactly eight beats.
  // Forward only the word currently requested by the CPU. If it arrives after
  // its beat passed, it waits for the completed line and takes a normal hit.
  wire stream_capture = STREAM_REFILL && state == S_REFILL && mem_ready &&
    cpu_valid && !cpu_write && cpu_cacheable &&
    cpu_addr[31:OFFSET_BITS] == req_addr[31:OFFSET_BITS] &&
    cpu_addr[2 +: WORD_BITS] == refill_word;
  // The dedicated SRAM cannot pause its eight beats. Capture only the word
  // matching the outstanding CPU request, then return data, error and address
  // together one clock later. A cancelled/different request never sees it.
  wire stream_response=STREAM_REFILL&&stream_valid&&cpu_valid&&!cpu_write&&
    cpu_cacheable&&cpu_addr==stream_addr;
  always_ff @(posedge clk)begin
    if(reset)begin stream_valid<=0;stream_addr<=0;stream_data<=0;stream_error<=0;end
    else begin
      stream_valid<=stream_capture;
      if(stream_capture)begin stream_addr<=cpu_addr;stream_data<=mem_rdata;stream_error<=mem_error;end
    end
  end

  logic store_bypass_valid;logic[31:0]store_bypass_addr,store_bypass_data;logic[3:0]store_bypass_mask;
  always_ff @(posedge clk)begin
    if(reset)store_bypass_valid<=0;
    else begin
      store_bypass_valid<=EARLY_STORE_REQUEST&&bank_hit_write&&bank_read_enable;
      if(bank_hit_write&&bank_read_enable)begin
        store_bypass_addr<=req_addr;store_bypass_data<=bank_write_data;store_bypass_mask<=bank_write_lane_enable;
      end
    end
  end
  wire[31:0]raw_hit_data=lookup_hit1?read1:read0;
  logic[31:0]hit_data;integer fb;
  always_comb begin
    hit_data=raw_hit_data;
    if(store_bypass_valid&&store_bypass_addr==req_addr)
      for(fb=0;fb<4;fb=fb+1)if(store_bypass_mask[fb])hit_data[fb*8+:8]=store_bypass_data[fb*8+:8];
  end
  assign read0 = {read0_b3, read0_b2, read0_b1, read0_b0};
  assign read1 = {read1_b3, read1_b2, read1_b1, read1_b0};

  // One byte-bank instance per way/lane gives each inferred BRAM a single
  // write port.  No bank memory is reset; valid bits still make all contents
  // unreachable after reset, exactly as in the original cache.
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data0_b0(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read0_b0),
    .wr_en(bank_write_enable && !bank_write_way && bank_write_lane_enable[0]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[7:0]));
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data0_b1(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read0_b1),
    .wr_en(bank_write_enable && !bank_write_way && bank_write_lane_enable[1]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[15:8]));
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data0_b2(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read0_b2),
    .wr_en(bank_write_enable && !bank_write_way && bank_write_lane_enable[2]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[23:16]));
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data0_b3(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read0_b3),
    .wr_en(bank_write_enable && !bank_write_way && bank_write_lane_enable[3]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[31:24]));
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data1_b0(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read1_b0),
    .wr_en(bank_write_enable && bank_write_way && bank_write_lane_enable[0]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[7:0]));
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data1_b1(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read1_b1),
    .wr_en(bank_write_enable && bank_write_way && bank_write_lane_enable[1]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[15:8]));
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data1_b2(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read1_b2),
    .wr_en(bank_write_enable && bank_write_way && bank_write_lane_enable[2]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[23:16]));
  rv32_cache_byte_bank #(.DEPTH(WAY_WORDS), .ADDR_WIDTH(RAM_BITS)) u_data1_b3(
    .clk(clk), .rd_en(bank_read_enable), .rd_addr(incoming_ram_index), .rd_data(read1_b3),
    .wr_en(bank_write_enable && bank_write_way && bank_write_lane_enable[3]),
    .wr_addr(bank_write_addr), .wr_data(bank_write_data[31:24]));

  // A downstream transaction keeps its payload stable until mem_ready.
  // A response is one whole cycle. A still-high CPU valid on the NEXT idle
  // cycle denotes a new request, allowing consecutive stores with no valid gap.
  // Keep response forwarding separate from request generation. This also
  // avoids a false delta-cycle feedback through zero-wait MMIO responders.
  wire complete_response=state==S_RESP&&(!STREAM_REFILL||(cpu_valid&&cpu_addr==req_addr));
  // A lookahead is speculative. Only the matching live request may retire it.
  // Comparing registered addresses removes CPU redirect/queue logic from BRAM CE.
  assign request_match = !LOOKAHEAD_HIT || (cpu_valid && cpu_write == req_write && cpu_addr == req_addr);
  wire backend_response=DIRECT_BACKEND_RESPONSE&&(state==S_WRITE||state==S_BYPASS||early_store)&&mem_ready;
  assign cpu_ready = ((complete_response || read_hit) && request_match) || stream_response || backend_response;
  assign cpu_rdata = backend_response ? (req_write?32'b0:mem_rdata) : stream_response ? stream_data :
      read_hit ? hit_data : response_data;
  assign cpu_error = backend_response ? mem_error : stream_response ? stream_error : read_hit ? 1'b0 : response_error;
  assign idle = state == S_IDLE && !pending_invalidate;
  always_comb begin
    mem_valid = 1'b0;
    mem_write = 1'b0;
    mem_burst = 1'b0;
    mem_addr = {req_addr[31:2], 2'b00};
    mem_wdata = req_wdata;
    mem_wstrb = req_wstrb;
    case (state)
      S_LOOKUP:begin
        mem_valid=early_store;mem_write=req_write;mem_wdata=cpu_wdata;mem_wstrb=cpu_wstrb;
      end
      S_WRITE, S_BYPASS: begin
        mem_valid = 1'b1;
        mem_write = req_write;
      end
      S_REFILL: begin
        mem_valid = 1'b1;
        mem_burst = STREAM_REFILL;
        // The burst command address stays fixed, including the starting word.
        // Legacy word requests retain their per-beat address/ready handshake.
        mem_addr = STREAM_REFILL ? {req_addr[31:2],2'b00} :
                   (req_addr & ~(LINE_BYTES-1)) +
                   ({{(32-WORD_BITS){1'b0}}, refill_word} << 2);
        mem_wstrb = 4'b0000;
      end
      default: begin end
    endcase
  end

  always_ff @(posedge clk) begin
    if (reset) begin
      state <= S_IDLE;
      req_addr <= 0; req_wdata <= 0; req_wstrb <= 0; req_write <= 0;
      req_hit <= 0; hit_way <= 0; refill_way <= 0; refill_word <= 0;
      refill_count <= 0; early_delivered <= 0; refill_failed <= 0;
      response_data <= 0; requested_word <= 0; response_error <= 0;
      pending_invalidate <= 0;
      hit_pulse <= 0; miss_pulse <= 0; refill_pulse <= 0;
      for (set_number = 0; set_number < SETS; set_number = set_number + 1) begin
        valid0[set_number] <= 0; valid1[set_number] <= 0;
        victim[set_number] <= 0;
      end
    end else begin
      hit_pulse <= 0; miss_pulse <= 0; refill_pulse <= 0;
      if (invalidate) pending_invalidate <= 1;
      if (stream_response) early_delivered<=1;
      case (state)
        S_IDLE: begin
          // FENCE.I is permitted while busy: defer it until this transaction
          // finishes. Clear validity, not RAM contents.
          if (pending_invalidate || invalidate) begin
            for (set_number = 0; set_number < SETS; set_number = set_number + 1) begin
              valid0[set_number] <= 0;
              valid1[set_number] <= 0;
            end
            pending_invalidate <= 0;
          end else if (IDLE_LOAD_LOOKAHEAD && read_ahead_probe)begin
            req_addr<=lookahead_addr;req_write<=lookahead_write;req_wdata<=lookahead_wdata;req_wstrb<=lookahead_wstrb;
            req_hit<=0;response_data<=0;response_error<=0;state<=S_LOOKUP;
          end else if (cpu_valid) begin
            req_addr <= cpu_addr;
            req_wdata <= cpu_wdata;
            req_wstrb <= cpu_wstrb;
            req_write <= cpu_write;
            req_hit <= 0;
            response_data <= 0;
            response_error <= 0;
            if (cpu_cacheable) state <= S_LOOKUP;
            else state <= S_BYPASS;
          end
        end
        S_LOOKUP: begin
          // A hint reserves a RAM read, never the store's authority/payload.
          // Live MEM bytes are used on first issue and latched across stalls.
          if(early_store)begin req_wdata<=cpu_wdata;req_wstrb<=cpu_wstrb;end
          // An unused hint must not launch a miss or acknowledge another PC.
          if (LOOKAHEAD_HIT && !request_match) begin
            state <= S_IDLE;
          end else if (lookup_hit0 || lookup_hit1) begin
            req_hit <= 1;
            hit_way <= lookup_hit1;
            victim[req_set] <= !lookup_hit1;
            hit_pulse <= 1;
            if (req_write)begin
              if(early_store&&mem_ready)begin
                response_data<=0;response_error<=mem_error;
                if(mem_error)begin if(lookup_hit1)valid1[req_set]<=0;else valid0[req_set]<=0;end
                if(accept_lookahead)begin
                  req_addr<=lookahead_addr;req_write<=lookahead_write;req_wdata<=lookahead_wdata;req_wstrb<=lookahead_wstrb;
                  req_hit<=0;state<=S_LOOKUP;
                end else state<=S_IDLE;
              end else state<=S_WRITE;
            end
            else if (accept_lookahead) begin
              req_addr <= lookahead_addr; req_write <= IDLE_LOAD_LOOKAHEAD?lookahead_write:1'b0;
              req_wdata <= lookahead_wdata; req_wstrb <= lookahead_wstrb;
              req_hit <= 0; response_data <= 0; response_error <= 0;
              state <= S_LOOKUP;
            end else state <= S_IDLE; // The registered RAM word is acknowledged now.
          end else begin
            miss_pulse <= 1;
            if (req_write) begin
              // No-write-allocate: a store miss is forwarded without a refill.
              if(early_store&&mem_ready)begin
                response_data<=0;response_error<=mem_error;
                if(accept_lookahead)begin
                  req_addr<=lookahead_addr;req_write<=lookahead_write;req_wdata<=lookahead_wdata;req_wstrb<=lookahead_wstrb;
                  req_hit<=0;state<=S_LOOKUP;
                end else state<=S_IDLE;
              end
              else state<=S_WRITE;
            end else begin
              refill_way <= !valid0[req_set] ? 1'b0 :
                            !valid1[req_set] ? 1'b1 : victim[req_set];
              if (!valid0[req_set] || (valid1[req_set] && !victim[req_set]))
                valid0[req_set] <= 0;
              else
                valid1[req_set] <= 0;
              refill_word <= STREAM_REFILL ? req_word : {WORD_BITS{1'b0}};
              refill_count <= 0;
              early_delivered <= 0;
              refill_failed <= 0;
              requested_word <= 0;
              state <= S_REFILL;
            end
          end
        end
        S_WRITE, S_BYPASS: if (mem_ready) begin
          response_data <= req_write ? 32'b0 : mem_rdata;
          response_error <= mem_error;
          // An errored write may have partially changed memory. Discard the
          // matching cache line instead of retaining a potentially stale copy.
          if (state == S_WRITE && req_hit && mem_error) begin
            if (hit_way) valid1[req_set] <= 0;
            else valid0[req_set] <= 0;
          end
          state <= DIRECT_BACKEND_RESPONSE ? S_IDLE : S_RESP;
        end
        S_REFILL: if (mem_ready) begin
          // Never abandon a burst after an early response or an error. Drain
          // all eight responses so a late beat cannot acknowledge a new miss.
          if (mem_error) refill_failed <= 1;
          else begin
            refill_pulse <= 1;
            if (refill_word == req_word) requested_word <= mem_rdata;
          end
          if (mem_error && !STREAM_REFILL) begin
            response_error <= 1;
            response_data <= 0;
            state <= S_RESP;
          end else if (refill_count == LAST_LINE_WORD[WORD_BITS-1:0]) begin
            if (!refill_failed && !mem_error) begin
              if (refill_way) begin
                valid1[req_set] <= 1;

              end else begin
                valid0[req_set] <= 1;

              end
              victim[req_set] <= !refill_way;
            end
            response_data <= refill_word == req_word ? mem_rdata : requested_word;
            response_error <= refill_failed || mem_error;
            // A last-beat match is still queued, even if an earlier request
            // already completed. Hold the cache out of IDLE until its delayed
            // ACK retires; otherwise IDLE could reaccept the old address.
            if(STREAM_REFILL&&stream_capture)state<=S_STREAM_RESP;
            else if(STREAM_REFILL&&(early_delivered||stream_response))state<=S_IDLE;
            else state<=S_RESP;
          end else begin
            refill_word <= refill_word + 1'b1;
            refill_count <= refill_count + 1'b1;
          end
        end
        S_STREAM_RESP:if(stream_response||!stream_valid)state<=S_IDLE;
        S_RESP: state <= S_IDLE;
        default: state <= S_IDLE;
      endcase
    end
  end

  // Tag payload has one explicit write event, separate from validity/reset.
  // Writing the inactive way's old value makes the pair one transaction;
  // data and validity semantics remain unchanged.
  always_ff @(posedge clk)begin
    if(!reset && state==S_REFILL && mem_ready && refill_count==LAST_LINE_WORD[WORD_BITS-1:0] && !refill_failed && !mem_error)begin
      tag0[req_set]<=refill_way?tag0[req_set]:req_tag;
      tag1[req_set]<=refill_way?req_tag:tag1[req_set];
    end
  end
  // Unsupported geometry fails at elaboration rather than silently aliasing.
  initial begin
    if (STREAM_REFILL && LINE_BYTES != 32)
      $fatal(1, "instruction SRAM burst requires 32-byte lines");
    if (LINE_BYTES < 8 || (LINE_BYTES & (LINE_BYTES-1)) != 0 ||
        SETS < 2 || (SETS & (SETS-1)) != 0)
      $fatal(1, "rv32_cache requires power-of-two line bytes and at least two sets");
  end
endmodule

// A byte-wide synchronous-read/single-write bank.  Keeping this as a small
// standalone module makes the RAM inference pattern explicit to ADS/PDS.
module rv32_cache_byte_bank #(
  parameter integer DEPTH = 512,
  parameter integer ADDR_WIDTH = 9
)(
  input  logic clk,
  input  logic rd_en,
  input  logic [ADDR_WIDTH-1:0] rd_addr,
  output logic [7:0] rd_data,
  input  logic wr_en,
  input  logic [ADDR_WIDTH-1:0] wr_addr,
  input  logic [7:0] wr_data
);
  logic [7:0] mem [0:DEPTH-1];
  always_ff @(posedge clk) begin
    if (rd_en) rd_data <= mem[rd_addr];
    if (wr_en) mem[wr_addr] <= wr_data;
  end
endmodule
`default_nettype wire

