#include "byte_tool_model.h"
#include "byte_tool_xnd.h"
#include "semantic_cached.h"
#include "tensor_plan.h"
#include "semantic_xnd.h"
#include "../xnd_runtime/xnd_mmio.h"

/* 只有调用者buffer不在共享AI区时才复制。模型自身workspace走零复制路径。 */
static int8_t input_stage[256] __attribute__((section(".ai_scratch"),aligned(4)));
static int32_t output_stage[256] __attribute__((section(".ai_scratch"),aligned(4)));
static nr_model_xnd_stats_t stats;
static nr_xnd_mode_t mode;
static nr_tensor_residence_t residence;
static int ai_pointer(const void *p,uint32_t bytes) {
    uintptr_t a=(uintptr_t)p;
    return a>=XND_AI_RAM_START && a<XND_AI_RAM_END &&
           bytes<=XND_AI_RAM_END-a && (a&3u)==0;
}
static int fail(int status) {
    stats.failures++;nr_tensor_reset(&residence);
    /* 超时后DMA可能仍写raw；这时必须中止推理，不能软件回退。 */
    return (XND_STATUS&XND_BUSY_MASK)?NR_GEMV_FATAL:status;
}
static const int32_t *pp_bias;
static uint32_t pp_shift,pp_mode;
int nr_model_xnd_gemv(const uint8_t *w,const int8_t *a,int32_t *y,
                       uint32_t rows,uint32_t cols,uint32_t flags) {
    xnd_job_t job;
    uint32_t i,weight_bytes,slot=0;
    int status,reuse;
    uintptr_t weight=(uintptr_t)w;
    const int8_t *input=a;
    int32_t *output=y;
    uint32_t out_bytes=pp_bias?rows:rows*4;
    if(!cols || cols>256 || !rows || rows>256 || cols%8) return fail(-1);
    weight_bytes=rows*(cols/2);
    if((weight&3u) || weight>=XND_AI_RAM_END || weight_bytes>XND_AI_RAM_END-weight)
        return fail(-1);
    /* 实际只有2x256B activation槽；生命周期计划不能超过真实容量。
       单槽模式与双槽模式使用同一LOAD/GEMV硬件，只有slot选择和last-use不同。 */
    status=nr_tensor_choose(&residence,(uint32_t)mode,a,cols,flags,
                            (XND_STATUS>>8)&3u,&slot,&reuse);
    if(status) return fail(status);
    if(!reuse && !ai_pointer(a,cols)) {
        for(i=0;i<cols;i++) input_stage[i]=a[i];
        input=input_stage;
    }
    if(!ai_pointer(y,out_bytes)) {if(pp_bias)return NR_GEMV_FATAL;output=output_stage;}
    job.activation_addr=(uint32_t)(uintptr_t)input;
    job.weight_addr=(uint32_t)weight;
    job.output_addr=(uint32_t)(uintptr_t)output;
    job.columns=cols;job.rows=rows;job.weight_stride_bytes=cols/2;
    job.control=XND_CTRL_INT4;job.slot=slot;
    if(!reuse) {
        nr_tensor_release(&residence,slot);
        xnd_ack();status=xnd_load_activation(&job);
        if(!status) status=xnd_wait(1000000u);
        if(status) return fail(status);
        stats.loads++;stats.activation_dma_bytes+=XND_DMA_READ_BYTES;
        stats.hardware_cycles+=XND_CYCLES;
        nr_tensor_commit(&residence,slot,a,cols);
    } else stats.reuses++;
    XND_BIAS_ADDR=(uint32_t)(uintptr_t)pp_bias;
    XND_POST_CFG=pp_bias?(1u|(pp_mode<<1)|(pp_shift<<3)):0;
    xnd_ack();status=xnd_launch_gemv(&job);
    if(!status) status=xnd_wait(1000000u);
    if(status) return fail(status);
    stats.jobs++;stats.hardware_cycles+=XND_CYCLES;
    if(pp_bias) {
        uint32_t bias_bytes=rows*4u,residual_bytes=pp_mode==2?rows*4u:0u;
        uint32_t reads=XND_DMA_READ_BYTES;
        if(reads<weight_bytes+bias_bytes+residual_bytes)return fail(NR_GEMV_FATAL);
        stats.bias_dma_bytes+=bias_bytes;stats.residual_dma_bytes+=residual_bytes;
        stats.weight_dma_bytes+=reads-bias_bytes-residual_bytes;
    } else stats.weight_dma_bytes+=XND_DMA_READ_BYTES;
    stats.output_dma_bytes+=XND_DMA_WRITE_BYTES;
    if(output!=y) for(i=0;i<rows;i++) y[i]=output_stage[i];
    if(flags&NR_GEMV_LAST_USE) nr_tensor_release(&residence,slot);
    return 0;
}
void nr_model_xnd_set_mode(nr_xnd_mode_t selected) {
    mode=(unsigned)selected<=NR_XND_LIFETIME?selected:NR_XND_SOFTWARE;
    nr_tensor_reset(&residence);
    nr_model_set_gemv_backend(mode==NR_XND_SOFTWARE?0:nr_model_xnd_gemv);
    nr_model_set_semantic_backend(mode==NR_XND_SOFTWARE?0:(NR_RESOURCE_CACHE_BACKEND?nr_semantic_cached_gemv:nr_semantic_xnd_gemv));
}
void nr_model_enable_xnd(int enabled) {
    nr_model_xnd_set_mode(enabled?NR_XND_RESIDENT:NR_XND_SOFTWARE);
}
void nr_model_xnd_reset_stats(void) {
    nr_model_xnd_stats_t empty={0};stats=empty;nr_tensor_reset(&residence);
}
nr_model_xnd_stats_t nr_model_xnd_stats(void) {return stats;}

int nr_model_xnd_gemv_post(const uint8_t *w,const int8_t *a,int8_t *y,
       uint32_t rows,uint32_t cols,const int32_t *bias,uint32_t shift,uint32_t post,uint32_t flags) {
    int result;
    if(!bias || shift>31 || post>2)return NR_GEMV_FATAL;
    pp_bias=bias;pp_shift=shift;pp_mode=post;
    result=nr_model_xnd_gemv(w,a,(int32_t*)y,rows,cols,flags);
    pp_bias=0;
    return result?NR_GEMV_FATAL:0;
}
