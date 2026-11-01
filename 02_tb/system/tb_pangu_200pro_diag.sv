`timescale 1ns/1ps
module tb_diag;
  reg clk_in=0,reset_in=1,key=1,uart_rx=1;
  wire uart_tx; wire [7:0] led;
  localparam integer DIV=234;
  always #18.5185 clk_in=~clk_in;
  pangu_200pro_diag #(.HARD_ADC(0),.REPORT_CYCLES(300000),.HEARTBEAT_BIT(10)) dut(.*);
  task automatic receive_byte(output reg [7:0] data);
    begin
      @(negedge uart_tx);
      repeat(DIV/2) @(posedge clk_in);
      if(uart_tx!==0) $fatal(1,"start bit");
      for(integer j=0;j<8;j=j+1) begin repeat(DIV) @(posedge clk_in);data[j]=uart_tx;end
      repeat(DIV) @(posedge clk_in);
      if(uart_tx!==1) $fatal(1,"stop bit");
    end
  endtask
  task automatic receive_line(output string line);
    reg [7:0] data;
    begin
      line="";
      for(integer j=0;j<63;j=j+1) begin receive_byte(data);line={line,data};end
    end
  endtask
  task automatic send_byte(input reg [7:0] data);
    begin
      @(negedge clk_in);uart_rx=0;repeat(DIV) @(posedge clk_in);
      for(integer j=0;j<8;j=j+1) begin @(negedge clk_in);uart_rx=data[j];repeat(DIV) @(posedge clk_in);end
      @(negedge clk_in);uart_rx=1;repeat(DIV) @(posedge clk_in);
    end
  endtask
  string line;
  initial begin
    receive_line(line);
    if(line.substr(0,60)!="NR_DIAG rst=1 key=1 rx=1 temp=000 v=0 f=0 ot=0 cnt=00 last=00" || line[61]!=8'h0d || line[62]!=8'h0a) $fatal(1,"first line: %s",line);
    @(negedge clk_in);reset_in=0;key=0;
    send_byte(8'h55);
    receive_line(line);
    if(line.substr(0,60)!="NR_DIAG rst=0 key=0 rx=1 temp=000 v=0 f=0 ot=0 cnt=01 last=55" || line[61]!=8'h0d || line[62]!=8'h0a) $fatal(1,"second line: %s",line);
    if(led[7:1]!==7'b0101100) $fatal(1,"pin LEDs %x",led);
    $display("PASS DIAG: periodic 115200 8N1 report; KEY0 low does not stop TX; input capture; UART RX byte 55 counted; ADC unavailable is explicit");
    $finish;
  end
  initial begin repeat(600000) @(posedge clk_in);$fatal(1,"timeout");end
endmodule
