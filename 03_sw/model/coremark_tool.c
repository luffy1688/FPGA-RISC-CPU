/* 将未修改的CoreMark算法作为同步工具调用，打印完整CRC/计时证据后返回。 */
#include "tool_dispatch.h"
#include "coremark.h"
int nr_coremark_validated;
int nr_coremark_entry(void);
nr_exec_status_t nr_coremark_execute(uint32_t *cycles) {
    nr_coremark_validated=0;
    nr_coremark_entry();
    if(cycles) *cycles=(uint32_t)get_time();
    return nr_coremark_validated?NR_EXEC_OK:NR_EXEC_FAILED;
}
