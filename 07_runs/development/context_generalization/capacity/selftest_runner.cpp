#include "Vneedle_soc.h"
#include "Vneedle_soc___024root.h"
#include "verilated.h"
#include <fstream>
#include <string>
#include <cstdio>
#include <cstdlib>
int main(int argc,char**argv){Verilated::commandArgs(argc,argv);Vneedle_soc dut;dut.reset=1;dut.uart_rx=1;dut.gpio_in=0;dut.clk=0;dut.eval();
 std::ifstream f(argv[1]);std::string s;unsigned at=0;while(f>>s){if(s[0]=='@'){at=std::stoul(s.substr(1),nullptr,16);continue;}dut.rootp->needle_soc__DOT__u_ram__DOT__mem[at++]=std::stoul(s,nullptr,16);}
 for(int i=0;i<5;i++){dut.clk=0;dut.eval();dut.clk=1;dut.eval();}dut.reset=0;
 for(unsigned i=0;i<1500000000u;i++){dut.clk=0;dut.eval();dut.clk=1;dut.eval();if(dut.uart_tx_valid)std::putchar(dut.uart_tx_data);if(dut.gpio_led==0xee){std::printf("SELFTEST_TRAP mepc=%x cause=%x\n",dut.rootp->needle_soc__DOT__u_cpu__DOT__csr__DOT__mepc,dut.rootp->needle_soc__DOT__u_cpu__DOT__csr__DOT__mcause);return 1;}if(dut.gpio_led==0xc0){std::printf("\nINTEGRATED_MODEL_DONE clocks=%u\n",i);return 0;}}
 return 2;
}
