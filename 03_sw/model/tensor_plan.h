/* tensor_plan: 两个XND输入槽的生命周期分配器；不代表外部DDR缓存。 */
#ifndef NR_TENSOR_PLAN_H
#define NR_TENSOR_PLAN_H
#include <stdint.h>
#define NR_TENSOR_SLOTS 2u
#define NR_TENSOR_SLOT_BYTES 256u /* 与xnd_engine MAX_COLS=256一致，每列INT8。 */
#define NR_TENSOR_NO_SLOT (-3)
typedef struct {
    const int8_t *key[NR_TENSOR_SLOTS];
    uint32_t columns[NR_TENSOR_SLOTS];
    uint8_t valid[NR_TENSOR_SLOTS];
} nr_tensor_residence_t;
void nr_tensor_reset(nr_tensor_residence_t *state);
/* mode: 1逐次加载，2单槽相邻复用，3双槽生命周期。flags用NR_GEMV_*。
   选择成功后调用commit；最后一个消费者完成后调用release。
   地址是内容身份的一部分，REUSE承诺该地址内容未变；没有REUSE必须重新LOAD。
   同址内容更新后必须去掉REUSE；LAST_USE之后、跨请求reset、硬件失效后不得复用。
   中断处理程序不得修改仍活跃的输入；若修改，调用方须reset/重新LOAD。
   本分配器不会检查任意写内存，不能被描述成硬件缓存一致性协议。 */
int nr_tensor_choose(nr_tensor_residence_t *state,uint32_t mode,
    const int8_t *key,uint32_t columns,uint32_t flags,uint32_t hardware_valid,
    uint32_t *slot,int *reuse);
void nr_tensor_commit(nr_tensor_residence_t *state,uint32_t slot,
                      const int8_t *key,uint32_t columns);
void nr_tensor_release(nr_tensor_residence_t *state,uint32_t slot);
#endif
