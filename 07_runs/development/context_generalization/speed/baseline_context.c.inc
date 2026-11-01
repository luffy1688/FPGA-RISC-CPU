/* Sparse signed Unicode1..4gram INT8 context head, independent C runtime.
 * Uses learned weights, no vocabulary/phrase denylist. Normalize ASCII case and
 * a contiguous ASCII decimal run exactly as the frozen training extractor.
 * Full-count accumulation precedes clipping: saturating each update is wrong
 * when positive and negative hash collisions cancel. */
#include "baseline_context_data.h"
#ifndef NR_CONTEXT_SCRATCH_ATTR
#define NR_CONTEXT_SCRATCH_ATTR
#endif
static int16_t nr_ctx_counts[NR_CONTEXT_BINS] NR_CONTEXT_SCRATCH_ATTR;
typedef nr_context_t nr_context_result_t;
static int nr_ctx_features(const uint8_t *b,uint32_t n) {
    uint32_t chars[64],i=0,k=0,j,width,h,v,cp,need;int digit=0;
    for(j=0;j<NR_CONTEXT_BINS;j++)nr_ctx_counts[j]=0;
    if(n>64u)return -1;
    while(i<n) {
        uint8_t a=b[i++],lo=0x80u,hi=0xbfu;
        if(!a)return -1;
        if(a<0x80u){cp=a;need=0;}
        else if(a>=0xc2u&&a<=0xdfu){cp=a&31u;need=1;}
        else if(a>=0xe0u&&a<=0xefu){cp=a&15u;need=2;if(a==0xe0u)lo=0xa0u;if(a==0xedu)hi=0x9fu;}
        else if(a>=0xf0u&&a<=0xf4u){cp=a&7u;need=3;if(a==0xf0u)lo=0x90u;if(a==0xf4u)hi=0x8fu;}
        else return -1;
        if(need) {
            if(n-i<need||b[i]<lo||b[i]>hi)return -1;
            for(j=0;j<need;j++){if(b[i+j]<0x80u||b[i+j]>0xbfu)return -1;cp=(cp<<6)|(b[i+j]&63u);}i+=need;
        }
        if(cp>=65u&&cp<=90u)cp+=32u;
        if(cp>=48u&&cp<=57u){if(digit)continue;cp=35u;digit=1;}else digit=0;
        chars[k++]=cp;
    }
    for(i=0;i<k;i++) {
        h=2166136261u;
        for(width=1;width<=4u&&i+width<=k;width++) {
            h=(h^chars[i+width-1u])*16777619u;
            v=h^(h>>16)^(width*0x9e3779b9u);
            nr_ctx_counts[v&(NR_CONTEXT_BINS-1u)]+=(v&NR_CONTEXT_BINS)?-1:1;
        }
    }
    return 0;
}
static int32_t nr_ctx_round(int32_t v) {
    return v>=0?(v+32)/64:-((-v+32)/64);
}
static int nr_context_apply(const uint8_t *bytes,uint32_t length,int32_t logits[6],nr_context_result_t *out) {
    uint32_t i,k;int32_t sum[2]={0,0},v,max_nonreject,bump;
    out->used=out->deny=out->nonzero_features=out->scalar_macs=0;
    out->logits[0]=out->logits[1]=out->margin=0;out->threshold=NR_CONTEXT_THRESHOLD;
    if(!NR_CONTEXT_ENABLED)return 0;
    if(nr_ctx_features(bytes,length))return -1;
    for(i=0;i<NR_CONTEXT_BINS;i++) {
        v=nr_ctx_counts[i];if(!v)continue;if(v>3)v=3;else if(v< -3)v=-3;v*=8;
        out->nonzero_features++;
        for(k=0;k<2;k++)sum[k]+=v*nr_ctx_weights[k][i];
    }
    out->used=1;out->scalar_macs=2*out->nonzero_features;
    out->logits[0]=nr_ctx_round(sum[0])+nr_ctx_bias[0];out->logits[1]=nr_ctx_round(sum[1])+nr_ctx_bias[1];
    out->margin=out->logits[1]-out->logits[0];out->deny=out->margin>=out->threshold;
    if(out->deny) {
        max_nonreject=logits[0];for(k=1;k<5;k++)if(logits[k]>max_nonreject)max_nonreject=logits[k];
        bump=max_nonreject+out->margin-out->threshold+1;
        if(logits[5]<bump)logits[5]=bump;
    }
    return 0;
}
