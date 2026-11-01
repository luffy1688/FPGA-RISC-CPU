/* NeedleRV-X bare-machine adapter for upstream riscv-tests.
 * Test bodies and scalar assertions stay unchanged; this header only sets
 * reset/trap addresses and routes pass/fail to the simulation observation port.
 * This is an adapted instruction regression, not a RISC-V certification suite. */
#ifndef NEEDLERVX_RISCV_TEST_H
#define NEEDLERVX_RISCV_TEST_H
#define TESTNUM gp
#define RVTEST_RV32U
#define RVTEST_RV64U RVTEST_RV32U
#define RVTEST_CODE_BEGIN \
 .section .text.init,"ax",@progbits; .balign 4; .globl _start; _start:; \
 .option norvc; .option norelax; la t0, nr_trap; csrw mtvec,t0; li TESTNUM,0;
#define RVTEST_PASS \
 li t0,1; li t1,0x100000fc; sw t0,0(t1); 1: j 1b;
#define RVTEST_FAIL \
 slli t0,TESTNUM,1; ori t0,t0,1; li t1,0x100000fc; sw t0,0(t1); 1: j 1b;
#define RVTEST_CODE_END \
 .balign 4; nr_trap:; csrr t0,mepc; li t1,0x100000f8; sw t0,0(t1); \
 csrr t0,mcause; li t1,0x80000000; or t0,t0,t1; \
 li t1,0x100000fc; sw t0,0(t1); 1: j 1b;
#define RVTEST_DATA_BEGIN .balign 16; .globl begin_signature; begin_signature:
#define RVTEST_DATA_END .balign 16; .globl end_signature; end_signature:
#endif
