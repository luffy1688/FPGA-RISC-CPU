/* platform = 本项目FPGA外设的轻量适配层，模型文件不直接处理串口。 */
#ifndef NR_PLATFORM_H
#define NR_PLATFORM_H
#include <stdint.h>
#ifndef NR_PLATFORM_CLOCK_HZ
#define NR_PLATFORM_CLOCK_HZ 27000000u
#endif
#ifndef NR_UART_BAUD
#define NR_UART_BAUD 115200u
#endif
#define NR_PWM_FREQUENCY_HZ 1000u
#define NR_PWM_PERIOD_TICKS (NR_PLATFORM_CLOCK_HZ/NR_PWM_FREQUENCY_HZ)
#if NR_PLATFORM_CLOCK_HZ < 1000
#error Platform clock too slow for the 1kHz PWM contract
#endif
#define NR_MMIO(address) (*(volatile uint32_t *)(address))
#define NR_LED NR_MMIO(0x10000004u)
uint32_t nr_cycle(void);
void nr_putc(char c);
void nr_puts(const char *s);
void nr_put_u32(uint32_t value);
void nr_put_i32(int32_t value);
uint32_t nr_length(const char *s);
/* 返回字节数，-1表示本行超过容量；排空整行以后才能读取下一条。 */
int nr_read_line(uint8_t *buffer,uint32_t capacity);
#ifndef NR_COREMARK_ITERATIONS
#define NR_COREMARK_ITERATIONS 300u
#endif
#endif
