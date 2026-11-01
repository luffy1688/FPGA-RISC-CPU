#ifndef NR_TOOL_DISPATCH_H
#define NR_TOOL_DISPATCH_H
#include "byte_tool_model.h"
typedef enum {NR_EXEC_OK=0,NR_EXEC_DENIED=1,NR_EXEC_UNAVAILABLE=2,NR_EXEC_FAILED=3} nr_exec_status_t;
nr_exec_status_t nr_coremark_execute(uint32_t *cycles);
typedef struct {
    uint32_t kind,requested,readback,match,period,high,enabled,adc_status,adc_raw;
} nr_tool_receipt_t;
nr_exec_status_t nr_tool_execute_receipt(const nr_tool_request_t *request,uint32_t *value,nr_tool_receipt_t *receipt);
nr_exec_status_t nr_tool_execute(const nr_tool_request_t *request,uint32_t *value);
#endif
