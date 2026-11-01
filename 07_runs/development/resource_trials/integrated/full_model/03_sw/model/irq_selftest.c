/* irq_selftest = 独立的“整模型被打断后继续”验收，不替换参赛默认镜像。
 * timer ISR 只记状态，不调用模型，不和现有单实例 workspace 并发。 */
#include "byte_tool_model.h"
#include "byte_tool_xnd.h"
#include "tool_dispatch.h"
#include "../platform/needle_platform.h"

/* 由 irq_startup.S 读写；volatile 保证编译器不把 ISR 共享状态藏在寄存器。 */
volatile uint32_t nr_irq_count,nr_irq_in_model,nr_irq_cause,nr_irq_cycle;
volatile uint32_t nr_irq_pc,nr_irq_xnd_status,nr_inference_active;
#define TIMER_LOW NR_MMIO(0x10000020u)
#define TIMER_HIGH NR_MMIO(0x10000024u)
#define COMPARE_LOW NR_MMIO(0x10000028u)
#define COMPARE_HIGH NR_MMIO(0x1000002cu)
#define TIMER_ENABLE NR_MMIO(0x10000030u)
#define IRQ_DELAY_CYCLES (NR_PLATFORM_CLOCK_HZ/108u)

static void timer_off(void) {
    __asm__ volatile("csrci mstatus,8; li t0,128; csrc mie,t0":::"t0","memory");
    TIMER_ENABLE=0;
}
static void timer_once(uint32_t delay) {
    uint32_t hi,lo,hi_again,next;
    timer_off();
    /* 一致读取 64 位 mtime：低字溢出时重读，不把 RV32 两次读取当原子操作。 */
    do {hi=TIMER_HIGH;lo=TIMER_LOW;hi_again=TIMER_HIGH;} while(hi!=hi_again);
    next=lo+delay;
    /* 先禁止 timer，再写 high=全1，最后提交真正 high，避免中间值早触发。 */
    COMPARE_HIGH=0xffffffffu;COMPARE_LOW=next;COMPARE_HIGH=hi+(next<lo);
    TIMER_ENABLE=1;
    __asm__ volatile("li t0,128; csrw mie,t0; csrsi mstatus,8":::"t0","memory");
}
static void field(const char *key,uint32_t value) {nr_puts(key);nr_put_u32(value);}
static void report(uint32_t enabled,uint32_t begin,uint32_t end,
                   const nr_prediction_t *p,const nr_tool_request_t *r,
                   nr_exec_status_t execution,uint32_t value,nr_model_xnd_stats_t s) {
    uint32_t i;
    nr_puts("NR_IRQ_RESULT {\"enabled\":");nr_put_u32(enabled);
    field(",\"mode\":",3);field(",\"graph\":",1);field(",\"dot4\":",1);
    field(",\"begin\":",begin);field(",\"end\":",end);field(",\"cycles\":",end-begin);
    field(",\"irq_count\":",nr_irq_count);field(",\"irq_in_model\":",nr_irq_in_model);
    field(",\"mcause\":",nr_irq_cause);field(",\"irq_cycle\":",nr_irq_cycle);
    field(",\"mepc\":",nr_irq_pc);field(",\"xnd_status_at_irq\":",nr_irq_xnd_status);
    field(",\"timer_enabled_after\":",TIMER_ENABLE);
    field(",\"tool\":",p->tool);field(",\"decode\":",r->status);
    field(",\"execute\":",execution);field(",\"value\":",value);field(",\"led\":",NR_LED);
    field(",\"loads\":",s.loads);field(",\"jobs\":",s.jobs);field(",\"reuses\":",s.reuses);
    field(",\"activation_bytes\":",s.activation_dma_bytes);
    field(",\"weight_bytes\":",s.weight_dma_bytes);field(",\"output_bytes\":",s.output_dma_bytes);
    field(",\"failures\":",s.failures);nr_puts(",\"logits\":[");
    for(i=0;i<6;i++) {if(i) nr_putc(',');nr_put_i32(p->logits[i]);}
    nr_puts("]}\n");
}
int main(void) {
    static const uint8_t text[]="读取计数器";
    nr_prediction_t baseline;
    uint32_t enabled,i;
    timer_off();NR_LED=37;
    nr_model_xnd_set_mode(NR_XND_LIFETIME);
    nr_model_set_qkv_interleaved(1);nr_model_set_attention_dot4(1);
    nr_puts("NR_IRQ_BEGIN clock_hz=");nr_put_u32(NR_PLATFORM_CLOCK_HZ);nr_puts("; compare_delay=");nr_put_u32(IRQ_DELAY_CYCLES);nr_puts("\n");
    for(enabled=0;enabled<2;enabled++) {
        nr_prediction_t p;nr_tool_request_t r;uint32_t begin,end,value;
        nr_exec_status_t execution;nr_model_xnd_stats_t stats;
        nr_irq_count=nr_irq_in_model=nr_irq_cause=nr_irq_cycle=nr_irq_pc=nr_irq_xnd_status=0;
        nr_model_xnd_reset_stats();
        nr_inference_active=1;begin=nr_cycle();
        if(enabled) timer_once(IRQ_DELAY_CYCLES);
        if(nr_model_predict(text,sizeof(text)-1,&p)) {
            timer_off();nr_puts("NR_IRQ_ERROR model backend\n");NR_LED=0xee;return 1;
        }
        end=nr_cycle();nr_inference_active=0;timer_off();
        stats=nr_model_xnd_stats();
        nr_tool_decode_prediction(text,sizeof(text)-1,&p,&r);
        execution=nr_tool_execute(&r,&value);
        report(enabled,begin,end,&p,&r,execution,value,stats);
        if(enabled==0) baseline=p;
        else for(i=0;i<6;i++) if(p.logits[i]!=baseline.logits[i]) {
            nr_puts("NR_IRQ_ERROR numeric mismatch\n");NR_LED=0xee;return 1;
        }
        if(p.tool!=NR_READ_COUNTER || r.status!=NR_TOOL_OK || execution!=NR_EXEC_OK ||
           !value || NR_LED!=37 || stats.failures ||
           (enabled ? (nr_irq_count!=1 || nr_irq_in_model!=1 || nr_irq_cause!=0x80000007u ||
                       nr_irq_cycle<=begin || nr_irq_cycle>=end) : nr_irq_count!=0)) {
            nr_puts("NR_IRQ_ERROR interrupt/tool acceptance\n");NR_LED=0xee;return 1;
        }
    }
    nr_puts("NR_MODEL_IRQ_PASS\n");NR_LED=0xc0;
    return 0;
}
