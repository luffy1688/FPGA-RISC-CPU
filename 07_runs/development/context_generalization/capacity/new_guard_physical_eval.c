#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
int main(void){char b[512];while(fgets(b,sizeof b,stdin)){size_t n=strlen(b);while(n&&(b[n-1]==10||b[n-1]==13))b[--n]=0;for(int mode=0;mode<2;mode++){nr_prediction_t p;nr_tool_request_t q;nr_context_t ctx={0};int handled=mode&&nr_tool_decode_machine((uint8_t*)b,n,&q)==NR_FAST_HANDLED;if(handled)nr_prediction_set_context(&p,&ctx);else{if(nr_model_context((uint8_t*)b,n,&ctx))return 2;if(mode&&nr_tool_decode_fast_with_context((uint8_t*)b,n,&q,&ctx)==NR_FAST_HANDLED)nr_prediction_set_context(&p,&ctx);else{if(nr_model_predict_with_context((uint8_t*)b,n,&p,&ctx))return 3;nr_tool_decode_prediction((uint8_t*)b,n,&p,&q);}}printf("%d %d %d %u",mode,q.tool,q.status,p.context_deny);putchar(10);}}return 0;}
