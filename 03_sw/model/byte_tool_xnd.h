/* mode把纯软件、每次加载、明确驻留复用放到同一条模型路径中比较。 */
#ifndef NR_BYTE_TOOL_XND_H
#define NR_BYTE_TOOL_XND_H
#include <stdint.h>
typedef enum { NR_XND_SOFTWARE=0, NR_XND_RELOAD=1, NR_XND_RESIDENT=2, NR_XND_LIFETIME=3 } nr_xnd_mode_t;
typedef struct {
    uint32_t loads,jobs,reuses,hardware_cycles,activation_dma_bytes;
    uint32_t weight_dma_bytes,output_dma_bytes,failures;
    uint32_t bias_dma_bytes,residual_dma_bytes;
} nr_model_xnd_stats_t;
/* 对外暴露raw GEMV供同硬件调度DAG测试；不做bias/quantization。 */
int nr_model_xnd_gemv(const uint8_t *weight,const int8_t *input,int32_t *raw,
                      uint32_t rows,uint32_t cols,uint32_t flags);
/* Fused RHS shift (half away from zero), THEN bias, THEN sat8.
 * post:0 plain,1 ReLU,2 sat8-before-residual-average. CPU remains fallback.
 * Bias must be immutable physical RAM; y must be uncached aligned AI RAM.
 * Any partial DMA failure aborts inference rather than repeating an in-place residual. */
int nr_model_xnd_gemv_post(const uint8_t *weight,const int8_t *input,int8_t *output,
                      uint32_t rows,uint32_t cols,const int32_t *bias,
                      uint32_t shift,uint32_t post,uint32_t flags);
void nr_model_xnd_set_mode(nr_xnd_mode_t mode);
void nr_model_enable_xnd(int enabled); /* 兼容原入口，enabled启用驻留模式。 */
void nr_model_xnd_reset_stats(void);
nr_model_xnd_stats_t nr_model_xnd_stats(void);
#endif
