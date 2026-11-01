// XND: tiny low-bit GEMV engine with two resident activation slots.
// CPU configures a job; DMA moves packed words; hardware returns INT32 sums.
// A slot is an on-chip "drawer": LOAD fills it once, many GEMVs can reuse it.
`default_nettype none
module xnd_engine #(
  parameter integer MAX_COLS = 256,
  parameter integer MAX_ROWS = 256,
  parameter integer DMA_TIMEOUT = 4096,
  parameter bit WEIGHT_PREFETCH = 1,
  parameter logic [31:0] AI_FIRST = 32'h00020000,
  parameter logic [31:0] RAM_LAST = 32'h0003ffff,
  parameter bit ENABLE_DDR=0,
  parameter logic [31:0] DDR_BASE=32'h80000000,
  parameter integer DDR_BYTES=1048576
)(
  input logic clk, reset,
  input logic req_valid, req_write,
  input logic [15:0] req_addr,
  input logic [31:0] req_wdata,
  input logic [3:0] req_wstrb,
  output logic req_ready,
  output logic [31:0] req_rdata,
  output logic req_error,
  output logic mem_valid, mem_write,
  output logic [31:0] mem_addr, mem_wdata,
  output logic [3:0] mem_wstrb,
  input logic mem_ready,
  input logic [31:0] mem_rdata,
  input logic mem_error,
  output logic irq
);
  localparam logic [7:0] E_COMMAND=1, E_PARAM=2, E_RANGE=3,
                           E_SLOT=4, E_DMA=5, E_TIMEOUT=6;
  // ADS subset: explicit constants replace the unsupported enum type.
  localparam logic [3:0] IDLE=4'd0, LOAD_REQ=4'd1, LOAD_STORE=4'd2,
    WEIGHT_REQ=4'd3, MAC=4'd4, Y_REQ=4'd5, BIAS_REQ=4'd6,
    RESIDUAL_REQ=4'd7, POST_SUBMIT=4'd8, POST_WAIT=4'd9;
  logic [3:0] state;
  logic [31:0] operand_a, operand_b, a_addr, w_addr, y_addr;
  logic [31:0] cols, rows, stride, control;
  // Experimental postprocessing config: enable[0], mode[2:1], right shift[7:3].
  logic [31:0] bias_addr, post_cfg, post_bias;
  logic signed [7:0] post_residual;
  wire post_enable=post_cfg[0];
  logic post_in_ready,post_out_valid;
  logic signed [7:0] post_quant;
  logic signed [31:0] post_logit;
  logic post_overflow;
  logic [15:0] post_tag;
  logic post_last;
  logic signed [7:0] post_result;
  logic signed [7:0] activation [0:1][0:MAX_COLS-1];
  logic [1:0] slot_valid;
  logic [31:0] slot_cols [0:1];
  logic slot;
  logic done, error;
  logic [7:0] error_code;
  logic [31:0] cycles, read_bytes, write_bytes, macs;
  localparam integer COL_INDEX_BITS = (MAX_COLS > 1) ? $clog2(MAX_COLS) : 1;
  localparam integer ROW_INDEX_BITS = (MAX_ROWS > 1) ? $clog2(MAX_ROWS) : 1;
  logic [COL_INDEX_BITS-1:0] col_counter;
  wire [31:0] col_index = {{(32-COL_INDEX_BITS){1'b0}},col_counter};
  wire [31:0] next_col_index = col_index + 32'd4;
  logic [ROW_INDEX_BITS-1:0] row_counter;
  wire [31:0] row_index = {{(32-ROW_INDEX_BITS){1'b0}},row_counter};
  wire [31:0] next_row_index = row_index + 32'd1;
  logic [31:0] packed_word, wait_cycles;
  logic [31:0] weight_row_addr;
  // Command checks reject rows==0 or rows>MAX_ROWS before this extent is used.
  wire [ROW_INDEX_BITS-1:0] last_valid_row = rows[ROW_INDEX_BITS-1:0] - 1'b1;
  logic [2:0] lane;
  logic weight_next_valid;
  logic [31:0] weight_next_word;
  wire [31:0] next_weight_col = control[0] ?
    ((col_index & 32'hfffffff8)+32'd8) : ((col_index & 32'hfffffffc)+32'd4);
  wire prefetch_weight = WEIGHT_PREFETCH && state==MAC &&
    next_weight_col<cols && !weight_next_valid;
  // Row DMA base advances only after a completed output write. This avoids
  // a full row_index*stride multiplier on every request, without extra cycles.
  // Column selection is shared by normal and same-row look-ahead requests.
  wire [31:0] dma_weight_col = prefetch_weight ? next_weight_col : col_index;
  wire [31:0] dma_weight_offset = control[0] ?
    ((dma_weight_col>>3)<<2) : ((dma_weight_col>>2)<<2);
  wire [31:0] dma_weight_row_base = weight_row_addr;
  wire [31:0] dma_weight_addr = dma_weight_row_base + dma_weight_offset;
  logic signed [31:0] accumulator, result;
  // Four physical MAC lanes; INT4 packs eight weights per DMA word.
  logic signed [7:0] current_a [0:3], current_w [0:3];
  logic signed [15:0] product [0:3];
  logic signed [31:0] vector_sum;
  logic [31:0] mac_lanes;
  logic [63:0] weight_extent, a_extent, y_extent;
  logic [31:0] row_bytes, padded_row_bytes;
  logic busy, addr_known, addr_writable, config_write, cmd_write;
  logic signed [31:0] dot_p0, dot_p1, dot_p2, dot_p3;

  wire [31:0] byte_y_addr=y_addr+row_index;
  postprocess_fusion u_post(
    .clk(clk),.reset(reset),.in_valid(state==POST_SUBMIT),.in_ready(post_in_ready),
    .in_raw(accumulator),.in_bias(post_bias),.in_shift(post_cfg[7:3]),
    .in_mode(post_cfg[2:1]),.in_residual(post_residual),
    .in_tag(row_index[15:0]),.in_last(row_index+1>=rows),
    .out_valid(post_out_valid),.out_ready(state==POST_WAIT),
    .out_quant(post_quant),.out_logit(post_logit),.out_overflow(post_overflow),
    .out_tag(post_tag),.out_last(post_last));
  // Byte enables matter: a CPU byte store must not change neighbouring bytes.
  function automatic [31:0] merge_bytes(input [31:0] old_value, new_value,
                                        input [3:0] strobes);
    integer b;
    begin
      merge_bytes=old_value;
      for (b=0;b<4;b=b+1)
        if (strobes[b]) merge_bytes[b*8 +: 8]=new_value[b*8 +: 8];
    end
  endfunction

  // Error completion is sticky, just like success. Software acknowledges W1C.
  task automatic fail_job(input logic [7:0] code);
    begin
      state<=IDLE; done<=1'b1; error<=1'b1; error_code<=code;
      weight_next_valid<=0;
    end
  endtask

  assign busy=(state!=IDLE);
  assign irq=control[1] && (done || error);
  assign req_ready=1'b1;
  assign config_write=req_valid && req_write &&
       (req_addr==16'h0008 || req_addr==16'h000c ||
        (req_addr>=16'h0020 && req_addr<=16'h0038) || req_addr==16'h0058 || req_addr==16'h005c);
  assign cmd_write=req_valid && req_write && req_addr==16'h0010 &&
                   req_wstrb==4'hf;
  assign row_bytes=control[0] ? ((cols+1)>>1) : cols;
  assign padded_row_bytes=(row_bytes+3)&32'hfffffffc;
  // Wide arithmetic prevents integer wraparound from passing a range check.
  // A tensor must fit wholly within ONE allowed memory window. Increasing
  // RAM_LAST across the MMIO gap would silently admit unrelated addresses.
  function automatic logic range_ok(input logic [31:0] first,
                                    input logic [63:0] last,input logic ai_only);
    begin
      // Keep the function result direct. ADS otherwise creates unused cloned
      // local-variable nodes and warns that their drivers are missing.
      range_ok=((!ai_only || first>=AI_FIRST) && last<={32'd0,RAM_LAST}) ||
               (ENABLE_DDR && first>=DDR_BASE &&
                last<({32'd0,DDR_BASE}+{32'd0,DDR_BYTES}));
    end
  endfunction
  assign a_extent={32'd0,a_addr}+{32'd0,((cols+32'd3)&32'hfffffffc)}-1;
  assign y_extent={32'd0,y_addr}+(post_enable?{32'd0,((rows+32'd3)&32'hfffffffc)}:({32'd0,rows}<<2))-1;
  wire [63:0] bias_extent={32'd0,bias_addr}+({32'd0,rows}<<2)-1;
  assign weight_extent={32'd0,w_addr}+
             ({{(64-ROW_INDEX_BITS){1'b0}},last_valid_row}*{32'd0,stride})+{32'd0,padded_row_bytes}-1;

  assign dot_p0=$signed({{24{operand_a[7]}},operand_a[7:0]}) *
                $signed({{24{operand_b[7]}},operand_b[7:0]});
  assign dot_p1=$signed({{24{operand_a[15]}},operand_a[15:8]}) *
                $signed({{24{operand_b[15]}},operand_b[15:8]});
  assign dot_p2=$signed({{24{operand_a[23]}},operand_a[23:16]}) *
                $signed({{24{operand_b[23]}},operand_b[23:16]});
  assign dot_p3=$signed({{24{operand_a[31]}},operand_a[31:24]}) *
                $signed({{24{operand_b[31]}},operand_b[31:24]});

  integer k;
  always_comb begin
    vector_sum=0; mac_lanes=0;
    for(k=0;k<4;k=k+1) begin
      current_a[k]=0; current_w[k]=0; product[k]=0;
      if(col_index+k<cols && col_index+k<MAX_COLS) begin
        current_a[k]=activation[slot][col_index+k];
        if(control[0])
          current_w[k]=$signed({{4{packed_word[({29'd0,lane}+k)*4+3]}},
                                packed_word[({29'd0,lane}+k)*4 +: 4]});
        else current_w[k]=$signed(packed_word[k*8 +: 8]);
        product[k]=current_a[k]*current_w[k];
        vector_sum=vector_sum+$signed({{16{product[k][15]}},product[k]});
        mac_lanes=mac_lanes+1;
      end
    end
  end

  // Single outstanding DMA transfer. Address/data remain stable during stalls.
  always_comb begin
    mem_valid=0; mem_write=0; mem_addr=0; mem_wdata=0; mem_wstrb=0;
    case (state)
      LOAD_REQ: begin
        mem_valid=1; mem_addr=a_addr+((col_index>>2)<<2);
      end
      WEIGHT_REQ: begin
        mem_valid=1;
        mem_addr=dma_weight_addr;
      end
      MAC: if(prefetch_weight) begin
        // Start only the following word of THIS row. When the MAC word ends,
        // WEIGHT_REQ keeps exactly this address until the same response arrives.
        mem_valid=1;
        mem_addr=dma_weight_addr;
      end
      Y_REQ: begin
        mem_valid=1; mem_write=1; mem_addr=y_addr+(row_index<<2);
        mem_wdata=accumulator; mem_wstrb=4'hf;
        if(post_enable) begin
          mem_addr={byte_y_addr[31:2],2'b0};
          mem_wdata={24'd0,post_result}<<({30'd0,byte_y_addr[1:0]}<<3);
          mem_wstrb=4'b0001<<byte_y_addr[1:0];
        end
      end
      BIAS_REQ: begin mem_valid=1;mem_addr=bias_addr+(row_index<<2);end
      RESIDUAL_REQ: begin mem_valid=1;mem_addr={byte_y_addr[31:2],2'b0};end
      default: ;
    endcase
  end

  always_comb begin
    req_rdata=0; addr_known=1; addr_writable=0;
    case(req_addr)
      16'h0000: begin
        req_rdata={22'd0,slot_valid,5'd0,error,done,busy}; addr_writable=1;
      end
      16'h0004: req_rdata=result;
      16'h0008: begin req_rdata=operand_a; addr_writable=1; end
      16'h000c: begin req_rdata=operand_b; addr_writable=1; end
      16'h0010: addr_writable=1;
      16'h0020: begin req_rdata=a_addr; addr_writable=1; end
      16'h0024: begin req_rdata=w_addr; addr_writable=1; end
      16'h0028: begin req_rdata=y_addr; addr_writable=1; end
      16'h002c: begin req_rdata=cols; addr_writable=1; end
      16'h0030: begin req_rdata=rows; addr_writable=1; end
      16'h0034: begin req_rdata=stride; addr_writable=1; end
      16'h0038: begin req_rdata=control; addr_writable=1; end
      16'h003c: req_rdata={24'd0,error_code};
      16'h0040: req_rdata=cycles;
      16'h0044: req_rdata=read_bytes;
      16'h0048: req_rdata=write_bytes;
      16'h004c: req_rdata=macs;
      16'h0050: req_rdata=slot_cols[0];
      16'h0054: req_rdata=slot_cols[1];
      16'h0058: begin req_rdata=bias_addr;addr_writable=1;end
      16'h005c: begin req_rdata=post_cfg;addr_writable=1;end
      default: addr_known=0;
    endcase
    req_error=req_valid &&
      (!addr_known || req_addr[1:0]!=0 ||
       (req_write && !addr_writable) ||
       (req_write && req_addr==16'h0010 && (busy || req_wstrb!=4'hf)) ||
       (config_write && busy));
  end

  integer i;
  always_ff @(posedge clk) begin
    if(reset) begin
      state<=IDLE; slot<=0; slot_valid<=0;
      slot_cols[0]<=0; slot_cols[1]<=0;
      operand_a<=0; operand_b<=0; a_addr<=0; w_addr<=0; y_addr<=0;
      cols<=0; rows<=0; stride<=0; control<=0;bias_addr<=0;post_cfg<=0;post_bias<=0;post_residual<=0;post_result<=0;
      done<=0; error<=0; error_code<=0;
      cycles<=0; read_bytes<=0; write_bytes<=0; macs<=0;
      col_counter<=0; row_counter<=0; packed_word<=0; lane<=0;
      accumulator<=0; result<=0; wait_cycles<=0;
      weight_next_valid<=0; weight_next_word<=0; weight_row_addr<=0;
      // Slot RAM is not reset: valid bits prevent use before LOAD.
    end else begin
      if(busy) cycles<=cycles+1;
      if(mem_valid && !mem_ready) begin
        if(wait_cycles>=DMA_TIMEOUT-1) fail_job(E_TIMEOUT);
        else wait_cycles<=wait_cycles+1;
      end else wait_cycles<=0;

      if(req_valid && req_write && req_addr==16'h0000 && req_wstrb[0]) begin
        if(req_wdata[1]) done<=0;
        if(req_wdata[2]) begin error<=0; error_code<=0; end
      end
      if(config_write && !req_error) case(req_addr)
        16'h0008: operand_a<=merge_bytes(operand_a,req_wdata,req_wstrb);
        16'h000c: operand_b<=merge_bytes(operand_b,req_wdata,req_wstrb);
        16'h0020: a_addr<=merge_bytes(a_addr,req_wdata,req_wstrb);
        16'h0024: w_addr<=merge_bytes(w_addr,req_wdata,req_wstrb);
        16'h0028: y_addr<=merge_bytes(y_addr,req_wdata,req_wstrb);
        16'h002c: cols<=merge_bytes(cols,req_wdata,req_wstrb);
        16'h0030: rows<=merge_bytes(rows,req_wdata,req_wstrb);
        16'h0034: stride<=merge_bytes(stride,req_wdata,req_wstrb);
        16'h0038: control<=merge_bytes(control,req_wdata,req_wstrb);
        16'h0058: bias_addr<=merge_bytes(bias_addr,req_wdata,req_wstrb);
        16'h005c: post_cfg<=merge_bytes(post_cfg,req_wdata,req_wstrb);
        default: ;
      endcase

      if(cmd_write && !busy) begin
        done<=0; error<=0; error_code<=0;
        cycles<=0; read_bytes<=0; write_bytes<=0; macs<=0; wait_cycles<=0;
        slot<=req_wdata[8]; col_counter<=0; row_counter<=0; lane<=0; accumulator<=0;
        weight_row_addr<=w_addr;
        weight_next_valid<=0;
        case(req_wdata[7:0])
          8'd1: begin
            result<=dot_p0+dot_p1+dot_p2+dot_p3; macs<=4; done<=1;
          end
          8'd2: begin
            slot_valid[req_wdata[8]]<=0;
            if(cols==0 || cols>MAX_COLS || a_addr[1:0]!=0) fail_job(E_PARAM);
            else if(!range_ok(a_addr,a_extent,1'b1)) fail_job(E_RANGE);
            else state<=LOAD_REQ;
          end
          8'd3: begin
            if(cols==0 || cols>MAX_COLS || rows==0 || rows>MAX_ROWS ||
               stride<padded_row_bytes || stride[1:0]!=0 ||
               w_addr[1:0]!=0 || y_addr[1:0]!=0 || (post_enable && (bias_addr[1:0]!=0 || post_cfg[2:1]==3 || post_cfg[31:8]!=0))) fail_job(E_PARAM);
            else if(!range_ok(w_addr,weight_extent,1'b0) || !range_ok(y_addr,y_extent,1'b1) || (post_enable && !range_ok(bias_addr,bias_extent,1'b0)))
              fail_job(E_RANGE);
            else if(!slot_valid[req_wdata[8]] || slot_cols[req_wdata[8]]!=cols)
              fail_job(E_SLOT);
            else state<=WEIGHT_REQ;
          end
          8'd4: begin slot_valid[req_wdata[8]]<=0; done<=1; end
          default: fail_job(E_COMMAND);
        endcase
      end

      case(state)
        LOAD_REQ: if(mem_ready) begin
          if(mem_error) fail_job(E_DMA);
          else begin packed_word<=mem_rdata; read_bytes<=read_bytes+4; state<=LOAD_STORE; end
        end
        LOAD_STORE: begin
          for(i=0;i<4;i=i+1)
            if(col_index+i<cols) activation[slot][col_index+i]<=packed_word[i*8 +: 8];
          if(col_index+4>=cols) begin
            slot_valid[slot]<=1; slot_cols[slot]<=cols; state<=IDLE; done<=1;
          end else begin col_counter<=next_col_index[COL_INDEX_BITS-1:0]; state<=LOAD_REQ; end
        end
        WEIGHT_REQ: if(mem_ready) begin
          if(mem_error) fail_job(E_DMA);
          else begin
            packed_word<=mem_rdata; lane<=0; read_bytes<=read_bytes+4; state<=MAC;
            weight_next_valid<=0;
          end
        end
        MAC: begin
          if(mem_valid && !mem_ready && wait_cycles>=DMA_TIMEOUT-1) begin
            // Global timeout completion above must not be overwritten by MAC.
          end else if(mem_valid && mem_ready && mem_error) fail_job(E_DMA);
          else begin
            // One word of look-ahead overlaps DMA with four physical MACs.
            // No wider MAC claim, no speculative read beyond the validated row.
            if(mem_valid && mem_ready) begin
              weight_next_word<=mem_rdata; weight_next_valid<=1;
              read_bytes<=read_bytes+4;
            end
            accumulator<=accumulator+vector_sum; macs<=macs+mac_lanes;
            if(col_index+4>=cols) begin state<=post_enable?BIAS_REQ:Y_REQ;weight_next_valid<=0;end
            else begin
              col_counter<=next_col_index[COL_INDEX_BITS-1:0];
              if(control[0] && lane==0) lane<=4;
              else begin
                lane<=0;
                if(WEIGHT_PREFETCH && (weight_next_valid || (mem_valid && mem_ready))) begin
                  packed_word<=weight_next_valid ? weight_next_word : mem_rdata;
                  weight_next_valid<=0;
                end else state<=WEIGHT_REQ;
              end
            end
          end
        end
        BIAS_REQ: if(mem_ready) begin
          if(mem_error)fail_job(E_DMA);
          else begin
            post_bias<=mem_rdata;read_bytes<=read_bytes+4;
            if(post_cfg[2:1]==2) state<=RESIDUAL_REQ;
            else begin post_residual<=0;state<=POST_SUBMIT;end
          end
        end
        RESIDUAL_REQ: if(mem_ready) begin
          if(mem_error)fail_job(E_DMA);
          else begin
            post_residual<=mem_rdata[({30'd0,byte_y_addr[1:0]}<<3) +: 8];
            read_bytes<=read_bytes+4;state<=POST_SUBMIT;
          end
        end
        POST_SUBMIT: if(post_in_ready) state<=POST_WAIT;
        POST_WAIT: if(post_out_valid) begin
          if(post_overflow || post_tag!=row_index[15:0] || post_last!=(row_index+1>=rows))fail_job(E_PARAM);
          else begin post_result<=post_quant;state<=Y_REQ;end
        end
        Y_REQ: if(mem_ready) begin
          if(mem_error) fail_job(E_DMA);
          else begin
            result<=post_enable?post_logit:accumulator; write_bytes<=write_bytes+(post_enable?1:4);
            if(row_index+1>=rows) begin state<=IDLE; done<=1; end
            else begin
              row_counter<=next_row_index[ROW_INDEX_BITS-1:0]; weight_row_addr<=weight_row_addr+stride;
              col_counter<=0; accumulator<=0; lane<=0; state<=WEIGHT_REQ;
            end
          end
        end
        default: ;
      endcase
    end
  end
endmodule
`default_nettype wire
