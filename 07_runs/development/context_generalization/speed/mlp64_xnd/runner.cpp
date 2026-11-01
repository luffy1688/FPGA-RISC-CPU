#include "Vneedle_soc.h"
#include "Vneedle_soc___024root.h"
#include "verilated.h"
#include <fstream>
#include <string>
#include <cstdio>
#include <cstdlib>
int main(int argc,char**argv){Verilated::commandArgs(argc,argv);Vneedle_soc d;d.reset=1;d.uart_rx=1;d.gpio_in=0;d.clk=0;d.eval();std::ifstream f(argv[1]);std::string s,line;unsigned at=0;while(f>>s){if(s[0]=='@'){at=std::stoul(s.substr(1),nullptr,16);continue;}d.rootp->needle_soc__DOT__u_ram__DOT__mem[at++]=std::stoul(s,nullptr,16);}for(unsigned i=0;i<5;i++){d.clk=0;d.eval();d.clk=1;d.eval();}d.reset=0;
unsigned previous=0,loads=0,jobs=0;unsigned long long macs=0,reads=0,writes=0;unsigned cases=0;
for(unsigned cycles=0;cycles<200000000u;cycles++){
 d.clk=0;d.eval();d.clk=1;d.eval();auto*r=d.rootp;unsigned state=r->needle_soc__DOT__gen_xnd__DOT__u_xnd__DOT__state;
 if(previous!=0&&state==0&&r->needle_soc__DOT__gen_xnd__DOT__u_xnd__DOT__done&&!r->needle_soc__DOT__gen_xnd__DOT__u_xnd__DOT__error){unsigned m=r->needle_soc__DOT__gen_xnd__DOT__u_xnd__DOT__macs;macs+=m;reads+=r->needle_soc__DOT__gen_xnd__DOT__u_xnd__DOT__read_bytes;writes+=r->needle_soc__DOT__gen_xnd__DOT__u_xnd__DOT__write_bytes;if(m)jobs++;else loads++;}previous=state;
 if(d.uart_tx_valid){char c=d.uart_tx_data;putchar(c);if(c=='\n'){if(line.rfind("MLP64_CASE ",0)==0){printf("MLP64_PROBE {\"case\":%u,\"macs8\":%llu,\"reads8\":%llu,\"writes8\":%llu,\"loads8\":%u,\"jobs8\":%u}\n",cases++,macs,reads,writes,loads,jobs);if(macs!=66560u*8||reads!=67648u*8||writes!=1088u*8||loads!=40||jobs!=40){puts("MLP64_PROBE_FAIL");return 2;}loads=jobs=0;macs=reads=writes=0;}line.clear();}else line+=c;}
 if(d.gpio_led==0xee){printf("MLP64_RTL_TRAP clocks=%u\n",cycles);return 1;}if(d.gpio_led==0xc0){printf("MLP64_RTL_DONE clocks=%u cases=%u\n",cycles,cases);return 0;}
}puts("MLP64_RTL_TIMEOUT");return 3;}
