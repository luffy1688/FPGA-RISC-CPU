#include <stdint.h>
#include "byte_context.c.inc"
int run_features(const uint8_t*b,uint32_t n,int16_t*out){int s=nr_ctx_features(b,n);if(!s)for(uint32_t i=0;i<NR_CONTEXT_BINS;i++)out[i]=nr_ctx_counts[i];return s;}
int run_apply(const uint8_t*b,uint32_t n,int32_t*z){nr_context_result_t r;return nr_context_apply(b,n,z,&r);}
