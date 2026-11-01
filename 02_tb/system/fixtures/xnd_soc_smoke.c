/* CPU-to-SoC-to-XND integration smoke firmware. */
typedef unsigned int u32;
typedef unsigned char u8;
#define REG32(a) (*(volatile u32 *)(a))
#define REG8(a)  (*(volatile u8 *)(a))
static void put32(u32 off,u32 v){ REG32(0x40000000u+off)=v; }
static u32 get32(u32 off){ return REG32(0x40000000u+off); }
int main(void){
  volatile u8 *a=(volatile u8 *)0x00020000u;
  volatile u8 *w=(volatile u8 *)0x00020010u;
  volatile u32 *y=(volatile u32 *)0x00020020u;
  unsigned i;
  for(i=0;i<8;i++) a[i]=(u8)(i+1);
  w[0]=0x21; w[1]=0x43; /* INT4 weights: 1,2,3,4,1,2,3,4 */
  y[0]=0;
  put32(0x20,0x00020000u);
  put32(0x24,0x00020010u);
  put32(0x28,0x00020020u);
  put32(0x2c,8u);
  put32(0x30,1u);
  put32(0x34,4u);
  put32(0x38,1u); /* INT4 mode */
  put32(0x10,2u); /* LOAD activation into slot 0 */
  while(get32(0x00)&1u) {}
  put32(0x10,3u); /* GEMV */
  while(get32(0x00)&1u) {}
  REG32(0x10000004u)= (get32(0x04)==100u) ? 0x5au : 0xe1u;
  for(;;) __asm__ volatile("nop");
}
