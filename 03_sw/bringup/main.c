/* main.c: self-checking firmware. This is executable by simulation or a board.
 * No operating system, host-side instruction emulator, or fake CPU result. */
typedef unsigned int u32;
extern u32 cpu_acceptance(void);
static void uart_putc(char c) { *(volatile u32 *)0x10000000u = (u32)(unsigned char)c; }
static void uart_puts(const char *s) { while (*s) uart_putc(*s++); }
int main(void) {
  u32 failure = cpu_acceptance();
  uart_puts(failure ? "CPU ACCEPT FAIL\n" : "CPU ACCEPT PASS\n");
  /* The standalone TB watches this register. Production SoC may expose the same
     test register, or use the UART line alone while testing on the board. */
  *(volatile u32 *)0x100000fcu = failure ? (0xbad00000u | failure) : 0x600dcafeu;
  for (;;) __asm__ volatile("nop");
}

