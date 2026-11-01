/* irq_startup = 独立启动与中断入口。CPU 的精确中断在流水线排空后进入。
 * 128B 栈帧保持 16B 对齐，保存除 x0/sp 外全部寄存器；sp 由相反 addi 恢复。 */
.section .text.startup,"ax",@progbits
.globl _start
.option norvc
.option norelax
_start:
    la gp,__global_pointer$
    la sp,__stack_top
    la t0,__bss_start
    la t1,__bss_end
1:  bgeu t0,t1,2f
    sw zero,0(t0)
    addi t0,t0,4
    j 1b
2:  la t0,nr_timer_trap
    csrw mtvec,t0
    call main
3:  j 3b

.balign 4
.globl nr_timer_trap
nr_timer_trap:
    addi sp,sp,-128
    sw ra,0(sp)
    sw gp,4(sp)
    sw tp,8(sp)
    sw t0,12(sp)
    sw t1,16(sp)
    sw t2,20(sp)
    sw s0,24(sp)
    sw s1,28(sp)
    sw a0,32(sp)
    sw a1,36(sp)
    sw a2,40(sp)
    sw a3,44(sp)
    sw a4,48(sp)
    sw a5,52(sp)
    sw a6,56(sp)
    sw a7,60(sp)
    sw s2,64(sp)
    sw s3,68(sp)
    sw s4,72(sp)
    sw s5,76(sp)
    sw s6,80(sp)
    sw s7,84(sp)
    sw s8,88(sp)
    sw s9,92(sp)
    sw s10,96(sp)
    sw s11,100(sp)
    sw t3,104(sp)
    sw t4,108(sp)
    sw t5,112(sp)
    sw t6,116(sp)
    csrr t1,mcause
    la t0,nr_irq_cause
    sw t1,0(t0)
    li t2,0x80000007
    bne t1,t2,nr_irq_unexpected
    la t0,nr_irq_count
    lw t1,0(t0)
    addi t1,t1,1
    sw t1,0(t0)
    la t0,nr_inference_active
    lw t1,0(t0)
    la t0,nr_irq_in_model
    sw t1,0(t0)
    csrr t1,mcycle
    la t0,nr_irq_cycle
    sw t1,0(t0)
    csrr t1,mepc
    la t0,nr_irq_pc
    sw t1,0(t0)
    li t0,0x40000000
    lw t1,0(t0)
    la t0,nr_irq_xnd_status
    sw t1,0(t0)
    /* 只停止 timer；不清 XND 状态，不改 DMA buffer，也不调用模型。 */
    li t0,0x10000030
    sw zero,0(t0)
    li t0,128
    csrc mie,t0
    lw ra,0(sp)
    lw gp,4(sp)
    lw tp,8(sp)
    lw t0,12(sp)
    lw t1,16(sp)
    lw t2,20(sp)
    lw s0,24(sp)
    lw s1,28(sp)
    lw a0,32(sp)
    lw a1,36(sp)
    lw a2,40(sp)
    lw a3,44(sp)
    lw a4,48(sp)
    lw a5,52(sp)
    lw a6,56(sp)
    lw a7,60(sp)
    lw s2,64(sp)
    lw s3,68(sp)
    lw s4,72(sp)
    lw s5,76(sp)
    lw s6,80(sp)
    lw s7,84(sp)
    lw s8,88(sp)
    lw s9,92(sp)
    lw s10,96(sp)
    lw s11,100(sp)
    lw t3,104(sp)
    lw t4,108(sp)
    lw t5,112(sp)
    lw t6,116(sp)
    addi sp,sp,128
    mret
nr_irq_unexpected:
    li t0,0x10000004
    li t1,0xee
    sw t1,0(t0)
4:  j 4b
