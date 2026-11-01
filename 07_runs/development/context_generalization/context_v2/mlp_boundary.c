#include <stdint.h>
#define NR_CONTEXT_BINS 1024u
#define NR_CONTEXT_SCRATCH_ATTR
#include "byte_context_mlp_data.h"
static int16_t nr_ctx_counts[NR_CONTEXT_BINS] NR_CONTEXT_SCRATCH_ATTR;
/* At most4*64-6=250 feature visits. Entries0..249 hold unique bins;
 * entry255 holds their count. Bits,not a zero count,track membership because
 * signed collisions may cancel to zero and later become nonzero again. */
static uint32_t nr_ctx_seen[NR_CONTEXT_BINS/32u] NR_CONTEXT_SCRATCH_ATTR;
static uint16_t nr_ctx_touched[256] NR_CONTEXT_SCRATCH_ATTR;

static int nr_ctx_features(const uint8_t *b,uint32_t n) {
    uint32_t chars[64],i=0,k=0,j,width,h,v,cp,need,bin,word,bit,used=0;int digit=0;
    for(j=0;j<NR_CONTEXT_BINS/32u;j++)nr_ctx_seen[j]=0;
    nr_ctx_touched[255]=0;
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
            bin=v&(NR_CONTEXT_BINS-1u);word=bin>>5;bit=1u<<(bin&31u);
            if(!(nr_ctx_seen[word]&bit)) {
                nr_ctx_seen[word]|=bit;nr_ctx_counts[bin]=0;
                nr_ctx_touched[used++]=(uint16_t)bin;
            }
            nr_ctx_counts[bin]+=(v&NR_CONTEXT_BINS)?-1:1;
        }
    }
    nr_ctx_touched[255]=(uint16_t)used;
    return 0;
}

#include "byte_context_mlp_kernel.c.inc"
int mlp(const uint8_t*b,uint32_t n,int32_t*out,uint32_t*nonzero,uint32_t*macs){if(nr_ctx_features(b,n))return -1;*macs=nr_ctx_mlp_scores(out,nonzero);return 0;}
