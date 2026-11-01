/* 原创的 Needle-inspired 字节工具意图推理；不依赖 PyTorch 或浮点库。 */
#ifndef NR_BYTE_TOOL_MODEL_H
#define NR_BYTE_TOOL_MODEL_H
#include <stdint.h>
#include <stddef.h>
#include "semantic_xnd.h"
#ifndef NR_RESOURCE_CACHE_BACKEND
#define NR_RESOURCE_CACHE_BACKEND 1
#endif
/* Frozen d64 trunk/head plus learned Unicode 2/3-gram contextual memory.
 * Set NR_MODEL_ENGRAM_ENABLED=0 for the original-model ablation. */
#ifndef NR_MODEL_ENGRAM_ENABLED
#define NR_MODEL_ENGRAM_ENABLED 1
#endif
#define NR_MODEL_MEMORY_BYTES (NR_MODEL_ENGRAM_ENABLED?12800u:0u)
#define NR_MODEL_MEMORY_SCRATCH_BYTES (NR_MODEL_ENGRAM_ENABLED?448u:0u)
#ifndef NR_MODEL_CONTEXT_ENABLED
#define NR_MODEL_CONTEXT_ENABLED 1
#endif
#define NR_MODEL_CONTEXT_HIDDEN 64u
#define NR_MODEL_CONTEXT_OUTPUTS 16u
#define NR_MODEL_CONTEXT_BYTES (NR_MODEL_CONTEXT_ENABLED?137580u:0u)
#define NR_MODEL_CONTEXT_SCRATCH_BYTES (NR_MODEL_CONTEXT_ENABLED?5376u:0u)
#define NR_MODEL_FUSION_BYTES (NR_MODEL_CONTEXT_ENABLED?370u:0u)
#define NR_MODEL_WEIGHT_BYTES (47066u+NR_MODEL_MEMORY_BYTES+NR_MODEL_CONTEXT_BYTES+NR_MODEL_FUSION_BYTES)
#ifndef NR_OPT_Q_REUSE
#define NR_OPT_Q_REUSE 1
#endif
#ifndef NR_OPT_AV4
#define NR_OPT_AV4 1
#endif
#ifndef NR_OPT_POST_FUSE
#define NR_OPT_POST_FUSE 1
#endif
#ifndef NR_OPT_SCORE_CACHE
#define NR_OPT_SCORE_CACHE 1
#endif
#ifndef NR_OPT_QKV_CACHE
#define NR_OPT_QKV_CACHE 0
#endif
#ifndef NR_OPT_V_CACHE
#define NR_OPT_V_CACHE 1
#endif
#ifndef NR_MODEL_PROFILE
#define NR_MODEL_PROFILE 0
#endif

typedef enum {
    NR_READ_TEMP=0, NR_SET_PWM=1, NR_RUN_COREMARK=2,
    NR_READ_COUNTER=3, NR_SET_LED=4, NR_REJECT=5
} nr_tool_t;
typedef enum {
    NR_TOOL_OK=0, NR_TOOL_REJECTED=1, NR_TOOL_MISSING_ARGUMENT=2,
    NR_TOOL_OUT_OF_RANGE=3, NR_TOOL_EMPTY=4, NR_TOOL_TOO_LONG=5,
    NR_TOOL_BAD_ARGUMENT=6, NR_TOOL_BACKEND_ERROR=7, NR_TOOL_POLICY_REJECTED=8
} nr_tool_status_t;
typedef struct {
    int32_t logits[2],margin,threshold;
    uint32_t used,deny,nonzero_features,scalar_macs;
    int32_t category_logits[9];uint32_t category,bucket,bucket_source;
    nr_semantic_stats_t hardware;uint32_t hardware_macs;
    int32_t tool_logits[5];
    int8_t hidden[64];
} nr_context_t;
typedef struct {
    nr_tool_t tool;
    int32_t logits[6]; /* Joint neural INT32 scores; never calibrated probabilities. */
    int32_t margin;
    int32_t encoder_logits[6],context_logits[2],context_margin,context_threshold;
    uint32_t encoder_used,context_used,context_deny,context_features,context_scalar_macs;
    uint32_t context_cycles;
    int32_t context_category_logits[9],intent_delta[5];
    uint32_t context_category,context_bucket,context_bucket_source,intent_repair_used;
    nr_semantic_stats_t context_hardware;uint32_t context_hardware_macs;
    int32_t context_tool_logits[5],intent_cascade_delta[5];uint32_t intent_cascade_used;
    int32_t fusion_delta[5];uint32_t fusion_used;int32_t fusion_gate_margin;
} nr_prediction_t;
typedef enum {NR_OP_DEFAULT=0,NR_OP_LED_ON=1,NR_OP_LED_OFF=2} nr_tool_operation_t;
/* Explicit schemas are software routes, never neural accuracy. */
typedef enum {NR_SELECT_NEURAL=0,NR_SELECT_READ_SCHEMA=1,NR_SELECT_LED_SCHEMA=2,
              NR_SELECT_DENIED=3,NR_SELECT_PWM_SCHEMA=4,NR_SELECT_CONTEXT_DENIED=5} nr_tool_selection_t;
