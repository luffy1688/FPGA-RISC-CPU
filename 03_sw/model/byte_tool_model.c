/* 先让整数模型跑通，再将 GEMV 换成 XND：算法和硬件接口互相独立。
   每个名字说明用途：q/k/v是注意力的查询/键/值，ff是前馈层。 */
#include "byte_tool_model.h"
#include "byte_tool_xnd.h"
#include "semantic_cached.h"
#ifndef NR_OPT_XND_POSTPROCESS
#define NR_OPT_XND_POSTPROCESS 1
#endif
#ifndef NR_MODEL_DATA_HEADER
#define NR_MODEL_DATA_HEADER "byte_model_data.h"
#endif
#include NR_MODEL_DATA_HEADER

/* 同一源码的逐项消融开关；模型数学定义与权重不变。 */
#ifndef NR_OPT_Q_REUSE
#define NR_OPT_Q_REUSE 1
#endif
#ifndef NR_OPT_AV4
#define NR_OPT_AV4 1
#endif
#ifndef NR_OPT_POST_FUSE
#define NR_OPT_POST_FUSE 1
#endif
#ifndef NR_MODEL_PROFILE
#define NR_MODEL_PROFILE 0
#endif
#if NR_MODEL_PROFILE
static nr_model_profile_t profile;
static uint32_t profile_cycle(void) {
#if defined(__riscv)
    uint32_t value;
    __asm__ volatile("csrr %0,mcycle":"=r"(value)::"memory");
    return value;
#else
    return 0; /* host只查数值，不把host时间当软核周期。 */
#endif
}
#define PROFILE_BEGIN(name) uint32_t name=profile_cycle()
#define PROFILE_END(stage,name) do {profile.cycles[stage]+=profile_cycle()-(name);profile.intervals[stage]++;} while(0)
void nr_model_profile_reset(void) {uint32_t i;for(i=0;i<NR_PROFILE_STAGES;i++){profile.cycles[i]=0;profile.intervals[i]=0;}}
void nr_model_profile_get(nr_model_profile_t *out) {*out=profile;}
#else
#define PROFILE_BEGIN(name)
#define PROFILE_END(stage,name)
#endif


typedef struct {
    const uint8_t *weight;
    const int32_t *bias;
    int shift;
    uint32_t rows, cols;
} nr_linear_t;
/* 预处理器宏区分大小写，直接列出参数便于初学者找到对应矩阵。 */
static const nr_linear_t layers[2][6] = {
    {
      {nr_blocks_0_q_weight,nr_blocks_0_q_bias,NR_BLOCKS_0_Q_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_0_k_weight,nr_blocks_0_k_bias,NR_BLOCKS_0_K_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_0_v_weight,nr_blocks_0_v_bias,NR_BLOCKS_0_V_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_0_o_weight,nr_blocks_0_o_bias,NR_BLOCKS_0_O_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_0_ff1_weight,nr_blocks_0_ff1_bias,NR_BLOCKS_0_FF1_WEIGHT_SHIFT,2*NR_D,NR_D},
      {nr_blocks_0_ff2_weight,nr_blocks_0_ff2_bias,NR_BLOCKS_0_FF2_WEIGHT_SHIFT,NR_D,2*NR_D}
    },
    {
      {nr_blocks_1_q_weight,nr_blocks_1_q_bias,NR_BLOCKS_1_Q_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_1_k_weight,nr_blocks_1_k_bias,NR_BLOCKS_1_K_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_1_v_weight,nr_blocks_1_v_bias,NR_BLOCKS_1_V_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_1_o_weight,nr_blocks_1_o_bias,NR_BLOCKS_1_O_WEIGHT_SHIFT,NR_D,NR_D},
      {nr_blocks_1_ff1_weight,nr_blocks_1_ff1_bias,NR_BLOCKS_1_FF1_WEIGHT_SHIFT,2*NR_D,NR_D},
      {nr_blocks_1_ff2_weight,nr_blocks_1_ff2_bias,NR_BLOCKS_1_FF2_WEIGHT_SHIFT,NR_D,2*NR_D}
    }
};
static const nr_linear_t head={
 nr_head_weight,nr_head_bias,NR_HEAD_WEIGHT_SHIFT,NR_CLASSES,NR_D
};
typedef struct { int32_t score[NR_SEQ],exp_weight[NR_SEQ]; } nr_attention_scratch_t;
typedef struct {
    int8_t x[NR_SEQ*NR_D],q[NR_SEQ*NR_D],k[NR_SEQ*NR_D],v[NR_SEQ*NR_D];
    int8_t context[NR_SEQ*NR_D],ff[2*NR_D],pooled[NR_D];
    int32_t raw[2*NR_D];
#if !NR_OPT_SCORE_CACHE
    nr_attention_scratch_t attention;
#endif
} nr_workspace_t;
/* 裸机linker把.ai_scratch放到0x20000开始的uncached共享区，DMA才不会读旧数据。
   host测试将这个普通静态section交给操作系统即可。没有malloc。 */
#if defined(__GNUC__)
static nr_workspace_t ws __attribute__((section(".ai_scratch"),aligned(4)));
#else
static nr_workspace_t ws;
#endif
/* CPU-only attention temporaries need no DMA visibility. Q/K/V retain their
 * uncached producer buffers; an optional explicit copy cannot expose stale DMA.
 * Buffer planning idea: CMSIS-NN scratch APIs (Apache-2.0), independently written
 * for this RV32 model; no Arm kernel code or quantization routine is copied. */
#if NR_OPT_SCORE_CACHE
static nr_attention_scratch_t attention_cache;
#define ATTN_WS attention_cache
#else
#define ATTN_WS ws.attention
#endif
#if NR_OPT_QKV_CACHE
static int8_t qkv_cache[3][NR_SEQ*NR_D] __attribute__((aligned(16)));
#elif NR_OPT_V_CACHE
static uint32_t v_cache[NR_D/4][NR_SEQ] __attribute__((aligned(16)));
#endif
static nr_gemv_backend_t selected_backend;
static nr_semantic_backend_t selected_semantic_backend;
static int qkv_interleaved;
static int attention_dot4;
void nr_model_set_qkv_interleaved(int enabled) {qkv_interleaved=enabled!=0;}
void nr_model_set_attention_dot4(int enabled) {attention_dot4=enabled!=0;}

static uint32_t pack4(const int8_t *p) {
    /* memcpy允许别名且不要求输入对齐；对齐分支帮助编译器生成一次LW。 */
    uint32_t result;
#if defined(__GNUC__)
    if(((uintptr_t)p&3u)==0) {
        const void *aligned=__builtin_assume_aligned(p,4);
        __builtin_memcpy(&result,aligned,4);
    } else {
        /* 当前软核对未对齐LW会陷入异常。volatile字节读取防止GCC重新合并为LW。 */
        const volatile uint8_t *byte=(const volatile uint8_t *)p;
        result=(uint32_t)byte[0]|((uint32_t)byte[1]<<8)|
               ((uint32_t)byte[2]<<16)|((uint32_t)byte[3]<<24);
    }
#else
    result=(uint8_t)p[0]|((uint32_t)(uint8_t)p[1]<<8)|
           ((uint32_t)(uint8_t)p[2]<<16)|((uint32_t)(uint8_t)p[3]<<24);
#endif
    return result;
}
static int32_t dot4_word(uint32_t a,uint32_t b) {
#if defined(__riscv)
    int32_t result;
    /* RV32 custom-3: funct7=0, funct3=0，与rv32i_core.sv的0x7b实现一致。 */
    __asm__ volatile(".insn r 0x7b, 0, 0, %0, %1, %2":"=r"(result):"r"(a),"r"(b));
    return result;
#else
    int32_t result=0;
    uint32_t lane;
    for(lane=0;lane<4;lane++) {
        int32_t va=(int32_t)((a>>(8*lane))&255u);
        int32_t vb=(int32_t)((b>>(8*lane))&255u);
        if(va>=128) va-=256;
        if(vb>=128) vb-=256;
        result+=va*vb;
    }
    return result;
#endif
}
int32_t nr_model_dot_i8(const int8_t *a,const int8_t *b,uint32_t count) {
    uint32_t i=0;
    int32_t sum=0;
    /* 模型head维度16，最坏值仅16*128*128，INT32累加安全。 */
    if(attention_dot4) for(;i+4<=count;i+=4) sum+=dot4_word(pack4(a+i),pack4(b+i));
    for(;i<count;i++) sum+=(int32_t)a[i]*(int32_t)b[i];
    return sum;
}

