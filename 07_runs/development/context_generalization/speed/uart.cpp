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
 void waitText(const std::string&s){unsigned limit=cycles+12000000;while(out.find(s)==std::string::npos&&cycles<limit)tick();if(out.find(s)==std::string::npos)throw std::runtime_error("missing "+s+" received "+out);}
 std::string request(std::string s){out.clear();send(s);waitText("NR_READY\n");std::fwrite(out.data(),1,out.size(),stdout);return out;}
};
static uint16_t crc16(const std::string&s){uint16_t c=0xffff;for(unsigned char x:s){c^=uint16_t(x)<<8;for(int i=0;i<8;i++)c=c&0x8000?uint16_t((c<<1)^0x1021):uint16_t(c<<1);}return c;}
static std::string frame(uint32_t seq,const std::string&s){std::string b;b.push_back(char(0xa5));b.push_back(char(0x5a));b.push_back(1);b.push_back(0x10);b.push_back(char(s.size()));b.push_back(0);for(int i=0;i<4;i++)b.push_back(char(seq>>(i*8)));b+=s;auto c=crc16(b);b.push_back(char(c));b.push_back(char(c>>8));return b;}
int main(int argc,char**argv){try{Verilated::commandArgs(argc,argv);Sim t;t.d.reset=1;t.d.uart_rx=1;t.d.gpio_in=0;t.d.clk=0;t.d.eval();std::ifstream f(argv[1]);std::string s;unsigned at=0;while(f>>s){if(s[0]=='@'){at=std::stoul(s.substr(1),nullptr,16);continue;}t.d.rootp->needle_soc__DOT__u_ram__DOT__mem[at++]=std::stoul(s,nullptr,16);}t.tick(5);t.d.reset=0;t.waitText("NR_READY\n");std::fwrite(t.out.data(),1,t.out.size(),stdout);
 auto a=t.request("led 37\n");if(a.find("NR_FAST [1,")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("canonical compact1");
 a=t.request("请读取FPGA当前温度。\n");if(a.find("NR_FAST [2,")==std::string::npos)throw std::runtime_error("NL compact2");
 a=t.request("演示如何编写读取计数器的命令\n");if(a.find("NR_FAST [2,")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("context compact2");
 a=t.request(std::string("\xed\xa0\x80\n",4));if(a.find("NR_INPUT_ERROR invalid_utf8")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("invalidUTF8");
 t.request(":format full\n");a=t.request("pwm 20\n");if(a.find("\"model_used\":0")==std::string::npos||a.find("\"context_used\":0")==std::string::npos||a.find("\"cycles\":0")==std::string::npos||a.find("\"jobs\":0")==std::string::npos)throw std::runtime_error("formal no model");
 a=t.request("请将PWM占空比设置为20%。\n");if(a.find("\"model_used\":2")==std::string::npos||a.find("\"context_used\":1")==std::string::npos)throw std::runtime_error("NL headonly");
 a=t.request("只关闭LED1，其他LED不要改变\n");if(a.find("\"execute\":0")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("bounded preserve denial");
 a=t.request("不要关闭LED1，只点亮LED0，其他位保持不变\n");if(a.find("\"execute\":1")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("unsupported two-specific-LED scope");
 a=t.request("不要读取温度然后点亮LED0\n");if(a.find("\"execute\":1")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("true multi denied");
 for(unsigned i=0;i<2;i++){t.out.clear();t.send(frame(100+i,i?"演示如何编写读取计数器的命令":"led 37"));unsigned limit=t.cycles+12000000;while(t.out.size()<64&&t.cycles<limit)t.tick();if(t.out.size()!=64||uint8_t(t.out[0])!=0xa5||crc16(t.out.substr(0,62))!=(uint16_t(uint8_t(t.out[62]))|(uint16_t(uint8_t(t.out[63]))<<8)))throw std::runtime_error("binaryCRC/length");if(i==0&&(uint8_t(t.out[21])!=0||(uint8_t(t.out[20])&12)))throw std::runtime_error("binary formal noNN");if(i==1&&(uint8_t(t.out[21])!=2||(uint8_t(t.out[20])&12)!=12||uint8_t(t.out[17]>>2)!=5||uint8_t(t.out[18])!=1))throw std::runtime_error("binary context deny");printf("BINARY_ACCEPT type=%s\n",i?"context_reject":"formal_no_model");}
 printf("SPEED_UART_PASS clocks=%u\n",t.cycles);return 0;
}catch(const std::exception&e){printf("SPEED_UART_FAIL %s\n",e.what());return 2;}}
