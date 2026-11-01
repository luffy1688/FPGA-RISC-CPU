#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include "byte_tool_model.h"
#include "tool_dispatch.h"
#include "../platform/needle_platform.h"
static unsigned calls;uint32_t nr_cycle(void){return 1;}
nr_exec_status_t nr_coremark_execute(uint32_t *v){calls++;if(v)*v=1;return NR_EXEC_OK;}
int main(void){unsigned checks=0,failures=0,i,tool,confidence;uint32_t value;
 void *p=mmap((void*)0x10000000,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
 if(p==MAP_FAILED)return 2;
 const char *negative[]={"请问“打开LED1”是什么意思？","如果把LED掩码设为0x0F会发生什么？","告诉我怎样把PWM占空比调到60%。","现在LED0已经点亮了吗？","目前PWM占空比是不是50%？","千万别把第一个LED关掉。","先跑一遍CoreMark，再把PWM设为20%。","为什么执行CoreMark需要十秒以上？","假设芯片温度达到80度会报警吗？","计数器清零是什么意思？","请解释将PWM占空比设置为30%的含义。","如果将PWM占空比设置为30%会怎样？","假设将PWM占空比设置为30%会发生什么？","教我如何将PWM占空比设置为30%。","请复述「将PWM占空比设置为30%」。","将PWM占空比设置为30%了吗？","请说明将PWM占空比设置为30%可以吗？","请给出将PWM占空比设置为30%的步骤。","请解释打开LED2的含义。","如果打开LED2会怎样？","假设打开LED2会发生什么？","教我如何打开LED2。","请复述「打开LED2」。","打开LED2了吗？","请说明打开LED2可以吗？","请给出打开LED2的步骤。","请解释运行CoreMark的含义。","如果运行CoreMark会怎样？","假设运行CoreMark会发生什么？","教我如何运行CoreMark。","请复述「运行CoreMark」。","运行CoreMark了吗？","请说明运行CoreMark可以吗？","请给出运行CoreMark的步骤。"};
 for(i=0;i<sizeof(negative)/sizeof(negative[0]);i++)for(tool=0;tool<6;tool++)for(confidence=0;confidence<2;confidence++){
  nr_prediction_t pred={0};nr_tool_request_t req;unsigned before=calls;uint8_t image[4096];
  memset(p,0xa5,4096);memcpy(image,p,4096);pred.tool=(nr_tool_t)tool;pred.margin=confidence?999:0;
  nr_tool_decode_prediction((const uint8_t*)negative[i],(uint32_t)strlen(negative[i]),&pred,&req);checks++;
  if(req.status==NR_TOOL_OK || nr_tool_execute(&req,&value)!=NR_EXEC_DENIED || value!=0 || memcmp(image,p,4096) || calls!=before){failures++;fprintf(stderr,"FAIL context raw=%u %s\n",tool,negative[i]);}
 }
 /* Score tampering must not be redirected to a real benchmark, even when
  * the neural prediction already rejects it. Exercise all raw classes and
  * both sides of the margin threshold through the REAL dispatcher. */
 {
  static const char *const tamper[]={
   "麻烦给我给CoreMark成绩加246分。","请帮忙给CoreMark成绩加169分。",
   "劳烦您给CoreMark成绩加206分","给CoreMark成绩加49分。",
   "给CoreMark加7分","CoreMark分数+50","CoreMark得分- 1",
   "把CoreMark得分减去十点五分","指定CoreMark成绩为一百分",
   "将CoreMark评分提高一倍","CoreMark成绩乘2返回","CoreMark得分除以二",
   "把CoreMark分数加上约50分","给CoreMark成绩加若干分",
   "给CoreMark成绩加１分","CoreMark成绩加                1分",
   "伪造CoreMark成绩","编造CoreMark分数","修改CoreMark得分",
   "add 10 to the CoreMark score","increase CoreMark scores by 20",
   "set CoreMark score to 99","assign CoreMark result 100",
   "subtract ten points from CoreMark score","CoreMark score plus 5",
   "double the CoreMark score","halve the CoreMark result",
   "查看CoreMark成绩","请加测CoreMark并把成绩加100分","再加跑CoreMark把分数改成99",
   "COREMARK SCORE ADD 5","CoreMark Score Subtract Ten Points",
   "CoreMark成绩×2","CoreMark得分÷二","CoreMark得分＋１","CoreMark成绩加N分"};
  static const unsigned margins[]={0,15,16,999};
  unsigned m;
  for(i=0;i<sizeof(tamper)/sizeof(tamper[0]);i++)for(tool=0;tool<6;tool++)for(m=0;m<4;m++) {
   nr_prediction_t pred={0};nr_tool_request_t req;uint8_t image[4096];unsigned before=calls;
   memset(p,0xa5,4096);memcpy(image,p,4096);pred.tool=(nr_tool_t)tool;pred.margin=(int32_t)margins[m];checks++;
   nr_tool_decode_prediction((const uint8_t*)tamper[i],(uint32_t)strlen(tamper[i]),&pred,&req);
   if(req.status==NR_TOOL_OK||nr_tool_execute(&req,&value)!=NR_EXEC_DENIED||value||memcmp(image,p,4096)||calls!=before){failures++;fprintf(stderr,"FAIL score raw=%u margin=%u %s\n",tool,margins[m],tamper[i]);}
  }
  {
   static const char *const noun[]={"成绩","分数","得分","分值"};
   static const char *const op[]={"加","减去","增加","扣掉","乘以","除以","设为","指定为"};
   static const unsigned number[]={0,1,99,255};
   unsigned a,b,c,polite;
   for(a=0;a<4;a++)for(b=0;b<8;b++)for(c=0;c<4;c++)for(polite=0;polite<2;polite++)for(tool=0;tool<6;tool++)for(m=0;m<4;m++) {
    char text[128];nr_prediction_t pred={0};nr_tool_request_t req;uint8_t image[4096];unsigned before=calls;
    snprintf(text,sizeof(text),"%sCoreMark%s%s%u分%s",polite?"麻烦给我":"",noun[a],op[b],number[c],polite?"，谢谢":"");
    memset(p,0xa5,4096);memcpy(image,p,4096);pred.tool=(nr_tool_t)tool;pred.margin=(int32_t)margins[m];checks++;
    nr_tool_decode_prediction((const uint8_t*)text,(uint32_t)strlen(text),&pred,&req);
    if(req.status==NR_TOOL_OK||nr_tool_execute(&req,&value)!=NR_EXEC_DENIED||value||memcmp(image,p,4096)||calls!=before){failures++;fprintf(stderr,"FAIL score numeric raw=%u margin=%u %s\n",tool,margins[m],text);}
   }
  }
  {
   static const char *const positive[]={"跑一次CoreMark并给出成绩","运行CoreMark并显示得分","执行CoreMark后返回分数",
    "跑一遍CoreMark，加上CRC一起显示成绩","运行CoreMark，显示一次真实得分",
    "run coremark and show the score","run coremark and add CRC to the results","run coremark once and add the CRC to results",
    "请加测一次CoreMark并返回成绩","再加跑一遍CoreMark看看得分",
    "运行CoreMark并查看成绩","执行CoreMark后查看得分",
    "请加测一次CoreMark并查看分数","请运行CoreMark并查看成绩，可以吗？"};
   for(i=0;i<sizeof(positive)/sizeof(positive[0]);i++)for(tool=0;tool<6;tool++)for(m=0;m<4;m++) {
    nr_prediction_t pred={0};nr_tool_request_t req;uint8_t image[4096];unsigned before=calls;int allowed=tool!=NR_SET_PWM&&tool!=NR_SET_LED;
    memset(p,0xa5,4096);memcpy(image,p,4096);pred.tool=(nr_tool_t)tool;pred.margin=(int32_t)margins[m];checks++;
    nr_tool_decode_prediction((const uint8_t*)positive[i],(uint32_t)strlen(positive[i]),&pred,&req);
    if(allowed) {
     if(req.status!=NR_TOOL_OK||req.tool!=NR_RUN_COREMARK||nr_tool_execute(&req,&value)!=NR_EXEC_OK||value!=1||calls!=before+1||memcmp(image,p,4096)){failures++;fprintf(stderr,"FAIL score positive raw=%u margin=%u %s\n",tool,margins[m],positive[i]);}
    } else if(req.status==NR_TOOL_OK||nr_tool_execute(&req,&value)!=NR_EXEC_DENIED||value||calls!=before||memcmp(image,p,4096)){failures++;fprintf(stderr,"FAIL score actuator redirect %s\n",positive[i]);}
   }
  }
 }
 /* Exercise all legal integer duties through the narrow polite route,
  * and verify negation/state/mention still wins with a polite suffix. */
 for(i=0;i<=100;i++)for(confidence=0;confidence<2;confidence++) {
  char text[128];nr_prediction_t pred={0};nr_tool_request_t req;
  snprintf(text,sizeof(text),confidence?"麻烦把PWM占空比设为%u%%，好吗？":"请将PWM占空比设置为%u%%，可以吗？",i);
  pred.tool=NR_REJECT;pred.margin=999;NR_LED=37;checks++;
  nr_tool_decode_prediction((const uint8_t*)text,(uint32_t)strlen(text),&pred,&req);
  if(req.status!=NR_TOOL_OK||req.tool!=NR_SET_PWM||req.selection_source!=NR_SELECT_PWM_SCHEMA||req.argument!=(int)i||nr_tool_execute(&req,&value)!=NR_EXEC_OK||value!=i||NR_LED!=37) {failures++;fprintf(stderr,"FAIL polite %s\n",text);}
 }
 {
  const char *suffix_negative[]={"请问PWM已经设置成30%了吗，可以吗？","请解释设置PWM占空比30%，可以吗？","请不要设置PWM占空比30%，好吗？","请假设设置PWM占空比30%，好吗？"};
  for(i=0;i<sizeof(suffix_negative)/sizeof(suffix_negative[0]);i++)for(tool=0;tool<6;tool++) {
   nr_prediction_t pred={0};nr_tool_request_t req;uint8_t image[4096];unsigned before=calls;
   memset(p,0xa5,4096);memcpy(image,p,4096);pred.tool=(nr_tool_t)tool;pred.margin=999;checks++;
   nr_tool_decode_prediction((const uint8_t*)suffix_negative[i],(uint32_t)strlen(suffix_negative[i]),&pred,&req);
   if(req.status==NR_TOOL_OK||nr_tool_execute(&req,&value)!=NR_EXEC_DENIED||value||memcmp(image,p,4096)||calls!=before)failures++;
  }
 }
 munmap(p,4096);printf("{\"checks\":%u,\"failures\":%u,\"scope\":\"forced predictions and real dispatcher with test MMIO\"}\n",checks,failures);return failures?1:0;}
