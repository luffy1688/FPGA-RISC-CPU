#include "/work/LUO/NeedleRV-X/03_sw/model/byte_tool_model.c"
#include "combined_candidate_data.h"
static int32_t candidate_round(int32_t v){return v>=0?(v+32)/64:-((-v+32)/64);}
/* out:joint6,context11,repair5,basebucket,contextthreshold,contextdeny. */
int run_combined(const uint8_t*text,uint32_t length,const int32_t*encoder,int32_t*out){
 uint32_t i,j,index,bucket=0;int32_t v,h[NR_COMBINED_HIDDEN],hidden_sum[NR_COMBINED_HIDDEN]={0},repair_sum[5]={0},z,max;
 if(nr_ctx_features(text,length))return -1;
 for(j=1;j<6;j++)if(encoder[j]>encoder[bucket])bucket=j;
 for(i=0;i<nr_ctx_touched[255];i++){
  index=nr_ctx_touched[i];v=nr_ctx_counts[index];if(!v)continue;if(v>3)v=3;else if(v< -3)v=-3;v*=8;
  for(j=0;j<NR_COMBINED_HIDDEN;j++)hidden_sum[j]+=v*nr_combined_w1[j][index];
  if(bucket==5)for(j=0;j<5;j++)repair_sum[j]+=v*nr_combined_repair_weight[j][index];
 }
 for(j=0;j<NR_COMBINED_HIDDEN;j++){v=candidate_round(hidden_sum[j])+nr_combined_b1[j];h[j]=v<0?0:v>127?127:v;}
 for(i=0;i<11;i++){z=0;for(j=0;j<NR_COMBINED_HIDDEN;j++)z+=h[j]*nr_combined_w2[i][j];out[6+i]=candidate_round(z)+nr_combined_b2[i];}
 for(j=0;j<5;j++)out[17+j]=bucket==5?candidate_round(repair_sum[j])+nr_combined_repair_bias[j]:0;
 for(j=0;j<6;j++)out[j]=encoder[j]+(j<5?out[17+j]:0);
 out[22]=bucket;out[23]=nr_combined_thresholds[bucket];v=out[7]-out[6];out[24]=v>=out[23];
 if(out[24]){max=out[0];for(j=1;j<5;j++)if(out[j]>max)max=out[j];z=max+v-out[23]+1;if(out[5]<z)out[5]=z;}
 return 0;
}

#include <stdio.h>
#include <string.h>
static void classify(nr_prediction_t*p){uint32_t i,best=0,second=1;if(p->logits[1]>p->logits[0]){best=1;second=0;}for(i=2;i<6;i++){if(p->logits[i]>p->logits[best]){second=best;best=i;}else if(p->logits[i]>p->logits[second])second=i;}p->tool=(nr_tool_t)best;p->margin=p->logits[best]-p->logits[second];}
int main(void){char line[512];while(fgets(line,sizeof(line),stdin)){size_t n=strlen(line);while(n&&(line[n-1]==10||line[n-1]==13))line[--n]=0;nr_prediction_t p;nr_tool_request_t full,fast;nr_context_t context;int32_t out[25];nr_term_scan_t scan;term_scan_init(&scan,(uint8_t*)line,n);int hint=contract_hint(&scan,(uint8_t*)line,n);if(nr_model_predict((uint8_t*)line,n,&p))return 2;if(run_combined((uint8_t*)line,n,p.encoder_logits,out))return 3;for(int i=0;i<6;i++)p.logits[i]=out[i];p.context_logits[0]=out[6];p.context_logits[1]=out[7];p.context_margin=out[7]-out[6];p.context_threshold=out[23];p.context_used=1;p.context_deny=out[24];classify(&p);nr_tool_decode_prediction((uint8_t*)line,n,&p,&full);
 int handled=nr_tool_decode_machine((uint8_t*)line,n,&fast);int bucket=hint<0?5:hint;memset(&context,0,sizeof(context));context.used=1;context.logits[0]=out[6];context.logits[1]=out[7];context.margin=out[7]-out[6];context.threshold=nr_combined_thresholds[bucket];context.deny=context.margin>=context.threshold;if(!handled)handled=nr_tool_decode_fast_with_context((uint8_t*)line,n,&fast,&context);if(!handled)fast=full;
 printf("{\"raw\":%d,\"full\":%d,\"full_status\":%d,\"full_arg\":%d,\"full_op\":%d,\"fast\":%d,\"fast_status\":%d,\"fast_arg\":%d,\"fast_op\":%d,\"fast_handled\":%d,\"hint\":%d,\"rawbucket\":%d,\"fastbucket\":%d,\"contextmargin\":%d}\n",p.tool,full.tool,full.status,full.argument,full.operation,fast.tool,fast.status,fast.argument,fast.operation,handled,hint,out[22],bucket,context.margin);
 }return 0;}
