// RV32M multiply. Cancellation resets validity, not arithmetic registers.
// Each newly accepted operation overwrites all operands before they are used.
module rv32_multiplier(
 input logic clk,reset,cancel,start,input logic[1:0]mode,
 input logic[31:0]operand_a,operand_b,
 output wire busy,output logic done,output logic[31:0]result);
 localparam [2:0] IDLE=0,PRODUCTS=1,MIDDLE=2,COMBINE=3,UPPER=4,CORRECT_A=5,CORRECT_B=6;
 logic[2:0]state;logic[1:0]mode_q;
 logic[31:0]a_q,b_q,p00,p01,p10,p11,upper_q,corrected_a;
 logic[17:0]middle_q,cross_q;
 assign busy=state!=IDLE;
 always_ff @(posedge clk)begin
  if(reset||cancel)begin state<=IDLE;done<=0;end
  else begin
   done<=0;
   case(state)
    IDLE:if(start)state<=PRODUCTS;
    PRODUCTS:state<=MIDDLE;
    MIDDLE:state<=COMBINE;
    COMBINE:if(mode_q==0)begin done<=1;state<=IDLE;end else state<=UPPER;
    UPPER:state<=CORRECT_A;
    CORRECT_A:state<=CORRECT_B;
    CORRECT_B:begin done<=1;state<=IDLE;end
    default:state<=IDLE;
   endcase
  end
 end
 // Payload writes use only the registered phase. A cancelled value can
 // change internally, but can never assert done or be architecturally retired.
 always_ff @(posedge clk)begin
  case(state)
   IDLE:if(start)begin a_q<=operand_a;b_q<=operand_b;mode_q<=mode;end
   PRODUCTS:begin
    p00<=a_q[15:0]*b_q[15:0];p01<=a_q[15:0]*b_q[31:16];
    p10<=a_q[31:16]*b_q[15:0];p11<=a_q[31:16]*b_q[31:16];
   end
   MIDDLE:middle_q<={2'b0,p00[31:16]}+{2'b0,p01[15:0]}+{2'b0,p10[15:0]};
   COMBINE:if(mode_q==0)result<={middle_q[15:0],p00[15:0]};
           else cross_q<={2'b0,p01[31:16]}+{2'b0,p10[31:16]}+{16'b0,middle_q[17:16]};
   UPPER:upper_q<=p11+{14'b0,cross_q};
   CORRECT_A:corrected_a<=upper_q-((mode_q!=3&&a_q[31])?b_q:32'b0);
   CORRECT_B:result<=corrected_a-((mode_q==1&&b_q[31])?a_q:32'b0);
   default:;
  endcase
 end
endmodule