static int32_t signed4(const uint8_t *w,uint32_t i) {
    int32_t nibble=(w[i>>1]>>((i&1)*4))&15;
    return nibble>=8?nibble-16:nibble;
}
static int32_t rounded_div(int32_t x,int32_t divisor) {
    /* 所有累加的最大值已由维度限制，不会出现INT32_MIN取负溢出。 */
    return x<0?-((-x+divisor/2)/divisor):(x+divisor/2)/divisor;
}
static int32_t rounded_shift(int32_t x,int shift) {
    if(shift<0) return x*(1<<(-shift));
    if(shift==0) return x;
    /* 2的幂用移位；正负数仍然采用原有的四舍五入规则。 */
    int32_t half=1<<(shift-1);
    return x<0?-((-x+half)>>shift):(x+half)>>shift;
}
static int8_t saturate(int32_t x) {
    if(x>127) return 127;
    if(x< -128) return -128;
    return (int8_t)x;
}
static void gemv_software(const nr_linear_t *m,const int8_t *x,int32_t *raw) {
    uint32_t r,c;
    for(r=0;r<m->rows;r++) {
        const uint8_t *row=m->weight+r*(m->cols/2);
        int32_t acc=0;
        /* 一次读取一个packed字节，解出两个有符号INT4，减少地址计算和读权重次数。 */
        for(c=0;c<m->cols;c+=2) {
            uint32_t packed=row[c/2];
            int32_t lo=(int32_t)(packed&15),hi=(int32_t)(packed>>4);
            lo=lo>=8?lo-16:lo; hi=hi>=8?hi-16:hi;
            acc+=lo*(int32_t)x[c]+hi*(int32_t)x[c+1];
        }
        raw[r]=acc;
    }
}
static int linear_one(const nr_linear_t *m,const int8_t *x,int8_t *y,int32_t *logit,
                       uint32_t flags,uint32_t post) {
    uint32_t r;
#if defined(__riscv) && NR_OPT_XND_POSTPROCESS
    /* The exact same quantization contract executes in XND only for the
     * standard hardware backend and INT8 destinations. Head logits stay INT32.
     * Model/rules and all software reference paths are unchanged. */
    if(y && selected_backend==nr_model_xnd_gemv)
        return nr_model_xnd_gemv_post(m->weight,x,y,m->rows,m->cols,m->bias,
                                      (uint32_t)m->shift,post,flags);
#endif
    int status=selected_backend?selected_backend(m->weight,x,ws.raw,m->rows,m->cols,flags):-1;
    if(status==NR_GEMV_FATAL) return NR_GEMV_FATAL;
    if(status) gemv_software(m,x,ws.raw);
#if NR_OPT_POST_FUSE
    /* Dispatch once per matrix, never inside the Q/K/V channel loop. Keep
     * saturation before residual averaging exactly as in the unfused graph. */
    if(post==2) {
        for(r=0;r<m->rows;r++) {
            int8_t quantized=saturate(rounded_shift(ws.raw[r],m->shift)+m->bias[r]);
            y[r]=saturate(rounded_div((int32_t)y[r]+quantized,2));
        }
        return 0;
    }
    if(post==1) {
        for(r=0;r<m->rows;r++) {
            int8_t quantized=saturate(rounded_shift(ws.raw[r],m->shift)+m->bias[r]);
            y[r]=quantized<0?0:quantized;
        }
        return 0;
    }
#else
    (void)post;
#endif
    for(r=0;r<m->rows;r++) {
        int32_t value=rounded_shift(ws.raw[r],m->shift)+m->bias[r];
        if(y) {
            int8_t quantized=saturate(value);
            y[r]=quantized;
        }
        if(logit) logit[r]=value;
    }
    return 0;
}
void nr_model_set_gemv_backend(nr_gemv_backend_t backend) { selected_backend=backend; }
void nr_model_set_semantic_backend(nr_semantic_backend_t backend) { selected_semantic_backend=backend; }
uint32_t nr_model_cached_workspace_bytes(void) {
    uint32_t bytes=0;
#if NR_OPT_SCORE_CACHE
    bytes+=sizeof(attention_cache);
#endif
#if NR_OPT_QKV_CACHE
    bytes+=sizeof(qkv_cache);
#elif NR_OPT_V_CACHE
    bytes+=sizeof(v_cache);
#endif
    return bytes;
}
uint32_t nr_model_workspace_bytes(void) { return sizeof(ws)+nr_model_cached_workspace_bytes()+NR_MODEL_MEMORY_SCRATCH_BYTES+NR_MODEL_CONTEXT_SCRATCH_BYTES+(NR_MODEL_CONTEXT_ENABLED?(NR_RESOURCE_CACHE_BACKEND?nr_semantic_cached_workspace_bytes():nr_semantic_xnd_workspace_bytes()):0u); }
uint32_t nr_model_dimension(void) { return NR_D; }
const char *nr_tool_name(nr_tool_t tool) {
    static const char *names[]={"read_temp","set_pwm","run_coremark","read_counter","set_led","reject"};
    return (unsigned)tool<6?names[tool]:"reject";
}
#if NR_MODEL_ENGRAM_ENABLED
#include "byte_engram.c.inc"
#endif
#define NR_CONTEXT_SCRATCH_ATTR __attribute__((section(".ai_scratch"),aligned(4)))
#include "byte_context.c.inc"
#include "byte_fusion.c.inc"
void nr_prediction_set_context(nr_prediction_t *p,const nr_context_t *c) {
    p->encoder_used=0;p->context_used=c->used;p->context_deny=c->deny;
    p->context_logits[0]=c->logits[0];p->context_logits[1]=c->logits[1];
    p->context_margin=c->margin;p->context_threshold=c->threshold;
    p->context_features=c->nonzero_features;p->context_scalar_macs=c->scalar_macs;p->context_cycles=0;
    {uint32_t i;for(i=0;i<9;i++)p->context_category_logits[i]=c->category_logits[i];for(i=0;i<5;i++){p->intent_delta[i]=0;p->intent_cascade_delta[i]=0;p->fusion_delta[i]=0;p->context_tool_logits[i]=c->tool_logits[i];}}
    p->context_category=c->category;p->context_bucket=c->bucket;p->context_bucket_source=c->bucket_source;p->intent_repair_used=0;p->intent_cascade_used=0;p->fusion_used=0;p->fusion_gate_margin=0;
    p->context_hardware=c->hardware;p->context_hardware_macs=c->hardware_macs;
}
int nr_model_context(const uint8_t *bytes,uint32_t length,nr_context_t *context) {
    int32_t unused[6]={0};
    if(!bytes||!context||!length||length>NR_SEQ)return -1;
    return nr_context_apply(bytes,length,unused,context);
}
int nr_model_predict(const uint8_t *bytes,uint32_t length,nr_prediction_t *prediction) {
    nr_context_t context;
    if(nr_model_context(bytes,length,&context))return -1;
    return nr_model_predict_with_context(bytes,length,prediction,&context);
}
int nr_model_predict_with_context(const uint8_t *bytes,uint32_t length,nr_prediction_t *prediction,const nr_context_t *context) {
    uint32_t token,d,layer,head_id,key,channel;
    const uint32_t hd=NR_D/NR_HEADS;
    if(!bytes || !prediction || !context || !length || length>NR_SEQ) return -1;
    nr_prediction_set_context(prediction,context);prediction->encoder_used=1;
    PROFILE_BEGIN(embedding_begin);
    for(token=0;token<length;token++) {
        uint8_t b=bytes[token];
        if(b>='A' && b<='Z') b=(uint8_t)(b+32);
        for(d=0;d<NR_D;d++) {
        int32_t e=rounded_shift(signed4(nr_embedding_weight,b*NR_D+d),NR_EMBEDDING_WEIGHT_SHIFT-5);
        int32_t p=rounded_shift(signed4(nr_position_weight,token*NR_D+d),NR_POSITION_WEIGHT_SHIFT-5);
        ws.x[token*NR_D+d]=saturate(rounded_div(e+p,2));
        }
    }
    PROFILE_END(NR_PROFILE_EMBEDDING,embedding_begin);
    for(layer=0;layer<NR_LAYERS;layer++) {
        PROFILE_BEGIN(qkv_begin);
        if(qkv_interleaved) {
            uint32_t first,projection,last;
            /* 同一token的三个消费者之间夹入另一个token：真实依赖图需要两个槽。
               不改矩阵或数学结果，只有GEMV提交次序变化；末尾奇数token也支持。 */
            for(first=0;first<length;first+=2) {
                last=first+2<length?first+2:length;
                for(projection=0;projection<3;projection++) for(token=first;token<last;token++) {
                    int8_t *out=projection==0?ws.q:projection==1?ws.k:ws.v;
                    uint32_t flags=projection?NR_GEMV_REUSE_INPUT:0;
                    if(projection==2) flags|=NR_GEMV_LAST_USE;
                    if(linear_one(&layers[layer][projection],ws.x+token*NR_D,
                                  out+token*NR_D,0,flags,0)) return NR_GEMV_FATAL;
                }
            }
        } else for(token=0;token<length;token++) {
            if(linear_one(&layers[layer][0],ws.x+token*NR_D,ws.q+token*NR_D,0,0,0)) return NR_GEMV_FATAL;
            if(linear_one(&layers[layer][1],ws.x+token*NR_D,ws.k+token*NR_D,0,NR_GEMV_REUSE_INPUT,0)) return NR_GEMV_FATAL;
            if(linear_one(&layers[layer][2],ws.x+token*NR_D,ws.v+token*NR_D,0,
                          NR_GEMV_REUSE_INPUT|NR_GEMV_LAST_USE,0)) return NR_GEMV_FATAL;
        }
        PROFILE_END(NR_PROFILE_QKV,qkv_begin);
        PROFILE_BEGIN(copy_begin);
        const int8_t *attention_q=ws.q,*attention_k=ws.k;
#if !NR_OPT_V_CACHE || NR_OPT_QKV_CACHE
        const int8_t *attention_v=ws.v;
#endif
#if NR_OPT_QKV_CACHE
        /* Deliberate CPU copy after synchronous GEMV completes. XND never reads
         * or writes the cached buffers; all layers refresh only valid tokens. */
        for(d=0;d<length*NR_D;d++) {
            qkv_cache[0][d]=ws.q[d];qkv_cache[1][d]=ws.k[d];qkv_cache[2][d]=ws.v[d];
        }
        attention_q=qkv_cache[0];attention_k=qkv_cache[1];attention_v=qkv_cache[2];
#elif NR_OPT_V_CACHE
        /* Store each four-channel block contiguously in key order. This is a
         * plain layout transform, not softmax approximation or changed weights. */
        for(d=0;d<NR_D;d+=4) for(token=0;token<length;token++)
            v_cache[d/4][token]=pack4(ws.v+token*NR_D+d);
#endif
        PROFILE_END(NR_PROFILE_COPY,copy_begin);
        /* attention先比较句内各个byte，再按exp查表权重混合V。
           这是双向encoder，没有autoregressive生成或KV缓存的宣传。 */
        for(token=0;token<length;token++) for(head_id=0;head_id<NR_HEADS;head_id++) {
            int32_t maximum=-2147483647,sum_exp=0;
            PROFILE_BEGIN(qk_begin);
#if NR_OPT_Q_REUSE
            if(attention_dot4 && hd==16) {
                /* 一个query/head只打包一次Q，所有key共享四个32bit值。
                   pack4保留对齐LW与字节fallback，不引入强制指针别名。 */
                const int8_t *query=attention_q+token*NR_D+head_id*hd;
                uint32_t q0=pack4(query),q1=pack4(query+4);
                uint32_t q2=pack4(query+8),q3=pack4(query+12);
                for(key=0;key<length;key++) {
                    const int8_t *kv=attention_k+key*NR_D+head_id*hd;
                    int32_t dot=dot4_word(q0,pack4(kv))+dot4_word(q1,pack4(kv+4))+
                                dot4_word(q2,pack4(kv+8))+dot4_word(q3,pack4(kv+12));
                    ATTN_WS.score[key]=rounded_shift(dot,9);
                    if(ATTN_WS.score[key]>maximum) maximum=ATTN_WS.score[key];
                }
            } else
#endif
            for(key=0;key<length;key++) {
                int32_t dot=nr_model_dot_i8(attention_q+token*NR_D+head_id*hd,
                                          attention_k+key*NR_D+head_id*hd,hd);
                ATTN_WS.score[key]=rounded_shift(dot,9);
                if(ATTN_WS.score[key]>maximum) maximum=ATTN_WS.score[key];
            }
            PROFILE_END(NR_PROFILE_QK,qk_begin);
            PROFILE_BEGIN(exp_begin);
            for(key=0;key<length;key++) {
                int32_t delta=maximum-ATTN_WS.score[key];
                ATTN_WS.exp_weight[key]=delta>128?0:nr_exp_lut[delta];
                sum_exp+=ATTN_WS.exp_weight[key];
            }
            PROFILE_END(NR_PROFILE_EXP,exp_begin);
            PROFILE_BEGIN(av_begin);
            channel=0;
#if NR_OPT_AV4
            /* 指数权重为0..4096，不能截成INT8给dot4。
               每个累加器保持原key顺序；最坏绝对和33554432。 */
            for(;channel+4<=hd;channel+=4) {
                int32_t s0=0,s1=0,s2=0,s3=0;
                for(key=0;key<length;key++) {
                    /* 只形成当前有效key地址，length=64时不产生越界尾指针。 */
                    #if NR_OPT_V_CACHE && !NR_OPT_QKV_CACHE
                    const int8_t *value=(const int8_t *)&v_cache[(head_id*hd+channel)/4][key];
#else
                    const int8_t *value=attention_v+key*NR_D+head_id*hd+channel;
#endif
                    int32_t weight=ATTN_WS.exp_weight[key];
                    s0+=weight*(int32_t)value[0];s1+=weight*(int32_t)value[1];
                    s2+=weight*(int32_t)value[2];s3+=weight*(int32_t)value[3];
                }
                int8_t *out=ws.context+token*NR_D+head_id*hd+channel;
                out[0]=saturate(rounded_div(s0,sum_exp));out[1]=saturate(rounded_div(s1,sum_exp));
                out[2]=saturate(rounded_div(s2,sum_exp));out[3]=saturate(rounded_div(s3,sum_exp));
            }
#endif
            for(;channel<hd;channel++) {
                int32_t sum=0;
                for(key=0;key<length;key++) {
#if NR_OPT_V_CACHE && !NR_OPT_QKV_CACHE
                    const int8_t *value=(const int8_t *)&v_cache[(head_id*hd+channel)/4][key];
                    sum+=ATTN_WS.exp_weight[key]*(int32_t)value[channel%4];
#else
                    sum+=ATTN_WS.exp_weight[key]*(int32_t)attention_v[key*NR_D+head_id*hd+channel];
#endif
                }
                ws.context[token*NR_D+head_id*hd+channel]=saturate(rounded_div(sum,sum_exp));
            }
            PROFILE_END(NR_PROFILE_AV,av_begin);
        }
        PROFILE_BEGIN(post_begin);
        for(token=0;token<length;token++) {
            /* 可以覆盖q，因为QKV注意力在上面已经计算完毕。 */
#if NR_OPT_POST_FUSE
            if(linear_one(&layers[layer][3],ws.context+token*NR_D,ws.x+token*NR_D,0,NR_GEMV_LAST_USE,2)) return NR_GEMV_FATAL;
            if(linear_one(&layers[layer][4],ws.x+token*NR_D,ws.ff,0,NR_GEMV_LAST_USE,1)) return NR_GEMV_FATAL;
            if(linear_one(&layers[layer][5],ws.ff,ws.x+token*NR_D,0,NR_GEMV_LAST_USE,2)) return NR_GEMV_FATAL;
#else
            if(linear_one(&layers[layer][3],ws.context+token*NR_D,ws.q+token*NR_D,0,NR_GEMV_LAST_USE,0)) return NR_GEMV_FATAL;
            for(d=0;d<NR_D;d++)
                ws.x[token*NR_D+d]=saturate(rounded_div((int32_t)ws.x[token*NR_D+d]+ws.q[token*NR_D+d],2));
            if(linear_one(&layers[layer][4],ws.x+token*NR_D,ws.ff,0,NR_GEMV_LAST_USE,0)) return NR_GEMV_FATAL;
            for(d=0;d<2*NR_D;d++) if(ws.ff[d]<0) ws.ff[d]=0;
            if(linear_one(&layers[layer][5],ws.ff,ws.q+token*NR_D,0,NR_GEMV_LAST_USE,0)) return NR_GEMV_FATAL;
            for(d=0;d<NR_D;d++)
                ws.x[token*NR_D+d]=saturate(rounded_div((int32_t)ws.x[token*NR_D+d]+ws.q[token*NR_D+d],2));
#endif
        }
        PROFILE_END(NR_PROFILE_POST,post_begin);
    }
    PROFILE_BEGIN(head_begin);
    for(d=0;d<NR_D;d++) {
        int32_t sum=0;
        for(token=0;token<length;token++) sum+=ws.x[token*NR_D+d];
        ws.pooled[d]=saturate(rounded_div(sum,length));
    }
#if NR_MODEL_ENGRAM_ENABLED
    if(nr_engram_mix(bytes,length)) return NR_GEMV_FATAL;
#endif
    if(linear_one(&head,ws.pooled,0,prediction->logits,NR_GEMV_LAST_USE,0)) return NR_GEMV_FATAL;
    for(d=0;d<6;d++)prediction->encoder_logits[d]=prediction->logits[d];
    nr_context_t selected_context=*context;uint32_t bucket=0;
    for(d=1;d<6;d++)if(prediction->encoder_logits[d]>prediction->encoder_logits[bucket])bucket=d;
    nr_context_select(&selected_context,bucket,0u);
    nr_prediction_set_context(prediction,&selected_context);prediction->encoder_used=1;
    prediction->intent_repair_used=nr_context_repair(prediction->logits,prediction->intent_delta);
    if(selected_context.used) {
        uint32_t repair_best=0;for(d=1;d<6;d++)if(prediction->logits[d]>prediction->logits[repair_best])repair_best=d;
        if(repair_best==5){prediction->intent_cascade_used=1;for(d=0;d<5;d++){prediction->intent_cascade_delta[d]=selected_context.tool_logits[d];prediction->logits[d]+=selected_context.tool_logits[d];}}
    }
    if(selected_context.used)nr_fusion_apply(prediction,&selected_context);
    context=&selected_context;
    if(context->used&&context->deny) {
        int32_t maximum=prediction->logits[0],bump;
        for(d=1;d<5;d++)if(prediction->logits[d]>maximum)maximum=prediction->logits[d];
        bump=maximum+context->margin-context->threshold+1;
        if(prediction->logits[5]<bump)prediction->logits[5]=bump;
    }
    {
        uint32_t best=0;
        int32_t second=-2147483647;
        for(d=1;d<NR_CLASSES;d++) if(prediction->logits[d]>prediction->logits[best]) best=d;
        for(d=0;d<NR_CLASSES;d++) if(d!=best && prediction->logits[d]>second) second=prediction->logits[d];
        prediction->tool=(nr_tool_t)best;
        prediction->margin=prediction->logits[best]-second;
    }
    PROFILE_END(NR_PROFILE_HEAD,head_begin);
    return 0;
}
/* Tool contract: neural scores stay observable. Only bounded read schemas and
 * explicit single-LED schemas can recover a rejected prediction. No action may
 * be substituted for an unsupported requested capability. */
