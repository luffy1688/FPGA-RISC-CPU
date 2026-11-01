#include "Vneedle_soc.h"
#include "Vneedle_soc___024root.h"
#include "verilated.h"
#include <fstream>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
struct Sim {Vneedle_soc d;std::string out;unsigned cycles=0;
 void tick(unsigned n=1){for(unsigned i=0;i<n;i++){d.clk=0;d.eval();d.clk=1;d.eval();cycles++;if(d.uart_tx_valid)out.push_back(char(d.uart_tx_data));if(d.gpio_led==0xee)throw std::runtime_error("firmware trap");}}
 void send(const std::string&s){for(unsigned char c:s){d.uart_rx=0;tick(41);for(int bit=0;bit<8;bit++){d.uart_rx=(c>>bit)&1;tick(41);}d.uart_rx=1;tick(41);}}
 void waitText(const std::string&s){unsigned limit=cycles+200000000;while(out.find(s)==std::string::npos&&cycles<limit)tick();if(out.find(s)==std::string::npos)throw std::runtime_error("missing "+s+" received "+out);}
 std::string request(std::string s){out.clear();send(s);waitText("NR_READY\n");std::printf("UART_REQUEST ");for(unsigned char c:s){if(c==10)break;if(c>=32)std::putchar(c);}std::putchar(10);std::fwrite(out.data(),1,out.size(),stdout);return out;}
};
static uint16_t crc16(const std::string&s){uint16_t c=0xffff;for(unsigned char x:s){c^=uint16_t(x)<<8;for(int i=0;i<8;i++)c=c&0x8000?uint16_t((c<<1)^0x1021):uint16_t(c<<1);}return c;}
static std::string frame(uint32_t seq,const std::string&s){std::string b;b.push_back(char(0xa5));b.push_back(char(0x5a));b.push_back(1);b.push_back(0x10);b.push_back(char(s.size()));b.push_back(0);for(int i=0;i<4;i++)b.push_back(char(seq>>(i*8)));b+=s;auto c=crc16(b);b.push_back(char(c));b.push_back(char(c>>8));return b;}
static long field(const std::string&s,const char*k){std::string t=std::string("\"")+k+"\":";auto p=s.find(t);if(p==std::string::npos)throw std::runtime_error("missing field "+t);return std::strtol(s.c_str()+p+t.size(),nullptr,10);}

#include "fourth_cases.h"
int main(int argc,char**argv){try{if(argc!=3)throw std::runtime_error("image caseindex required");unsigned index=std::stoul(argv[2]);if(index<23||index>=25)throw std::runtime_error("OnlyremainingF24F25");auto c=cases[index];Verilated::commandArgs(argc,argv);Sim t;t.d.reset=1;t.d.uart_rx=1;t.d.gpio_in=0;t.d.clk=0;t.d.eval();std::ifstream f(argv[1]);std::string word;unsigned at=0;while(f>>word){if(word[0]=='@'){at=std::stoul(word.substr(1),nullptr,16);continue;}t.d.rootp->needle_soc__DOT__u_ram__DOT__mem[at++]=std::stoul(word,nullptr,16);}t.tick(5);t.d.reset=0;t.waitText("NR_READY\n");std::fwrite(t.out.data(),1,t.out.size(),stdout);t.request(":format full\n");t.out.clear();t.send(std::string(c.text)+"\n");t.waitText("NR_ACTION ");unsigned limit=t.cycles+200000000;while(t.out.find('\n',t.out.find("NR_ACTION "))==std::string::npos&&t.cycles<limit)t.tick();std::printf("UART_REQUEST %s [start only]\n",c.text);std::fwrite(t.out.data(),1,t.out.size(),stdout);if(field(t.out,"selected_tool")!=2||field(t.out,"decode")!=0)throw std::runtime_error("CoreMark permission/start");std::printf("RESOURCE_FOURTH_START_PASS id=%s model_used=%ld benchmark_completed=false clocks=%u\n",c.id,field(t.out,"model_used"),t.cycles);return 0;}catch(const std::exception&e){std::printf("RESOURCE_FOURTH_START_FAIL %s\n",e.what());return 2;}}
