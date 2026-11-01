// Restoring unsigned divider with signed pre/post processing.
// 每拍做一次移位/减法，共32拍；不把“/”综合成很长的组合电路。
module rv32_divider(
  input logic clk,reset,start,
  input logic signed_mode, remainder_mode,
  input logic [31:0] dividend,divisor,
  output logic busy,done,
  output logic [31:0] result
);
  logic [31:0] quotient,denominator;
  logic [32:0] remainder_q, trial;
  logic [31:0] quotient_next;
  logic [5:0] count;
  logic neg_q,neg_r,want_rem;
  always_comb begin
    trial={remainder_q[31:0],quotient[31]};
    quotient_next={quotient[30:0],1'b0};
    if(trial>={1'b0,denominator}) begin
      trial=trial-{1'b0,denominator};
      quotient_next[0]=1;
    end
  end
  always_ff @(posedge clk) begin
    if(reset) begin busy<=0;done<=0;result<=0;count<=0;
      quotient<=0;denominator<=0;remainder_q<=0;neg_q<=0;neg_r<=0;want_rem<=0; end
    else begin
      done<=0;
      if(start&&!busy) begin
        neg_q<=signed_mode && (dividend[31]^divisor[31]);
        neg_r<=signed_mode && dividend[31];
        want_rem<=remainder_mode;
        if(divisor==0) begin
          result<=remainder_mode?dividend:32'hffffffff;done<=1;
        end else begin
          quotient<=signed_mode&&dividend[31]?(~dividend+1):dividend;
          denominator<=signed_mode&&divisor[31]?(~divisor+1):divisor;
          remainder_q<=0;count<=0;busy<=1;
        end
      end else if(busy) begin
        quotient<=quotient_next;remainder_q<=trial;count<=count+1;
        if(count==31) begin
          busy<=0;done<=1;
          if(want_rem) result<=neg_r?(~trial[31:0]+1):trial[31:0];
          else result<=neg_q?(~quotient_next+1):quotient_next;
        end
      end
    end
  end
endmodule