static uint8_t lower_ascii(uint8_t c) {return c>='A'&&c<='Z'?(uint8_t)(c+32):c;}
static int ascii_letter(uint8_t c) {c=lower_ascii(c);return c>='a'&&c<='z';}
/* A per-request first-byte position index bounds dictionary lookup to plausible
 * starts. Buckets only select candidates: the complete bytes and original
 * ASCII word boundaries are still checked, including on trimmed subranges. */
#define NR_TERM_BUCKETS 256u
typedef struct {
    const uint8_t *bytes;
    union {uint16_t head[NR_TERM_BUCKETS];uint32_t words[NR_TERM_BUCKETS/2u];} bucket;
    uint16_t next[NR_SEQ];
} nr_term_scan_t;
static void term_scan_init(nr_term_scan_t *scan,const uint8_t *b,uint32_t n) {
    uint32_t i,bucket;
    scan->bytes=b;
    for(i=0;i<NR_TERM_BUCKETS/2u;i++)scan->bucket.words[i]=NR_SEQ*0x00010001u;
    for(i=n;i>0;) {
        --i;bucket=lower_ascii(b[i])&(NR_TERM_BUCKETS-1u);
        scan->next[i]=scan->bucket.head[bucket];scan->bucket.head[bucket]=(uint16_t)i;
    }
}
static int has_term(const uint8_t *b,uint32_t length,const char *term,int word) {
    uint32_t at,i,n=0;
    while(term[n]) n++;
    if(n>length) return 0;
    for(at=0;at+n<=length;at++) {
        for(i=0;i<n;i++) if(lower_ascii(b[at+i])!=lower_ascii((uint8_t)term[i])) break;
        if(i==n && (!word || ((at==0 || !ascii_letter(b[at-1])) &&
                    (at+n==length || !ascii_letter(b[at+n]))))) return 1;
    }
    return 0;
}
static int scan_has_term(const nr_term_scan_t *scan,const uint8_t *b,uint32_t length,
                         const char *term,int word) {
    uint32_t at,i,n=0,offset=(uint32_t)(b-scan->bytes),limit=offset+length;
    uint8_t first=lower_ascii((uint8_t)term[0]);
    if(!first)return has_term(b,length,term,word);
    at=scan->bucket.head[first];
    if(at>=NR_SEQ)return 0;
    while(term[n])n++;
    if(n>length)return 0;
    for(;at<NR_SEQ;at=scan->next[at]) {
        if(at<offset)continue;
        if(at+n>limit)break;
        if(word && ((at>offset && ascii_letter(scan->bytes[at-1])) ||
            (at+n<limit && ascii_letter(scan->bytes[at+n]))))continue;
        for(i=1;i<n;i++)if(scan->bytes[at+i]!=(uint8_t)term[i] &&
            lower_ascii(scan->bytes[at+i])!=lower_ascii((uint8_t)term[i]))break;
        if(i==n)return 1;
    }
    return 0;
}
static int has_any(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n,
                   const char *const *terms,uint32_t count) {
    uint32_t i;
    for(i=0;i<count;i++)
        if(scan_has_term(scan,b,n,terms[i],(uint8_t)terms[i][0]<128)) return 1;
    return 0;
}
#define HAS_TERMS(b,n,terms) has_any(scan,b,n,terms,(uint32_t)(sizeof(terms)/sizeof((terms)[0])))
static int contract_hint(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n) {
    static const char *const terms[5][10]={
        {"温度","结温","摄氏","多热","发热","temperature","temp","thermal","hot",0},
        {"pwm","占空比","duty",0},
        {"coremark","性能测试","cpu性能","跑分","基准测试","benchmark",0},
        {"计数器","计数值","计数寄存器","周期计数","当前计数","counter","cycle count","cpu cycles",0},
        {"led","灯","发光二极管",0}
    };
    uint32_t t,i,mask=0;
    for(t=0;t<5;t++) for(i=0;terms[t][i];i++)
        if(scan_has_term(scan,b,n,terms[t][i],(uint8_t)terms[t][i][0]<128)) {mask|=1u<<t;break;}
    if(mask && !(mask&(mask-1u))) {
        for(t=0;t<5;t++) if(mask==(1u<<t)) return (int)t;
    }
    return -1;
}
static int at_term(const uint8_t *b,uint32_t n,uint32_t at,const char *s);
/* One execution-context gate precedes neural acceptance and all schema rescue.
 * It describes this bounded command interface, not a general-language proof.
 * Questions remain valid for sensor/counter reads. Polite actuator requests
 * require a terminal request suffix; a status/hypothetical frame cannot use
 * that suffix to bypass this gate. */
