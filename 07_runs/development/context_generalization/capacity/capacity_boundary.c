#include "byte_tool_model.h"
static nr_semantic_backend_t selected_semantic_backend;
#include "byte_context.c.inc"
#include "capacity_data.h"
static int32_t capacity_round(int32_t v){return v>=0?(v+32)/64:-((-v+32)/64);}
static uint32_t capacity_best(const int32_t*z){uint32_t best=0;for(uint32_t j=1;j<6;j++)if(z[j]>z[best])best=j;return best;}
/* out=joint6,head16,oldrepair5,newrepair5,originalbucket,threshold,deny,newrepairused */
int run_capacity(const uint8_t*text,uint32_t length,const int32_t*encoder,int32_t*out){
 uint32_t i,j,index,bucket=capacity_best(encoder);int32_t v,h[64],hs[64]={0},rs[5]={0},z,max;
 if(nr_ctx_features(text,length))return -1;
 for(i=0;i<nr_ctx_touched[255];i++){
  index=nr_ctx_touched[i];v=nr_ctx_counts[index];if(!v)continue;if(v>3)v=3;else if(v< -3)v=-3;v*=8;
  for(j=0;j<64;j++)hs[j]+=v*nr_capacity_w1[j][index];
  if(bucket==5)for(j=0;j<5;j++)rs[j]+=v*nr_capacity_oldrepair_weight[j][index];
 }
 for(j=0;j<64;j++){v=capacity_round(hs[j])+nr_capacity_b1[j];h[j]=v<0?0:v>127?127:v;}
 for(i=0;i<16;i++){z=0;for(j=0;j<64;j++)z+=h[j]*nr_capacity_w2[i][j];out[6+i]=capacity_round(z)+nr_capacity_b2[i];}
 for(j=0;j<5;j++)out[22+j]=bucket==5?capacity_round(rs[j])+nr_capacity_oldrepair_bias[j]:0;
 for(j=0;j<6;j++)out[j]=encoder[j]+(j<5?out[22+j]:0);
 out[35]=capacity_best(out)==5;
 for(j=0;j<5;j++){out[27+j]=out[35]?out[17+j]:0;out[j]+=out[27+j];}
 out[32]=bucket;out[33]=nr_capacity_thresholds[bucket];v=out[7]-out[6];out[34]=v>=out[33];
 if(out[34]){max=out[0];for(j=1;j<5;j++)if(out[j]>max)max=out[j];z=max+v-out[33]+1;if(out[5]<z)out[5]=z;}
 return 0;
}
