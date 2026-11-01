// NeedleRV-X: five-stage, single-issue in-order RV32IM CPU.
// IF/ID -> ID/EX -> EX/MEM -> MEM/WB are the four pipeline boundaries.
// 指令/数据valid一直保持到ready；load数据在MEM/WB锁存；异常只清除年轻指令。
// Frontend intentionally has one outstanding fetch. Performance is measured,
// never inferred from the fact that the datapath has five stages.
module rv32i_core #(
  parameter logic [31:0] RESET_PC=32'd0,
  parameter bit PREDICT_ENABLE=1,
  parameter bit FETCH_DECODE_OVERLAP=1,
  parameter bit FETCH_PREFETCH_ENABLE=1
)(
  input logic clk,reset,
  output logic imem_valid,output logic [31:0] imem_addr,
  input logic imem_ready,input logic [31:0] imem_rdata,input logic imem_error,
  output logic imem_lookahead_valid,output logic [31:0] imem_lookahead_addr,
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
  logic [31:0] next_fetch_pc,fetch_prediction,architectural_pc;
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

  // Result bypass. A load is forwarded only after its value reached WB.
  always_comb begin
    operand_a=ex_rs1==0?32'd0:ex_a;
    operand_b=ex_rs2==0?32'd0:ex_b;
    if(mem_valid&&mem_write_rd&&!mem_load&&mem_rd!=0&&mem_rd==ex_rs1) operand_a=mem_result;
    else if(wb_valid&&wb_write_rd&&wb_rd!=0&&wb_rd==ex_rs1) operand_a=wb_data;
    if(mem_valid&&mem_write_rd&&!mem_load&&mem_rd!=0&&mem_rd==ex_rs2) operand_b=mem_result;
    else if(wb_valid&&wb_write_rd&&wb_rd!=0&&wb_rd==ex_rs2) operand_b=wb_data;
  end

  wire [31:0] imm_i={{20{ex_insn[31]}},ex_insn[31:20]};
  wire [31:0] imm_s={{20{ex_insn[31]}},ex_insn[31:25],ex_insn[11:7]};
  wire [31:0] imm_b={{19{ex_insn[31]}},ex_insn[31],ex_insn[7],ex_insn[30:25],ex_insn[11:8],1'b0};
  wire [31:0] imm_j={{11{ex_insn[31]}},ex_insn[31],ex_insn[19:12],ex_insn[20],ex_insn[30:21],1'b0};
  logic [31:0] result,nextpc,branch_target,csr_input,csr_new;
  logic write_rd,is_load,is_store,is_branch,is_jump,taken,is_div,is_csr,csr_do_write,is_mret,is_fencei;
  logic ex_fault;logic [31:0] ex_cause,ex_tval;
  logic [63:0] prod_uu;
  logic signed [65:0] prod_ss,prod_su;
  logic signed [31:0] dot_sum;
  integer lane;
  logic [31:0] csr_rdata;
  logic csr_legal,csr_readonly;
  logic irq_pending;logic [31:0] irq_cause,trap_vector,saved_mepc;
  logic [63:0] cycle_count,instret_count;
  logic div_start,div_busy,div_done,div_started,div_complete;
  logic [31:0] div_result,div_saved;

  rv32_divider divider(.clk(clk),.reset(reset),.start(div_start),
    .signed_mode(!funct3[0]),.remainder_mode(funct3[1]),
    .dividend(operand_a),.divisor(operand_b),.busy(div_busy),.done(div_done),.result(div_result));

  // Decode + ALU in EX. Explicit full funct7 checks avoid silently accepting
  // reserved encodings. The ISA testbench checks x0 and trap behavior too.
  always_comb begin
    result=0;nextpc=ex_pc+4;branch_target=ex_pc+imm_b;
    write_rd=0;is_load=0;is_store=0;is_branch=0;is_jump=0;taken=0;
    is_div=0;is_csr=0;csr_do_write=0;is_mret=0;is_fencei=0;
    ex_fault=0;ex_cause=2;ex_tval=ex_insn;
    csr_input=funct3[2]?{27'd0,ex_rs1}:operand_a;
    csr_new=csr_input;
    prod_uu=operand_a*operand_b;
    prod_ss=$signed({operand_a[31],operand_a})*$signed({operand_b[31],operand_b});
    prod_su=$signed({operand_a[31],operand_a})*$signed({1'b0,operand_b});
    dot_sum=0;
    for(lane=0;lane<4;lane=lane+1)
      dot_sum=dot_sum+($signed(operand_a[lane*8+:8])*$signed(operand_b[lane*8+:8]));
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
            0:result=prod_uu[31:0];1:result=prod_ss[63:32];2:result=prod_su[63:32];3:result=prod_uu[63:32];
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
        if(funct7==0&&funct3==0) begin result=dot_sum;write_rd=1;end
        else ex_fault=1;
      end
      default:ex_fault=1;
    endcase
    if((is_jump||(is_branch&&taken))&&nextpc[1:0]!=0)
      begin ex_fault=1;ex_cause=0;ex_tval=nextpc;end
    if(ex_fetch_error) begin ex_fault=1;ex_cause=1;ex_tval=ex_pc;end
  end

  // Memory stage requests word-aligned addresses with byte strobes.
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
  wire fence_hold=ex_valid&&is_fencei&&!icache_idle;
  wire execute=ex_valid&&!mem_hold&&!div_hold&&!fence_hold&&!mem_fault;
  assign div_start=ex_valid&&is_div&&!div_started&&!mem_hold&&!mem_fault;
  wire load_hazard=ex_valid&&is_load&&ex_rd!=0&&(ex_rd==id_rs1||ex_rd==id_rs2);
  wire csr_serial=id_valid&&id_insn[6:0]==7'h73&&(ex_valid||mem_valid||wb_valid);
  wire irq_take=irq_pending&&!id_valid&&!ex_valid&&!mem_valid&&!wb_valid&&!pf_valid&&!fetch_active;
  wire trap_fire=mem_fault||(execute&&ex_fault)||irq_take;
  wire [31:0] trap_pc=mem_fault?mem_pc:(irq_take?architectural_pc:ex_pc);
  wire [31:0] trap_cause=mem_fault?(mem_load?32'd5:32'd7):(irq_take?irq_cause:ex_cause);
  wire [31:0] trap_value=mem_fault?mem_result:(irq_take?32'd0:ex_tval);
  wire mispredict=execute&&!ex_fault&&nextpc!=ex_pred;
  wire redirect=trap_fire||(execute&&(is_mret||is_fencei||mispredict));
  wire [31:0] redirect_pc=trap_fire?trap_vector:nextpc;
  wire id_advance=id_valid&&!mem_hold&&!div_hold&&!fence_hold&&!load_hazard&&!csr_serial&&!redirect;
  assign icache_invalidate=execute&&is_fencei&&!ex_fault;
  wire fetch_response_good=fetch_active&&imem_ready&&!fetch_drop&&!redirect&&!irq_pending;
  wire [31:0] issue_pc=(FETCH_PREFETCH_ENABLE&&fetch_response_good)?fetch_prediction:next_fetch_pc;
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

  logic [31:0] prediction;
  rv32_predictor predictor(.clk(clk),.reset(reset),.clear(icache_invalidate),
    .query_pc(issue_pc),.predicted_pc(prediction),
    .update(execute&&!ex_fault&&(is_branch||is_jump)),
    .resolved_pc(ex_pc),.target_pc(is_branch?branch_target:nextpc),
    .taken(is_jump||taken),.conditional(is_branch));

  // Sideband only: this address is accepted exactly when the old response
  // retires and the CPU reserves the next request. It never replaces a held bus.
  assign imem_lookahead_valid=fetch_active&&imem_ready&&fetch_launch&&!irq_pending&&!redirect;
  assign imem_lookahead_addr=issue_pc;
  assign imem_valid=fetch_active;
  assign dbg_pc=next_fetch_pc;
  logic [31:0] load_shifted,load_value;
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

  always_ff @(posedge clk) begin
    if(reset) begin
      id_valid<=0;ex_valid<=0;mem_valid<=0;wb_valid<=0;fetch_active<=0;fetch_drop<=0;
      pf_valid<=0;pf_pc<=0;pf_insn<=0;pf_pred<=0;pf_fetch_error<=0;
      next_fetch_pc<=RESET_PC;architectural_pc<=RESET_PC;
      imem_addr<=RESET_PC;fetch_prediction<=RESET_PC+4;
      id_pc<=0;id_insn<=0;id_pred<=0;id_fetch_error<=0;
      ex_pc<=0;ex_insn<=0;ex_pred<=0;ex_a<=0;ex_b<=0;ex_fetch_error<=0;
      mem_pc<=0;mem_result<=0;mem_store<=0;mem_rd<=0;mem_write_rd<=0;mem_load<=0;mem_store_en<=0;
      mem_funct3<=0;mem_nextpc<=0;wb_pc<=0;wb_data<=0;wb_rd<=0;wb_write_rd<=0;wb_nextpc<=0;
      commit_valid<=0;commit_pc<=0;commit_rd<=0;commit_data<=0;
      div_started<=0;div_complete<=0;div_saved<=0;
    end else begin
      // WB retires once even while younger stages are stalled.
      commit_valid<=wb_valid;commit_pc<=wb_pc;
      commit_rd<=wb_write_rd?wb_rd:5'd0;commit_data<=wb_data;
      wb_valid<=0;
      if(wb_valid) architectural_pc<=wb_nextpc;
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
      if(ex_valid && (mem_hold || div_hold || fence_hold)) begin
        ex_a<=operand_a;ex_b<=operand_b;
      end
      if(!mem_hold&&!div_hold&&!fence_hold) begin
        ex_valid<=0;div_started<=0;div_complete<=0;
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
        fetch_prediction<=PREDICT_ENABLE?prediction:issue_pc+4;
      end
      if(redirect) begin
        id_valid<=0;pf_valid<=0;ex_valid<=0;div_started<=0;div_complete<=0;
        next_fetch_pc<=redirect_pc;
        if(fetch_active&&!imem_ready) fetch_drop<=1;
        if(trap_fire) architectural_pc<=redirect_pc;
        if(mem_fault) mem_valid<=0;
      end
    end
  end
endmodule