static uint32_t trim_request_end(const uint8_t *b,uint32_t n) {
    for(;;) {
        if(n && (b[n-1]==' ' || b[n-1]=='\t' || b[n-1]=='.' || b[n-1]=='!' || b[n-1]=='?')) {n--;continue;}
        if(n>=3 && ((b[n-3]==0xe3 && b[n-2]==0x80 && b[n-1]==0x82) ||
                    (b[n-3]==0xef && b[n-2]==0xbc && (b[n-1]==0x81 || b[n-1]==0x9f)))) {n-=3;continue;}
        return n;
    }
}
static uint32_t terminal_term(const uint8_t *b,uint32_t n,const char *term) {
    uint32_t size=0,i;while(term[size])size++;
    if(size>n)return n;
    for(i=0;i<size;i++)if(b[n-size+i]!=(uint8_t)term[i])return n;
    return n-size;
}
/* A comma-delimited suffix may preserve OTHER bits rather than negate the
 * requested write. Consume a complete small grammar, never erase arbitrary
 * negative text or a second positive action. The learned context head always
 * sees the original complete sentence. */
static uint32_t preserve_token(const uint8_t *b,uint32_t n,uint32_t at,const char *const *words,uint32_t count) {
    uint32_t j;int k;for(j=0;j<count;j++){k=at_term(b,n,at,words[j]);if(k)return at+(uint32_t)k;}return at;
}
static uint32_t preserve_other(const uint8_t *b,uint32_t n,uint32_t at) {
    static const char *const other[]={"其他","其余","别的"};
    static const char *const object[]={"LED状态","LED输出","LED灯","led状态","led输出","led灯","LED","led","灯","位","输出","状态"};
    uint32_t p=preserve_token(b,n,at,other,3);if(p==at)return at;
    uint32_t q=preserve_token(b,n,p,object,12);return q==p?at:q;
}
static int preservation_suffix(const uint8_t *b,uint32_t n) {
    static const char *const neg[]={"不要","别","不"};
    static const char *const keep[]={"改动","改变","修改","调整","动","改"};
    uint32_t i=0,j,k;while(i<n&&(b[i]==' '||b[i]=='\t'))i++;
    j=preserve_other(b,n,i);
    if(j!=i){i=j;j=preserve_token(b,n,i,neg,3);if(j==i)return 0;i=j;j=preserve_token(b,n,i,keep,6);return j!=i&&j==n;}
    j=preserve_token(b,n,i,neg,3);if(j==i)return 0;i=j;
    j=preserve_token(b,n,i,keep,6);if(j==i)return 0;
    k=preserve_other(b,n,j);return k!=j&&k==n;
}
static uint32_t contract_request_start(const uint8_t *b,uint32_t n) {
    static const char *const neg[]={"不必","不用","不要","无需","不需要","不是要求","不要求"};
    static const char *const modifier[]={"长篇","详细","多余","逐字"};
    static const char *const explanation[]={"解释","说明","阐释","讲解","阐明","解说"};
    static const char *const wait[]={"别等","不用等","不必等","无需等"};
    static const char *const message[]={"消息","回复","反馈","通知"};
    uint32_t k=0,j,end;
    while(k<n&&(b[k]==' '||b[k]=='\t'))k++;
    if(at_term(b,n,k,"先"))k+=3;
    j=preserve_token(b,n,k,neg,7);end=k;
    if(j!=k){j=preserve_token(b,n,j,modifier,4);end=preserve_token(b,n,j,explanation,6);if(end==j)end=k;}
    if(end==k){j=preserve_token(b,n,k,wait,4);if(j!=k){end=preserve_token(b,n,j,message,4);if(end==j)end=k;}}
    if(end==k)return 0;
    if(at_term(b,n,end,"了"))end+=3;
    if(end<n&&b[end]==',')return end+1;
    if(end+3<=n&&b[end]==0xef&&b[end+1]==0xbc&&b[end+2]==0x8c)return end+3;
    return 0;
}
static uint32_t contract_request_end(const uint8_t *b,uint32_t n) {
    uint32_t i,end=trim_request_end(b,n),after;
    for(i=0;i<end;i++) {
        if(b[i]==',')after=i+1;
        else if(i+3<=end&&b[i]==0xef&&b[i+1]==0xbc&&b[i+2]==0x8c)after=i+3;
        else if(at_term(b,end,i,"不要")||at_term(b,end,i,"别")||at_term(b,end,i,"其他")||at_term(b,end,i,"其余")||at_term(b,end,i,"别的"))after=i;
        else continue;
        if(preservation_suffix(b+after,end-after))return i;
    }
    return n;
}
/* A high-margin reject remains a veto except for this narrow transparent
 * request form. Context/capability checks above routing still apply. This is
 * labeled schema selection, never relabeled as neural confidence. */
static int explicit_polite_request(const uint8_t *b,uint32_t n) {
    static const char *const prefix[]={"请","帮我","麻烦","劳驾"};
    static const char *const tail[]={"可以吗","好吗","行吗","好不好","行不行","可以不"};
    uint32_t i,start=0,end=trim_request_end(b,n);int begins=0;
    while(start<end && (b[start]==' ' || b[start]=='\t'))start++;
    for(i=0;i<sizeof(prefix)/sizeof(prefix[0]);i++)if(at_term(b,end,start,prefix[i]))begins=1;
    if(!begins)return 0;
    for(i=0;i<sizeof(tail)/sizeof(tail[0]);i++)if(terminal_term(b,end,tail[i])!=end)return 1;
    return 0;
}
/* A sequential connector separates two hardware actions, even when both
 * name the same tool. Reporting an outcome/CRC is not a second action.
 * No sentence-specific strings or city-name lists are involved. */
static int repeated_action_requested(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n,int hint) {
    static const char *const join[]={"然后","随后","接着","之后","另外","完成后","顺手","再处理","再","并","then","and then"};
    static const char *const verbs[5][14]={
        {"读取","读","查询","获取","返回","报告","给我","read","get",0},
        {"设置","设为","调整","改为","改成","调到","set","change","configure",0},
        {"运行","执行","启动","跑","测试","run","start","execute",0},
        {"读取","读","查询","获取","返回","报告","给我","read","get",0},
        {"点亮","打开","开启","关闭","熄灭","设置","设为","turn","set","switch",0}
    };
    uint32_t at,j,k,size;int before,after;
    if(hint<0||hint>4)return 0;
    for(at=1;at<n;at++)for(j=0;j<sizeof(join)/sizeof(join[0]);j++) {
        for(size=0;join[j][size];size++){}
        if(at+size>=n || !scan_has_term(scan,b+at,size,join[j],0))continue;
        if((uint8_t)join[j][0]<128u && ((at&&ascii_letter(b[at-1]))||ascii_letter(b[at+size])))continue;
        if(contract_hint(scan,b,at)!=hint)continue;
        before=after=0;
        for(k=0;verbs[hint][k];k++) {
            int word=(uint8_t)verbs[hint][k][0]<128u;
            before|=scan_has_term(scan,b,at,verbs[hint][k],word);
            after|=scan_has_term(scan,b+at+size,n-at-size,verbs[hint][k],word);
        }
        if(before&&after)return 1;
    }
    return 0;
}
static int execution_context_allowed(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n,int hint) {
    static const char *const mention[]={"理解","解释","说明","含义","意思","是什么","什么是","为什么","为何","原理",
        "教程","方法","步骤","教我","编写","编程","生成代码","如何读取","怎么读取","怎样读取","示例","举例","比如","意义","说说","讲解","阐释","阐明","分析","设想","分析这项操作","只展示","文字","照抄","逐字","假想","设定情境","如果","假如","假设","假若","假定","要是","倘若","万一",
        "会怎样","会如何","会发生","引用","复述","翻译","这句话","这条指令","这个命令",
        "“","”","「","」","『","』","‘","’","explain","meaning","how to","how do","what if","why","tutorial","example","hypothetically"};
    static const char *const text_verb[]={"抄写","抄到","摘录","复写"};
    static const char *const text_object[]={"这几个字","下面的话","原话","这段话","原文"};
    static const char *const state_query[]={"了吗","了么","是否","是不是","有没有","能不能","可不可以","已经",
        "查询","读取","读一下","查看","多少","如何","怎么","怎样","what","how","whether","has","have","is","are","did","does"};
    static const char *const polite[]={"可以吗","好吗","行吗","好不好","行不行","可以不"};
    static const char *const action[]={"点亮","打开","开启","关闭","关掉","熄灭","设置","设为","设到","设成","调整","调到","调成","改为","改成","修改","更新","让","运行","执行","跑","启动","测一次","run","start","execute","set","turn","change","configure"};
    static const char *const core_observe[]={"看看性能怎么样","看看结果怎么样","看看效果怎么样",
        "查看成绩","查看得分","查看分数","看看成绩","看看得分","看看分数"};
    uint32_t i,end,cut,tail_steps;int polite_tail=0;
    int core_add_run=hint==NR_RUN_COREMARK && scan_has_term(scan,b,n,"加测",0);
    if(HAS_TERMS(b,n,mention)||(HAS_TERMS(b,n,text_verb)&&HAS_TERMS(b,n,text_object))||repeated_action_requested(scan,b,n,hint))return 0;
    for(i=0;i<n;i++) {
        if(b[i]=='"' || b[i]=='`')return 0;
        if(b[i]=='\'' && !(i>0 && i+1<n && ascii_letter(b[i-1]) && ascii_letter(b[i+1])))return 0;
    }
    if(hint==NR_READ_TEMP || hint==NR_READ_COUNTER) {
        static const char *const past[]={"此前","先前","上一次","上次","之前","刚才"};
        static const char *const completion[]={"是否完成","是否执行","执行过","读过","查过","完成了吗","完成了么"};
        /* Asking whether a past request completed does not request a new read. */
        if(HAS_TERMS(b,n,past)&&HAS_TERMS(b,n,completion))return 0;
        return 1;
    }
    end=trim_request_end(b,n);
    /* Strip only terminal courtesy fragments, bounded by four suffixes.
     * Repeated tails do not erase state/negation/mention words in the request. */
    for(tail_steps=0;tail_steps<4u;tail_steps++) {
        cut=end;
        for(i=0;i<sizeof(polite)/sizeof(polite[0]);i++) {
            cut=terminal_term(b,end,polite[i]);
            if(cut!=end){polite_tail=1;break;}
        }
        if(cut==end)cut=terminal_term(b,end,"一下吧");
        if(cut==end)break;
        end=cut;
        while(end && (b[end-1]==' ' || b[end-1]=='\t'))end--;
        /* A comma separating request tails is punctuation, not an observation. */
        if(end && b[end-1]==',')end--;
        else if(end>=3 && b[end-3]==0xef && b[end-2]==0xbc && b[end-1]==0x8c)end-=3;
        while(end && (b[end-1]==' ' || b[end-1]=='\t'))end--;
    }
    if(hint==NR_RUN_COREMARK) for(i=0;i<sizeof(core_observe)/sizeof(core_observe[0]);i++) {
        cut=terminal_term(b,end,core_observe[i]);
        if(cut!=end && (HAS_TERMS(b,cut,action)||core_add_run)){end=cut;polite_tail=1;break;}
    }
    for(i=0;i<end;i++) if(at_term(b,end,i,"状态") &&
        !at_term(b,end,i,"状态不变") && !at_term(b,end,i,"状态保持不变") &&
        !at_term(b,end,i,"状态保持原样"))return 0;
    if(HAS_TERMS(b,end,state_query))return 0;
    if(scan_has_term(scan,b,end,"吗",0)||scan_has_term(scan,b,end,"呢",0)||scan_has_term(scan,b,end,"?",0)||scan_has_term(scan,b,end,"？",0))return 0;
    if((scan_has_term(scan,b,n,"?",0)||scan_has_term(scan,b,n,"？",0)) && !polite_tail)return 0;
    if(polite_tail && !HAS_TERMS(b,end,action) && !core_add_run)return 0;
    return 1;
}
/* Score changes are not a benchmark request. Detect a quantity after an
 * arithmetic operator, not every occurrence of 加 (e.g. 加上CRC is output).
 * No number is evaluated or used to produce a benchmark result here. */
