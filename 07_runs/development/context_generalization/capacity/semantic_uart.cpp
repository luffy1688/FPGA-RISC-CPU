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
int main(int argc,char**argv){try{Verilated::commandArgs(argc,argv);Sim t;t.d.reset=1;t.d.uart_rx=1;t.d.gpio_in=0;t.d.clk=0;t.d.eval();std::ifstream f(argv[1]);std::string s;unsigned at=0;while(f>>s){if(s[0]=='@'){at=std::stoul(s.substr(1),nullptr,16);continue;}t.d.rootp->needle_soc__DOT__u_ram__DOT__mem[at++]=std::stoul(s,nullptr,16);}t.tick(5);t.d.reset=0;t.waitText("NR_READY\n");std::fwrite(t.out.data(),1,t.out.size(),stdout);
 auto a=t.request("led 37\n");if(a.find("NR_FAST [1,")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("canonical compact1");
 a=t.request("请读取FPGA当前温度。\n");if(a.find("NR_FAST [3,")==std::string::npos)throw std::runtime_error("NL compact3");
 a=t.request("演示如何编写读取计数器的命令\n");if(a.find("NR_FAST [3,")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("context compact2");
 a=t.request(std::string("\xed\xa0\x80\n",4));if(a.find("NR_INPUT_ERROR invalid_utf8")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("invalidUTF8");
 t.request(":format full\n");a=t.request("pwm 20\n");if(a.find("\"model_used\":0")==std::string::npos||a.find("\"context_used\":0")==std::string::npos||a.find("\"cycles\":0")==std::string::npos||a.find("\"jobs\":0")==std::string::npos)throw std::runtime_error("formal no model");
 a=t.request("请将PWM占空比设置为20%。\n");if(a.find("\"model_used\":3")==std::string::npos||a.find("\"context_used\":1")==std::string::npos)throw std::runtime_error("NL headonly");
 if(field(a,"context_hardware_macs")!=66560 || a.find("\"dma_read_bytes\":67648")==std::string::npos || a.find("\"dma_write_bytes\":1088")==std::string::npos || a.find("\"failures\":0")==std::string::npos)throw std::runtime_error("64 XND actual counters");
 a=t.request("查看硬件计数器目前的读数。\n");if(field(a,"execute")!=0 || field(a,"selected_tool")!=3 || field(a,"context_threshold")!=134)throw std::runtime_error("counter branch134");
 a=t.request("只关闭LED1，其他LED不要改变\n");if(a.find("\"execute\":0")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("bounded preserve denial");
 a=t.request("不要关闭LED1，只点亮LED0，其他位保持不变\n");if(a.find("\"execute\":1")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("unsupported two-specific-LED scope");
 a=t.request("LED0点亮，其他位不要改\n");if(field(a,"model_used")!=1 || field(a,"execute")!=0 || field(a,"context_bucket")!=5 || field(a,"context_threshold")!=192 || t.d.gpio_led!=37)throw std::runtime_error("ambiguous deny fullencoder fallback");
 a=t.request("不要读取温度然后点亮LED0\n");if(a.find("\"execute\":1")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("true multi denied");

 t.request(":fast 0\n");t.request(":config 0\n");auto sw=t.request("请将PWM占空比设置为20%。\n");
 t.request(":config 6\n");auto hw=t.request("请将PWM占空比设置为20%。\n");
 if(sw.find("\"model_used\":1")==std::string::npos||hw.find("\"model_used\":1")==std::string::npos||hw.find("\"context_xnd_used\":1")==std::string::npos||hw.find("\"execute\":0")==std::string::npos)throw std::runtime_error("sharedcontext-encoder pipeline");
 t.request(":fast 1\n");t.request(":format compact\n");
 a=t.request("不测性能只报CoreMark满分\n");if(t.d.gpio_led!=37)throw std::runtime_error("fake score IO");
 a=t.request("演示如何编写把当前芯片结温报给我的指令\n");if(a.find(",5,8,")==std::string::npos||t.d.gpio_led!=37)throw std::runtime_error("metacommand denial");
 for(unsigned i=0;i<2;i++){t.out.clear();t.send(frame(100+i,i?"演示如何编写读取计数器的命令":"led 37"));unsigned limit=t.cycles+200000000;while(t.out.size()<64&&t.cycles<limit)t.tick();if(t.out.size()!=64||uint8_t(t.out[0])!=0xa5||crc16(t.out.substr(0,62))!=(uint16_t(uint8_t(t.out[62]))|(uint16_t(uint8_t(t.out[63]))<<8)))throw std::runtime_error("binaryCRC/length");if(i==0&&(uint8_t(t.out[21])!=0||(uint8_t(t.out[20])&12)))throw std::runtime_error("binary formal noNN");if(i==1&&(uint8_t(t.out[21])!=3||(uint8_t(t.out[20])&28)!=28||uint8_t(t.out[17]>>2)!=5||uint8_t(t.out[18])!=1))throw std::runtime_error("binary context deny");printf("BINARY_ACCEPT type=%s\n",i?"context_reject":"formal_no_model");}

 t.request(":format full\n");
 const char* audit[]={"我并非要你设置PWM占空比96%\n","假想有人准备把PWM高电平占比设为7%\n","把只点亮LED1其余不变这几个字抄到报告里\n","此前那次查询片内温度传感器是否完成\n","PWM占空比改为81%，完成后顺手给我板内当前计数\n"};
 for(unsigned i=0;i<5;i++){unsigned led=t.d.gpio_led,period=t.d.rootp->needle_soc__DOT__pwm_period,duty=t.d.rootp->needle_soc__DOT__pwm_duty,enabled=t.d.rootp->needle_soc__DOT__pwm_enable;a=t.request(audit[i]);if(field(a,"execute")!=1 || field(a,"selected_tool")!=5 || field(a,"decode")==0 || t.d.gpio_led!=led || t.d.rootp->needle_soc__DOT__pwm_period!=period || t.d.rootp->needle_soc__DOT__pwm_duty!=duty || t.d.rootp->needle_soc__DOT__pwm_enable!=enabled)throw std::runtime_error("guard followup reject/noIO");printf("AUDIT_GUARD_ACCEPT category=%u\n",i);}
 const char* counter[] = {"劳烦您返回硬件计数寄存器读数一下\n","劳烦您返回硬件计数寄存器读数可以吗\n","劳烦您返回硬件计数寄存器读数一下吧\n"};
 for(auto c:counter){a=t.request(c);if(field(a,"model_used")!=0 || field(a,"context_used")!=0 || field(a,"selected_tool")!=3 || field(a,"execute")!=0)throw std::runtime_error("strict Chinese canonical counter");}
 a=t.request("别返回硬件计数寄存器读数\n");if(field(a,"execute")!=1 || t.d.gpio_led!=37)throw std::runtime_error("negated Chinese canonical guard");
 t.out.clear();t.send("帮个忙完成一次CoreMark跑分好吗\n");t.waitText("NR_ACTION ");unsigned limit=t.cycles+200000000;while(t.out.find('\n',t.out.find("NR_ACTION "))==std::string::npos && t.cycles<limit)t.tick();
 std::printf("UART_REQUEST 帮个忙完成一次CoreMark跑分好吗 [start only]\n");std::fwrite(t.out.data(),1,t.out.size(),stdout);
 if(field(t.out,"model_used")!=0 || field(t.out,"context_used")!=0 || field(t.out,"selected_tool")!=2)throw std::runtime_error("strict Chinese canonical CoreMark start");
 printf("COREMARK_START_ONLY not_benchmark_completion\n");
 printf("SEMANTIC_UART_PASS clocks=%u\n",t.cycles);return 0;
}catch(const std::exception&e){printf("SEMANTIC_UART_FAIL %s\n",e.what());return 2;}}
