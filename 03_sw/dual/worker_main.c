#include "coremark.h"
int nr_coremark_validated;
int nr_coremark_entry(void);
int main(void){while(!*(volatile ee_u32*)0x10000134u){}nr_coremark_validated=0;nr_coremark_entry();*(volatile ee_u32*)0x10000120u=get_time();*(volatile ee_u32*)0x10000124u=ITERATIONS;*(volatile ee_u32*)0x10000128u=nr_coremark_validated;*(volatile ee_u32*)0x10000004u=nr_coremark_validated?0xc0:0xee;return 0;}