static int score_at_term(const uint8_t *b,uint32_t n,uint32_t at,const char *term) {
    uint32_t i;
    for(i=0;term[i];i++)if(at+i>=n || lower_ascii(b[at+i])!=lower_ascii((uint8_t)term[i]))return 0;
    return (int)i;
}
static int score_quantity_at(const uint8_t *b,uint32_t n,uint32_t at) {
    static const char *const quantity[]={"零","〇","一","二","三","四","五","六","七","八","九","十","百","千","两",
        "０","１","２","３","４","５","６","７","８","９","若干","一些","几",
        "zero","one","two","three","four","five","six","seven","eight","nine","ten","hundred","thousand","some","n"};
    uint32_t i;int size;
    if(at<n && b[at]>='0' && b[at]<='9')return 1;
    for(i=0;i<sizeof(quantity)/sizeof(quantity[0]);i++) {
        size=score_at_term(b,n,at,quantity[i]);
        if(size && ((uint8_t)quantity[i][0]>=128 || at+(uint32_t)size==n || !ascii_letter(b[at+(uint32_t)size])))return 1;
    }
    return 0;
}
static int score_arithmetic_requested(const uint8_t *b,uint32_t n) {
    static const char *const arithmetic[]={"增加","减少","加","减","扣","乘","除","+","-","＋","－","−","×","÷","add","subtract","plus","minus"};
    static const char *const particle[]={"上","去","掉","以","到","至","个","点","约","大约","至少","最多","by","another","about"};
    uint32_t i,j,k,at,steps;int size,moved;
    for(i=0;i<n;i++)for(j=0;j<sizeof(arithmetic)/sizeof(arithmetic[0]);j++) {
        size=score_at_term(b,n,i,arithmetic[j]);
        if(!size || ((uint8_t)arithmetic[j][0]<128 && ascii_letter((uint8_t)arithmetic[j][0]) && i && ascii_letter(b[i-1])))continue;
        at=i+(uint32_t)size;
        /* Bounded fillers allow 加上/减去/乘以/加约N, including whitespace. */
        for(steps=0;steps<n && at<n;steps++) {
            if(b[at]==' ' || b[at]=='\t'){at++;continue;}
            if(score_quantity_at(b,n,at))return 1;
            moved=0;
            for(k=0;k<sizeof(particle)/sizeof(particle[0]);k++) {
                size=score_at_term(b,n,at,particle[k]);
                if(size){at+=(uint32_t)size;moved=1;break;}
            }
            if(!moved)break;
        }
        if(score_quantity_at(b,n,at))return 1;
    }
    return 0;
}
static int capability_allowed(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n,int hint) {
    static const char *const denied[]={"不要","别","不用","取消","禁止","不许","不能","不准","勿","停止","暂停","中止","暂缓","不允许","先不做","先不执行","没让","未让","并未要求","并没有要求","并非要","暂不执行","取消本次",
        "不必","无需","无须","没有","没开","没亮","不打开","不点亮","不运行","不执行",
        "不想打开","不想点亮","不想熄灭","不想关闭","不想关掉",
        "not","don't","dont","never","cancel","stop"};
    static const char *const firmware[]={"烧录","固件","刷机","firmware","bootloader"};
    static const char *const counter_write[]={"清零","重置","复位","归零","重新计数","重新开始计数","恢复零值","恢复为零","重设为零",
        "关闭","关掉","reset","clear","zero","disable"};
    static const char *const temp_write[]={"打开","开启","降低","降到","降至","调低","升高","升到","升至","调高","降温","冷却","加热",
        "设置","设定","设为","设到","调到","调整","固定","恒定","维持","控制","锁定","调节","制冷","温控","关闭","关掉",
        "set","change","cool","heat","lower","raise","reduce","disable"};
    static const char *const score_write[]={"伪造","修改","篡改","编造","虚构","改成","改高","改分",
        "假分","满分","填写","填报","fake","forge","alter","edit","modify"};
    static const char *const score_target[]={"成绩","分数","得分","分值","评分","结果","score","scores","points","result","results"};
    static const char *const score_control[]={"指定","设定","设置","设为","设成","设到","定为","写成","改为","改到","变成","填为","填成",
        "调高","调低","提高","提升","降低","上调","下调","翻倍","倍增","减半","乘以","除以",
        "set","assign","increase","decrease","raise","lower","boost","double","halve","multiply","divide","override","force"};
    static const char *const pwm_unsupported[]={"频率","frequency","hertz","hz"};
    if(HAS_TERMS(b,n,denied) || HAS_TERMS(b,n,firmware) ||
       !execution_context_allowed(scan,b,n,hint)) return 0;
    if(hint==NR_READ_COUNTER && HAS_TERMS(b,n,counter_write)) return 0;
    if(hint==NR_SET_LED) {
        static const char *const analog_led[]={"亮度","明暗","百分","%","闪烁","闪灯","呼吸灯","周期","频率","秒","blink","brightness","dimming"};
        if(HAS_TERMS(b,n,analog_led))return 0;
    }
    if(hint==NR_READ_TEMP) {
        static const char *const external[]={"天气","气温","预报","室外","外面","户外","明天","昨天","未来","历史",
            "weather","forecast","outdoor","outside","tomorrow","yesterday","historical"};
        if(HAS_TERMS(b,n,temp_write)||HAS_TERMS(b,n,external))return 0;
    }
    if(hint==NR_RUN_COREMARK && (HAS_TERMS(b,n,score_write) ||
       (HAS_TERMS(b,n,score_target) && HAS_TERMS(b,n,score_control)) ||
       score_arithmetic_requested(b,n))) return 0;
    if(hint==NR_SET_PWM) {
        static const char *const query[]={"读取","读一下","查询","查看","显示","多少","read","show","what","query","get"};
        static const char *const negated[]={"不想","不希望","不需要","不打算","不改变","不调整"};
        if(HAS_TERMS(b,n,query) || HAS_TERMS(b,n,negated)) return 0;
    }
    if(hint==NR_SET_PWM && (HAS_TERMS(b,n,pwm_unsupported) ||
       ((scan_has_term(scan,b,n,"周期",0) || scan_has_term(scan,b,n,"period",1)) &&
        !scan_has_term(scan,b,n,"占空比",0) && !scan_has_term(scan,b,n,"高电平",0) &&
        !scan_has_term(scan,b,n,"duty",1) && !scan_has_term(scan,b,n,"成",0) && !scan_has_term(scan,b,n,"%",0)))) return 0;
    return 1;
}
/* Exactly one ASCII decimal argument; no missing/truncated/multiple numbers.
 * The argument is evidenced by the request, never generated by the model. */
static int at_term(const uint8_t *b,uint32_t n,uint32_t at,const char *s) {
    uint32_t i;for(i=0;s[i];i++) if(at+i>=n || b[at+i]!=(uint8_t)s[i]) return 0;
    return (int)i;
}
static int hex_digit(uint8_t c) {
    c=lower_ascii(c);
    if(c>='0'&&c<='9') return c-'0';
    return c>='a'&&c<='f'?c-'a'+10:-1;
}
static nr_tool_status_t decimal_argument(const uint8_t *b,uint32_t n,int32_t *out,
                                         uint32_t *start,uint32_t *end) {
    uint32_t i,count=0,value=0;int negative=0;
    for(i=0;i<n;i++) if(b[i]>='0' && b[i]<='9') {
        uint32_t base=10,digits=0;int d;
        if(++count>1) return NR_TOOL_BAD_ARGUMENT;
        *start=i;negative=i>0 && b[i-1]=='-';
        if(i>=3 && at_term(b,n,i-3,"−")) return NR_TOOL_OUT_OF_RANGE;
        if(i+1<n && b[i]=='0' && lower_ascii(b[i+1])=='x') {base=16;i+=2;}
        while(i<n && (d=(base==16?hex_digit(b[i]):(b[i]>='0'&&b[i]<='9'?b[i]-'0':-1)))>=0) {
            if(value>100000u) return NR_TOOL_OUT_OF_RANGE;
            value=value*base+(uint32_t)d;i++;digits++;
        }
        if(!digits) return NR_TOOL_BAD_ARGUMENT;
        *end=i;
        if(i<n && (b[i]=='.' || (base==16 && ascii_letter(b[i])))) return NR_TOOL_BAD_ARGUMENT;
    }
    if(!count) return NR_TOOL_MISSING_ARGUMENT;
    if(negative) return NR_TOOL_OUT_OF_RANGE;
    *out=(int32_t)value;return NR_TOOL_OK;
}
/* All supported Chinese numeral atoms are three-byte UTF-8. Decode exactly
 * those atoms once; continuation bytes and ASCII cannot begin one. */
