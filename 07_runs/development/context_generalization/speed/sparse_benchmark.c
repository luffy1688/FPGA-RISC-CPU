#include "/work/LUO/NeedleRV-X/03_sw/platform/needle_platform.h"
#include "byte_tool_model.h"
#define NR_CONTEXT_SCRATCH_ATTR __attribute__((section(".ai_scratch"),aligned(4)))
#include "/work/LUO/NeedleRV-X/03_sw/model/byte_context.c.inc"
static const char *const cases[]={"led 37","请将PWM占空比设置为20%。","请解释PWM占空比设置为20%的含义。","假设把LED0点亮会发生什么？","0123456789012345678901234567890123456789012345678901234567890123","请读取FPGA当前温度。","abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl","LED0已经点亮了吗？","读取计数器","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};
int main(void){for(uint32_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++){
 uint32_t n=0;while(cases[i][n])n++;nr_context_result_t r;int32_t z[6]={-300,-200,-100,100,20,0};
 uint32_t begin=nr_cycle();for(uint32_t repeat=0;repeat<16;repeat++)if(nr_context_apply((const uint8_t*)cases[i],n,z,&r)){NR_LED=0xee;return 2;}uint32_t end=nr_cycle();
 nr_puts("CONTEXT_COST {\"case\":");nr_put_u32(i);nr_puts(",\"length\":");nr_put_u32(n);nr_puts(",\"cycles16\":");nr_put_u32(end-begin);nr_puts(",\"nonzero\":");nr_put_u32(r.nonzero_features);nr_puts(",\"scalar_macs\":");nr_put_u32(r.scalar_macs);nr_puts(",\"margin\":");nr_put_i32(r.margin);nr_puts("}\n");
}NR_LED=0xc0;return 0;}
