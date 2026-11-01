/* startup.s: first instructions after FPGA reset.
 * Set a stack, clear zero-initialized data, then enter main(). */
.section .text.startup,"ax",@progbits
.globl _start
.option norvc
.option norelax
_start:
  la gp, __global_pointer$
  la sp, __stack_top
  la t0, __bss_start
  la t1, __bss_end
1: bgeu t0,t1,2f
  sw zero,0(t0)
  addi t0,t0,4
  j 1b
2:
  la t0, trap_entry
  csrw mtvec,t0
  call main
3: j 3b

/* Trap records let executable assertions check the real CPU behavior.
 * Preserve every temporary used here. Return past the fault, or to an explicit
 * resume address when a test intentionally jumps into an invalid region. */
.align 2
.globl trap_entry
trap_entry:
  addi sp,sp,-16
  sw t0,0(sp)
  sw t1,4(sp)
  sw t2,8(sp)
  sw t3,12(sp)
  la t1,trap_cause
  csrr t0,mcause
  sw t0,0(t1)
  la t1,trap_value
  csrr t2,mtval
  sw t2,0(t1)
  la t1,trap_pc
  csrr t2,mepc
  sw t2,0(t1)
  la t1,trap_seen
  lw t3,0(t1)
  addi t3,t3,1
  sw t3,0(t1)
  bgez t0,1f
  csrw mie,zero             /* A test IRQ stays asserted until main clears it. */
1:
  la t1,trap_resume
  lw t3,0(t1)
  sw zero,0(t1)
  beqz t3,2f
  mv t2,t3
  j 3f
2: addi t2,t2,4
3: csrw mepc,t2
  lw t0,0(sp)
  lw t1,4(sp)
  lw t2,8(sp)
  lw t3,12(sp)
  addi sp,sp,16
  mret

.section .bss,"aw",@nobits
.align 2
.globl trap_seen,trap_cause,trap_value,trap_pc,trap_resume
trap_seen: .word 0
trap_cause: .word 0
trap_value: .word 0
trap_pc: .word 0
trap_resume: .word 0

