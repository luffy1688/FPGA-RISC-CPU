#include "/work/LUO/NeedleRV-X/03_sw/platform/needle_platform.h"
#define NR_CONTEXT_SCRATCH_ATTR __attribute__((section(".ai_scratch"),aligned(4)))
#include "capacity_boundary.c"
static const char *const cases[]={"请读取FPGA当前温度。","请将PWM占空比设置为20%。","只关闭LED0，其他LED不要改变","假设把LED0点亮会发生什么？"};
int main(void){for(uint32_t i=0;i<4;i++){uint32_t n=0;while(cases[i][n])n++;int32_t encoder[6]={-300,-200,-100,100,20,500},out[36];uint32_t start=nr_cycle();for(uint32_t rep=0;rep<16;rep++)if(run_capacity((const uint8_t*)cases[i],n,encoder,out)){NR_LED=0xee;return 2;}uint32_t end=nr_cycle();nr_puts("COMBINED_COST {\"case\":");nr_put_u32(i);nr_puts(",\"cycles16\":");nr_put_u32(end-start);nr_puts(",\"bytes\":");nr_put_u32(n);nr_puts(",\"bucket\":");nr_put_i32(out[32]);nr_puts("}\n");}NR_LED=0xc0;return 0;}
