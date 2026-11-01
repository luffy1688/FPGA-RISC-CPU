/* dispatch = 按工具编号执行；只有软件检查通过才能改变外设。 */
#include "tool_dispatch.h"
#include "../platform/needle_platform.h"
nr_exec_status_t nr_tool_execute_receipt(const nr_tool_request_t *r,uint32_t *value,nr_tool_receipt_t *receipt) {
    nr_tool_receipt_t local={0};uint32_t expected;
    if(!receipt)receipt=&local;
    *receipt=local;
    if(value) *value=0;
    if(!r || r->status!=NR_TOOL_OK) return NR_EXEC_DENIED;
    if(r->tool!=NR_SET_LED && r->operation!=NR_OP_DEFAULT) return NR_EXEC_DENIED;
    switch(r->tool) {
    case NR_SET_LED:
        if(r->operation==NR_OP_DEFAULT) {
            if((uint32_t)r->argument>255u) return NR_EXEC_DENIED;
            expected=(uint32_t)r->argument;NR_LED=expected;
        } else {
            uint32_t mask,current;
            if((r->operation!=NR_OP_LED_ON && r->operation!=NR_OP_LED_OFF) ||
               (uint32_t)r->argument>7u) return NR_EXEC_DENIED;
            /* GPIO7 belongs to PWM while enabled. Do not silently disable it. */
            if(r->argument==7 && (NR_MMIO(0x1000003cu)&1u)) return NR_EXEC_UNAVAILABLE;
            mask=1u<<(uint32_t)r->argument;current=NR_LED;
            expected=r->operation==NR_OP_LED_ON ? current|mask : current&~mask;NR_LED=expected;
        }
        receipt->kind=1;receipt->requested=expected;receipt->readback=NR_LED;
        receipt->match=receipt->readback==expected;
        if(value) *value=receipt->readback;
        return receipt->match?NR_EXEC_OK:NR_EXEC_FAILED;
    case NR_RUN_COREMARK:
        return nr_coremark_execute(value);
    case NR_SET_PWM:
        if((uint32_t)r->argument>100u) return NR_EXEC_DENIED;
        NR_MMIO(0x10000038u)=NR_PWM_PERIOD_TICKS; /* Platform clock / target 1kHz. */
        NR_MMIO(0x10000034u)=(NR_PWM_PERIOD_TICKS*(uint32_t)r->argument)/100u;
        NR_MMIO(0x1000003cu)=1;
        receipt->kind=2;receipt->requested=(uint32_t)r->argument;
        receipt->period=NR_MMIO(0x10000038u);receipt->high=NR_MMIO(0x10000034u);
        receipt->enabled=NR_MMIO(0x1000003cu)&1u;
        receipt->readback=receipt->period?(receipt->high*100u)/receipt->period:0;
        receipt->match=receipt->period==NR_PWM_PERIOD_TICKS &&
            receipt->high==(NR_PWM_PERIOD_TICKS*(uint32_t)r->argument)/100u && receipt->enabled==1;
        if(value) *value=receipt->readback;
        return receipt->match?NR_EXEC_OK:NR_EXEC_FAILED;
    case NR_READ_TEMP: {
        /* 真实ADC有效位与故障位决定能否执行；没有采样绝不伪造温度。 */
        uint32_t status=NR_MMIO(0x10000100u),raw;
        if((status&7u)!=5u) return NR_EXEC_UNAVAILABLE;
        raw=NR_MMIO(0x10000104u)&4095u;
        receipt->kind=3;receipt->adc_status=status;receipt->adc_raw=raw;
        receipt->readback=raw;receipt->match=1;
        /* UG040009: T=code*0.1219-273.15; return signed centi-degrees C. */
        if(value) *value=(uint32_t)((int32_t)((raw*1219u+50u)/100u)-27315);
        return NR_EXEC_OK;
    }
    case NR_READ_COUNTER:
        receipt->kind=4;receipt->readback=nr_cycle();receipt->match=1;
        if(value) *value=receipt->readback;
        return NR_EXEC_OK;
    default:
        /* Unsupported tool IDs must never silently execute another operation. */
        return NR_EXEC_UNAVAILABLE;
    }
}

nr_exec_status_t nr_tool_execute(const nr_tool_request_t *r,uint32_t *value) {
    return nr_tool_execute_receipt(r,value,0);
}
