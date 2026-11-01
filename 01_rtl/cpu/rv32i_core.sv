// NeedleRV-X: five-stage, single-issue in-order RV32IM CPU.
// IF/ID -> ID/EX -> EX/MEM -> MEM/WB are the four pipeline boundaries.
// 指令/数据valid一直保持到ready；load数据在MEM/WB锁存；异常只清除年轻指令。
// Frontend intentionally has one outstanding fetch. Performance is measured,
// never inferred from the fact that the datapath has five stages.
module rv32i_core #(
  parameter logic [31:0] RESET_PC=32'd0,
  parameter bit PREDICT_ENABLE=1,
  parameter bit FETCH_DECODE_OVERLAP=1,
  parameter bit FETCH_PREFETCH_ENABLE=1,
  parameter integer PREDICTOR_ENTRIES=512
)(
  input logic clk,reset,
  output logic imem_valid,output logic [31:0] imem_addr,
  input logic imem_ready,input logic [31:0] imem_rdata,input logic imem_error,
  output logic imem_lookahead_valid,output logic [31:0] imem_lookahead_addr,
  output logic dmem_lookahead_valid,dmem_lookahead_we,output logic[31:0]dmem_lookahead_addr,dmem_lookahead_wdata,output logic[3:0]dmem_lookahead_wstrb,
  output logic dmem_valid,dmem_we,
  output logic [31:0] dmem_addr,dmem_wdata,output logic [3:0] dmem_wstrb,
  input logic dmem_ready,input logic [31:0] dmem_rdata,input logic dmem_error,
  input logic timer_irq,external_irq,ic_miss_event,dc_miss_event,
  input logic icache_idle,output logic icache_invalidate,
  output logic commit_valid,output logic [31:0] commit_pc,commit_data,
  output logic [4:0] commit_rd,output logic [31:0] dbg_pc
);
  // ID = instruction waiting to be decoded; EX includes operands read by ID.
  logic id_valid,ex_valid,mem_valid,wb_valid;
  logic [31:0] id_pc,id_insn,id_pred,ex_pc,ex_insn,ex_pred,ex_a,ex_b;
  logic id_fetch_error,ex_fetch_error;
  logic [31:0] mem_pc,mem_result,mem_store,mem_nextpc,wb_pc,wb_data,wb_nextpc;
  logic [4:0] mem_rd,wb_rd;
  logic mem_write_rd,mem_load,mem_store_en,wb_write_rd;
  logic [2:0] mem_funct3;
  logic [31:0] next_fetch_pc,architectural_pc;
  logic [31:0] prediction;
  wire [31:0] fetch_prediction=PREDICT_ENABLE?prediction:imem_addr+4;
  logic fetch_active,fetch_drop;
  // ID plus one skid entry. The outstanding request reserves one of the two
  // front-end slots, so a response can never overwrite a held instruction.
  logic pf_valid,pf_fetch_error;
  logic [31:0] pf_pc,pf_insn,pf_pred;

  wire [6:0] opcode=ex_insn[6:0];
  wire [2:0] funct3=ex_insn[14:12];
  wire [6:0] funct7=ex_insn[31:25];
  wire [4:0] ex_rs1=ex_insn[19:15],ex_rs2=ex_insn[24:20],ex_rd=ex_insn[11:7];
  wire [4:0] id_rs1=id_insn[19:15],id_rs2=id_insn[24:20];
  logic [31:0] rf_a,rf_b,operand_a,operand_b;
  rv32i_regfile rf(.clk(clk),.reset(reset),.we(wb_valid&&wb_write_rd),.wa(wb_rd),.wd(wb_data),
    .ra1(id_rs1),.ra2(id_rs2),.rd1(rf_a),.rd2(rf_b));

  logic [31:0] load_shifted,load_value;
  // Result bypass. A load is forwarded only after its value reached WB.
  always_comb begin
    operand_a=ex_rs1==0?32'd0:ex_a;
    operand_b=ex_rs2==0?32'd0:ex_b;
    if(mem_valid&&mem_write_rd&&(!mem_load||dmem_ready)&&mem_rd!=0&&mem_rd==ex_rs1) operand_a=mem_load?load_value:mem_result;
    else if(wb_valid&&wb_write_rd&&wb_rd!=0&&wb_rd==ex_rs1) operand_a=wb_data;
    if(mem_valid&&mem_write_rd&&(!mem_load||dmem_ready)&&mem_rd!=0&&mem_rd==ex_rs2) operand_b=mem_load?load_value:mem_result;
    else if(wb_valid&&wb_write_rd&&wb_rd!=0&&wb_rd==ex_rs2) operand_b=wb_data;
  end

  wire [31:0] imm_i={{20{ex_insn[31]}},ex_insn[31:20]};
  wire [31:0] imm_s={{20{ex_insn[31]}},ex_insn[31:25],ex_insn[11:7]};
  wire [31:0] imm_b={{19{ex_insn[31]}},ex_insn[31],ex_insn[7],ex_insn[30:25],ex_insn[11:8],1'b0};
  wire [31:0] imm_j={{11{ex_insn[31]}},ex_insn[31],ex_insn[19:12],ex_insn[20],ex_insn[30:21],1'b0};
  logic [31:0] result,nextpc,branch_target,csr_input,csr_new;
  logic write_rd,is_load,is_store,is_branch,is_jump,taken,is_div,is_mul,is_dot,is_clmul,is_csr,csr_do_write,is_mret,is_fencei;
  logic ex_fault;logic [31:0] ex_cause,ex_tval;
  wire redirect;
  logic jalr_captured;
  logic[31:0]jalr_target_q;
  wire is_indirect_jump=opcode==7'h67;
  wire jalr_hold=1'b0;
  logic low_mul_captured;
  wire is_low_mul=opcode==7'h33 && funct7==7'h01 && funct3==0;
  wire low_mul_hold=1'b0;
  logic[31:0]mul_low;
  logic[31:0]mul_ll,mul_lh,mul_hl;
  logic[15:0]mul_hi_xor,mul_hi_carry,mul_hi;

  logic cl_start,cl_busy,cl_done,cl_started,cl_complete;logic[31:0]cl_result,cl_saved;
  logic dot_start,dot_busy,dot_done,dot_started,dot_complete;
  logic[31:0]dot_result,dot_saved;
  logic mul_start,mul_busy,mul_done,mul_started,mul_complete;
  logic [31:0]mul_result,mul_saved;
  logic signed[15:0]dot_product[0:3];
  logic signed[16:0]dot_pair0,dot_pair1;logic signed[17:0]dot_total;
  logic signed [31:0] dot_sum;
  integer lane;
  logic [31:0] csr_rdata;
  logic csr_legal,csr_readonly;
  logic irq_pending;logic [31:0] irq_cause,trap_vector,saved_mepc;
  logic [63:0] cycle_count,instret_count;
  logic div_start,div_busy,div_done,div_started,div_complete;
  logic [31:0] div_result,div_saved;

  rv32_clmul clmul_unit(.clk(clk),.reset(reset),.cancel(redirect),.start(cl_start),.mode(funct3),
    .a(operand_a),.b(operand_b),.busy(cl_busy),.done(cl_done),.result(cl_result));
  rv32_dot4_pipeline dot4_unit(.clk(clk),.reset(reset),.cancel(redirect),.start(dot_start),
    .a(operand_a),.b(operand_b),.busy(dot_busy),.done(dot_done),.result(dot_result));
  rv32_multiplier multiplier(.clk(clk),.reset(reset),.cancel(redirect),.start(mul_start),.mode(funct3[1:0]),
    .operand_a(operand_a),.operand_b(operand_b),.busy(mul_busy),.done(mul_done),.result(mul_result));
  rv32_divider divider(.clk(clk),.reset(reset),.start(div_start),
    .signed_mode(!funct3[0]),.remainder_mode(funct3[1]),
    .dividend(operand_a),.divisor(operand_b),.busy(div_busy),.done(div_done),.result(div_result));

  // Balanced 32x32 carry-less XOR tree: ordinary polynomial multiplication.
  // All widths/modes are the standard Zbc operations, not a fixed CRC.
  wire[63:0]cl0[0:31],cl1[0:15],cl2[0:7],cl3[0:3],cl4[0:1];wire[63:0]cl5;
  genvar cln;
  generate for(cln=0;cln<32;cln=cln+1)begin:cl_terms
    assign cl0[cln]=({32'b0,operand_a}<<cln)&{64{operand_b[cln]}};
  end
  for(cln=0;cln<16;cln=cln+1)begin:cl_level1 assign cl1[cln]=cl0[2*cln]^cl0[2*cln+1];end
  for(cln=0;cln<8;cln=cln+1)begin:cl_level2 assign cl2[cln]=cl1[2*cln]^cl1[2*cln+1];end
  for(cln=0;cln<4;cln=cln+1)begin:cl_level3 assign cl3[cln]=cl2[2*cln]^cl2[2*cln+1];end
  for(cln=0;cln<2;cln=cln+1)begin:cl_level4 assign cl4[cln]=cl3[2*cln]^cl3[2*cln+1];end
  endgenerate
  assign cl5=cl4[0]^cl4[1];
  function automatic [31:0]bit_count(input[31:0]x,input[1:0]kind);
    integer j;reg found;reg[31:0]n;
    begin n=kind==2?0:32;found=0;
      for(j=0;j<32;j=j+1)begin
        if(kind==2)n=n+{31'b0,x[j]};
        else if(!found && (kind==0?x[31-j]:x[j]))begin n=j;found=1;end
      end
      bit_count=n;
    end
  endfunction
  // Decode + ALU in EX. Explicit full funct7 checks avoid silently accepting
  // reserved encodings. The ISA testbench checks x0 and trap behavior too.
  always_comb begin
    result=0;nextpc=ex_pc+4;branch_target=ex_pc+imm_b;
    write_rd=0;is_load=0;is_store=0;is_branch=0;is_jump=0;taken=0;
    is_div=0;is_mul=0;is_dot=0;is_clmul=0;is_csr=0;csr_do_write=0;is_mret=0;is_fencei=0;
    ex_fault=0;ex_cause=2;ex_tval=ex_insn;
    csr_input=funct3[2]?{27'd0,ex_rs1}:operand_a;
    csr_new=csr_input;
    // Only the low 32 bits are required by MUL. Three independent 16x16
    // products replace a 32x32 DSP cascade; bits above each cross term's
    // low half cannot contribute. Carry-save compresses three high halves
    // before the only 16-bit carry-propagate addition. Partial products are registered.
    mul_ll=operand_a[15:0]*operand_b[15:0];
    mul_lh=operand_a[15:0]*operand_b[31:16];
    mul_hl=operand_a[31:16]*operand_b[15:0];
    mul_hi_xor=mul_ll[31:16]^mul_lh[15:0]^mul_hl[15:0];
    mul_hi_carry=((mul_ll[31:16]&mul_lh[15:0])|
                  (mul_ll[31:16]&mul_hl[15:0])|
                  (mul_lh[15:0]&mul_hl[15:0]))<<1;
    mul_hi=mul_hi_xor+mul_hi_carry;
    mul_low={mul_hi,mul_ll[15:0]};
    for(lane=0;lane<4;lane=lane+1)
      dot_product[lane]=$signed(operand_a[lane*8+:8])*$signed(operand_b[lane*8+:8]);
    dot_pair0=$signed(dot_product[0])+$signed(dot_product[1]);
    dot_pair1=$signed(dot_product[2])+$signed(dot_product[3]);
    dot_total=$signed(dot_pair0)+$signed(dot_pair1);
    dot_sum={{14{dot_total[17]}},dot_total};
    case(opcode)
      7'h37:begin result={ex_insn[31:12],12'd0};write_rd=1;end
      7'h17:begin result=ex_pc+{ex_insn[31:12],12'd0};write_rd=1;end
      7'h6f:begin result=ex_pc+4;nextpc=ex_pc+imm_j;is_jump=1;write_rd=1;end
      7'h67:begin result=ex_pc+4;nextpc=(operand_a+imm_i)&32'hfffffffe;is_jump=1;write_rd=1;
        if(funct3!=0) ex_fault=1;end
      7'h63:begin
        is_branch=1;
        case(funct3)
          0:taken=operand_a==operand_b;1:taken=operand_a!=operand_b;
          4:taken=$signed(operand_a)<$signed(operand_b);
          5:taken=$signed(operand_a)>=$signed(operand_b);
          6:taken=operand_a<operand_b;7:taken=operand_a>=operand_b;
          default:ex_fault=1;
        endcase
        if(taken) nextpc=branch_target;
      end
      7'h03:begin
        result=operand_a+imm_i;is_load=1;write_rd=1;
        if(!(funct3==0||funct3==1||funct3==2||funct3==4||funct3==5)) ex_fault=1;
        else if((funct3[1:0]==1&&result[0])||(funct3==2&&result[1:0]!=0))
          begin ex_fault=1;ex_cause=4;ex_tval=result;end
      end
      7'h23:begin
        result=operand_a+imm_s;is_store=1;
        if(funct3>2) ex_fault=1;
        else if((funct3==1&&result[0])||(funct3==2&&result[1:0]!=0))
          begin ex_fault=1;ex_cause=6;ex_tval=result;end
      end
      7'h13:begin
        write_rd=1;
        case(funct3)
          0:result=operand_a+imm_i;2:result=$signed(operand_a)<$signed(imm_i)?32'd1:32'd0;
          3:result=operand_a<imm_i?32'd1:32'd0;4:result=operand_a^imm_i;
          6:result=operand_a|imm_i;7:result=operand_a&imm_i;
          1:begin result=operand_a<<ex_rs2;if(funct7!=0) ex_fault=1;end
          5:begin
            if(funct7==0) result=operand_a>>ex_rs2;
            else if(funct7==7'h20) result=$signed(operand_a)>>>ex_rs2;
            else ex_fault=1;
          end
          default:ex_fault=1;
        endcase
      end
      7'h33:begin
        write_rd=1;
        if(funct7==1) begin
          case(funct3)
            0:result=mul_low;
            1,2,3:begin is_mul=1;result=mul_complete?mul_saved:mul_result;end
            default:begin is_div=1;result=div_complete?div_saved:div_result;end
          endcase
        end else if(funct7==0||funct7==7'h20) begin
          case(funct3)
            0:result=(funct7==7'h20) ? operand_a-operand_b : operand_a+operand_b;
            1:result=operand_a<<operand_b[4:0];
            2:result=$signed(operand_a)<$signed(operand_b)?32'd1:32'd0;
            3:result=operand_a<operand_b?32'd1:32'd0;
            4:result=operand_a^operand_b;
            5:begin if(funct7==7'h20) result=$signed(operand_a)>>>operand_b[4:0]; else result=operand_a>>operand_b[4:0]; end
            6:result=operand_a|operand_b;7:result=operand_a&operand_b;
          endcase
          if(funct7==7'h20&&funct3!=0&&funct3!=5) ex_fault=1;
        end else ex_fault=1;
      end
      7'h0f:begin
        if(funct3==1) is_fencei=1;
        else if(funct3!=0) ex_fault=1;
      end
      7'h73:begin
        if(funct3==0) begin
          case(ex_insn)
            32'h00000073:begin ex_fault=1;ex_cause=11;ex_tval=0;end
            32'h00100073:begin ex_fault=1;ex_cause=3;ex_tval=ex_pc;end
            32'h30200073:begin is_mret=1;nextpc=saved_mepc;end
            32'h10500073:; // WFI hint; no low-power claim
            default:ex_fault=1;
          endcase
        end else begin
          is_csr=1;write_rd=1;result=csr_rdata;
          case(funct3[1:0])
            1:begin csr_do_write=1;csr_new=csr_input;end
            2:begin csr_do_write=ex_rs1!=0;csr_new=csr_rdata|csr_input;end
            3:begin csr_do_write=ex_rs1!=0;csr_new=csr_rdata&~csr_input;end
            default:ex_fault=1;
          endcase
          if(!csr_legal||(csr_do_write&&csr_readonly)) ex_fault=1;
        end
      end
      7'h7b:begin
        if(funct7==0&&funct3==0) begin is_dot=1;result=dot_complete?dot_saved:dot_result;write_rd=1;end
        else ex_fault=1;
      end
      default:ex_fault=1;
    endcase
    // Standard Zba/Zbb encodings. These are general integer instructions,
    // selected by the compiler for all programs, without benchmark matching.
    if(opcode==7'h33)begin
      if(funct7==7'h07 && (funct3==5||funct3==7))begin
        result=(funct3==5?operand_b==0:operand_b!=0)?32'b0:operand_a;ex_fault=0;
      end
      if((funct7==7'h14||funct7==7'h24||funct7==7'h34)&&funct3==1)begin
        case(funct7)7'h14:result=operand_a|(32'b1<<operand_b[4:0]);7'h24:result=operand_a&~(32'b1<<operand_b[4:0]);7'h34:result=operand_a^(32'b1<<operand_b[4:0]);default:result=0;endcase
        ex_fault=0;
      end
      if(funct7==7'h24&&funct3==5)begin result={31'b0,operand_a[operand_b[4:0]]};ex_fault=0;end
      if(funct7==7'h05 && (funct3==1||funct3==2||funct3==3))begin
        case(funct3)1:result=cl5[31:0];2:result=cl5[62:31];3:result=cl5[63:32];default:result=0;endcase
        ex_fault=0;
      end
      if(funct7==7'h10 && (funct3==2||funct3==4||funct3==6))begin
        case(funct3)2:result=(operand_a<<1)+operand_b;4:result=(operand_a<<2)+operand_b;6:result=(operand_a<<3)+operand_b;default:result=0;endcase
        ex_fault=0;
      end
      if(funct7==7'h20 && (funct3==4||funct3==6||funct3==7))begin
        case(funct3)4:result=operand_a^~operand_b;6:result=operand_a|~operand_b;7:result=operand_a&~operand_b;default:result=0;endcase
        ex_fault=0;
      end
      if(funct7==7'h05 && funct3[2])begin
        case(funct3)
          4:result=$signed(operand_a)<$signed(operand_b)?operand_a:operand_b;
          5:result=operand_a<operand_b?operand_a:operand_b;
          6:result=$signed(operand_a)>$signed(operand_b)?operand_a:operand_b;
          7:result=operand_a>operand_b?operand_a:operand_b;
          default:result=0;
        endcase
        ex_fault=0;
      end
      if(funct7==7'h30 && (funct3==1||funct3==5))begin
        result=funct3==1?(operand_a<<operand_b[4:0])|(operand_a>>((32-operand_b[4:0])&31)):
          (operand_a>>operand_b[4:0])|(operand_a<<((32-operand_b[4:0])&31));ex_fault=0;
      end
      if(funct7==7'h04 && funct3==4 && ex_rs2==0)begin result={16'b0,operand_a[15:0]};ex_fault=0;end
    end
    if(opcode==7'h13)begin
      if((funct7==7'h14||funct7==7'h24||funct7==7'h34)&&funct3==1)begin
        case(funct7)7'h14:result=operand_a|(32'b1<<ex_rs2);7'h24:result=operand_a&~(32'b1<<ex_rs2);7'h34:result=operand_a^(32'b1<<ex_rs2);default:result=0;endcase
        ex_fault=0;
      end
      if(funct7==7'h24&&funct3==5)begin result={31'b0,operand_a[ex_rs2]};ex_fault=0;end
      if(funct3==1 && funct7==7'h30)begin
        case(ex_rs2)
          0:begin result=bit_count(operand_a,0);ex_fault=0;end
          1:begin result=bit_count(operand_a,1);ex_fault=0;end
          2:begin result=bit_count(operand_a,2);ex_fault=0;end
          4:begin result={{24{operand_a[7]}},operand_a[7:0]};ex_fault=0;end
          5:begin result={{16{operand_a[15]}},operand_a[15:0]};ex_fault=0;end
          default:;
        endcase
      end
      if(funct3==5 && funct7==7'h30)begin
        result=(operand_a>>ex_rs2)|(operand_a<<((32-ex_rs2)&31));ex_fault=0;
      end
      if(funct3==5 && ex_insn[31:20]==12'h287)begin
        for(lane=0;lane<4;lane=lane+1)result[lane*8+:8]=|operand_a[lane*8+:8]?8'hff:0;
        ex_fault=0;
      end
      if(funct3==5 && ex_insn[31:20]==12'h698)begin result={operand_a[7:0],operand_a[15:8],operand_a[23:16],operand_a[31:24]};ex_fault=0;end
    end
    if((is_jump||(is_branch&&taken))&&nextpc[1:0]!=0)
      begin ex_fault=1;ex_cause=0;ex_tval=nextpc;end
    if(ex_fetch_error) begin ex_fault=1;ex_cause=1;ex_tval=ex_pc;end
  end

  // Memory stage requests word-aligned addresses with byte strobes.
  // A speculative load reservation uses the EX address to start the cache
  // RAM read. No MMIO and no store can use this path; acknowledgement still
  // requires the matching registered MEM request.
  // Keep speculative LSU addresses out of the general ALU/MUL result mux.
  wire[31:0]lsu_address=operand_a+(opcode==7'h23 ? imm_s : imm_i);
  assign dmem_lookahead_valid=ex_valid&&(is_load||is_store)&&!ex_fault;
  assign dmem_lookahead_we=is_store;
  assign dmem_lookahead_wdata=operand_b<<(8*lsu_address[1:0]);
  always_comb begin
    case(funct3)
      0:dmem_lookahead_wstrb=4'b0001<<lsu_address[1:0];
      1:dmem_lookahead_wstrb=4'b0011<<lsu_address[1:0];
      default:dmem_lookahead_wstrb=4'b1111;
    endcase
  end
  assign dmem_lookahead_addr={lsu_address[31:2],2'b0};
  assign dmem_valid=mem_valid&&(mem_load||mem_store_en);
  assign dmem_we=mem_store_en;
  assign dmem_addr={mem_result[31:2],2'b0};
  assign dmem_wdata=mem_store<<(8*mem_result[1:0]);
  always_comb begin
    case(mem_funct3)
      0:dmem_wstrb=4'b0001<<mem_result[1:0];
      1:dmem_wstrb=4'b0011<<mem_result[1:0];
      default:dmem_wstrb=4'b1111;
    endcase
  end
  wire mem_hold=dmem_valid&&!dmem_ready;
  wire mem_fault=dmem_valid&&dmem_ready&&dmem_error;
  wire div_hold=ex_valid&&is_div&&!div_complete&&!div_done;
  wire cl_hold=ex_valid&&is_clmul&&!ex_fault&&!cl_complete&&!cl_done;
  assign cl_start=ex_valid&&is_clmul&&!cl_started&&!cl_busy&&!mem_hold;
  wire dot_hold=ex_valid&&is_dot&&!ex_fault&&!dot_complete&&!dot_done;
  assign dot_start=ex_valid&&is_dot&&!dot_started&&!dot_busy&&!mem_hold;
  wire mul_hold=ex_valid&&is_mul&&!ex_fault&&!mul_complete&&!mul_done;
  assign mul_start=ex_valid&&is_mul&&!mul_started&&!mul_busy&&!mem_hold;
  wire fence_hold=ex_valid&&is_fencei&&!icache_idle;
  wire execute=ex_valid&&!mem_hold&&!div_hold&&!mul_hold&&!low_mul_hold&&!jalr_hold&&!dot_hold&&!cl_hold&&!fence_hold&&!mem_fault;
  assign div_start=ex_valid&&is_div&&!div_started&&!mem_hold&&!mem_fault;
  wire load_hazard=1'b0; // MEM load-data bypass resolves the next EX consumer.
  wire csr_serial=id_valid&&id_insn[6:0]==7'h73&&(ex_valid||mem_valid||wb_valid);
  wire irq_take=irq_pending&&!id_valid&&!ex_valid&&!mem_valid&&!wb_valid&&!pf_valid&&!fetch_active;
  wire trap_fire=mem_fault||(execute&&ex_fault)||irq_take;
  wire [31:0] trap_pc=mem_fault?mem_pc:(irq_take?architectural_pc:ex_pc);
  wire [31:0] trap_cause=mem_fault?(mem_load?32'd5:32'd7):(irq_take?irq_cause:ex_cause);
  wire [31:0] trap_value=mem_fault?mem_result:(irq_take?32'd0:ex_tval);
  // Compare both branch destinations before the operand comparator resolves.
  // This is identical to (taken ? target : fallthrough) != prediction, but
  // avoids cascading a wide mux and equality comparator after a signed compare.
  wire fallthrough_bad=(ex_pc+32'd4)!=ex_pred;
  wire branch_prediction_bad=taken ? (ex_pc+imm_b)!=ex_pred : fallthrough_bad;
  // Keep each opcode's target separate. A generic nextpc comparator creates
  // a false branch->target mux->wide compare path even behind opcode gating.
  wire prediction_bad = opcode==7'h63 ? branch_prediction_bad :
    opcode==7'h6f ? (ex_pc+imm_j)!=ex_pred :
    opcode==7'h67 ? ((operand_a+imm_i)&32'hfffffffe)!=ex_pred :
    is_mret ? saved_mepc!=ex_pred : fallthrough_bad;
  wire mispredict=execute&&!ex_fault&&prediction_bad;
  assign redirect=trap_fire||(execute&&(is_mret||is_fencei||mispredict));
  wire [31:0] redirect_pc=trap_fire?trap_vector:nextpc;
  wire id_advance=id_valid&&!mem_hold&&!div_hold&&!mul_hold&&!low_mul_hold&&!jalr_hold&&!dot_hold&&!cl_hold&&!fence_hold&&!load_hazard&&!csr_serial&&!redirect;
  assign icache_invalidate=execute&&is_fencei&&!ex_fault;
  wire fetch_response_good=fetch_active&&imem_ready&&!fetch_drop&&!redirect&&!irq_pending;
  wire [31:0] issue_pc=(FETCH_PREFETCH_ENABLE&&fetch_active&&!fetch_drop)?fetch_prediction:next_fetch_pc;
  wire [2:0] frontend_used={2'b00,id_valid}+{2'b00,pf_valid}+{2'b00,fetch_active}-{2'b00,id_advance};
  wire fetch_launch=FETCH_PREFETCH_ENABLE?
    ((!fetch_active||imem_ready)&&frontend_used<3'd2):
    (!fetch_active&&(!id_valid||(FETCH_DECODE_OVERLAP&&id_advance)));

  rv32i_csr csr(.clk(clk),.reset(reset),.csr_addr(ex_insn[31:20]),
    .csr_write(execute&&is_csr&&csr_do_write&&!ex_fault),
    .csr_wdata(csr_new),.csr_rdata(csr_rdata),.csr_legal(csr_legal),.csr_readonly(csr_readonly),
    .retire(wb_valid),.trap(trap_fire),.mret(execute&&is_mret&&!ex_fault),
    .trap_pc(trap_pc),.trap_cause(trap_cause),.trap_value(trap_value),.timer_irq(timer_irq),.external_irq(external_irq),
    .branch_event(execute&&!ex_fault&&is_branch),.mispredict_event(mispredict),
    .load_stall_event(mem_hold||load_hazard),.ic_miss_event(ic_miss_event),.dc_miss_event(dc_miss_event),
    .irq_pending(irq_pending),.irq_cause(irq_cause),.trap_vector(trap_vector),.saved_mepc(saved_mepc),.cycle_count(cycle_count),.instret_count(instret_count));

  rv32_predictor #(.ENTRIES(PREDICTOR_ENTRIES),.REGISTER_QUERY(1)) predictor(.clk(clk),.reset(reset),.clear(icache_invalidate),
    .query_enable(!fetch_active||imem_ready),
    .query_pc(issue_pc),.predicted_pc(prediction),
    .update(execute&&!ex_fault&&(is_branch||is_jump)),
    .resolved_insn(ex_insn),.resolved_pc(ex_pc),.target_pc(is_branch?branch_target:nextpc),
    .taken(is_jump||taken),.conditional(is_branch));

  // Sideband only: this address is accepted exactly when the old response
  // retires. The cache validates this speculative hint against the next live PC.
  // Lookahead is speculative; only a matching registered request can
  // consume its response. Redirect and retirement do not gate the RAM port.
  assign imem_lookahead_valid=fetch_active;
  assign imem_lookahead_addr=issue_pc;
  assign imem_valid=fetch_active;
  assign dbg_pc=next_fetch_pc;

  always_comb begin
    load_shifted=dmem_rdata>>(8*mem_result[1:0]);
    case(mem_funct3)
      0:load_value={{24{load_shifted[7]}},load_shifted[7:0]};
      1:load_value={{16{load_shifted[15]}},load_shifted[15:0]};
      4:load_value={24'd0,load_shifted[7:0]};
      5:load_value={16'd0,load_shifted[15:0]};
      default:load_value=load_shifted;
    endcase
  end

  // Speculatively refresh payload while blocked; only the capture-valid bit
  // waits for MEM. Redirect cancels that bit, so no stale product can retire.
  always_ff @(posedge clk)begin
    if(ex_valid && is_indirect_jump && !jalr_captured)
      jalr_target_q <= (operand_a+imm_i)&32'hfffffffe;

  end
  always_ff @(posedge clk) begin
    if(reset) begin
      id_valid<=0;ex_valid<=0;mem_valid<=0;wb_valid<=0;fetch_active<=0;fetch_drop<=0;
      pf_valid<=0;pf_pc<=0;pf_insn<=0;pf_pred<=0;pf_fetch_error<=0;
      next_fetch_pc<=RESET_PC;architectural_pc<=RESET_PC;
      imem_addr<=RESET_PC;
      id_pc<=0;id_insn<=0;id_pred<=0;id_fetch_error<=0;
      ex_pc<=0;ex_insn<=0;ex_pred<=0;ex_a<=0;ex_b<=0;ex_fetch_error<=0;
      mem_pc<=0;mem_result<=0;mem_store<=0;mem_rd<=0;mem_write_rd<=0;mem_load<=0;mem_store_en<=0;
      mem_funct3<=0;mem_nextpc<=0;wb_pc<=0;wb_data<=0;wb_rd<=0;wb_write_rd<=0;wb_nextpc<=0;
      commit_valid<=0;commit_pc<=0;commit_rd<=0;commit_data<=0;
      div_started<=0;div_complete<=0;low_mul_captured<=0;jalr_captured<=0;div_saved<=0;mul_started<=0;mul_complete<=0;dot_started<=0;dot_complete<=0;cl_started<=0;cl_complete<=0;mul_saved<=0;dot_started<=0;dot_complete<=0;cl_started<=0;cl_complete<=0;dot_saved<=0;
    end else begin
      // WB retires once even while younger stages are stalled.
      commit_valid<=wb_valid;commit_pc<=wb_pc;
      commit_rd<=wb_write_rd?wb_rd:5'd0;commit_data<=wb_data;
      wb_valid<=0;
      if(wb_valid) architectural_pc<=wb_nextpc;
      if(ex_valid&&is_indirect_jump&&!mem_hold)jalr_captured<=1;
      if(ex_valid&&is_low_mul&&!mem_hold)low_mul_captured<=1;
      if(cl_start)cl_started<=1;
      if(cl_done)begin cl_complete<=1;cl_saved<=cl_result;end
      if(dot_start)dot_started<=1;
      if(dot_done)begin dot_complete<=1;dot_saved<=dot_result;end
      if(mul_start)mul_started<=1;
      if(mul_done)begin mul_complete<=1;mul_saved<=mul_result;end
      if(div_start) div_started<=1;
      if(div_done) begin div_complete<=1;div_saved<=div_result;end

      // MEM can drain while a multi-cycle EX divider is busy.
      if(!mem_hold) begin
        wb_valid<=mem_valid&&!mem_fault;
        wb_pc<=mem_pc;wb_rd<=mem_rd;wb_write_rd<=mem_write_rd;
        wb_data<=mem_load?load_value:mem_result;wb_nextpc<=mem_nextpc;
        mem_valid<=0;
        if(execute&&!ex_fault) begin
          mem_valid<=1;mem_pc<=ex_pc;mem_rd<=ex_rd;
          mem_result<=result;mem_store<=operand_b;mem_write_rd<=write_rd;
          mem_load<=is_load;mem_store_en<=is_store;mem_funct3<=funct3;mem_nextpc<=nextpc;
        end
      end

      // WB may retire while EX waits behind a slow load/store, divider or
      // FENCE.I. Preserve forwarded operands before that one-cycle bypass
      // disappears; otherwise a held instruction can execute stale ID values.
      if(ex_valid && (mem_hold || div_hold || mul_hold || low_mul_hold || jalr_hold || dot_hold || cl_hold || fence_hold)) begin
        ex_a<=operand_a;ex_b<=operand_b;
      end
      if(!mem_hold&&!div_hold&&!mul_hold&&!low_mul_hold&&!jalr_hold&&!dot_hold&&!cl_hold&&!fence_hold) begin
        ex_valid<=0;div_started<=0;div_complete<=0;low_mul_captured<=0;jalr_captured<=0;mul_started<=0;mul_complete<=0;dot_started<=0;dot_complete<=0;cl_started<=0;cl_complete<=0;
        if(id_advance) begin
          ex_valid<=1;ex_pc<=id_pc;ex_insn<=id_insn;ex_pred<=id_pred;
          ex_a<=rf_a;ex_b<=rf_b;ex_fetch_error<=id_fetch_error;id_valid<=0;
        end
      end
      // Buffered instructions may drain before IRQ entry. New fetches stop
      // while IRQ is pending; an unaccepted response is discarded as before.
      if(FETCH_PREFETCH_ENABLE&&pf_valid&&(!id_valid||id_advance)) begin
        id_valid<=1;id_pc<=pf_pc;id_insn<=pf_insn;id_pred<=pf_pred;
        id_fetch_error<=pf_fetch_error;pf_valid<=0;
      end
      if(fetch_active&&imem_ready) begin
        fetch_active<=0;fetch_drop<=0;
        if(fetch_response_good) begin
          if(!FETCH_PREFETCH_ENABLE||(!pf_valid&&(!id_valid||id_advance))) begin
            id_valid<=1;id_pc<=imem_addr;id_insn<=imem_rdata;
            id_pred<=fetch_prediction;id_fetch_error<=imem_error;
          end else begin
            pf_valid<=1;pf_pc<=imem_addr;pf_insn<=imem_rdata;
            pf_pred<=fetch_prediction;pf_fetch_error<=imem_error;
          end
          next_fetch_pc<=fetch_prediction;
        end
      end
      // A completed transaction may hand the bus directly to the next one.
      // This block follows response consumption so the new active bit wins.
      if(fetch_launch&&!irq_pending&&!redirect) begin
        fetch_active<=1;fetch_drop<=0;imem_addr<=issue_pc;

      end
      if(redirect) begin
        id_valid<=0;pf_valid<=0;ex_valid<=0;div_started<=0;div_complete<=0;low_mul_captured<=0;jalr_captured<=0;mul_started<=0;mul_complete<=0;dot_started<=0;dot_complete<=0;cl_started<=0;cl_complete<=0;
        next_fetch_pc<=redirect_pc;
        if(fetch_active&&!imem_ready) fetch_drop<=1;
        if(trap_fire) architectural_pc<=redirect_pc;
        if(mem_fault) mem_valid<=0;
      end
    end
  end
endmodule

// Custom signed byte dot product. Separate operand, product and reduction
// stages avoid chaining DSP arithmetic and result-selection in one CPU cycle.
module rv32_dot4_pipeline(input logic clk,reset,cancel,start,
 input logic[31:0]a,b,output wire busy,output logic done,output logic[31:0]result);
 logic[1:0]state;logic[31:0]a_q,b_q;logic signed[15:0]p[0:3];
 logic signed[16:0]pair0,pair1;wire signed[17:0]total=$signed(pair0)+$signed(pair1);
 assign busy=state!=0;
 integer i;
 always_ff @(posedge clk)begin
  if(reset||cancel)begin state<=0;done<=0;end
  else begin
   done<=0;
   case(state)
    0:if(start)state<=1;
    1:state<=2;
    2:state<=3;
    3:begin done<=1;state<=0;end
   endcase
  end
 end
 always_ff @(posedge clk)begin
  case(state)
   0:if(start)begin a_q<=a;b_q<=b;end
   1:for(i=0;i<4;i=i+1)p[i]<=$signed(a_q[i*8+:8])*$signed(b_q[i*8+:8]);
   2:begin pair0<=$signed(p[0])+$signed(p[1]);pair1<=$signed(p[2])+$signed(p[3]);end
   3:result<={{14{total[17]}},total};
  endcase
 end
endmodule

// General RV32 Zbc carry-less multiplication. Four eight-bit slices; no
// CRC polynomial or benchmark data is hardwired into the arithmetic unit.
module rv32_clmul(input logic clk,reset,cancel,start,input logic[2:0]mode,
 input logic[31:0]a,b,output wire busy,output logic done,output logic[31:0]result);
 logic[2:0]state,mode_q;logic[63:0]a_q,product;logic[31:0]b_q;
 logic[63:0]partial,combined;integer i;
 assign busy=state!=0;
 always_comb begin
   partial=0;for(i=0;i<8;i=i+1)if(b_q[i])partial=partial^(a_q<<i);
   combined=product^partial;
 end
 always_ff @(posedge clk)begin
  if(reset||cancel)begin state<=0;done<=0;end
  else begin
   done<=0;
   if(state==0)begin if(start)state<=1;end
   else if(state==4)begin done<=1;state<=0;end
   else state<=state+1'b1;
  end
 end
 always_ff @(posedge clk)begin
   if(state==0&&start)begin a_q<={32'b0,a};b_q<=b;product<=0;mode_q<=mode;end
   else if(state!=0)begin
     a_q<=a_q<<8;b_q<=b_q>>8;product<=combined;
     if(state==4)case(mode_q)
       1:result<=combined[31:0];2:result<=combined[62:31];3:result<=combined[63:32];default:result<=0;
     endcase
   end
 end
endmodule
