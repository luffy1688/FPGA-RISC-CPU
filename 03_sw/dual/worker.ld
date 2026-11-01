OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { RAM (rwx) : ORIGIN = 0, LENGTH = 64K }
SECTIONS {
 .text : { KEEP(*(.text.startup)) *(.text*) } > RAM
 .rodata : { *(.rodata*) *(.srodata*) } > RAM
 .data : { __global_pointer$ = . + 0x800; *(.sdata*) *(.data*) } > RAM
 .bss (NOLOAD) : { . = ALIGN(4); __bss_start = .; *(.sbss*) *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .; } > RAM
 __stack_top = ORIGIN(RAM) + LENGTH(RAM) - 16;
 ASSERT(__bss_end < __stack_top - 8192, "worker RAM overflow")
}
