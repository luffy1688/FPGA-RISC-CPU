
#include "semantic_cached.h"
#include "../xnd_runtime/xnd_mmio.h"
#define CXREG(off) (*(volatile uint32_t*)(0x40010000u+(off)))
static int8_t dense[2048] __attribute__((section(".ai_scratch"),aligned(4)));
static uint16_t previous[512] __attribute__((section(".ai_scratch"),aligned(4)));
static uint32_t initialized,previous_n,last_macs;
static const int8_t *resident_w1,*resident_w2;
static const int32_t *resident_b1,*resident_b2;
uint32_t nr_semantic_cached_workspace_bytes(void){return sizeof(dense)+sizeof(previous)+7u*4u;}
uint32_t nr_semantic_cached_last_macs(void){return last_macs;}
static void barrier(void){__asm__ volatile("fence iorw,iorw":::"memory");}
static int range(const void*p,uint32_t bytes){uintptr_t a=(uintptr_t)p;return a>=0x20000u&&a<0x80000u&&!(a&3u)&&bytes<=0x80000u-a;}
static int wait(void){for(uint32_t i=0;i<1000000u;i++){uint32_t status=CXREG(0);if(status&2u){barrier();return status&4u?-2:0;}}return -2;}
static int command(uint32_t cmd){CXREG(0)=6;barrier();CXREG(4)=cmd;barrier();return wait();}
static uint32_t pack(const int8_t*p){return (uint32_t)(uint8_t)p[0]|((uint32_t)(uint8_t)p[1]<<8)|((uint32_t)(uint8_t)p[2]<<16)|((uint32_t)(uint8_t)p[3]<<24);}
static void cfg(uint32_t target,uint32_t index,uint32_t data){CXREG(16)=target;CXREG(20)=index;CXREG(24)=data;}
static int failed(nr_semantic_stats_t*s){s->failures++;resident_w1=0;return -2;}
int nr_semantic_cached_gemv(const int8_t*w1,const int32_t*b1,const int8_t*w2,const int32_t*b2,const int16_t*counts,const uint16_t*touched,uint32_t count,uint32_t hidden,uint32_t outputs,int32_t*scores,int8_t*hidden_out,nr_semantic_stats_t*s){
 uint32_t i,status;nr_semantic_stats_t empty={0};
 if(!s)return -2;
 *s=empty;last_macs=0;
 if(!counts||!touched||!scores||!hidden_out||count>500u||hidden!=64u||outputs!=16u||!range(w1,131072)||!range(w2,1024)||!range(b1,256)||!range(b2,64))return failed(s);
 for(i=0;i<count;i++)if(touched[i]>=2048u)return failed(s);
 status=CXREG(0);if(status&1u)return failed(s);
 if(!initialized){for(i=0;i<2048;i++)dense[i]=0;initialized=1;}
 else for(i=0;i<previous_n;i++)dense[previous[i]]=0;
 previous_n=0;
 for(i=0;i<count;i++){uint32_t k=touched[i];int32_t v=counts[k];if(v>3)v=3;else if(v< -3)v=-3;dense[k]=(int8_t)(v*8);previous[previous_n++]=(uint16_t)k;}
 if(!(status&256u)||resident_w1!=w1||resident_w2!=w2||resident_b1!=b1||resident_b2!=b2){
  for(i=0;i<64;i++)cfg(2,i,(uint32_t)b1[i]);
  for(i=0;i<16;i++)cfg(3,i,(uint32_t)b2[i]);
  for(i=0;i<256;i++)cfg(1,i,pack(w2+4*i));
  CXREG(8)=(uint32_t)(uintptr_t)w1;if(command(0))return failed(s);
  s->used=1;s->loads=1;s->dma_read_bytes=CXREG(36)*4u;s->engine_cycles=CXREG(32);
  resident_w1=w1;resident_w2=w2;resident_b1=b1;resident_b2=b2;
 }
 CXREG(16)=0;for(i=0;i<512;i++){CXREG(20)=i;CXREG(24)=pack(dense+4*i);}barrier();
 if(command(1))return failed(s);
 if(!(CXREG(0)&512u))return failed(s);
 s->used=1;s->jobs=1;s->engine_cycles+=CXREG(32);s->dma_read_bytes+=CXREG(36)*4u;last_macs=CXREG(40);
 for(i=0;i<16;i++)scores[i]=(int32_t)CXREG(256+4*i);
 for(i=0;i<16;i++){uint32_t v=CXREG(512+4*i);for(uint32_t q=0;q<4;q++)hidden_out[i*4+q]=(int8_t)(v>>(8*q));}
 barrier();return 0;
}
