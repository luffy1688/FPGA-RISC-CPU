// Clock-by-clock RTL execution; no instruction emulation.
// Default is CoreMark, MODEL_DONE uses model selftest, MODEL_UART feeds real RX bits.
#include "Vneedle_soc.h"
#include "verilated.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#ifndef NR_SIM_CLK_HZ
#define NR_SIM_CLK_HZ 27000000u
#endif
#ifndef NR_SIM_BAUD
#define NR_SIM_BAUD 1000000u
#endif
int main(int argc,char **argv) {
  Verilated::commandArgs(argc,argv);
  const char *done_label=argc>1?argv[1]:"COREMARK_DONE";
  unsigned limit=argc>2?(unsigned)std::strtoul(argv[2],nullptr,10):600000000u;
  bool interactive=std::strcmp(done_label,"MODEL_UART")==0;
  // Match the UART RTL integer divider and the platform PWM period.
  const unsigned bit_clocks=NR_SIM_CLK_HZ/NR_SIM_BAUD;
  const unsigned pwm_period=NR_SIM_CLK_HZ/1000u;
  const unsigned pwm_expected_high=(pwm_period*30u)/100u;
  std::string commands[]={"led 37\r\n","打开LED1\n","关闭LED0\n","第六颗LED关掉\n","LED掩码0xA5\n","让PWM高电平占整个周期的三成。\n","PWM按九成占空比运行。\n","LED7打开\n","计数器清零\n","将温度设定为25\n","读取计数值\n","读取温度\n","run coremark\n","不要设置PWM50\n","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n","\n",":config 0\n","led 37\n",":config 6\n","led 37\n","请解释将PWM占空比设置为30%的含义。\n","如果打开LED2会怎样？\n","现在LED0已经点亮了吗？\n","为什么执行CoreMark需要十秒以上？\n","请将PWM占空比设置为30%，可以吗？\n","请打开LED1，好吗？\n"};
  bool pwm_watch=false;unsigned pwm_samples=0,pwm_high=0;
  std::string output_line;
  unsigned next_command=0,byte_index=0,frame_tick=0;
  bool feeding=false;
  Vneedle_soc dut;
  dut.uart_rx=1;dut.gpio_in=0;dut.reset=1;
  for(unsigned i=0;i<5;i++) {dut.clk=0;dut.eval();dut.clk=1;dut.eval();}
  dut.reset=0;
  for(unsigned cycles=0;cycles<limit;cycles++) {
    if(feeding) {
      unsigned bit=frame_tick/bit_clocks;
      unsigned char c=(unsigned char)commands[next_command-1][byte_index];
      dut.uart_rx=bit==0?0:(bit<=8?((c>>(bit-1))&1):1);
      if(++frame_tick==11*bit_clocks) { // one start, eight data, two stop bits
        frame_tick=0;
        if(++byte_index==commands[next_command-1].size()) feeding=false;
      }
    } else dut.uart_rx=1;
    dut.clk=0;dut.eval();dut.clk=1;dut.eval();
    if(pwm_watch && pwm_samples<pwm_period) {pwm_samples++;pwm_high+=(dut.gpio_out>>7)&1;}
    if(dut.uart_tx_valid) {
      char c=(char)dut.uart_tx_data;std::putchar(c);
      if(interactive) {
        if(c=='\n') {
          if(output_line.find("\"selected_tool\":1,")!=std::string::npos &&
             output_line.find("\"decode\":0,")!=std::string::npos &&
             output_line.find("\"execute\":0,")!=std::string::npos)
            pwm_watch=true;
          if(output_line=="NR_READY") {
            std::printf("NR_SIM_STATE {\"after\":%u,\"led\":%u,\"gpio\":%u}\n",next_command,(unsigned)dut.gpio_led,(unsigned)dut.gpio_out);
            if(next_command==sizeof(commands)/sizeof(commands[0])) {
              if(dut.gpio_led!=39) {std::puts("UART_LED_ERROR");return 1;}
              if(!pwm_watch || pwm_samples!=pwm_period || pwm_high!=pwm_expected_high) {
                std::printf("PWM_WAVE_ERROR clocks=%u high=%u\n",pwm_samples,pwm_high);return 1;
              }
              std::printf("PWM_LINE_PASS clocks=%u high=%u\n",pwm_samples,pwm_high);
              std::printf("MODEL_UART_DONE sim_cycles=%u\n",cycles+1);
              dut.final();return 0;
            }
            next_command++;byte_index=frame_tick=0;feeding=true;
          }
          output_line.clear();
        } else output_line+=c;
      }
    }
    if(dut.gpio_led==0xee) {std::printf("\nRTL_TRAP pc=%08x\n",dut.dbg_pc);return 1;}
    if(!interactive && dut.gpio_led==0xc0) {
      std::printf("\n%s sim_cycles=%u\n",done_label,cycles+1);dut.final();return 0;
    }
  }
  std::printf("\nRTL_TIMEOUT pc=%08x\n",dut.dbg_pc);dut.final();return 1;
}
