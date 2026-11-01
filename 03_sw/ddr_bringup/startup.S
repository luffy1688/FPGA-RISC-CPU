/* 本固件从片上BRAM地址0启动；DDR只作为数据窗，不放启动指令或栈。 */
.section .text.startup,"ax",@progbits
.globl _start
.option norvc
.option norelax
_start:
  la gp,__global_pointer$
  la sp,__stack_top
  la t0,__bss_start
  la t1,__bss_end
1: bgeu t0,t1,2f
  sw zero,0(t0)
  addi t0,t0,4
  j 1b
2:
  la t0,ddr_unexpected_trap
  csrw mtvec,t0
  csrw mie,zero
  call main
3: j 3b
/* Any unexpected CPU exception fails visibly. Fault injection targets XND DMA,
 * which reports through XND status while this CPU continues executing BRAM. */
.balign 4
ddr_unexpected_trap:
  /* The bring-up negative test intentionally reads DDR_LIMIT and the
   * peripheral-map hole.  Consume exactly those load access faults, advance
   * mepc, and return; every other trap remains a visible failure. */
  csrr t0,mcause
  li t1,5
  beq t0,t1,5f
  li t1,7
  bne t0,t1,9f
5:
  la t2,ddr_expected_traps
  lw t3,0(t2)
  beqz t3,9f
  addi t3,t3,-1
  sw t3,0(t2)
  la t2,ddr_observed_traps
  lw t3,0(t2)
  addi t3,t3,1
  sw t3,0(t2)
  csrr t2,mepc
  addi t2,t2,4
  csrw mepc,t2
  mret
9:
  li t0,0x10000004
  li t1,0xef
  sw t1,0(t0)
4: j 4b
