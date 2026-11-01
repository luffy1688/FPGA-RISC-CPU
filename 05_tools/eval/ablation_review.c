/* Offline ablation adapter. No hardware dispatch and never linked in firmware.
 * Shared numeric parsing remains necessary: neural logits do not encode slots. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "../../03_sw/model/byte_tool_model.c"
static uint64_t process_ns(void) {struct timespec t;clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&t);return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;}
static void initialize(nr_tool_request_t *r) {r->tool=NR_REJECT;r->status=NR_TOOL_REJECTED;r->argument=0;r->operation=NR_OP_DEFAULT;r->selection_source=NR_SELECT_DENIED;r->margin=0;}
int main(int argc,char **argv) {
 const uint8_t *b;uint32_t n;nr_prediction_t p={0};nr_tool_request_t request;int neural,rc=0,hint;uint64_t begin,model_ns=0,decode_ns;
 if(argc!=3)return 2;
 b=(const uint8_t*)argv[2];n=(uint32_t)strlen(argv[2]);initialize(&request);
 neural=!strcmp(argv[1],"neural")||!strcmp(argv[1],"hybrid");
 begin=process_ns();
 if(neural&&n&&n<=NR_SEQ)rc=nr_model_predict(b,n,&p);
 model_ns=process_ns()-begin;begin=process_ns();
 if(!n)request.status=NR_TOOL_EMPTY;
 else if(n>NR_SEQ)request.status=NR_TOOL_TOO_LONG;
 else if(rc)request.status=NR_TOOL_BACKEND_ERROR;
 else if(!strcmp(argv[1],"hybrid"))nr_tool_decode_prediction(b,n,&p,&request);
 else if(!strcmp(argv[1],"neutral_route")){p.tool=NR_REJECT;p.margin=0;nr_tool_decode_prediction(b,n,&p,&request);}
 else if(!strcmp(argv[1],"rules")) {
  /* Competitive transparent baseline: exact unique domain + common gate and
   * evidenced numeric parser. Includes legal shorthand, not just rescue verbs. */
  hint=contract_hint(b,n);
  if(hint<0||!capability_allowed(b,n,hint))request.status=NR_TOOL_POLICY_REJECTED;
  else {request.tool=(nr_tool_t)hint;request.status=NR_TOOL_OK;
   if(hint==NR_SET_LED)request.status=led_arguments(b,n,&request);
   if(hint==NR_SET_PWM)request.status=duty_argument(b,n,&request.argument);
  }
 } else if(!strcmp(argv[1],"neural")) {
  request.margin=p.margin;
  if(p.tool!=NR_REJECT&&p.margin>=NR_MIN_CONFIDENCE_MARGIN) {
   request.tool=p.tool;request.status=NR_TOOL_OK;
   if(p.tool==NR_SET_LED)request.status=led_arguments(b,n,&request);
   if(p.tool==NR_SET_PWM)request.status=duty_argument(b,n,&request.argument);
  }
 } else return 2;
 decode_ns=process_ns()-begin;
 printf("{\"mode\":\"%s\",\"raw_index\":%d,\"raw_margin\":%d,\"final_index\":%d,\"status\":%d,\"argument\":%d,\"operation\":%u,\"selection_source\":%d,\"model_rc\":%d,\"host_model_cpu_ns\":%llu,\"host_decode_cpu_ns\":%llu,\"physical_board\":false}\n",argv[1],neural?(int)p.tool:-1,neural?p.margin:0,(int)request.tool,(int)request.status,request.argument,(unsigned)request.operation,neural?(int)request.selection_source:-1,rc,(unsigned long long)model_ns,(unsigned long long)decode_ns);
 return 0;
}
