#include "needle_platform.h"
uint32_t nr_cycle(void) {
    uint32_t value;__asm__ volatile("csrr %0,mcycle":"=r"(value));return value;
}
void nr_putc(char c) {NR_MMIO(0x10000000u)=(uint8_t)c;}
void nr_puts(const char *s) {while(*s) nr_putc(*s++);}
void nr_put_u32(uint32_t value) {
    char digits[10];uint32_t n=0;
    do {digits[n++]=(char)('0'+value%10);value/=10;} while(value);
    while(n) nr_putc(digits[--n]);
}
void nr_put_i32(int32_t value) {
    uint32_t magnitude=(uint32_t)value;
    if(value<0) {nr_putc('-');magnitude=0u-magnitude;}
    nr_put_u32(magnitude);
}
uint32_t nr_length(const char *s) {uint32_t n=0;while(s[n]) n++;return n;}
int nr_read_line(uint8_t *buffer,uint32_t capacity) {
    static int skip_lf=0;
    uint32_t length=0;int overflow=0;
    for(;;) {
        uint8_t c;
        while(!(NR_MMIO(0x1000000cu)&2u)) {}
        c=(uint8_t)NR_MMIO(0x10000010u);
        /* CRLF is one terminator; a standalone empty line is observable. */
        if(skip_lf) {skip_lf=0;if(c=='\n') continue;}
        if(c=='\r' || c=='\n') {
            skip_lf=c=='\r';
            return overflow?-1:(int)length;
        }
        if(c==8 || c==127) {if(length && !overflow) length--;continue;}
        if(length<capacity) buffer[length++]=c;else overflow=1;
    }
}

/* GCC may lower zero-initialized structs to these freestanding C ABI helpers.
 * Volatile byte stores keep the helper itself from becoming a recursive
 * builtin call. memcpy follows the C non-overlap contract. */
void *memset(void *destination,int value,__SIZE_TYPE__ length) {
    volatile uint8_t *out=(volatile uint8_t *)destination;
    while(length--)*out++=(uint8_t)value;
    return destination;
}
void *memcpy(void *destination,const void *source,__SIZE_TYPE__ length) {
    volatile uint8_t *out=(volatile uint8_t *)destination;
    const uint8_t *in=(const uint8_t *)source;
    while(length--)*out++=*in++;
    return destination;
}
