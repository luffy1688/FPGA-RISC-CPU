#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include "byte_tool_model.h"
#include "tool_dispatch.h"
#include "../platform/needle_platform.h"
static unsigned checks,errors,coremark_calls;
uint32_t nr_cycle(void) {return 123456u;}
nr_exec_status_t nr_coremark_execute(uint32_t *v) {coremark_calls++;if(v)*v=999;return NR_EXEC_OK;}
static void check(int ok,const char *name) {checks++;if(!ok){errors++;fprintf(stderr,"FAIL %s\n",name);}}
static nr_tool_request_t decode(nr_tool_t raw,const char *s,int margin) {
 nr_prediction_t p={0};nr_tool_request_t r;memset(&r,0xa5,sizeof(r));
 p.tool=raw;p.margin=margin;nr_tool_decode_prediction((const uint8_t*)s,(uint32_t)strlen(s),&p,&r);return r;
}
static void expect(const char *text,nr_tool_t raw,nr_tool_status_t status,nr_tool_t tool,
                   nr_tool_operation_t op,int argument) {
 nr_tool_request_t r=decode(raw,text,999);
 if(r.status!=status || r.tool!=tool || r.operation!=op || r.argument!=argument) {
  fprintf(stderr,"CASE %s: status=%u tool=%u op=%u arg=%d\n",text,r.status,r.tool,r.operation,r.argument);
  check(0,text);
 }else check(1,text);
}
static void cn(int v,char *out) {
 static const char *d[]={"零","一","二","三","四","五","六","七","八","九"};
 out[0]=0;
 if(v<10)strcpy(out,d[v]);
 else if(v==100)strcpy(out,"一百");
 else {if(v>=20)strcat(out,d[v/10]);strcat(out,"十");if(v%10)strcat(out,d[v%10]);}
}
int main(void) {
 char text[128],number[32];uint32_t before,value;unsigned old,bit,on,i;
 void *mem=mmap((void*)0x10000000u,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
 if(mem==MAP_FAILED){perror("test-only MMIO mmap");return 2;}
 for(i=0;i<256;i++) {
  snprintf(text,sizeof(text),"设置LED掩码0x%02X",i);
  expect(text,NR_SET_LED,NR_TOOL_OK,NR_SET_LED,NR_OP_DEFAULT,(int)i);
 }
 for(i=0;i<=100;i++) {
  snprintf(text,sizeof(text),"pwm %u",i);
  expect(text,NR_SET_PWM,NR_TOOL_OK,NR_SET_PWM,NR_OP_DEFAULT,(int)i);
  cn((int)i,number);snprintf(text,sizeof(text),"PWM百分之%s",number);
  expect(text,NR_SET_PWM,NR_TOOL_OK,NR_SET_PWM,NR_OP_DEFAULT,(int)i);
 }
 for(i=0;i<=10;i++) {
  cn((int)i,number);snprintf(text,sizeof(text),"PWM占比%s成",number);
  expect(text,NR_SET_PWM,NR_TOOL_OK,NR_SET_PWM,NR_OP_DEFAULT,(int)i*10);
 }
 expect("LED掩码0x100",NR_SET_LED,NR_TOOL_OUT_OF_RANGE,NR_SET_LED,NR_OP_DEFAULT,0);
 expect("LED掩码0xGG",NR_SET_LED,NR_TOOL_BAD_ARGUMENT,NR_SET_LED,NR_OP_DEFAULT,0);
 expect("LED0.5点亮",NR_SET_LED,NR_TOOL_BAD_ARGUMENT,NR_SET_LED,NR_OP_DEFAULT,0);
 expect("LED0和LED1打开",NR_SET_LED,NR_TOOL_BAD_ARGUMENT,NR_SET_LED,NR_OP_DEFAULT,0);
 expect("LED8打开",NR_SET_LED,NR_TOOL_OUT_OF_RANGE,NR_SET_LED,NR_OP_DEFAULT,0);
 expect("LED0打开又关闭",NR_SET_LED,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("第8颗LED关闭",NR_SET_LED,NR_TOOL_OK,NR_SET_LED,NR_OP_LED_OFF,7);
 expect("第二颗LED打开",NR_SET_LED,NR_TOOL_OK,NR_SET_LED,NR_OP_LED_ON,1);
 expect("LED全部熄灭",NR_SET_LED,NR_TOOL_OK,NR_SET_LED,NR_OP_DEFAULT,0);
 expect("全部LED点亮",NR_SET_LED,NR_TOOL_OK,NR_SET_LED,NR_OP_DEFAULT,255);
 expect("LED整体关闭掩码3",NR_SET_LED,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("pwm -1",NR_SET_PWM,NR_TOOL_OUT_OF_RANGE,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("pwm 101",NR_SET_PWM,NR_TOOL_OUT_OF_RANGE,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("pwm 1.5",NR_SET_PWM,NR_TOOL_BAD_ARGUMENT,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("pwm 1 2",NR_SET_PWM,NR_TOOL_BAD_ARGUMENT,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("pwm −1",NR_SET_PWM,NR_TOOL_OUT_OF_RANGE,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("pwm 0x32",NR_SET_PWM,NR_TOOL_BAD_ARGUMENT,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("PWM一成半",NR_SET_PWM,NR_TOOL_BAD_ARGUMENT,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("PWM百分之一百零一",NR_SET_PWM,NR_TOOL_BAD_ARGUMENT,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("PWM百分之二十五30",NR_SET_PWM,NR_TOOL_BAD_ARGUMENT,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("PWM五十",NR_SET_PWM,NR_TOOL_MISSING_ARGUMENT,NR_SET_PWM,NR_OP_DEFAULT,0);
 expect("PWM频率设置为50",NR_SET_PWM,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("PWM周期改为20",NR_SET_PWM,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("温度降到30",NR_READ_TEMP,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("调整温度到30",NR_READ_TEMP,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("重置计数器",NR_READ_COUNTER,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("改高CoreMark成绩",NR_RUN_COREMARK,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("不要关闭LED0",NR_SET_LED,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 expect("LED0打开",NR_SET_PWM,NR_TOOL_POLICY_REJECTED,NR_REJECT,NR_OP_DEFAULT,0);
 {
  nr_tool_request_t r=decode(NR_SET_LED,"set led 7",15);
  check(r.status==NR_TOOL_REJECTED && r.tool==NR_REJECT,"legacy mask keeps confidence gate");
  r=decode(NR_REJECT,"LED4点亮",0);
  check(r.status==NR_TOOL_OK && r.selection_source==NR_SELECT_LED_SCHEMA && r.argument==4,"explicit LED rescue is labeled");
  r=decode(NR_REJECT,"读一下计数值",0);
  check(r.status==NR_TOOL_OK && r.selection_source==NR_SELECT_READ_SCHEMA,"read-only rescue is labeled");
 }
 {
  nr_tool_request_t t=decode(NR_READ_TEMP,"让PWM高电平比例为四成",99);
  check(t.status==NR_TOOL_OK && t.tool==NR_SET_PWM && t.argument==40 &&
        t.selection_source==NR_SELECT_PWM_SCHEMA,"exact PWM set can recover read-class confusion");
  NR_LED=37;
  check(nr_tool_execute(&t,&value)==NR_EXEC_OK && value==40 && NR_LED==37 &&
        NR_MMIO(0x10000038u)==27000 && NR_MMIO(0x10000034u)==10800 &&
        NR_MMIO(0x1000003cu)==1,"explicit PWM dispatch writes evidenced duty only");
  t=decode(NR_SET_PWM,"将PWM占空比设为35%",0);
  check(t.status==NR_TOOL_OK && t.argument==35 && t.selection_source==NR_SELECT_PWM_SCHEMA,"bounded PWM route labels low-confidence rescue");
  t=decode(NR_SET_LED,"将PWM占空比设为35%",999);
  check(t.status==NR_TOOL_POLICY_REJECTED,"no cross-actuator redirection");
  t=decode(NR_SET_PWM,"读取PWM占空比35%",999);
  check(t.status==NR_TOOL_POLICY_REJECTED,"PWM query cannot become a write");
  t=decode(NR_REJECT,"我不想调整PWM占空比35%",999);
  check(t.status==NR_TOOL_POLICY_REJECTED,"negated PWM schema is denied");
  t=decode(NR_SET_PWM,"pwm 35",0);
  check(t.status==NR_TOOL_REJECTED,"unqualified PWM shorthand retains neural gate");
 }
 /* All 8-bit prior states: the target changes, every other bit stays unchanged. */
 for(old=0;old<256;old++)for(bit=0;bit<8;bit++)for(on=0;on<2;on++) {
  nr_tool_request_t r={0};r.tool=NR_SET_LED;r.status=NR_TOOL_OK;
  r.argument=(int32_t)bit;r.operation=on?NR_OP_LED_ON:NR_OP_LED_OFF;
  NR_MMIO(0x1000003cu)=0;NR_LED=old;
  check(nr_tool_execute(&r,&value)==NR_EXEC_OK &&
        ((value>>bit)&1u)==on && (value&~(1u<<bit))==(old&~(1u<<bit)) &&
        NR_LED==value,"LED preserves all non-target bits");
 }
 {
  nr_tool_request_t r={0};r.tool=NR_SET_LED;r.status=NR_TOOL_OK;r.operation=NR_OP_LED_OFF;r.argument=7;
  NR_LED=165;NR_MMIO(0x1000003cu)=1;
  check(nr_tool_execute(&r,&value)==NR_EXEC_UNAVAILABLE && NR_LED==165 &&
        NR_MMIO(0x1000003cu)==1,"PWM owns GPIO7");
  r.argument=8;before=NR_LED;
  check(nr_tool_execute(&r,&value)==NR_EXEC_DENIED && NR_LED==before,"dispatcher bounds LED pin");
  r.tool=NR_SET_PWM;r.argument=25;before=NR_MMIO(0x10000034u);
  check(nr_tool_execute(&r,&value)==NR_EXEC_DENIED && NR_MMIO(0x10000034u)==before,"dispatcher denies foreign operation tag");
 }
 {
  const char *denied[]={"计数器清零","设置温度为40","修改CoreMark成绩","不要把LED设成7","LED1打开PWM50","下载固件"};
  nr_tool_t raw[]={NR_READ_COUNTER,NR_READ_TEMP,NR_RUN_COREMARK,NR_SET_LED,NR_SET_LED,NR_RUN_COREMARK};
  for(i=0;i<sizeof(raw)/sizeof(raw[0]);i++) {
   nr_tool_request_t r=decode(raw[i],denied[i],999);unsigned calls=coremark_calls;
   NR_LED=37;NR_MMIO(0x10000034u)=6750;before=NR_MMIO(0x1000003cu);
   check(nr_tool_execute(&r,&value)==NR_EXEC_DENIED && value==0 &&
         NR_LED==37 && NR_MMIO(0x10000034u)==6750 && NR_MMIO(0x1000003cu)==before &&
         calls==coremark_calls,"rejected command has no dispatcher side effects");
  }
 }
 munmap(mem,4096);
 printf("{\"checks\":%u,\"failures\":%u,\"scope\":\"host real dispatcher with test-only mapped MMIO; not FPGA\"}\n",checks,errors);
 return errors?1:0;
}