static int cn_digit(const uint8_t *b,uint32_t n,uint32_t at) {
    uint32_t code;
    if(at>=n || n-at<3u || b[at]<0xe4u || b[at]>0xe9u)return -1;
    code=((uint32_t)b[at]<<16)|((uint32_t)b[at+1]<<8)|b[at+2];
    switch(code) {
    case 0xe99bb6u:return 0; /* 零 */
    case 0xe4b880u:return 1; /* 一 */
    case 0xe4ba8cu:return 2; /* 二 */
    case 0xe4b889u:return 3; /* 三 */
    case 0xe59b9bu:return 4; /* 四 */
    case 0xe4ba94u:return 5; /* 五 */
    case 0xe585adu:return 6; /* 六 */
    case 0xe4b883u:return 7; /* 七 */
    case 0xe585abu:return 8; /* 八 */
    case 0xe4b99du:return 9; /* 九 */
    case 0xe58d81u:return 10; /* 十 */
    case 0xe799beu:return 100; /* 百 */
    case 0xe4b8a4u:return 2; /* 两 */
    default:return -1;
    }
}
static int cn_number(const uint8_t *b,uint32_t n,uint32_t at,uint32_t *end) {
    int first=cn_digit(b,n,at),next,value;
    if(first<0) return -1;
    if(first==100){*end=at+3;return 100;}
    at+=3;value=first;next=cn_digit(b,n,at);
    if(first==10) {
        if(next>=0 && next<10) {value+=next;at+=3;}
    } else if(next==100 && first==1) {value=100;at+=3;}
    else if(next==10 && first>0) {
        value=first*10;at+=3;next=cn_digit(b,n,at);
        if(next>=0 && next<10) {value+=next;at+=3;}
    }
    *end=at;return value;
}
static nr_tool_status_t duty_argument(const uint8_t *b,uint32_t n,int32_t *out) {
    int32_t numeric=0;uint32_t start=0,end=0,i,found=0;int value=0;
    nr_tool_status_t numeric_status=decimal_argument(b,n,&numeric,&start,&end);
    for(i=0;i<n;i++) {
        uint32_t stop=0;int v;
        if(b[i]<0xe4u || b[i]>0xe9u)continue;
        if(at_term(b,n,i,"百分百")){v=100;stop=i+9;}
        else if(at_term(b,n,i,"百分之")) {
            v=cn_number(b,n,i+9,&stop);
            if(v<0) continue; /* ASCII percent uses the ordinary integer parser. */
        } else {
            v=cn_number(b,n,i,&stop);
            if(v<0 || !at_term(b,n,stop,"成")) continue;
            v*=10;stop+=3;
        }
        if(cn_digit(b,n,stop)>=0 || at_term(b,n,stop,"半") || at_term(b,n,stop,"点"))
            return NR_TOOL_BAD_ARGUMENT;
        if(++found>1) return NR_TOOL_BAD_ARGUMENT;
        value=v;i=stop-1;
    }
    if(found) {
        if(numeric_status!=NR_TOOL_MISSING_ARGUMENT) return NR_TOOL_BAD_ARGUMENT;
        if(value>100) return NR_TOOL_OUT_OF_RANGE;
        *out=value;return NR_TOOL_OK;
    }
    if(numeric_status==NR_TOOL_OK && start+1<n && b[start]=='0' && lower_ascii(b[start+1])=='x')
        return NR_TOOL_BAD_ARGUMENT; /* hex is an LED-mask notation, not a duty notation. */
    if(numeric_status==NR_TOOL_OK && at_term(b,n,end,"成")) {
        if(has_term(b,n,"百分之",0) || at_term(b,n,end+3,"半") ||
           cn_digit(b,n,end+3)>=0) return NR_TOOL_BAD_ARGUMENT;
        numeric*=10;
    }
    if(numeric_status==NR_TOOL_OK && numeric>100) return NR_TOOL_OUT_OF_RANGE;
    if(numeric_status==NR_TOOL_OK) *out=numeric;
    return numeric_status;
}
static int led_mask_schema(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n) {
    static const char *const terms[]={"掩码","整体","全部","所有","灯值","LED值","mask"};
    return HAS_TERMS(b,n,terms);
}
static int explicit_pwm_schema(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n) {
    static const char *const verbs[]={"设置","设为","设到","调整","调到","调成","调为","改为","改成","取","运行","保持","输出","让",
        "set","write","change","configure","更新"};
    static const char *const units[]={"占空比","高电平","duty","%","成","百分之","percent","pct"};
    return HAS_TERMS(b,n,verbs) && HAS_TERMS(b,n,units);
}
static int chinese_ordinal(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n) {
    static const char *const names[8][3]={
        {"第一个","第一颗","第一盏"},{"第二个","第二颗","第二盏"},
        {"第三个","第三颗","第三盏"},{"第四个","第四颗","第四盏"},
        {"第五个","第五颗","第五盏"},{"第六个","第六颗","第六盏"},
        {"第七个","第七颗","第七盏"},{"第八个","第八颗","第八盏"}
    };
    uint32_t i,j;int found=-1;
    for(i=0;i<8;i++) for(j=0;j<3;j++) if(scan_has_term(scan,b,n,names[i][j],0)) {
        if(found>=0 && found!=(int)i) return -2;
        found=(int)i;
    }
    return found;
}
static nr_tool_status_t led_arguments(const nr_term_scan_t *scan,const uint8_t *b,uint32_t n,nr_tool_request_t *r) {
    static const char *const on[]={"点亮","打开","开启","亮起","on"};
    static const char *const off[]={"关掉","关闭","熄灭","灭掉","关","off"};
    int is_on=HAS_TERMS(b,n,on),is_off=HAS_TERMS(b,n,off);
    uint32_t begin=0,end=0;int32_t argument=0;
    nr_tool_status_t status=decimal_argument(b,n,&argument,&begin,&end);
    if(is_on && is_off) return NR_TOOL_POLICY_REJECTED;
    if(led_mask_schema(scan,b,n)) {
        if(status==NR_TOOL_MISSING_ARGUMENT && is_on!=is_off) {
            argument=is_on?255:0;status=NR_TOOL_OK;
        }
        if(status!=NR_TOOL_OK) return status;
        if(argument>255) return NR_TOOL_OUT_OF_RANGE;
        if((is_off && argument!=0) || (is_on && argument!=255)) return NR_TOOL_POLICY_REJECTED;
        r->argument=argument;return NR_TOOL_OK;
    }
    if(is_on || is_off) {
        int ordinal=chinese_ordinal(scan,b,n);
        if(ordinal==-2) return NR_TOOL_BAD_ARGUMENT;
        if(ordinal>=0) {
            if(status!=NR_TOOL_MISSING_ARGUMENT) return NR_TOOL_BAD_ARGUMENT;
            argument=ordinal;status=NR_TOOL_OK;
        } else if(status==NR_TOOL_OK && begin>=3 &&
                  b[begin-3]==0xe7 && b[begin-2]==0xac && b[begin-1]==0xac &&
                  (scan_has_term(scan,b+end,n-end,"个",0) || scan_has_term(scan,b+end,n-end,"颗",0) ||
                   scan_has_term(scan,b+end,n-end,"盏",0))) {
            /* UTF-8 第 + ASCII 1..8; convert ordinal to zero-based pin. */
            if(argument<1 || argument>8) return NR_TOOL_OUT_OF_RANGE;
            argument--;
        }
        if(status!=NR_TOOL_OK) return status;
        if(argument>7) return NR_TOOL_OUT_OF_RANGE;
        r->argument=argument;r->operation=is_on?NR_OP_LED_ON:NR_OP_LED_OFF;
        return NR_TOOL_OK;
    }
    if(chinese_ordinal(scan,b,n)>=0) return NR_TOOL_MISSING_ARGUMENT;
    if(status!=NR_TOOL_OK) return status;
    if(argument>255) return NR_TOOL_OUT_OF_RANGE;
    r->argument=argument;return NR_TOOL_OK;
}
/* Conservative explicit-command admission shares the exact capability/context
 * gate with the model path. Unrecognized wording is a MISS, never an inferred
 * actuator argument. Rule results are not neural predictions. */
static int canonical_numeric_command(const uint8_t *b,uint32_t n,const char *name) {
    uint32_t i=0,k=0,end=trim_request_end(b,n);
    while(i<end && (b[i]==' '||b[i]=='\t'))i++;
    /* A complete ASCII assignment grammar, not an arbitrary keyword hit. */
    if(score_at_term(b,end,i,"please ")){i+=7;while(i<end&&(b[i]==' '||b[i]=='\t'))i++;}
    if(score_at_term(b,end,i,"configure "))i+=10;
    else if(score_at_term(b,end,i,"write "))i+=6;
    else if(score_at_term(b,end,i,"set "))i+=4;
    while(i<end&&(b[i]==' '||b[i]=='\t'))i++;
    while(name[k]) {if(i>=end||lower_ascii(b[i++])!=(uint8_t)name[k++])return 0;}
    if(i>=end||(b[i]!=' '&&b[i]!='\t'))return 0;
    while(i<end&&(b[i]==' '||b[i]=='\t'))i++;
    if(i==end)return 0;
    for(;i<end;i++) if(!((b[i]>='0'&&b[i]<='9') ||
        (lower_ascii(b[i])>='a'&&lower_ascii(b[i])<='f') ||
        b[i]=='x'||b[i]=='X'))return 0;
    return 1;
}
/* Complete polite Chinese command grammar. Every byte must belong to one
 * bounded prefix/action/object/suffix; negation, quotation, conditions and
 * second actions cannot be consumed. This is explicit parsing (model_used=0),
 * never a repaired neural score. */
/* Small immutable grammar tables live beside AI constants, preserving the
 * full 8 KiB CPU stack. They are parser vocabulary, not learned weights. */
static uint32_t canonical_literal_at(const uint8_t *b,uint32_t n,uint32_t at,const char *words,uint32_t count) {
    uint32_t j;int size;
    for(j=0;j<count;j++){
        size=score_at_term(b,n,at,words);if(size)return at+(uint32_t)size;
        while(*words){words++;}
        words++;
    }
    return at;
}
static int canonical_chinese_command(const uint8_t *b,uint32_t n,nr_tool_t *tool) {
    static const char prefix[] __attribute__((section(".ai_const"),aligned(4)))="麻烦您\0劳烦您\0帮个忙\0麻烦\0劳烦\0帮我\0请";
    static const char counter_action[] __attribute__((section(".ai_const"),aligned(4)))="读取一下\0查询一下\0读一下\0读取\0返回\0查询\0获取";
    static const char counter_object[] __attribute__((section(".ai_const"),aligned(4)))="硬件计数寄存器读数\0硬件计数器当前值\0计数器当前值\0当前计数器数值\0硬件计数器\0计数器";
    static const char core_action[] __attribute__((section(".ai_const"),aligned(4)))="完成一次\0运行一次\0执行一次\0启动一次\0运行\0执行\0启动";
    static const char core_object[] __attribute__((section(".ai_const"),aligned(4)))="CoreMark性能基准测试\0CoreMark性能测试\0CoreMark基准测试\0CoreMark测试\0CoreMark跑分\0CoreMark";
    static const char suffix[] __attribute__((section(".ai_const"),aligned(4)))="一下吧\0一下\0可以吗\0好吗\0吧";
    uint32_t i=0,start,end=trim_request_end(b,n),branch,at,next;
    while(i<end&&(b[i]==' '||b[i]=='\t'))i++;
    start=canonical_literal_at(b,end,i,prefix,7);
    for(branch=0;branch<2;branch++) {
        at=canonical_literal_at(b,end,start,branch?core_action:counter_action,7);
        if(at==start)continue;
        next=canonical_literal_at(b,end,at,branch?core_object:counter_object,6);
        if(next==at)continue;
        at=next;
        if(at!=end){at=canonical_literal_at(b,end,at,suffix,5);if(at!=end)continue;}
        *tool=branch?NR_RUN_COREMARK:NR_READ_COUNTER;return 1;
    }
    return 0;
}
/* Whole-input machine grammar. No free-text prefix/suffix, comments, quoting
 * or inferred action is admitted. The bounded Chinese grammar above shares
 * the same dispatcher and hardware receipt. */
