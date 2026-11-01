#include "Vneedle_soc.h"
#include "Vneedle_soc___024root.h"
#include "verilated.h"
#include <fstream>
#include <string>
#include <vector>
#include <cstdio>
#include <cstdint>
static uint16_t crc(const std::string&s){uint16_t v=65535;for(uint8_t c:s){v^=uint16_t(c)<<8;for(int i=0;i<8;i++)v=(v&32768)?uint16_t((v<<1)^0x1021):uint16_t(v<<1);}return v;}
static std::string rpc(uint32_t seq,std::string s){std::string b;for(uint8_t c:std::vector<uint8_t>{0xa5,0x5a,1,0x10,uint8_t(s.size()),0})b+=char(c);for(int i=0;i<4;i++)b+=char(seq>>(8*i));b+=s;auto c=crc(b);b+=char(c);b+=char(c>>8);return b;}
int main(int argc,char**argv){Verilated::commandArgs(argc,argv);Vneedle_soc dut;dut.reset=1;dut.uart_rx=1;dut.gpio_in=0;std::ifstream f(argv[1]);std::string s;unsigned addr=0;while(f>>s){if(s[0]=='@')addr=std::stoul(s.substr(1),nullptr,16);else dut.rootp->needle_soc__DOT__u_ram__DOT__mem[addr++]=std::stoul(s,nullptr,16);}for(int i=0;i<5;i++){dut.clk=0;dut.eval();dut.clk=1;dut.eval();}dut.reset=0;
std::vector<std::string> req={":fast 1\n","led 37\n","演示如何编写读取计数器的命令\n",":fast 0\n","演示如何编写读取计数器的命令\n",":format full\n",":fast 1\n","请读取FPGA当前温度。\n",rpc(100,"led 37"),rpc(101,"演示如何编写读取计数器的命令")};
unsigned next=0,tick=0,byte=0,done=0;bool feed=false;std::string line,bin;
auto finish=[&](){done++;if(next<req.size()){feed=true;tick=byte=0;next++;}};
for(unsigned clocks=0;clocks<100000000u;clocks++){
 if(feed){auto&s=req[next-1];unsigned bit=tick/41;uint8_t c=s[byte];dut.uart_rx=bit==0?0:bit<=8?((c>>(bit-1))&1):1;if(++tick==410){tick=0;if(++byte==s.size())feed=false;}}else dut.uart_rx=1;
 dut.clk=0;dut.eval();dut.clk=1;dut.eval();
 if(dut.uart_tx_valid){uint8_t c=dut.uart_tx_data;
  if(!bin.empty()||c==0xa5){bin+=char(c);if(bin.size()==64){bool deny=next==req.size();if(uint8_t(bin[21])!=2||(uint8_t(bin[20])&12)!=(deny?12:4)||uint8_t(bin[17]>>2)!=(deny?5:2)||uint8_t(bin[18])!=(deny?1:0)||crc(bin.substr(0,62))!=(uint16_t(uint8_t(bin[62]))|(uint16_t(uint8_t(bin[63]))<<8))){puts("CONTEXT_UART_BINARY_FAIL");return 2;}printf("CONTEXT_BINARY_PASS deny=%d\n",deny);bin.clear();finish();}}
  else{putchar(c);if(c=='\n'){if(line=="NR_READY")finish();line.clear();}else line+=char(c);}
 }
 if(dut.gpio_led==0xee){puts("CONTEXT_UART_TRAP");return 3;}
 if(next==req.size()&&done==req.size()+1){printf("CONTEXT_UART_PASS transactions=%zu cycles=%u\n",req.size(),clocks);return 0;}
}puts("CONTEXT_UART_TIMEOUT");return 4;}
