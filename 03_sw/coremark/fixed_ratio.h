/* Fixed-point reporting only; no floating point or toolchain udivdi3.
 * Some installed libgcc variants contain compressed instructions. This local
 * restoring divider uses shifts/add/subtract that compile for RV32IM. */
#ifndef NR_FIXED_RATIO_H
#define NR_FIXED_RATIO_H
#include <stdint.h>
static uint32_t nr_report_div_u64_u32(uint64_t numerator,uint32_t denominator) {
    uint64_t rem=0,quotient=0;unsigned i;
    if(!denominator)return 0;
    for(i=0;i<64;i++) {
        rem=(rem<<1)|(numerator>>63);numerator<<=1;quotient<<=1;
        if(rem>=denominator){rem-=denominator;quotient|=1;}
    }
    return quotient>0xffffffffu?0xffffffffu:(uint32_t)quotient;
}
#endif
