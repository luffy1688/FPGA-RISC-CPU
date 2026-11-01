/* Put each independently executed upstream test at the CPU reset PC. */
OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { RAM (rwx) : ORIGIN = 0, LENGTH = 256K }
SECTIONS {
 .text : { *(.text.init) *(.text .text.*) } > RAM
 .rodata : { *(.rodata .rodata.*) } > RAM
 .data : { *(.data .data.*) *(.sdata .sdata.*) } > RAM
 .bss (NOLOAD) : { *(.bss .bss.*) *(.sbss .sbss.*) } > RAM
 /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
