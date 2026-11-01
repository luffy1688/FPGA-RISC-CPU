/* cpu_acceptance.S: real RV32IM instructions with software assertions.
 * Each nonzero return code identifies one requirement. Registers t5/t6 are
 * reserved for the assertion macros. Successful completion returns a0=0. */
.option norvc
.option norelax
.section .text,"ax",@progbits
.align 2
.globl cpu_acceptance

.macro CHECK reg, value, code
  li t5,\value
  beq \reg,t5,1f
  li a0,\code
  j acceptance_fail
1:
.endm
.macro CHECK_REG left, right, code
  beq \left,\right,1f
  li a0,\code
  j acceptance_fail
1:
.endm
.macro MUST_TAKE insn, left, right, code
  \insn \left,\right,1f
  li a0,\code
  j acceptance_fail
1:
.endm
.macro MUST_SKIP insn, left, right, code
  \insn \left,\right,1f
  j 2f
1:
  li a0,\code
  j acceptance_fail
2:
.endm
.macro CLEAR_TRAP
  la t4,trap_seen
  sw zero,0(t4)
.endm
.macro CHECK_TRAP cause, value, pc_label, code
  la t4,trap_seen
  lw a1,0(t4)
  CHECK a1,1,\code
  la t4,trap_cause
  lw a1,0(t4)
  CHECK a1,\cause,\code
  la t4,trap_value
  lw a1,0(t4)
  CHECK a1,\value,\code
  la t4,trap_pc
  lw a1,0(t4)
  la a2,\pc_label
  CHECK_REG a1,a2,\code
.endm
cpu_acceptance:
  addi sp,sp,-16
  sw ra,12(sp)

  /* Integer arithmetic, x0, shift truncation, signed/unsigned comparisons. */
  addi zero,zero,77
  CHECK zero,0,0x01
  li a1,-7
  li a2,3
  add a3,a1,a2
  CHECK a3,-4,0x02
  sub a3,a1,a2
  CHECK a3,-10,0x03
  slt a3,a1,a2
  CHECK a3,1,0x04
  sltu a3,a1,a2
  CHECK a3,0,0x05
  slti a3,a1,-6
  CHECK a3,1,0x06
  sltiu a3,a1,-1
  CHECK a3,1,0x07
  li a1,0x80000001
  srai a3,a1,1
  CHECK a3,0xc0000000,0x08
  srli a3,a1,1
  CHECK a3,0x40000000,0x09
  slli a3,a1,1
  CHECK a3,2,0x0a
  li a2,33
  sll a3,a1,a2
  CHECK a3,2,0x0b
  srl a3,a1,a2
  CHECK a3,0x40000000,0x0c
  sra a3,a1,a2
  CHECK a3,0xc0000000,0x0d
  li a1,0xaa55aa55
  li a2,0x0ff00ff0
  xor a3,a1,a2
  CHECK a3,0xa5a5a5a5,0x0e
  or a3,a1,a2
  CHECK a3,0xaff5aff5,0x0f
  and a3,a1,a2
  CHECK a3,0x0a500a50,0x10
  xori a3,a1,-1
  CHECK a3,0x55aa55aa,0x11
  andi a3,a1,0x55
  CHECK a3,0x55,0x12
  ori a3,zero,0x7ff
  CHECK a3,0x7ff,0x13
  lui a3,0xfffff
  CHECK a3,0xfffff000,0x14
