#include "byte_tool_model.h"
#include "byte_context.c.inc"
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
