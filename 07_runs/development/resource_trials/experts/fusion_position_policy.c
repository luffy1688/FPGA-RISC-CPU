#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "byte_tool_model.h"
/* Keep the current shared decoder implementation, but its fast context
 * selection must use this candidate's calibration,not production64 values. */
#define nr_combined_thresholds nr_production_thresholds_unused
#include "byte_semantic_data.h"
#undef nr_combined_thresholds
static const int32_t nr_combined_thresholds[6]={152,116,55,93,5,160};
#include "private_byte_tool_model.c"
#define best resource_best
#define ra resource_ra
#include "../capacity/validate_capacity.c"
#undef best
#undef ra
#define best fusion_best
#include "fusion_position_boundary.c"
#undef best
#include "../capacity/h64_f2048_position_data.h"
static void array(const int32_t*v,int n){for(int i=0;i<n;i++)printf("%d ",v[i]);}
static int candidate(const uint8_t*b,uint32_t n,nr_prediction_t*p,nr_context_t*ctx,int32_t head16[16],int32_t fusion_delta[5]){
 int32_t out[36],h[64],pre[6];int8_t x[2048],ft[70];unsigned i,j;
 nr_context_t empty={0};nr_prediction_t original;
 /* This call computes immutable encoder only. Empty context supplies no
  * semantic head; disregard the old repair result and copy encoder_logits. */
 if(nr_model_predict_with_context(b,n,&original,&empty))return -1;
 if(infer_c(b,n,2048,64,1,nr_resource_w1,nr_resource_b1,nr_resource_w2,nr_resource_b2,nr_resource_oldrepair_weight,nr_resource_oldrepair_bias,nr_combined_thresholds,original.encoder_logits,out))return -2;
 if(features_c(b,n,2048,1,x))return -3;
 for(j=0;j<64;j++){int32_t sum=0,v;for(i=0;i<2048;i++)sum+=(int32_t)x[i]*nr_resource_w1[j*2048+i];v=resource_ra(sum)+nr_resource_b1[j];h[j]=v<0?0:v>127?127:v;}
 memset(ctx,0,sizeof(*ctx));ctx->used=1;ctx->logits[0]=out[6];ctx->logits[1]=out[7];ctx->margin=out[7]-out[6];
 for(i=0;i<9;i++){ctx->category_logits[i]=out[8+i];if(out[8+i]>ctx->category_logits[ctx->category])ctx->category=i;}
 for(i=0;i<5;i++)ctx->tool_logits[i]=out[17+i];
 nr_context_select(ctx,(uint32_t)out[32],0);memset(p,0,sizeof(*p));nr_prediction_set_context(p,ctx);p->encoder_used=1;
 for(i=0;i<6;i++){p->encoder_logits[i]=original.encoder_logits[i];pre[i]=original.encoder_logits[i]+(i<5?out[22+i]+out[27+i]:0);}
 if(fusion_one(h,original.encoder_logits,pre,ctx->logits,nr_combined_thresholds,p->logits,ft,fusion_delta))return -4;
 for(i=0;i<5;i++){p->intent_delta[i]=out[22+i];p->intent_cascade_delta[i]=out[27+i];}
 p->intent_repair_used=out[32]==5;p->intent_cascade_used=out[35];
 unsigned best=0;int32_t second=-2147483647;
 for(i=1;i<6;i++)if(p->logits[i]>p->logits[best])best=i;
 for(i=0;i<6;i++)if(i!=best&&p->logits[i]>second)second=p->logits[i];p->tool=(nr_tool_t)best;p->margin=p->logits[best]-second;
 for(i=0;i<16;i++)head16[i]=out[6+i];return 0;
}
int main(void){char b[512];while(fgets(b,sizeof b,stdin)){size_t n=strlen(b);while(n&&(b[n-1]==10||b[n-1]==13))b[--n]=0;nr_prediction_t p;nr_tool_request_t full,fast;nr_context_t ctx;int32_t head16[16],delta[5];int status=candidate((uint8_t*)b,n,&p,&ctx,head16,delta);if(status)return 20-status;
 nr_tool_decode_prediction((uint8_t*)b,n,&p,&full);int handled=nr_tool_decode_machine((uint8_t*)b,n,&fast);if(!handled)handled=nr_tool_decode_fast_with_context((uint8_t*)b,n,&fast,&ctx);if(!handled)fast=full;
 printf("%d %u %u %d %u %u %u %d %u %d %u %d %u %d %u %d ",p.tool,p.context_bucket,p.context_bucket_source,p.context_threshold,p.context_deny,p.context_used,p.intent_repair_used,full.tool,full.status,full.argument,full.operation,fast.tool,fast.status,fast.argument,fast.operation,handled);array(p.logits,6);array(p.encoder_logits,6);array(head16,16);array(delta,5);putchar(10);
 }return 0;}