typedef struct {
    nr_tool_t tool;
    int32_t argument;
    nr_tool_status_t status;
    int32_t margin;
    nr_tool_operation_t operation;
    nr_tool_selection_t selection_source;
} nr_tool_request_t;

#ifndef NR_MIN_CONFIDENCE_MARGIN
#define NR_MIN_CONFIDENCE_MARGIN 16 /* 低于此分差只拒绝工具，不写外设。 */
#endif
#define NR_GEMV_FATAL (-2) /* DMA仍在运行等情况：禁止与软件回退同时写workspace。 */
#define NR_GEMV_LAST_USE 2u /* 本次GEMV后不再消费当前内容，释放驻留槽。 */
#define NR_GEMV_REUSE_INPUT 1u /* 仅在明确输入内容未改变时使用，不能按指针猜测。 */

/* backend只计算raw=sum(INT4 weight * INT8 input)，缩放和偏置由本模块处理。
   权重按[rows,cols]排列，低nibble先存第0列，cols必须为偶数。
   返回0完成，一般非0回退software，NR_GEMV_FATAL中止推理；不可异步返回。 */
typedef int (*nr_gemv_backend_t)(const uint8_t *packed_weight, const int8_t *input,
                               int32_t *raw, uint32_t rows, uint32_t cols, uint32_t flags);
void nr_model_set_gemv_backend(nr_gemv_backend_t backend);
void nr_model_set_semantic_backend(nr_semantic_backend_t backend);
/* 两开关独立：同一QKV图能公平比较三种存储策略；默认保持原token-major和标量。 */
void nr_model_set_qkv_interleaved(int enabled);
void nr_model_set_attention_dot4(int enabled);
/* 通用INT8内积；非RISC-V主机用标量fallback，不表示主机执行了自定义指令。 */
int32_t nr_model_dot_i8(const int8_t *a,const int8_t *b,uint32_t count);
int nr_model_predict(const uint8_t *bytes, uint32_t length, nr_prediction_t *prediction);
/* Compute the learned context head exactly once before any schema admission.
 * A provided context must refer to these exact bytes/length in this request. */
int nr_model_context(const uint8_t *bytes,uint32_t length,nr_context_t *context);
void nr_prediction_set_context(nr_prediction_t *prediction,const nr_context_t *context);
int nr_model_predict_with_context(const uint8_t *bytes,uint32_t length,nr_prediction_t *prediction,const nr_context_t *context);
int nr_tool_decode_fast_with_context(const uint8_t *bytes,uint32_t length,nr_tool_request_t *request,nr_context_t *context);

nr_tool_status_t nr_tool_decode(const uint8_t *bytes, uint32_t length, nr_tool_request_t *request);
nr_tool_status_t nr_tool_decode_prediction(const uint8_t *bytes, uint32_t length,
    const nr_prediction_t *prediction, nr_tool_request_t *request);
enum {NR_FAST_MISS=0,NR_FAST_HANDLED=1};
/* Learned context admission precedes explicit software schemas. MISS must go
 * through encoder inference; HANDLED can be a real context/policy rejection.
 * Use the with_context API to reuse the exact already-computed request head. */
/* Whole-input canonical ASCII grammar; no neural inference on HANDLED. */
int nr_tool_decode_machine(const uint8_t *bytes,uint32_t length,nr_tool_request_t *request);
int nr_tool_decode_fast(const uint8_t *bytes,uint32_t length,nr_tool_request_t *request);
const char *nr_tool_name(nr_tool_t tool);
uint32_t nr_model_workspace_bytes(void);
uint32_t nr_model_cached_workspace_bytes(void);
uint32_t nr_model_dimension(void);
/* 正常固件关闭插桩；专用profile固件才读额外CSR。 */
enum {NR_PROFILE_EMBEDDING,NR_PROFILE_QKV,NR_PROFILE_QK,NR_PROFILE_EXP,
      NR_PROFILE_AV,NR_PROFILE_POST,NR_PROFILE_HEAD,NR_PROFILE_COPY,NR_PROFILE_STAGES};
typedef struct {uint32_t cycles[NR_PROFILE_STAGES],intervals[NR_PROFILE_STAGES];} nr_model_profile_t;
#if defined(NR_MODEL_PROFILE) && NR_MODEL_PROFILE
void nr_model_profile_reset(void);
void nr_model_profile_get(nr_model_profile_t *out);
#endif
#endif