auipc_site:
  auipc a1,0
  la a2,auipc_site
  CHECK_REG a1,a2,0x15

  /* Memory: byte enables, all byte offsets, signed/zero-extended halfwords. */
  la t0,acceptance_buffer
  li a1,0x80ff7f01
  sw a1,0(t0)
  lb a2,0(t0)
  CHECK a2,1,0x20
  lb a2,1(t0)
  CHECK a2,127,0x21
  lb a2,2(t0)
  CHECK a2,-1,0x22
  lb a2,3(t0)
  CHECK a2,-128,0x23
  lbu a2,2(t0)
  CHECK a2,255,0x24
  lbu a2,3(t0)
  CHECK a2,128,0x25
  lh a2,0(t0)
  CHECK a2,0x7f01,0x26
  lh a2,2(t0)
  CHECK a2,0xffff80ff,0x27
  lhu a2,2(t0)
  CHECK a2,0x80ff,0x28
  li a1,0xaa
  sb a1,1(t0)
  lw a2,0(t0)
  CHECK a2,0x80ffaa01,0x29
  li a1,0xbbee
  sh a1,2(t0)
  lw a2,0(t0)
  CHECK a2,0xbbeeaa01,0x2a
  sw zero,4(t0)
  lw zero,0(t0)
  CHECK zero,0,0x2b
  lw a2,4(t0)
  CHECK a2,0,0x2c
  /* Load -> immediate consumer, then store -> load, with delayed RAM. */
  lw a1,0(t0)
  addi a2,a1,1
  sw a2,8(t0)
  lw a3,8(t0)
  CHECK a3,0xbbeeaa02,0x2d

  /* Six branch types, both taken and not taken; repeated loop trains BHT. */
  li a1,-1
  li a2,1
  MUST_TAKE beq,a1,a1,0x30
  MUST_SKIP beq,a1,a2,0x31
  MUST_TAKE bne,a1,a2,0x32
  MUST_SKIP bne,a1,a1,0x33
  MUST_TAKE blt,a1,a2,0x34
  MUST_SKIP blt,a2,a1,0x35
  MUST_TAKE bge,a2,a1,0x36
  MUST_SKIP bge,a1,a2,0x37
  MUST_TAKE bltu,a2,a1,0x38
  MUST_SKIP bltu,a1,a2,0x39
  MUST_TAKE bgeu,a1,a2,0x3a
  MUST_SKIP bgeu,a2,a1,0x3b
  li t0,7
  li a1,0
1: addi a1,a1,1
  addi t0,t0,-1
  bnez t0,1b
  CHECK a1,7,0x3c
  jal ra,jal_destination
jal_return_address:
  li a0,0x3d
  j acceptance_fail
jal_destination:
  la a1,jal_return_address
  CHECK_REG ra,a1,0x3d
  la t0,jalr_destination
  ori t0,t0,1              /* JALR must clear target bit 0. */
  jalr ra,0(t0)
jalr_return_address:
  li a0,0x3e
  j acceptance_fail
