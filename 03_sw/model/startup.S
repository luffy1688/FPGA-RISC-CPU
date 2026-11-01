/* Bare-metal entry; any unexpected trap stops this firmware visibly. */
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
2: la t0,model_trap
  csrw mtvec,t0
  call main
3: j 3b
.align 2
model_trap:
  li t0,0x10000004
  li t1,0xee
  sw t1,0(t0)
4: j 4b
