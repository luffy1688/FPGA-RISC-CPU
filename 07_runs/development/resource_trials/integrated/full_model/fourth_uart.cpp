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
 void waitText(const std::string&s){unsigned limit=cycles+900000000;while(out.find(s)==std::string::npos&&cycles<limit)tick();if(out.find(s)==std::string::npos)throw std::runtime_error("missing "+s+" received "+out);}
 std::string request(std::string s){out.clear();send(s);waitText("NR_READY\n");std::printf("UART_REQUEST ");for(unsigned char c:s){if(c==10)break;if(c>=32)std::putchar(c);}std::putchar(10);std::fwrite(out.data(),1,out.size(),stdout);return out;}
};
static uint16_t crc16(const std::string&s){uint16_t c=0xffff;for(unsigned char x:s){c^=uint16_t(x)<<8;for(int i=0;i<8;i++)c=c&0x8000?uint16_t((c<<1)^0x1021):uint16_t(c<<1);}return c;}
static std::string frame(uint32_t seq,const std::string&s){std::string b;b.push_back(char(0xa5));b.push_back(char(0x5a));b.push_back(1);b.push_back(0x10);b.push_back(char(s.size()));b.push_back(0);for(int i=0;i<4;i++)b.push_back(char(seq>>(i*8)));b+=s;auto c=crc16(b);b.push_back(char(c));b.push_back(char(c>>8));return b;}
static long field(const std::string&s,const char*k){std::string t=std::string("\"")+k+"\":";auto p=s.find(t);if(p==std::string::npos)throw std::runtime_error("missing field "+t);return std::strtol(s.c_str()+p+t.size(),nullptr,10);}

#include "fourth_cases.h"
int main(int argc,char**argv){try{Verilated::commandArgs(argc,argv);Sim t;t.d.reset=1;t.d.uart_rx=1;t.d.gpio_in=0;t.d.clk=0;t.d.eval();std::ifstream f(argv[1]);std::string word;unsigned at=0;while(f>>word){if(word[0]=='@'){at=std::stoul(word.substr(1),nullptr,16);continue;}t.d.rootp->needle_soc__DOT__u_ram__DOT__mem[at++]=std::stoul(word,nullptr,16);}t.tick(5);t.d.reset=0;t.waitText("NR_READY\n");std::fwrite(t.out.data(),1,t.out.size(),stdout);
 t.request(":format full\n");t.request("led 37\n");t.request("pwm 20\n");unsigned led=37;
 for(auto c:cases){auto*r=t.d.rootp;unsigned beforeled=t.d.gpio_led,period=r->needle_soc__DOT__pwm_period,duty=r->needle_soc__DOT__pwm_duty,enabled=r->needle_soc__DOT__pwm_enable;
  auto a=t.request(std::string(c.text)+"\n");auto v=a.substr(a.rfind("NR_RESULT "));
  if(field(v,"selected_tool")!=c.tool||field(v,"execute")!=(c.reject?1:c.tool==0?2:0)||(field(v,"decode")!=0)!=bool(c.reject))throw std::runtime_error(std::string(c.id)+" tool/status");
  if(!c.reject){
   if(field(v,"argument")!=c.arg||field(v,"operation")!=c.op)throw std::runtime_error(std::string(c.id)+" args/operation");
   if(c.tool==4){led=c.op==0?c.arg:c.op==1?led|(1u<<c.arg):led&~(1u<<c.arg);if(t.d.gpio_led!=led||field(v,"value")!=led||field(v,"match")!=1)throw std::runtime_error(std::string(c.id)+" LED receipt");}
   if(c.tool==1&&(field(v,"value")!=c.arg||field(v,"readback")!=c.arg||field(v,"period")!=40500||field(v,"high")!=405*c.arg||field(v,"match")!=1))throw std::runtime_error(std::string(c.id)+" PWM receipt");
   if(c.tool==2){if(a.find("Correct operation validated.")==std::string::npos||a.find("NR_ITERATIONS=1200")==std::string::npos||a.find("NR_COREMARK_RETURN")==std::string::npos||field(v,"value")<405000000)throw std::runtime_error(std::string(c.id)+" CoreMark timing/CRC");}
  }else if(t.d.gpio_led!=beforeled||r->needle_soc__DOT__pwm_period!=period||r->needle_soc__DOT__pwm_duty!=duty||r->needle_soc__DOT__pwm_enable!=enabled)throw std::runtime_error(std::string(c.id)+" rejection side effect");
  std::printf("RESOURCE_FOURTH_PASS id=%s model_used=%ld execute=%ld simulated_ADC_available=0\n",c.id,field(v,"model_used"),field(v,"execute"));std::fflush(stdout);
 }
 t.request("led 37\n");t.request("pwm 20\n");std::printf("RESOURCE_FOURTH_ALL_PASS count=25 clocks=%u\n",t.cycles);return 0;
}catch(const std::exception&e){printf("RESOURCE_FOURTH_FAIL %s\n",e.what());return 2;}}
