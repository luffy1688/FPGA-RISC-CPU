#include "byte_tool_model.h"
#include "semantic_cached.h"
uint32_t nr_semantic_cached_last_macs(void){return 0;}
uint32_t nr_semantic_cached_workspace_bytes(void){return 3100;}
uint32_t nr_semantic_xnd_workspace_bytes(void){return 5256;}
int nr_semantic_cached_gemv(const int8_t*a,const int32_t*b,const int8_t*c,const int32_t*d,const int16_t*e,const uint16_t*f,uint32_t g,uint32_t h,uint32_t i,int32_t*j,int8_t*k,nr_semantic_stats_t*l){(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h;(void)i;(void)j;(void)k;(void)l;return -2;}
int nr_semantic_xnd_gemv(const int8_t*a,const int32_t*b,const int8_t*c,const int32_t*d,const int16_t*e,const uint16_t*f,uint32_t g,uint32_t h,uint32_t i,int32_t*j,int8_t*k,nr_semantic_stats_t*l){return nr_semantic_cached_gemv(a,b,c,d,e,f,g,h,i,j,k,l);}
/* encoder6,headbinary2,category9,tool5,repair5,cascade5,joint6,fusion5,used,gate,bucket,th,deny */
int integrated_cpu(const uint8_t*b,uint32_t n,int32_t*out){nr_context_t c;nr_prediction_t p;uint32_t j,k=0;nr_model_set_gemv_backend(0);nr_model_set_semantic_backend(0);if(nr_model_context(b,n,&c)||nr_model_predict_with_context(b,n,&p,&c))return -1;
 for(j=0;j<6;j++)out[k++]=p.encoder_logits[j];for(j=0;j<2;j++)out[k++]=p.context_logits[j];for(j=0;j<9;j++)out[k++]=p.context_category_logits[j];for(j=0;j<5;j++)out[k++]=p.context_tool_logits[j];for(j=0;j<5;j++)out[k++]=p.intent_delta[j];for(j=0;j<5;j++)out[k++]=p.intent_cascade_delta[j];for(j=0;j<6;j++)out[k++]=p.logits[j];for(j=0;j<5;j++)out[k++]=p.fusion_delta[j];out[k++]=p.fusion_used;out[k++]=p.fusion_gate_margin;out[k++]=p.context_bucket;out[k++]=p.context_threshold;out[k++]=p.context_deny;return (int)k;}
