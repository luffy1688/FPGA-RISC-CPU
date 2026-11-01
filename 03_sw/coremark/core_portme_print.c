/* Small freestanding printf port for CoreMark's integer configuration. */
#include "coremark.h"
#include <stdarg.h>
static void putc_nr(char c) {
  // The SoC holds a UART store until the transmitter accepts it.
  *(volatile ee_u32*)0x10000000u=(unsigned char)c;
}
static int number_nr(ee_u32 v,unsigned base,int width,int zero,int neg) {
  char b[32]; int n=0,count=0;
  do { b[n++]="0123456789abcdef"[v%base]; v/=base; } while(v);
  if(neg && zero) {putc_nr('-'); count++;}
  while(width>n+neg) {putc_nr(zero?'0':' ');width--;count++;}
  if(neg && !zero) {putc_nr('-');count++;}
  while(n) {putc_nr(b[--n]);count++;} return count;
}
int ee_printf(const char *fmt,...) {
#if defined(NR_COREMARK_LIBRARY)
  extern int nr_coremark_validated;
  const char *prefix="Correct operation validated.";
  const char *a=fmt,*b=prefix;
  while(*b && *a==*b) {a++;b++;}
  if(!*b) nr_coremark_validated=1;
#endif
  va_list ap; int count=0; va_start(ap,fmt);
  while(*fmt) {
    if(*fmt!='%') {putc_nr(*fmt++);count++;continue;}
    fmt++; int zero=0,width=0,islong=0;
    if(*fmt=='0') {zero=1;fmt++;}
    while(*fmt>='0' && *fmt<='9') width=width*10+(*fmt++-'0');
    if(*fmt=='l') {islong=1;fmt++;}
    char f=*fmt++;
    if(f=='s') {const char *s=va_arg(ap,const char*);while(*s){putc_nr(*s++);count++;}}
    else if(f=='c') {putc_nr((char)va_arg(ap,int));count++;}
    else if(f=='%') {putc_nr('%');count++;}
    else if(f=='d' || f=='i') {ee_s32 v=islong?(ee_s32)va_arg(ap,long):va_arg(ap,int);count+=number_nr(v<0?0u-(ee_u32)v:(ee_u32)v,10,width,zero,v<0);}
    else if(f=='u'||f=='x') {ee_u32 v=islong?(ee_u32)va_arg(ap,unsigned long):va_arg(ap,unsigned int);count+=number_nr(v,f=='x'?16:10,width,zero,0);}
    else {putc_nr('?');count++;}
  }
  va_end(ap);return count;
}
