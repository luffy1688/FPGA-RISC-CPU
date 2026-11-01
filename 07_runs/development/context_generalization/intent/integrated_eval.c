#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
static void array(const int32_t*v,int n){for(int i=0;i<n;i++)printf("%d ",v[i]);}
int main(void){char b[512];while(fgets(b,sizeof b,stdin)){size_t n=strlen(b);while(n&&(b[n-1]==10||b[n-1]==13))b[--n]=0;nr_prediction_t p;nr_tool_request_t full,fast;nr_context_t ctx;int handled=nr_tool_decode_machine((uint8_t*)b,n,&fast);if(!handled){if(nr_model_context((uint8_t*)b,n,&ctx))return 3;handled=nr_tool_decode_fast_with_context((uint8_t*)b,n,&fast,&ctx);}if(nr_model_predict((uint8_t*)b,n,&p))return 2;nr_tool_decode_prediction((uint8_t*)b,n,&p,&full);if(!handled)fast=full;
printf("%d %u %u %d %u %u %u %d %d %d %d %d %d %d %d %d ",p.tool,p.context_bucket,p.context_bucket_source,p.context_threshold,p.context_deny,p.context_used,p.intent_repair_used,full.tool,full.status,full.argument,full.operation,fast.tool,fast.status,fast.argument,fast.operation,handled);array(p.logits,6);array(p.encoder_logits,6);array(p.context_logits,2);array(p.context_category_logits,9);array(p.intent_delta,5);putchar(10);}return 0;}