static int machine_equal(const uint8_t *b,uint32_t n,const char *s) {
    uint32_t i=0;while(s[i]){if(i>=n||lower_ascii(b[i])!=(uint8_t)s[i])return 0;i++;}return i==n;
}

/* Bounded explicit command grammar, before context inference. Immutable
 * vocabulary lives in shared SRAM; this parser adds no learned weights.
 * All bytes must be consumed. No quote, hypothetical, negation or second
 * action slot exists. A matching rule is observable as model_used=0. */
#define NR_EXPLICIT_CONST __attribute__((section(".ai_const"),aligned(4)))
static uint32_t explicit_word(const uint8_t*b,uint32_t n,uint32_t at,const char*words,uint32_t count,uint32_t*which){
 for(uint32_t j=0;j<count;j++){int size=score_at_term(b,n,at,words);if(size){if(which)*which=j;return at+(uint32_t)size;}while(*words){words++;}words++;}return at;
}
static uint32_t explicit_uint(const uint8_t*b,uint32_t n,uint32_t at,uint32_t hex,uint32_t*value){
 uint32_t start=at,v=0,base=10,d,digits=0;
 if(hex&&at+2<n&&b[at]=='0'&&lower_ascii(b[at+1])=='x'){base=16;at+=2;}
 for(;at<n;at++){int digit=base==16?hex_digit(b[at]):b[at]>='0'&&b[at]<='9'?b[at]-'0':-1;if(digit<0||(uint32_t)digit>=base)break;d=(uint32_t)digit;if(v<=255)v=v*base+d;digits++;}
 if(!digits)return start;
 *value=v;return at;
}
static int explicit_finish(nr_tool_request_t*r,nr_tool_t tool,uint32_t value,nr_tool_operation_t op){
 uint32_t limit=tool==NR_SET_LED?(op==NR_OP_DEFAULT?255u:7u):tool==NR_SET_PWM?100u:0u;
 r->tool=tool;r->argument=(int32_t)value;r->operation=op;r->margin=0;r->status=NR_TOOL_OK;
 r->selection_source=tool==NR_SET_LED?NR_SELECT_LED_SCHEMA:tool==NR_SET_PWM?NR_SELECT_PWM_SCHEMA:NR_SELECT_READ_SCHEMA;
 if(limit&&value>limit){r->tool=NR_REJECT;r->argument=0;r->operation=NR_OP_DEFAULT;r->status=NR_TOOL_OUT_OF_RANGE;r->selection_source=NR_SELECT_DENIED;}
 return 1;
}
static int canonical_extended_command(const uint8_t*b,uint32_t n,nr_tool_request_t*r){
 static const char polite[] NR_EXPLICIT_CONST="请把这次任务办好：\0麻烦您\0劳烦您\0帮个忙\0麻烦\0劳烦\0帮我\0请";
 static const char courtesy[] NR_EXPLICIT_CONST="一下吧\0一下\0可以吗\0好吗\0吧";
 static const char reads[] NR_EXPLICIT_CONST="读取一下\0查询一下\0读一下\0读出\0查看\0读取\0返回\0查询\0获取";
 static const char counter[] NR_EXPLICIT_CONST="计数寄存器\0计数器\0计数值";
 static const char time[] NR_EXPLICIT_CONST="目前的\0当前的\0现在的\0目前\0当前\0现在";
 static const char value_words[] NR_EXPLICIT_CONST="实时读数\0当前读数\0当前值\0计数值\0数值\0读数\0值";
 static const char led_verbs[] NR_EXPLICIT_CONST="点亮\0打开\0开启\0关闭\0关掉\0熄灭";
 static const char other[] NR_EXPLICIT_CONST="其他\0其余";
 static const char objects[] NR_EXPLICIT_CONST="LED状态\0LED输出\0LED\0位\0灯";
 static const char keep[] NR_EXPLICIT_CONST="保持\0维持";
 static const char state[] NR_EXPLICIT_CONST="原状\0原样\0不变";
 static const char pwm_assign[] NR_EXPLICIT_CONST="设置为\0调整为\0修改为\0设为\0改为\0调为\0调到";
 uint32_t end=trim_request_end(b,n),at=0,start,next,ix=0,v=0,mod;int k;
 while(at<end&&(b[at]==' '||b[at]=='\t'))at++;
 start=explicit_word(b,end,at,polite,8,0);
 /* read + hardware? + counter object + present-time? + value object? */
 at=explicit_word(b,end,start,reads,9,0);
 if(at!=start){
  k=score_at_term(b,end,at,"硬件");if(k)at+=(uint32_t)k;k=score_at_term(b,end,at,"实时");if(k)at+=(uint32_t)k;next=explicit_word(b,end,at,counter,3,0);
  if(next!=at){at=next;mod=explicit_word(b,end,at,time,6,0);next=explicit_word(b,end,mod,value_words,7,0);
   if(mod==at||next!=mod){at=next;if(at!=end)at=explicit_word(b,end,at,courtesy,5,0);if(at==end)return explicit_finish(r,NR_READ_COUNTER,0,NR_OP_DEFAULT);}
  }
 }
 /* only?/single? + on/off + LED bit + complete keep-other-bits clause? */
 at=start;k=score_at_term(b,end,at,"单独");if(!k)k=score_at_term(b,end,at,"只");if(k)at+=(uint32_t)k;
 next=explicit_word(b,end,at,led_verbs,6,&ix);
 if(next!=at){at=next;k=score_at_term(b,end,at,"led");if(k){at+=(uint32_t)k;if(at<end&&b[at]>='0'&&b[at]<='7'){
  int complete=0;v=b[at++]-'0';
  if(at==end)complete=1;
  else{
   if(b[at]==',')at++;else{k=score_at_term(b,end,at,"，");if(k)at+=(uint32_t)k;}
   while(at<end&&(b[at]==' '||b[at]=='\t'))at++;
   next=explicit_word(b,end,at,other,2,0);
   if(next!=at){at=next;next=explicit_word(b,end,at,objects,5,0);
    if(next!=at){at=next;next=explicit_word(b,end,at,keep,2,0);
     if(next!=at){at=next;next=explicit_word(b,end,at,state,3,0);if(next!=at){at=next;complete=1;}}
     else{k=score_at_term(b,end,at,"不变");if(k){at+=(uint32_t)k;complete=1;}}
    }
   }
   if(complete&&at!=end)at=explicit_word(b,end,at,courtesy,5,0);
  }
  if(complete&&at==end)return explicit_finish(r,NR_SET_LED,v,ix<3?NR_OP_LED_ON:NR_OP_LED_OFF);
 }}}
 /* Explicit PWM scalar assignment; no frequency/period noun is admitted. */
 at=start;k=score_at_term(b,end,at,"把");if(!k)k=score_at_term(b,end,at,"将");if(k)at+=(uint32_t)k;
 k=score_at_term(b,end,at,"pwm");if(k){at+=(uint32_t)k;k=score_at_term(b,end,at,"的");if(k)at+=(uint32_t)k;k=score_at_term(b,end,at,"占空比");if(k)at+=(uint32_t)k;
  next=explicit_word(b,end,at,pwm_assign,7,0);if(next!=at){at=next;next=explicit_uint(b,end,at,0,&v);if(next!=at){at=next;if(at<end&&b[at]=='%')at++;if(at!=end)at=explicit_word(b,end,at,courtesy,5,0);if(at==end)return explicit_finish(r,NR_SET_PWM,v,NR_OP_DEFAULT);}}
 }
 /* Complete ASCII assignment: please? (write N to led | verb target N). */
 at=0;while(at<end&&(b[at]==' '||b[at]=='\t'))at++;k=score_at_term(b,end,at,"please ");if(k)at+=(uint32_t)k;start=at;
 k=score_at_term(b,end,at,"write ");if(k){at+=(uint32_t)k;next=explicit_uint(b,end,at,1,&v);if(next!=at){at=next;k=score_at_term(b,end,at," to led");if(k&&at+(uint32_t)k==end)return explicit_finish(r,NR_SET_LED,v,NR_OP_DEFAULT);}}
 at=start;k=score_at_term(b,end,at,"configure ");if(!k)k=score_at_term(b,end,at,"set ");if(!k)k=score_at_term(b,end,at,"write ");if(k){at+=(uint32_t)k;int led=score_at_term(b,end,at,"led ");int pwm=score_at_term(b,end,at,"pwm ");if(led||pwm){at+=(uint32_t)(led?led:pwm);next=explicit_uint(b,end,at,led!=0,&v);if(next==end&&next!=at)return explicit_finish(r,led?NR_SET_LED:NR_SET_PWM,v,NR_OP_DEFAULT);}}
 return 0;
}
#undef NR_EXPLICIT_CONST

