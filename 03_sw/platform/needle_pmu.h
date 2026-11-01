/* pmu = performance monitoring unit：CPU内的小计数器帮助解释时间花在哪里。
   前后采样以无符号减法处理一次32位回绕；一个区间必须短于2^32周期/事件。
   CSR逐个读取，不是原子快照；PMU区间包含少量采样指令，不能当零开销CPI。 */
#ifndef NR_PMU_H
#define NR_PMU_H
#include <stdint.h>
typedef struct {
    uint32_t cycles, instret, branches, redirect_misses;
    uint32_t mem_load_stall_cycles, ic_misses, dc_misses;
} nr_pmu_t;
static inline void nr_pmu_snapshot(nr_pmu_t *s) {
    uint32_t cy,ir,br,mp,st,ic,dc;
    __asm__ volatile (
        "csrr %0,mcycle\n\tcsrr %1,minstret\n\t"
        "csrr %2,0xb03\n\tcsrr %3,0xb04\n\tcsrr %4,0xb05\n\t"
        "csrr %5,0xb06\n\tcsrr %6,0xb07"
        : "=r"(cy),"=r"(ir),"=r"(br),"=r"(mp),"=r"(st),"=r"(ic),"=r"(dc)
        : : "memory");
    s->cycles=cy;s->instret=ir;s->branches=br;s->redirect_misses=mp;
    s->mem_load_stall_cycles=st;s->ic_misses=ic;s->dc_misses=dc;
}
static inline nr_pmu_t nr_pmu_delta(const nr_pmu_t *a,const nr_pmu_t *b) {
    nr_pmu_t d;
    d.cycles=b->cycles-a->cycles;d.instret=b->instret-a->instret;
    d.branches=b->branches-a->branches;d.redirect_misses=b->redirect_misses-a->redirect_misses;
    d.mem_load_stall_cycles=b->mem_load_stall_cycles-a->mem_load_stall_cycles;
    d.ic_misses=b->ic_misses-a->ic_misses;d.dc_misses=b->dc_misses-a->dc_misses;
    return d;
}
/* B03只统计条件branch；B04统计nextpc!=prediction（含jump等），
   因此B04/B03不等于条件分支错误预测率。B05是mem_hold||load_hazard周期。 */
#endif
