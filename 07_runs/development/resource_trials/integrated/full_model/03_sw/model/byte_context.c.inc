/* Sparse signed Unicode1..4gram INT8 context head, independent C runtime.
 * Uses learned weights, no vocabulary/phrase denylist. Normalize ASCII case and
 * a contiguous ASCII decimal run exactly as the frozen training extractor.
 * Full-count accumulation precedes clipping: saturating each update is wrong
 * when positive and negative hash collisions cancel. */
#include "byte_semantic_data.h"
#define NR_CONTEXT_BINS 2048u
#define NR_CONTEXT_ENABLED NR_MODEL_CONTEXT_ENABLED
#ifndef NR_CONTEXT_SCRATCH_ATTR
#define NR_CONTEXT_SCRATCH_ATTR
#endif
static int16_t nr_ctx_counts[NR_CONTEXT_BINS] NR_CONTEXT_SCRATCH_ATTR;
/* At most494 global+position visits for64 normalizedcodepoints.
 * Entries0..499 hold unique bins;entry511 holds their count. Bits,not a zero count,track membership because
 * signed collisions may cancel to zero and later become nonzero again. */
static uint32_t nr_ctx_seen[NR_CONTEXT_BINS/32u] NR_CONTEXT_SCRATCH_ATTR;
static uint16_t nr_ctx_touched[512] NR_CONTEXT_SCRATCH_ATTR;
typedef nr_context_t nr_context_result_t;
static void nr_ctx_add(uint32_t bin,uint32_t negative,uint32_t *used) {
    uint32_t word=bin>>5,bit=1u<<(bin&31u);
    if(!(nr_ctx_seen[word]&bit)){nr_ctx_seen[word]|=bit;nr_ctx_counts[bin]=0;nr_ctx_touched[(*used)++]=(uint16_t)bin;}
    nr_ctx_counts[bin]+=negative?-1:1;
}
static int nr_ctx_features(const uint8_t *b,uint32_t n) {
    uint32_t chars[64],i=0,k=0,j,width,h,v,cp,need,used=0,mid;int digit=0;
    for(j=0;j<NR_CONTEXT_BINS/32u;j++)nr_ctx_seen[j]=0;
    nr_ctx_touched[511]=0;
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
    mid=(k+1u)/2u;
    for(i=0;i<k;i++) {
        h=2166136261u;
        for(width=1;width<=4u&&i+width<=k;width++) {
            h=(h^chars[i+width-1u])*16777619u;v=h^(h>>16)^(width*0x9e3779b9u);
            nr_ctx_add(v&1023u,v&1024u,&used);
            if(i<mid&&i+width<=mid)nr_ctx_add(1024u+(v&511u),v&512u,&used);
            else if(i>=mid)nr_ctx_add(1536u+(v&511u),v&512u,&used);
        }
    }
    nr_ctx_touched[511]=(uint16_t)used;return 0;
}
static int32_t nr_ctx_round(int32_t v) {return v>=0?(v+32)/64:-((-v+32)/64);}
static void nr_context_select(nr_context_result_t *out,uint32_t bucket,uint32_t source) {
    out->bucket=bucket<6u?bucket:5u;out->bucket_source=source;
    out->threshold=nr_combined_thresholds[out->bucket];out->deny=out->used&&out->margin>=out->threshold;
}
static int nr_context_apply(const uint8_t *bytes,uint32_t length,int32_t logits[6],nr_context_result_t *out) {
    uint32_t i,j,bin,best=0;int32_t v,sum[NR_COMBINED_HIDDEN]={0},scores[NR_COMBINED_OUTPUTS];
    (void)logits;
    out->used=out->deny=out->nonzero_features=out->scalar_macs=0;out->logits[0]=out->logits[1]=out->margin=0;
    nr_semantic_stats_t empty_hardware={0};out->hardware=empty_hardware;out->hardware_macs=0;
    out->bucket=5;out->bucket_source=0;out->threshold=nr_combined_thresholds[5];out->category=0;
    for(i=0;i<9;i++){out->category_logits[i]=0;}
    for(i=0;i<5;i++){out->tool_logits[i]=0;}
    for(i=0;i<64;i++)out->hidden[i]=0;
    if(!NR_CONTEXT_ENABLED)return 0;
    if(nr_ctx_features(bytes,length))return -1;
    for(i=0;i<nr_ctx_touched[511];i++)if(nr_ctx_counts[nr_ctx_touched[i]])out->nonzero_features++;
    if(selected_semantic_backend&&out->nonzero_features>=24u) {
        if(selected_semantic_backend(&nr_combined_w1[0][0],nr_combined_b1,&nr_combined_w2[0][0],nr_combined_b2,
            nr_ctx_counts,nr_ctx_touched,nr_ctx_touched[511],NR_COMBINED_HIDDEN,NR_COMBINED_OUTPUTS,scores,out->hidden,&out->hardware))return NR_GEMV_FATAL;
        out->hardware_macs=selected_semantic_backend==nr_semantic_cached_gemv?nr_semantic_cached_last_macs():NR_COMBINED_HIDDEN*(NR_CONTEXT_BINS+NR_COMBINED_OUTPUTS);
    } else {
    for(i=0;i<nr_ctx_touched[511];i++) {
        bin=nr_ctx_touched[i];v=nr_ctx_counts[bin];if(!v)continue;
        if(v>3)v=3;else if(v< -3)v=-3;v*=8;
        for(j=0;j<NR_COMBINED_HIDDEN;j++)sum[j]+=v*nr_combined_w1[j][bin];
    }
    for(j=0;j<NR_COMBINED_HIDDEN;j++){v=nr_ctx_round(sum[j])+nr_combined_b1[j];out->hidden[j]=(int8_t)(v<0?0:v>127?127:v);}
    for(i=0;i<NR_COMBINED_OUTPUTS;i++) {
        v=0;for(j=0;j<NR_COMBINED_HIDDEN;j++)v+=(int32_t)out->hidden[j]*nr_combined_w2[i][j];
        scores[i]=nr_ctx_round(v)+nr_combined_b2[i];
    }
    }
    out->used=1;out->scalar_macs=out->hardware.used?0u:NR_COMBINED_HIDDEN*(out->nonzero_features+NR_COMBINED_OUTPUTS);
    out->logits[0]=scores[0];out->logits[1]=scores[1];out->margin=scores[1]-scores[0];
    for(i=0;i<9;i++){out->category_logits[i]=scores[2+i];if(scores[2+i]>scores[2+best])best=i;}
    for(i=0;i<5;i++)out->tool_logits[i]=scores[11+i];
    out->category=best;nr_context_select(out,5u,0u);return 0;
}
static uint32_t nr_context_repair(int32_t logits[6],int32_t delta[5]) {
    uint32_t i,j,bin;int32_t v,sums[5]={0};
    for(j=0;j<5;j++)delta[j]=0;
    if(!NR_CONTEXT_ENABLED)return 0;
    for(j=0;j<5;j++)if(logits[j]>=logits[5])return 0;
    for(i=0;i<nr_ctx_touched[511];i++) {
        bin=nr_ctx_touched[i];if(bin>=1024u)continue;v=nr_ctx_counts[bin];if(!v)continue;if(v>3)v=3;else if(v< -3)v=-3;v*=8;
        for(j=0;j<5;j++)sums[j]+=v*nr_combined_repair_weight[j][bin];
    }
    for(j=0;j<5;j++){delta[j]=nr_ctx_round(sums[j])+nr_combined_repair_bias[j];logits[j]+=delta[j];}
    return 1;
}
