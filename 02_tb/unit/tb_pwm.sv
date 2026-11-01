`timescale 1ns/1ps
module tb_pwm;
  logic clk=0,reset=1,enable=0;
  logic [31:0] period=8,duty=0;
  wire pin;
  always #5 clk=~clk;
  pwm #(.DEFAULT_PERIOD(8)) dut(.*);
  task automatic frame(input integer wanted);
    integer high_count;
    begin
      high_count=0;
      for(integer i=0;i<8;i=i+1) begin
        #1;if(pin) high_count=high_count+1;
        @(posedge clk);@(negedge clk);
      end
      if(high_count!=wanted) $fatal(1,"PWM highs %0d expected %0d",high_count,wanted);
    end
  endtask
  task automatic check(input integer amount);
    begin
      enable=0;duty=amount;
      repeat(2) @(negedge clk);
      enable=1;frame(amount);frame(amount);
    end
  endtask
  initial begin
    repeat(2) @(negedge clk);reset=0;
    check(0);check(2);check(4);check(8);
    enable=0;duty=2;repeat(2) @(negedge clk);enable=1;
    #1;if(!pin) $fatal(1,"first pulse missing");
    @(posedge clk);@(negedge clk);duty=6;
    for(integer i=1;i<8;i=i+1) begin
      #1;if(pin!=(i<2)) $fatal(1,"midperiod config glitch");
      @(posedge clk);@(negedge clk);
    end
    frame(6);
    enable=0;#1;if(pin) $fatal(1,"disabled high");
    $display("PASS PWM: 0/25/50/100 percent, boundary update, disabled low");$finish;
  end
endmodule
