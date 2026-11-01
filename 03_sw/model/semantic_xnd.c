#include "semantic_xnd.h"
#include "../xnd_runtime/xnd_mmio.h"
#define SEM_FEATURES 2048u
#define SEM_MAX_TOUCHED 500u
#define SEM_MAX_HIDDEN 64u
#define SEM_MAX_OUTPUTS 16u
#define SEM_FATAL (-2)
#define SEM_AI __attribute__((section(".ai_scratch"),aligned(4)))
static int8_t semantic_dense[SEM_FEATURES] SEM_AI;
static uint16_t semantic_previous[512] SEM_AI;
static int8_t semantic_hidden[SEM_MAX_HIDDEN] SEM_AI;
static int32_t semantic_partial[8][SEM_MAX_HIDDEN] SEM_AI;
static int32_t semantic_raw2[SEM_MAX_OUTPUTS] SEM_AI;
/* AI_RAM is NOLOAD,so no buffer initialization may be inferred from powerup.
 * The CPU .bss state is explicitly cleared by startup and guards first use. */
static uint32_t semantic_initialized,semantic_previous_count;
uint32_t nr_semantic_xnd_workspace_bytes(void) {
    return sizeof(semantic_dense)+sizeof(semantic_previous)+sizeof(semantic_hidden)+
        sizeof(semantic_partial)+sizeof(semantic_raw2)+sizeof(semantic_initialized)+
        sizeof(semantic_previous_count);
}
static int ai_range(const void *p,uint32_t n) {
    uintptr_t a=(uintptr_t)p;
    return a>=XND_AI_RAM_START&&a<XND_AI_RAM_END&&!(a&3u)&&n<=XND_AI_RAM_END-a;
}
static int32_t halfaway6(int32_t x) {
    return x>=0?(x+32)/64:-((-x+32)/64);
}
static int failure(nr_semantic_stats_t *s) {
    if(s)s->failures++;
    return SEM_FATAL;
}
static int invalidate_slots(void) {
    if(XND_STATUS&XND_BUSY_MASK)return SEM_FATAL;
    if(xnd_invalidate(0)||xnd_invalidate(1))return SEM_FATAL;
    xnd_fence();return 0;
}
static void collect_completed(nr_semantic_stats_t *s) {
    s->engine_cycles+=XND_CYCLES;
    s->dma_read_bytes+=XND_DMA_READ_BYTES;
    s->dma_write_bytes+=XND_DMA_WRITE_BYTES;
}
static int gemv(const int8_t *input,const int8_t *weight,int32_t *output,
                uint32_t rows,uint32_t cols,uint32_t stride,uint32_t slot,
                nr_semantic_stats_t *s) {
    int status;
    xnd_job_t j={(uint32_t)(uintptr_t)input,(uint32_t)(uintptr_t)weight,
        (uint32_t)(uintptr_t)output,cols,rows,stride,0,slot};
    /* control0 selects INT8 weights; plain INT32 raw output. Quantizing the
     * four first-layer partials separately would change the model. */
    XND_POST_CFG=0;xnd_ack();status=xnd_load_activation(&j);
    if(status)return SEM_FATAL;
    s->used=1;status=xnd_wait(1000000u);
    if(status)return SEM_FATAL;
    s->loads++;collect_completed(s);
    xnd_ack();status=xnd_launch_gemv(&j);
    if(status)return SEM_FATAL;
    status=xnd_wait(1000000u);
    if(status)return SEM_FATAL;
    s->jobs++;collect_completed(s);return 0;
}
int nr_semantic_xnd_gemv(const int8_t *w1,const int32_t *b1,
    const int8_t *w2,const int32_t *b2,const int16_t *counts,
    const uint16_t *touched,uint32_t count,uint32_t hidden,uint32_t outputs,
    int32_t *scores,int8_t *hidden_out,nr_semantic_stats_t *stats) {
    uint32_t i,row,chunk,index;nr_semantic_stats_t empty={0};
    if(!stats)return SEM_FATAL;
    *stats=empty;
    if(!counts||!touched||!scores||!hidden_out||!b1||!b2||count>SEM_MAX_TOUCHED||
       !hidden||hidden>SEM_MAX_HIDDEN||(hidden&3u)||!outputs||outputs>SEM_MAX_OUTPUTS||
       !ai_range(w1,hidden*SEM_FEATURES)||!ai_range(w2,outputs*hidden))return failure(stats);
    for(i=0;i<count;i++)if(touched[i]>=SEM_FEATURES)return failure(stats);
    /* Own the two physical slots only while idle. On success both are
     * invalidated,so the encoder residence planner cannot reuse stale data. */
    if(invalidate_slots())return failure(stats);
    if(!semantic_initialized) {
        for(i=0;i<SEM_FEATURES;i++)semantic_dense[i]=0;
        semantic_initialized=1;
    } else for(i=0;i<semantic_previous_count;i++)semantic_dense[semantic_previous[i]]=0;
    semantic_previous_count=0;
    for(i=0;i<count;i++) {
        int32_t v;index=touched[i];v=counts[index];
        if(v>3)v=3;else if(v< -3)v=-3;
        semantic_dense[index]=(int8_t)(v*8);
        /* Save even a canceled bin. Reset remains correct for the next
         * request and repeated use never assumes old NOLOAD contents. */
        semantic_previous[semantic_previous_count++]=(uint16_t)index;
    }
    for(chunk=0;chunk<8;chunk++)if(gemv(semantic_dense+chunk*256,
        w1+chunk*256,semantic_partial[chunk],hidden,256,SEM_FEATURES,chunk&1,stats))return failure(stats);
    for(row=0;row<hidden;row++) {
        int32_t sum=0,v;for(chunk=0;chunk<8;chunk++)sum+=semantic_partial[chunk][row];
        v=halfaway6(sum)+b1[row];semantic_hidden[row]=v<0?0:v>127?127:(int8_t)v;
    }
    if(gemv(semantic_hidden,w2,semantic_raw2,outputs,hidden,hidden,0,stats))return failure(stats);
    for(row=0;row<hidden;row++)hidden_out[row]=semantic_hidden[row];
    for(row=0;row<outputs;row++)scores[row]=halfaway6(semantic_raw2[row])+b2[row];
    if(invalidate_slots())return failure(stats);
    return 0;
}
