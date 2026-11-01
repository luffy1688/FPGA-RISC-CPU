/* linker.ld: describes WHERE firmware lives, not what it computes.
 * FPGA RAM: 0x00000000..0x0007ffff, 512 KiB.
 * Lower 128 KiB = CPU program/data/stack; upper 384 KiB = AI constants/workspace. */
OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
  CPU_RAM (rwx) : ORIGIN = 0x00000000, LENGTH = 128K
  AI_RAM  (rw)  : ORIGIN = 0x00020000, LENGTH = 384K
}
SECTIONS {
  .text : { KEEP(*(.text.startup)) *(.text .text.*) } > CPU_RAM
  .rodata : { *(.rodata .rodata.*) } > CPU_RAM
  .data : { *(.data .data.*) *(.sdata .sdata.*) } > CPU_RAM
  __global_pointer$ = ADDR(.data) + 0x800;
  .bss (NOLOAD) : {
    . = ALIGN(4);
    __bss_start = .;
    *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON)
    . = ALIGN(4);
    __bss_end = .;
  } > CPU_RAM
  __stack_top = ORIGIN(CPU_RAM) + LENGTH(CPU_RAM);
  __stack_bottom = __stack_top - 8192;
  ASSERT(__bss_end <= __stack_bottom, "CPU firmware exceeds RAM below stack")
  /* Read-only learned auxiliary heads use the spare shared SRAM without
   * reducing CPU stack. They are initialized by the same RAM image, not DMA
   * writes. No uninitialized scratch object may overlap these constants. */
  .ai_const : {
    . = ALIGN(16);
    __ai_const_start = .;
    *(.ai_const .ai_const.*)
    . = ALIGN(16);
    __ai_const_end = .;
  } > AI_RAM
  .ai_scratch (NOLOAD) : {
    . = ALIGN(16);
    __ai_scratch_start = .;
    *(.ai_scratch .ai_scratch.*)
    __ai_scratch_used_end = .;
    __ai_scratch_end = ORIGIN(AI_RAM) + LENGTH(AI_RAM);
  } > AI_RAM
  ASSERT(__ai_scratch_used_end <= ORIGIN(AI_RAM)+LENGTH(AI_RAM), "AI constants and workspace exceed SRAM")
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}

