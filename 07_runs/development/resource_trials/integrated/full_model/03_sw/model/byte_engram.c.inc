#include "byte_engram_data.h"
/* Candidate-only independently written compact Engram branch; inspired by
 * cactus-compute/needle architecture.py (Apache-2.0). See 07_runs/development/engram_lite/report.json.
 * Two learned hash tables + contextual hard-sigmoid gate, no text rules. */
#ifndef NR_ENGRAM_DISABLE
#define NR_ENGRAM_DISABLE 0
#endif
static const nr_linear_t eg_key={nr_memory_key_weight,nr_memory_key_bias,NR_MEMORY_KEY_WEIGHT_SHIFT,64,64};
static const nr_linear_t eg_value={nr_memory_value_weight,nr_memory_value_bias,NR_MEMORY_VALUE_WEIGHT_SHIFT,64,64};
typedef struct {int32_t sum[64];int8_t e[64],key[64],value[64];} nr_engram_scratch_t;
static nr_engram_scratch_t eg __attribute__((section(".ai_scratch"),aligned(4)));
/* Decode Unicode scalar values; reject malformed UTF-8 rather than guessing. */
static int eg_next(const uint8_t *b,uint32_t n,uint32_t *at,uint32_t *code){
    uint32_t i=*at,c=b[i++],k,min;
    if(c<128){*at=i;*code=c>='A'&&c<='Z'?c+32:c;return 0;}
    if(c>=0xc2&&c<=0xdf){k=1;c&=31;min=0x80;}
    else if(c>=0xe0&&c<=0xef){k=2;c&=15;min=0x800;}
    else if(c>=0xf0&&c<=0xf4){k=3;c&=7;min=0x10000;}
    else return -1;
    if(n-i<k)return -1;
    while(k--){if((b[i]&0xc0)!=0x80)return -1;c=(c<<6)|(b[i++]&63);}
    if(c<min||c>0x10ffff||(c>=0xd800&&c<=0xdfff))return -1;
    *at=i;*code=c;return 0;
}
static uint32_t eg_slot(const uint32_t *recent,uint32_t order){
    uint32_t j,acc=0x9e3779b9u*(order-1u);
    for(j=0;j<order;j++)acc=(acc^recent[j])*0x01000193u;
    return (acc^(acc>>15))&255u;
}
static int nr_engram_mix(const uint8_t *bytes,uint32_t length){
    uint32_t order,at=0,c,n=0,recent[3]={0,0,0},code;int32_t dot=0,gate;
    if(NR_ENGRAM_DISABLE)return 0;
    for(c=0;c<64;c++)eg.sum[c]=0;
    while(at<length){
        if(eg_next(bytes,length,&at,&code))return NR_GEMV_FATAL;
        recent[2]=recent[1];recent[1]=recent[0];recent[0]=code;n++;
        for(order=2;order<=3;order++)if(n>=order){
            const uint8_t *table=order==2?nr_memory_emb2_weight:nr_memory_emb3_weight;
            int shift=order==2?NR_MEMORY_EMB2_WEIGHT_SHIFT:NR_MEMORY_EMB3_WEIGHT_SHIFT;
            uint32_t offset=(order-2)*32,slot=eg_slot(recent,order);
            for(c=0;c<32;c++)eg.sum[offset+c]+=saturate(rounded_shift(signed4(table,slot*32+c),shift-5));
        }
    }
    for(order=2;order<=3;order++){
        uint32_t offset=(order-2)*32,count=n>=order?n-order+1:1;
        for(c=0;c<32;c++)eg.e[offset+c]=saturate(rounded_div(eg.sum[offset+c],count));
    }
    if(linear_one(&eg_key,eg.e,eg.key,0,0,0))return NR_GEMV_FATAL;
    if(linear_one(&eg_value,eg.e,eg.value,0,NR_GEMV_REUSE_INPUT|NR_GEMV_LAST_USE,0))return NR_GEMV_FATAL;
    for(c=0;c<64;c++)dot+=(int32_t)ws.pooled[c]*eg.key[c];
    gate=128+rounded_shift(dot,7);if(gate<0)gate=0;if(gate>256)gate=256;
    for(c=0;c<64;c++){
        int32_t mem=rounded_shift((int32_t)eg.value[c]*gate,8);
        ws.pooled[c]=saturate(rounded_div(2*(int32_t)ws.pooled[c]+mem,2));
    }
    return 0;
}
