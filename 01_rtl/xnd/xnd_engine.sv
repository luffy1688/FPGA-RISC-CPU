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
  localparam logic [4:0] IDLE=4'd0, LOAD_REQ=4'd1, LOAD_STORE=4'd2,
    WEIGHT_REQ=4'd3, MAC=4'd4, Y_REQ=4'd5, BIAS_REQ=4'd6,
    RESIDUAL_REQ=4'd7, POST_SUBMIT=4'd8, POST_WAIT=4'd9,
    CHECK_PARAM=4'd10, CHECK_PRODUCT=4'd11, CHECK_BASE=4'd12,
    CHECK_END=4'd13,CHECK_RANGE=4'd14,MAC_DRAIN=5'd15,
    DOT_PRODUCT=5'd16,DOT_SUM=5'd17,DOT_DONE=5'd18,
    PARAM_EVAL=5'd19,RANGE_EVAL=5'd20;
  logic [4:0] state;
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
  logic mac_valid0,mac_valid1,mac_valid2,mac_last0,mac_last1,mac_last2;
  logic [31:0]mac_lanes0,mac_lanes1,mac_lanes2;
  logic signed[7:0]activation_q[0:3],weight_q[0:3];
  logic signed[15:0]product_q[0:3],dot_product_q[0:3];
  logic signed[16:0]pair0_q,pair1_q,dot_pair0_q,dot_pair1_q;
  wire signed[17:0]pair_sum=$signed(pair0_q)+$signed(pair1_q);
  wire signed[31:0]registered_vector_sum={{14{pair_sum[17]}},pair_sum};
  wire signed[17:0]dot_pair_sum=$signed(dot_pair0_q)+$signed(dot_pair1_q);
  wire signed[31:0]registered_dot_sum={{14{dot_pair_sum[17]}},dot_pair_sum};
  wire mac_timeout=mem_valid&&!mem_ready&&wait_cycles>=DMA_TIMEOUT-1;
  wire mac_dma_error=mem_valid&&mem_ready&&mem_error;
  wire mac_issue=state==MAC&&!mac_timeout&&!mac_dma_error;
  // A command owns the configuration while these checked setup stages run.
  // Partial products avoid a multiplier plus two wide carry chains plus a
  // range comparator in the command-accept cycle. No DMA is issued here.
  logic validation_gemv;
  logic validation_param_bad,validation_range_bad,validation_slot_ok;
  logic [ROW_INDEX_BITS-1:0] validation_last_row;
  logic [31:0] validation_a_last,validation_y_last,validation_bias_last;
  logic [31:0] validation_weight_last;
  logic [ROW_INDEX_BITS+15:0] validation_product_low,validation_product_high;
  logic [63:0] validation_row_span,validation_weight_base;
  logic [63:0] weight_extent, a_extent, y_extent,bias_extent;
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
      weight_next_valid<=0;mac_valid0<=0;mac_valid1<=0;mac_valid2<=0;
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
      accumulator<=0;result<=0;wait_cycles<=0;
      mac_valid0<=0;mac_valid1<=0;mac_valid2<=0;mac_last0<=0;mac_last1<=0;mac_last2<=0;mac_lanes0<=0;mac_lanes1<=0;mac_lanes2<=0;
      pair0_q<=0;pair1_q<=0;dot_pair0_q<=0;dot_pair1_q<=0;
      for(i=0;i<4;i=i+1)begin activation_q[i]<=0;weight_q[i]<=0;product_q[i]<=0;dot_product_q[i]<=0;end
      weight_next_valid<=0; weight_next_word<=0; weight_row_addr<=0;
      validation_gemv<=0;validation_last_row<=0;validation_param_bad<=0;validation_range_bad<=0;validation_slot_ok<=0;
      validation_a_last<=0;validation_y_last<=0;validation_bias_last<=0;validation_weight_last<=0;
      validation_product_low<=0;validation_product_high<=0;
      validation_row_span<=0;validation_weight_base<=0;
      weight_extent<=0;a_extent<=0;y_extent<=0;bias_extent<=0;
      // Slot RAM is not reset: valid bits prevent use before LOAD.
    end else begin
      if(busy) cycles<=cycles+1;
      if(mem_valid && !mem_ready) begin
        if(wait_cycles>=DMA_TIMEOUT-1) fail_job(E_TIMEOUT);
        else wait_cycles<=wait_cycles+1;
      end else wait_cycles<=0;

      // One four-lane group can issue every MAC cycle. The adder tree is
      // pipelined independently of DMA wait states. Only a row's final group
      // drains before output/postprocessing, so the cost is three clocks/row.
      // The asynchronous activation bank mux ends at activation_q; it does
      // not share a timing path with either the DSP products or accumulator.
      if(mac_timeout||mac_dma_error)begin mac_valid0<=0;mac_valid1<=0;mac_valid2<=0;end
      else begin
        mac_valid0<=mac_issue;mac_valid1<=mac_valid0;mac_valid2<=mac_valid1;
        if(mac_issue)begin
          for(i=0;i<4;i=i+1)begin activation_q[i]<=current_a[i];weight_q[i]<=current_w[i];end
          mac_last0<=col_index+4>=cols;mac_lanes0<=mac_lanes;
        end
        if(mac_valid0)begin
          for(i=0;i<4;i=i+1)product_q[i]<=activation_q[i]*weight_q[i];
          mac_last1<=mac_last0;mac_lanes1<=mac_lanes0;
        end
        if(mac_valid1)begin
          pair0_q<=$signed(product_q[0])+$signed(product_q[1]);
          pair1_q<=$signed(product_q[2])+$signed(product_q[3]);
          mac_last2<=mac_last1;mac_lanes2<=mac_lanes1;
        end
        if(mac_valid2)begin
          accumulator<=accumulator+registered_vector_sum;macs<=macs+mac_lanes2;
          if(mac_last2)state<=post_enable?BIAS_REQ:Y_REQ;
        end
      end

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
            state<=DOT_PRODUCT;
          end
          8'd2: begin
            slot_valid[req_wdata[8]]<=0;
            validation_gemv<=0;state<=PARAM_EVAL;
          end
          8'd3: begin
            validation_gemv<=1;state<=PARAM_EVAL;
          end
          8'd4: begin slot_valid[req_wdata[8]]<=0; done<=1; end
          default: fail_job(E_COMMAND);
        endcase
      end

      case(state)
        PARAM_EVAL:begin
          validation_param_bad<=validation_gemv ? (cols==0 || cols>MAX_COLS || rows==0 || rows>MAX_ROWS ||
               stride<padded_row_bytes || stride[1:0]!=0 ||
               w_addr[1:0]!=0 || y_addr[1:0]!=0 ||
               (post_enable && (bias_addr[1:0]!=0 || post_cfg[2:1]==3 || post_cfg[31:8]!=0))) : (cols==0 || cols>MAX_COLS || a_addr[1:0]!=0);
          state<=CHECK_PARAM;
        end
        CHECK_PARAM:begin
          // Keep the original PARAM -> RANGE -> SLOT error precedence.
          if(!validation_gemv)begin
            if(validation_param_bad)fail_job(E_PARAM);
            else begin
              validation_a_last<=((cols+32'd3)&32'hfffffffc)-32'd1;
              state<=CHECK_PRODUCT;
            end
          end else begin
            if(validation_param_bad)fail_job(E_PARAM);
            else begin
              validation_last_row<=last_valid_row;
              validation_weight_last<=padded_row_bytes-32'd1;
              validation_y_last<=post_enable?((rows+32'd3)&32'hfffffffc)-32'd1:(rows<<2)-32'd1;
              validation_bias_last<=(rows<<2)-32'd1;
              state<=CHECK_PRODUCT;
            end
          end
        end
        CHECK_PRODUCT:begin
          if(validation_gemv)begin
            validation_product_low<=validation_last_row*stride[15:0];
            validation_product_high<=validation_last_row*stride[31:16];
            y_extent<={32'd0,y_addr}+{32'd0,validation_y_last};
            bias_extent<={32'd0,bias_addr}+{32'd0,validation_bias_last};
            state<=CHECK_BASE;
          end else begin
            a_extent<={32'd0,a_addr}+{32'd0,validation_a_last};
            state<=RANGE_EVAL;
          end
        end
        CHECK_BASE:begin
          validation_row_span<=({{(48-ROW_INDEX_BITS){1'b0}},validation_product_high}<<16)+
                                {{(48-ROW_INDEX_BITS){1'b0}},validation_product_low};
          validation_weight_base<={32'd0,w_addr}+{32'd0,validation_weight_last};
          state<=CHECK_END;
        end
        CHECK_END:begin
          weight_extent<=validation_weight_base+validation_row_span;
          state<=RANGE_EVAL;
        end
        RANGE_EVAL:begin
          validation_range_bad<=validation_gemv ?
            (!range_ok(w_addr,weight_extent,1'b0) || !range_ok(y_addr,y_extent,1'b1) ||
             (post_enable&&!range_ok(bias_addr,bias_extent,1'b0))) : !range_ok(a_addr,a_extent,1'b1);
          validation_slot_ok<=slot_valid[slot] && slot_cols[slot]==cols;
          state<=CHECK_RANGE;
        end
        CHECK_RANGE:begin
          if(validation_range_bad)fail_job(E_RANGE);
          else if(!validation_gemv)state<=LOAD_REQ;
          else if(!validation_slot_ok)fail_job(E_SLOT);
          else state<=WEIGHT_REQ;
        end
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

            if(col_index+4>=cols)begin state<=MAC_DRAIN;weight_next_valid<=0;end
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
        MAC_DRAIN:begin end
        DOT_PRODUCT:begin
          dot_product_q[0]<=dot_p0[15:0];dot_product_q[1]<=dot_p1[15:0];
          dot_product_q[2]<=dot_p2[15:0];dot_product_q[3]<=dot_p3[15:0];state<=DOT_SUM;
        end
        DOT_SUM:begin
          dot_pair0_q<=$signed(dot_product_q[0])+$signed(dot_product_q[1]);
          dot_pair1_q<=$signed(dot_product_q[2])+$signed(dot_product_q[3]);state<=DOT_DONE;
        end
        DOT_DONE:begin result<=registered_dot_sum;macs<=4;done<=1;state<=IDLE;end
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
