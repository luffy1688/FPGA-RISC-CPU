#ifndef NR_SEMANTIC_XND_H
#define NR_SEMANTIC_XND_H
#include <stdint.h>
/* Independent context-head hardware counters. These do not belong to the
 * encoder GEMV counters. Loads/jobs count successful completions; after a
 * failure they cover completed operations only,not a still-active DMA. */
typedef struct {
    uint32_t used,loads,jobs,dma_read_bytes,dma_write_bytes,engine_cycles,failures;
} nr_semantic_stats_t;
/* weights: row-major signedINT8 w1[hidden][2048],w2[outputs][hidden].
 * Current bounds:hidden1..64,multipleof4;outputs1..16.
 * counts are complete signed Unicode1..4gram counts; touched contains only
 * this request's unique bin indices. Mathematical order is accumulation,
 * clipcounts[-3,3]*8,layer1 roundhalfaway/64+bias/ReLUclip[0,127],
 * layer2 roundhalfaway/64+bias. Every output is retained as INT32.
 * Success0; any descriptor/engine/busy/timeout failure returnsfatal-2.
 * No software fallback is permitted after a submitted hardware operation. */
typedef int (*nr_semantic_backend_t)(const int8_t *w1,const int32_t *b1,
    const int8_t *w2,const int32_t *b2,const int16_t *counts,
    const uint16_t *touched,uint32_t count,uint32_t hidden,uint32_t outputs,
    int32_t *scores,int8_t *hidden_out,nr_semantic_stats_t *stats);
int nr_semantic_xnd_gemv(const int8_t *w1,const int32_t *b1,
    const int8_t *w2,const int32_t *b2,const int16_t *counts,
    const uint16_t *touched,uint32_t count,uint32_t hidden,uint32_t outputs,
    int32_t *scores,int8_t *hidden_out,nr_semantic_stats_t *stats);
/* Includes all persistent buffers and the CPU initialization state.
 * It excludes the caller's feature buffers and temporary stack locals. */
uint32_t nr_semantic_xnd_workspace_bytes(void);
#endif
