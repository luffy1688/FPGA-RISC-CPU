/* Deliberate illegal instruction validates mcause/mepc reporting. */
#include "riscv_test.h"
RVTEST_RV32U
RVTEST_CODE_BEGIN
trap_instruction:
  .word 0xffffffff
  RVTEST_PASS
RVTEST_CODE_END
