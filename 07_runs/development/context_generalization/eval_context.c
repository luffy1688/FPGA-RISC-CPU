#include <stdio.h>
#include <string.h>
#include "/work/LUO/NeedleRV-X/03_sw/model/byte_tool_model.c"
#include "byte_context.c.inc"
int main(void){char b[512];while(fgets(b,sizeof b,stdin)){
 size_t n=strlen(b);while(n&&(b[n-1]==10||b[n-1]==13))b[--n]=0;
 nr_prediction_t p;nr_tool_request_t q;nr_context_result_t c;int32_t encoder[6];
 if(nr_model_predict((const uint8_t*)b,n,&p)){puts("{\"error\":1}");continue;}
 memcpy(encoder,p.logits,sizeof encoder);if(nr_context_apply((const uint8_t*)b,n,p.logits,&c)){puts("{\"error\":2}");continue;}
 p.tool=0;for(int i=1;i<6;i++)if(p.logits[i]>p.logits[p.tool])p.tool=(nr_tool_t)i;
 int second=p.tool?0:1;for(int i=0;i<6;i++)if(i!=(int)p.tool&&p.logits[i]>p.logits[second])second=i;
 p.margin=p.logits[p.tool]-p.logits[second];nr_tool_decode_prediction((const uint8_t*)b,n,&p,&q);
 printf("{\"index\":%d,\"margin\":%d,\"selected\":%d,\"status\":%d,\"argument\":%d,\"operation\":%d,\"source\":%d,\"encoder_logits\":[",p.tool,p.margin,q.tool,q.status,q.argument,q.operation,q.selection_source);
 for(int i=0;i<6;i++){printf(i?",%d":"%d",encoder[i]);}
 printf("],\"logits\":[");
 for(int i=0;i<6;i++)printf(i?",%d":"%d",p.logits[i]);
 printf("],\"context_logits\":[%d,%d],\"context_margin\":%d,\"context_threshold\":%d,\"context_used\":%u,\"context_deny\":%u,\"context_features\":%u,\"context_scalar_macs\":%u}\n",c.logits[0],c.logits[1],c.margin,c.threshold,c.used,c.deny,c.nonzero_features,c.scalar_macs);
}return 0;}
