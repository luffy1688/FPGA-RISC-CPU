#include <stdint.h>
#include "byte_tool_model.h"
#include "/work/LUO/NeedleRV-X/07_runs/development/context_generalization/speed/baseline_context.c.inc"
int vector(const uint8_t*b,uint32_t n,int16_t*out){int s=nr_ctx_features(b,n);if(!s)for(uint32_t i=0;i<NR_CONTEXT_BINS;i++)out[i]=nr_ctx_counts[i];return s;}
int apply(const uint8_t*b,uint32_t n,int32_t*z,int32_t*out){nr_context_result_t c;int s=nr_context_apply(b,n,z,&c);out[0]=c.logits[0];out[1]=c.logits[1];out[2]=c.margin;out[3]=c.threshold;out[4]=c.used;out[5]=c.deny;out[6]=c.nonzero_features;out[7]=c.scalar_macs;return s;}
void poison(void){for(uint32_t i=0;i<NR_CONTEXT_BINS;i++)nr_ctx_counts[i]=0x5555;}
