// Independent NeedleRV-X P2 experiment. No third-party accelerator code.
// Contract: symmetric half-away-from-zero RIGHT shift, THEN bias, THEN sat8.
// Modes: 0 quantize, 1 ReLU, 2 residual-average (sat8 before averaging).
// Extended safety: wide bias addition, clamped INT32 logit + overflow flag.
// Legal current-model domain never asserts overflow. Three elastic stages.
`default_nettype none
module postprocess_fusion(
 input wire clk, reset,
 input wire in_valid, output wire in_ready,
 input wire signed [31:0] in_raw, in_bias,
 input wire [4:0] in_shift,
 input wire [1:0] in_mode,
 input wire signed [7:0] in_residual,
 input wire [15:0] in_tag,
 input wire in_last,
 output wire out_valid, input wire out_ready,
 output reg signed [7:0] out_quant,
 output reg signed [31:0] out_logit,
 output reg out_overflow,
 output reg [15:0] out_tag,
 output reg out_last
);
 reg v0,v1,v2;
 wire r2=!v2 || out_ready;
 wire r1=!v1 || r2;
 wire r0=!v0 || r1;
 assign in_ready=r0;
 assign out_valid=v2;
 reg signed [32:0] s0_round,s1_sum;
 reg signed [31:0] s0_bias;
 reg [1:0] s0_mode,s1_mode;
 reg signed [7:0] s0_residual,s1_residual;
 reg [15:0] s0_tag,s1_tag;
 reg s0_last,s1_last;
 reg [32:0] magnitude,rounded_magnitude,half;
 reg signed [32:0] round_comb;
 reg signed [7:0] quant_comb;
 reg signed [8:0] residual_sum;
 reg signed [9:0] average_comb;
 always @* begin
   magnitude=in_raw[31] ? -$signed({in_raw[31],in_raw}) : {1'b0,in_raw};
   half=0;
   if(in_shift!=0) half=33'd1<<(in_shift-1'b1);
   rounded_magnitude=(magnitude+half)>>in_shift;
   round_comb=in_raw[31] ? -$signed(rounded_magnitude) : $signed(rounded_magnitude);
   if(s1_sum>33'sd127) quant_comb=8'sd127;
   else if(s1_sum< -33'sd128) quant_comb=-8'sd128;
   else quant_comb=s1_sum[7:0];
   residual_sum=$signed({quant_comb[7],quant_comb})+$signed({s1_residual[7],s1_residual});
   if(residual_sum<0) average_comb=-((-$signed({residual_sum[8],residual_sum})+10'sd1)>>>1);
   else average_comb=($signed({residual_sum[8],residual_sum})+10'sd1)>>>1;
 end
 always @(posedge clk) begin
  if(reset) begin
   v0<=0;v1<=0;v2<=0;s0_round<=0;s0_bias<=0;s1_sum<=0;
   s0_mode<=0;s1_mode<=0;s0_residual<=0;s1_residual<=0;
   s0_tag<=0;s1_tag<=0;s0_last<=0;s1_last<=0;
   out_quant<=0;out_logit<=0;out_overflow<=0;out_tag<=0;out_last<=0;
  end else begin
   if(r0) begin
    v0<=in_valid;
    if(in_valid) begin
      s0_round<=round_comb;s0_bias<=in_bias;s0_mode<=in_mode;
      s0_residual<=in_residual;s0_tag<=in_tag;s0_last<=in_last;
    end
   end
   if(r1) begin
    v1<=v0;
    if(v0) begin
      s1_sum<=s0_round+$signed({s0_bias[31],s0_bias});
      s1_mode<=s0_mode;s1_residual<=s0_residual;s1_tag<=s0_tag;s1_last<=s0_last;
    end
   end
   if(r2) begin
    v2<=v1;
    if(v1) begin
      if(s1_sum>33'sd2147483647) begin out_logit<=32'sh7fffffff;out_overflow<=1;end
      else if(s1_sum< -33'sd2147483648) begin out_logit<=32'sh80000000;out_overflow<=1;end
      else begin out_logit<=s1_sum[31:0];out_overflow<=0;end
      if(s1_mode==2) begin
        if(average_comb>10'sd127) out_quant<=8'sd127;
        else if(average_comb< -10'sd128) out_quant<=-8'sd128;
        else out_quant<=average_comb[7:0];
      end
      else if(s1_mode==1 && quant_comb<0) out_quant<=0;
      else out_quant<=quant_comb;
      out_tag<=s1_tag;out_last<=s1_last;
    end
   end
  end
 end
endmodule
`default_nettype wire
