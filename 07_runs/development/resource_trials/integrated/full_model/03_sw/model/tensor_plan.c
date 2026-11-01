#include "tensor_plan.h"
#include "byte_tool_model.h"
void nr_tensor_reset(nr_tensor_residence_t *s) {
    uint32_t i;
    for(i=0;i<NR_TENSOR_SLOTS;i++) {
        s->valid[i]=0;s->key[i]=0;s->columns[i]=0;
    }
}
int nr_tensor_choose(nr_tensor_residence_t *s,uint32_t mode,const int8_t *key,
    uint32_t cols,uint32_t flags,uint32_t hardware_valid,uint32_t *slot,int *reuse) {
    uint32_t i,slots=mode==3?NR_TENSOR_SLOTS:1u;
    if(!key || !cols || cols>NR_TENSOR_SLOT_BYTES || mode<1 || mode>3) return -1;
    *reuse=0;
    /* 硬件reset/invalidate之后软件状态也失效。输入被修改时同地址旧内容失效。 */
    for(i=0;i<slots;i++) if(!(hardware_valid&(1u<<i)) ||
       (!(flags&NR_GEMV_REUSE_INPUT) && s->key[i]==key)) s->valid[i]=0;
    if(mode!=1 && (flags&NR_GEMV_REUSE_INPUT))
        for(i=0;i<slots;i++) if(s->valid[i] && s->key[i]==key && s->columns[i]==cols) {
            *slot=i;*reuse=1;return 0;
        }
    if(mode!=3) {*slot=0;return 0;}
    for(i=0;i<slots;i++) if(!s->valid[i]) {*slot=i;return 0;}
    /* 不静默覆盖还有消费者的槽。上游图必须限制同时活跃输入<=2或显式释放。 */
    return NR_TENSOR_NO_SLOT;
}
void nr_tensor_commit(nr_tensor_residence_t *s,uint32_t slot,const int8_t *key,uint32_t cols) {
    s->key[slot]=key;s->columns[slot]=cols;s->valid[slot]=1;
}
void nr_tensor_release(nr_tensor_residence_t *s,uint32_t slot) {s->valid[slot]=0;}
