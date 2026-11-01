#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
int main(void){char b[512];while(fgets(b,sizeof b,stdin)){size_t n=strlen(b);while(n&&(b[n-1]==10||b[n-1]==13))b[--n]=0;nr_prediction_t p;nr_tool_request_t full,fast;nr_context_t ctx;int handled=nr_tool_decode_machine((uint8_t*)b,n,&fast);if(!handled){if(nr_model_context((uint8_t*)b,n,&ctx))return 3;handled=nr_tool_decode_fast_with_context((uint8_t*)b,n,&fast,&ctx);}if(nr_model_predict((uint8_t*)b,n,&p))return 2;nr_tool_decode_prediction((uint8_t*)b,n,&p,&full);if(!handled)fast=full;printf("%d %d %d %d %d %d %d %d",full.tool,full.status,full.argument,full.operation,fast.tool,fast.status,fast.argument,fast.operation);putchar(10);}return 0;}