jalr_destination:
  la a1,jalr_return_address
  CHECK_REG ra,a1,0x3e

  /* M extension: all eight operations, negative values and architectural edges. */
  li a1,-7
  li a2,3
  mul a3,a1,a2
  CHECK a3,-21,0x40
  mulh a3,a1,a2
  CHECK a3,-1,0x41
  mulhsu a3,a1,a2
  CHECK a3,-1,0x42
  mulhu a3,a1,a2
  CHECK a3,2,0x43
  div a3,a1,a2
  CHECK a3,-2,0x44
  rem a3,a1,a2
  CHECK a3,-1,0x45
  divu a3,a1,a2
  CHECK a3,0x55555553,0x46
  remu a3,a1,a2
  CHECK a3,0,0x47
  li a1,-1
  li a2,-1
  mulhu a3,a1,a2
  CHECK a3,0xfffffffe,0x48
  mulhsu a3,a1,a2
  CHECK a3,-1,0x49
  li a1,0x80000000
  li a2,0x7fffffff
  mulh a3,a1,a2
  CHECK a3,0xc0000000,0x4a
  li a2,-1
  div a3,a1,a2
  CHECK a3,0x80000000,0x4b
  rem a3,a1,a2
  CHECK a3,0,0x4c
  div a3,a1,zero
  CHECK a3,-1,0x4d
  rem a3,a1,zero
  CHECK a3,0x80000000,0x4e
  divu a3,a1,zero
  CHECK a3,-1,0x4f
  remu a3,a1,zero
  CHECK a3,0x80000000,0x50
  li a1,7
  li a2,-3
  div a3,a1,a2
  CHECK a3,-2,0x51
  rem a3,a1,a2
  CHECK a3,1,0x52

  /* Custom dot4 opcode 0x7b: four SIGNED INT8 products added into INT32. */
  li a1,0x04fd02ff         /* lanes = -1, 2, -3, 4 */
  li a2,0xfc03fe01         /* lanes =  1,-2,  3,-4 */
  .insn r 0x7b,0,0,a3,a1,a2
  CHECK a3,-30,0x58

  /* CSR read/write/set/clear, including zimm and zero-source read semantics. */
  li a1,0x1234
  csrrw a2,mscratch,a1
  CHECK a2,0,0x60
  csrr a2,mscratch
  CHECK a2,0x1234,0x61
  li a1,3
  csrrs a2,mscratch,a1
  CHECK a2,0x1234,0x62
  csrr a2,mscratch
  CHECK a2,0x1237,0x63
  csrrc a2,mscratch,a1
  CHECK a2,0x1237,0x64
  csrr a2,mscratch
  CHECK a2,0x1234,0x65
  csrrwi a2,mscratch,7
  CHECK a2,0x1234,0x66
  csrrsi a2,mscratch,8
  CHECK a2,7,0x67
  csrrci a2,mscratch,1
  CHECK a2,15,0x68
  csrrs a2,mscratch,zero
  CHECK a2,14,0x69
  csrrc a2,mscratch,zero
  CHECK a2,14,0x6a
  csrr a1,cycle
  nop
  csrr a2,cycle
  sub a3,a2,a1
  bnez a3,1f
  li a0,0x6b
  j acceptance_fail
1: fence
  fence.i

  /* Trap path must record cause/PC/value and return through MRET exactly once. */
  CLEAR_TRAP
illegal_site:
  .word 0xffffffff
  CHECK_TRAP 2,0xffffffff,illegal_site,0x70
  CLEAR_TRAP
ecall_site:
  ecall
  CHECK_TRAP 11,0,ecall_site,0x71
  CLEAR_TRAP
break_site:
  ebreak
  la t4,trap_value
  lw a1,0(t4)
  la a2,break_site
  CHECK_REG a1,a2,0x72
  la t4,trap_cause
  lw a1,0(t4)
  CHECK a1,3,0x72
  la t4,trap_seen
  lw a1,0(t4)
  CHECK a1,1,0x72
  CLEAR_TRAP
  li t0,1
misaligned_load_site:
  lw a3,0(t0)
  CHECK_TRAP 4,1,misaligned_load_site,0x73
  CLEAR_TRAP
  li t0,3
misaligned_store_site:
  sh zero,0(t0)
  CHECK_TRAP 6,3,misaligned_store_site,0x74
  CLEAR_TRAP
readonly_csr_site:
  csrrw a3,cycle,zero
  CHECK_TRAP 2,0xc00016f3,readonly_csr_site,0x75
  CLEAR_TRAP
reserved_csr_site:
  csrr a3,0x777
  CHECK_TRAP 2,0x777026f3,reserved_csr_site,0x76
  CLEAR_TRAP
  li t0,2
misaligned_jump_site:
  jalr zero,0(t0)
  CHECK_TRAP 0,2,misaligned_jump_site,0x77
  /* Bad data addresses make the bus return an error rather than hang. */
  CLEAR_TRAP
  li t0,0x80000000
access_load_site:
  lw a3,0(t0)
  CHECK_TRAP 5,0x80000000,access_load_site,0x78
  CLEAR_TRAP
  li t0,0x80000000
access_store_site:
  sw zero,0(t0)
  CHECK_TRAP 7,0x80000000,access_store_site,0x79

  li a0,0
acceptance_fail:
  lw ra,12(sp)
  addi sp,sp,16
  ret

.section .bss,"aw",@nobits
.align 4
acceptance_buffer: .space 16

