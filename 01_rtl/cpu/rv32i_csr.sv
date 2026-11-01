// M-mode bare-metal CSR subset, not a complete privileged ISA implementation.
// CSR地址合法性、只读保护、MIE屏蔽、中断优先级和64位性能计数器。
module rv32i_csr(
  input logic clk,reset,
  input logic [11:0] csr_addr,
  input logic csr_write,
  input logic [31:0] csr_wdata,
  output logic [31:0] csr_rdata,
  output logic csr_legal,csr_readonly,
  input logic retire,trap,mret,
  input logic [31:0] trap_pc,trap_cause,trap_value,
  input logic timer_irq,external_irq,
  input logic branch_event,mispredict_event,load_stall_event,
  input logic ic_miss_event,dc_miss_event,
  output logic irq_pending,
  output logic [31:0] irq_cause,trap_vector,saved_mepc,
  output logic [63:0] cycle_count,instret_count
);
  logic [31:0] mstatus,mie,mscratch,mepc,mcause,mtval,mtvec;
  logic [31:0] branches,mispredicts,stalls,ic_misses,dc_misses;
  wire [31:0] pending_bits={20'd0,external_irq,3'd0,timer_irq,7'd0};
  assign trap_vector=mtvec;assign saved_mepc=mepc;
  assign irq_pending=mstatus[3] && |(mie&pending_bits);
  assign irq_cause=(mie[11]&&external_irq)?32'h8000000b:32'h80000007;
  assign csr_readonly=(csr_addr[11:10]==2'b11);
  always_comb begin
    csr_legal=1;csr_rdata=0;
    case(csr_addr)
      12'h300:csr_rdata=mstatus;
      12'h301:csr_rdata=32'h40001100; // RV32 I + M
      12'h304:csr_rdata=mie;
      12'h305:csr_rdata=mtvec;
      12'h340:csr_rdata=mscratch;
      12'h341:csr_rdata=mepc;
      12'h342:csr_rdata=mcause;
      12'h343:csr_rdata=mtval;
      12'h344:csr_rdata=pending_bits;
      12'hB00,12'hC00:csr_rdata=cycle_count[31:0];
      12'hB80,12'hC80:csr_rdata=cycle_count[63:32];
      12'hB02,12'hC02:csr_rdata=instret_count[31:0];
      12'hB82,12'hC82:csr_rdata=instret_count[63:32];
      12'hB03:csr_rdata=branches;
      12'hB04:csr_rdata=mispredicts;
      12'hB05:csr_rdata=stalls;
      12'hB06:csr_rdata=ic_misses;
      12'hB07:csr_rdata=dc_misses;
      12'hF11,12'hF12,12'hF13,12'hF14:csr_rdata=0;
      default:csr_legal=0;
    endcase
  end
  always_ff @(posedge clk) begin
    if(reset) begin
      mstatus<=32'h1800;mie<=0;mscratch<=0;mepc<=0;mcause<=0;mtval<=0;mtvec<=0;
      cycle_count<=0;instret_count<=0;branches<=0;mispredicts<=0;stalls<=0;ic_misses<=0;dc_misses<=0;
    end else begin
      cycle_count<=cycle_count+64'd1;
      if(retire) instret_count<=instret_count+64'd1;
      if(branch_event) branches<=branches+1;
      if(mispredict_event) mispredicts<=mispredicts+1;
      if(load_stall_event) stalls<=stalls+1;
      if(ic_miss_event) ic_misses<=ic_misses+1;
      if(dc_miss_event) dc_misses<=dc_misses+1;
      if(csr_write) case(csr_addr)
        12'h300:mstatus<=32'h1800|(csr_wdata&32'h88); // MPP=M, MIE/MPIE writable
        12'h304:mie<=csr_wdata&32'h880;
        12'h305:mtvec<=csr_wdata&32'hfffffffc; // direct mode only
        12'h340:mscratch<=csr_wdata;
        12'h341:mepc<=csr_wdata&32'hfffffffc;
        12'h342:mcause<=csr_wdata;
        12'h343:mtval<=csr_wdata;
        12'hB00:cycle_count[31:0]<=csr_wdata;
        12'hB80:cycle_count[63:32]<=csr_wdata;
        12'hB02:instret_count[31:0]<=csr_wdata;
        12'hB82:instret_count[63:32]<=csr_wdata;
        12'hB03:branches<=csr_wdata;
        12'hB04:mispredicts<=csr_wdata;
        12'hB05:stalls<=csr_wdata;
        12'hB06:ic_misses<=csr_wdata;
        12'hB07:dc_misses<=csr_wdata;
        default:;
      endcase
      if(trap) begin
        mepc<=trap_pc&32'hfffffffc;mcause<=trap_cause;mtval<=trap_value;
        mstatus[7]<=mstatus[3];mstatus[3]<=0;
      end else if(mret) begin mstatus[3]<=mstatus[7];mstatus[7]<=1; end
    end
  end
endmodule