int nr_tool_decode_machine(const uint8_t *b,uint32_t n,nr_tool_request_t *r) {
    uint32_t i=4,v=0,d,base=10,limit=0;nr_tool_t tool;
    if(!b||!r||!n||n>NR_SEQ)return NR_FAST_MISS;
    if(canonical_extended_command(b,n,r))return NR_FAST_HANDLED;
    if(n>=5 && b[3]==' ' && ((lower_ascii(b[0])=='l'&&lower_ascii(b[1])=='e'&&lower_ascii(b[2])=='d') ||
        (lower_ascii(b[0])=='p'&&lower_ascii(b[1])=='w'&&lower_ascii(b[2])=='m'))) {
        tool=lower_ascii(b[0])=='l'?NR_SET_LED:NR_SET_PWM;limit=tool==NR_SET_LED?255u:100u;
        if(tool==NR_SET_LED && n>=7 && b[i]=='0'&&lower_ascii(b[i+1])=='x'){i+=2;base=16;}
        if(i>=n)return NR_FAST_MISS;
        for(;i<n;i++) {
            d=b[i]>='0'&&b[i]<='9'?(uint32_t)(b[i]-'0'):base==16&&lower_ascii(b[i])>='a'&&lower_ascii(b[i])<='f'?lower_ascii(b[i])-'a'+10u:99u;
            if(d>=base)return NR_FAST_MISS;
            if(v<=limit)v=v*base+d; /* bounded before multiplication, no overflow */
        }
    } else if(machine_equal(b,n,"read temp")||machine_equal(b,n,"read temperature"))tool=NR_READ_TEMP;
    else if(machine_equal(b,n,"read counter"))tool=NR_READ_COUNTER;
    else if(machine_equal(b,n,"run coremark"))tool=NR_RUN_COREMARK;
    else if(canonical_chinese_command(b,n,&tool)){}
    else return NR_FAST_MISS;
    r->tool=tool;r->argument=(int32_t)v;r->operation=NR_OP_DEFAULT;r->margin=0;
    r->status=NR_TOOL_OK;r->selection_source=tool==NR_SET_LED?NR_SELECT_LED_SCHEMA:tool==NR_SET_PWM?NR_SELECT_PWM_SCHEMA:NR_SELECT_READ_SCHEMA;
    if(limit&&v>limit){r->tool=NR_REJECT;r->argument=0;r->status=NR_TOOL_OUT_OF_RANGE;r->selection_source=NR_SELECT_DENIED;}
    return NR_FAST_HANDLED;
}
int nr_tool_decode_fast(const uint8_t *b,uint32_t n,nr_tool_request_t *r) {
    nr_context_t context;
    if(nr_tool_decode_machine(b,n,r)==NR_FAST_HANDLED)return NR_FAST_HANDLED;
    if(!b||!n||n>NR_SEQ)return nr_tool_decode_fast_with_context(b,n,r,0);
    if(nr_model_context(b,n,&context)) {
        if(r){r->tool=NR_REJECT;r->argument=0;r->operation=NR_OP_DEFAULT;r->margin=0;r->selection_source=NR_SELECT_DENIED;r->status=NR_TOOL_BAD_ARGUMENT;}
        return NR_FAST_HANDLED;
    }
    return nr_tool_decode_fast_with_context(b,n,r,&context);
}
int nr_tool_decode_fast_with_context(const uint8_t *b,uint32_t n,nr_tool_request_t *r,nr_context_t *context) {
    static const char *const read_words[]={"读","查询","查看","获取","返回","报告","多少","多热","热不热","报的","read","get","temperature","counter"};
    static const char *const run_words[]={"运行","执行","跑","启动","加测","测一次","run","start","execute"};
    nr_term_scan_t storage,*scan=&storage;
    int hint;int32_t argument=0;nr_tool_status_t status;
    if(!r)return NR_FAST_MISS;
    r->tool=NR_REJECT;r->argument=0;r->status=NR_TOOL_REJECTED;r->margin=0;
    r->operation=NR_OP_DEFAULT;r->selection_source=NR_SELECT_DENIED;
    if(!b||!n){r->status=NR_TOOL_EMPTY;return NR_FAST_HANDLED;}
    if(n>NR_SEQ){r->status=NR_TOOL_TOO_LONG;return NR_FAST_HANDLED;}
    {uint32_t start=contract_request_start(b,n);b+=start;n-=start;}
    n=contract_request_end(b,n);
    term_scan_init(scan,b,n);hint=contract_hint(scan,b,n);
    if(context)nr_context_select(context,hint>=0?(uint32_t)hint:5u,1u);
    if(context&&context->used&&context->deny){
        uint32_t i;int32_t maximum=nr_combined_thresholds[0];
        for(i=1;i<6;i++)if(nr_combined_thresholds[i]>maximum)maximum=nr_combined_thresholds[i];
        /* Schema hints and immutable encoder classes have different calibrated
         * branches. Ambiguous rejection defers to the full encoder,never
         * changes raw scores or silently overrides a learned veto. */
        if(context->margin<maximum&&hint>=0&&capability_allowed(scan,b,n,hint))return NR_FAST_MISS;
        r->status=NR_TOOL_POLICY_REJECTED;r->margin=context->margin;r->selection_source=NR_SELECT_CONTEXT_DENIED;return NR_FAST_HANDLED;
    }
    if(hint<0)return NR_FAST_MISS;
    if(!capability_allowed(scan,b,n,hint)){r->status=NR_TOOL_POLICY_REJECTED;return NR_FAST_HANDLED;}
    if(hint==NR_READ_TEMP||hint==NR_READ_COUNTER) {
        if(!HAS_TERMS(b,n,read_words))return NR_FAST_MISS;
        r->tool=(nr_tool_t)hint;r->status=NR_TOOL_OK;r->selection_source=NR_SELECT_READ_SCHEMA;
        return NR_FAST_HANDLED;
    }
    if(hint==NR_RUN_COREMARK) {
        if(!HAS_TERMS(b,n,run_words))return NR_FAST_MISS;
        r->tool=NR_RUN_COREMARK;r->status=NR_TOOL_OK;r->selection_source=NR_SELECT_READ_SCHEMA;
        return NR_FAST_HANDLED;
    }
    if(hint==NR_SET_LED) {
        status=led_arguments(scan,b,n,r);
        if(r->operation==NR_OP_DEFAULT && !led_mask_schema(scan,b,n) && !canonical_numeric_command(b,n,"led"))
            return NR_FAST_MISS;
        r->status=status;r->tool=status==NR_TOOL_OK?NR_SET_LED:NR_REJECT;
        r->selection_source=status==NR_TOOL_OK?NR_SELECT_LED_SCHEMA:NR_SELECT_DENIED;
        return NR_FAST_HANDLED;
    }
    if(!explicit_pwm_schema(scan,b,n)&&!canonical_numeric_command(b,n,"pwm"))return NR_FAST_MISS;
    status=duty_argument(b,n,&argument);r->status=status;
    if(status==NR_TOOL_OK){r->tool=NR_SET_PWM;r->argument=argument;r->selection_source=NR_SELECT_PWM_SCHEMA;}
    return NR_FAST_HANDLED;
}
nr_tool_status_t nr_tool_decode_prediction(const uint8_t *b,uint32_t n,
    const nr_prediction_t *prediction,nr_tool_request_t *r) {
    nr_term_scan_t storage,*scan=&storage;
    int hint;int32_t argument=0;nr_tool_status_t status;
    if(!r) return NR_TOOL_BAD_ARGUMENT;
    r->tool=NR_REJECT;r->argument=0;r->status=NR_TOOL_REJECTED;r->margin=0;
    r->operation=NR_OP_DEFAULT;r->selection_source=NR_SELECT_DENIED;
    if(!b || !n) return r->status=NR_TOOL_EMPTY;
    if(n>NR_SEQ) return r->status=NR_TOOL_TOO_LONG;
    if(!prediction || (unsigned)prediction->tool>=NR_CLASSES)
        return r->status=NR_TOOL_BAD_ARGUMENT;
    if(prediction->context_used&&prediction->context_deny){r->margin=prediction->context_margin;r->selection_source=NR_SELECT_CONTEXT_DENIED;return r->status=NR_TOOL_POLICY_REJECTED;}
    r->margin=prediction->margin;{uint32_t start=contract_request_start(b,n);b+=start;n-=start;}n=contract_request_end(b,n);term_scan_init(scan,b,n);hint=contract_hint(scan,b,n);
    if(hint<0) return r->status=prediction->tool==NR_REJECT?NR_TOOL_REJECTED:NR_TOOL_POLICY_REJECTED;
    if(!capability_allowed(scan,b,n,hint)) return r->status=NR_TOOL_POLICY_REJECTED;
    /* This metadata records routing separately from the immutable raw logits. */
    if(hint==NR_READ_TEMP || hint==NR_RUN_COREMARK || hint==NR_READ_COUNTER) {
        if(prediction->tool==NR_SET_LED || prediction->tool==NR_SET_PWM)
            return r->status=NR_TOOL_POLICY_REJECTED;
        r->tool=(nr_tool_t)hint;
        r->selection_source=(prediction->tool==r->tool &&
             prediction->margin>=NR_MIN_CONFIDENCE_MARGIN)?NR_SELECT_NEURAL:NR_SELECT_READ_SCHEMA;
        return r->status=NR_TOOL_OK;
    }
    if(hint==NR_SET_LED) {
        status=led_arguments(scan,b,n,r);
        /* Only explicit bounded LED schemas may recover a rejecting class.
         * Another actionable class may not be redirected into an actuator. */
        if((r->operation!=NR_OP_DEFAULT || led_mask_schema(scan,b,n)) && status==NR_TOOL_OK &&
           (prediction->tool==NR_REJECT || prediction->tool==NR_SET_LED)) {
            r->tool=NR_SET_LED;
            r->selection_source=(prediction->tool==NR_SET_LED &&
                prediction->margin>=NR_MIN_CONFIDENCE_MARGIN)?NR_SELECT_NEURAL:NR_SELECT_LED_SCHEMA;
            return r->status=NR_TOOL_OK;
        }
        r->argument=0;r->operation=NR_OP_DEFAULT;
    } else {
        status=duty_argument(b,n,&argument);
        /* An exact bounded write schema is an explicit user action, not a
         * neural confidence claim. Never redirect an LED prediction into PWM. */
        if(status==NR_TOOL_OK && explicit_pwm_schema(scan,b,n) && prediction->tool!=NR_SET_LED &&
           !(prediction->tool==NR_REJECT && prediction->margin>=NR_MIN_CONFIDENCE_MARGIN &&
             !explicit_polite_request(b,n)) &&
           (prediction->tool!=NR_SET_PWM || prediction->margin<NR_MIN_CONFIDENCE_MARGIN)) {
            r->tool=NR_SET_PWM;r->argument=argument;r->selection_source=NR_SELECT_PWM_SCHEMA;
            return r->status=NR_TOOL_OK;
        }
    }
    if(prediction->tool==NR_REJECT || prediction->margin<NR_MIN_CONFIDENCE_MARGIN)
        return r->status=NR_TOOL_REJECTED;
    if((int)prediction->tool!=hint) return r->status=NR_TOOL_POLICY_REJECTED;
    r->tool=(nr_tool_t)hint;r->selection_source=NR_SELECT_NEURAL;
    if(status!=NR_TOOL_OK) {
        if(status==NR_TOOL_POLICY_REJECTED) r->tool=NR_REJECT;
        return r->status=status;
    }
    if(hint==NR_SET_LED) return r->status=led_arguments(scan,b,n,r);
    r->argument=argument;return r->status=NR_TOOL_OK;
}
nr_tool_status_t nr_tool_decode(const uint8_t *b,uint32_t n,nr_tool_request_t *r) {
    nr_prediction_t prediction;
    if(!r) return NR_TOOL_BAD_ARGUMENT;
    if(!b || !n || n>NR_SEQ) return nr_tool_decode_prediction(b,n,0,r);
    if(nr_model_predict(b,n,&prediction)) {
        nr_tool_decode_prediction(b,n,0,r);
        return r->status=NR_TOOL_BACKEND_ERROR;
    }
    return nr_tool_decode_prediction(b,n,&prediction,r);
}
