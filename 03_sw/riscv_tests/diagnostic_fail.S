/* Deliberate failure validates harness test number and branch-PC reporting.
 * This is project harness code, not an upstream ISA test. */
#include "riscv_test.h"
RVTEST_RV32U
RVTEST_CODE_BEGIN
  li TESTNUM,42
assertion_branch:
  bnez TESTNUM,fail
  RVTEST_PASS
fail:
  RVTEST_FAIL
RVTEST_CODE_END
