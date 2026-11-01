#include "/work/LUO/NeedleRV-X/03_sw/platform/needle_platform.h"
#include "03_sw/xnd_runtime/xnd_mmio.h"
#include "semantic_xnd.h"
#include "data.h"
#define NR_CONTEXT_SCRATCH_ATTR __attribute__((section(".ai_scratch"),aligned(4)))
#include "features.inc"
static int32_t scores_cpu[16],scores_xnd[16];
extern uint32_t __ai_scratch_start[],__ai_scratch_used_end[];
static int32_t ra(int32_t v){return v>=0?(v+32)/64:-((-v+32)/64);}
static uint32_t count_nonzero(void){uint32_t count=0;for(uint32_t i=0;i<nr_ctx_touched[255];i++)count+=nr_ctx_counts[nr_ctx_touched[i]]!=0;return count;}
/* Same sparse algorithm as capacity_boundary.c,without the separateCPUrepair5.
 * This is the entire64x1024->16MLP,includingallclipsandrounds. */
static void cpu(int32_t*out){int32_t sums[64]={0},hidden[64],v,z;uint32_t i,j,index;
 for(i=0;i<nr_ctx_touched[255];i++){index=nr_ctx_touched[i];v=nr_ctx_counts[index];if(!v)continue;if(v>3)v=3;else if(v< -3)v=-3;v*=8;for(j=0;j<64;j++)sums[j]+=v*nr_capacity_w1[j][index];}
 for(j=0;j<64;j++){v=ra(sums[j])+nr_capacity_b1[j];hidden[j]=v<0?0:v>127?127:v;}
 for(i=0;i<16;i++){z=0;for(j=0;j<64;j++)z+=hidden[j]*nr_capacity_w2[i][j];out[i]=ra(z)+nr_capacity_b2[i];}
}
static void error(uint32_t code){nr_puts("MLP64_FAIL ");nr_put_u32(code);nr_putc('\n');NR_LED=0xee;}
static void emit(const char*name,uint32_t*a){nr_puts(name);nr_putc('[');for(uint32_t i=0;i<8;i++){if(i)nr_putc(',');nr_put_u32(a[i]);}nr_putc(']');}

static int expanded_memory_boundary(void){
 const uint32_t a[4]={0x0003fffcu,0x00040000u,0x00060000u,XND_AI_RAM_END-4u};
 uint32_t saved[4],i;
 for(i=0;i<4;i++)saved[i]=*(volatile uint32_t*)(uintptr_t)a[i];
 for(i=0;i<4;i++)*(volatile uint32_t*)(uintptr_t)a[i]=0xa5200000u+i;
 for(i=0;i<4;i++)if(*(volatile uint32_t*)(uintptr_t)a[i]!=(0xa5200000u+i))return 81;
 *(volatile uint8_t*)(uintptr_t)(XND_AI_RAM_END-4u)=0x5au;
 if(*(volatile uint32_t*)(uintptr_t)(XND_AI_RAM_END-4u)!=0xa520005au)return 82;
 for(i=0;i<4;i++)*(volatile uint32_t*)(uintptr_t)a[i]=saved[i];
 XND_A_ADDR=XND_AI_RAM_END-4u;XND_COLS=19;XND_START=2;xnd_fence();
 if(xnd_wait(10000u)!=3)return 83;
 xnd_ack();XND_A_ADDR=0x1fffcu;XND_COLS=19;XND_START=2;xnd_fence();
 if(xnd_wait(10000u)!=3)return 84;
 xnd_ack();nr_puts("EXPANDED_MEMORY_BOUNDARY_PASS\n");return 0;
}
int main(void){int memory_error=expanded_memory_boundary();if(memory_error){error((uint32_t)memory_error);return 1;}
 for(uint32_t*p=__ai_scratch_start;p<__ai_scratch_used_end;p++)*p=0x55555555u;
 for(uint32_t c=0;c<CASES;c++){
  if(c<TEXT_CASES){uint32_t n=0;while(texts[c][n])n++;if(nr_ctx_features((const uint8_t*)texts[c],n)){error(1);return 1;}}
  else{uint32_t n=0;for(uint32_t i=0;i<1024;i++)if(expected_x[c][i]){nr_ctx_touched[n++]=(uint16_t)i;nr_ctx_counts[i]=expected_x[c][i]>0?32767:-32768;}nr_ctx_touched[255]=(uint16_t)n;}
  uint32_t cc[8],hc[8],nz=count_nonzero();nr_semantic_stats_t st;
  for(uint32_t rep=0;rep<8;rep++){
   uint32_t begin=nr_cycle();cpu(scores_cpu);cc[rep]=nr_cycle()-begin;
   begin=nr_cycle();int code=nr_semantic_xnd_gemv(&nr_capacity_w1[0][0],nr_capacity_b1,&nr_capacity_w2[0][0],nr_capacity_b2,nr_ctx_counts,nr_ctx_touched,nr_ctx_touched[255],64,16,scores_xnd,&st);hc[rep]=nr_cycle()-begin;
   if(code||!st.used||st.failures||st.loads!=5||st.jobs!=5){error(2);return 1;}
   for(uint32_t i=0;i<16;i++)if(scores_cpu[i]!=expected_score[c][i]||scores_xnd[i]!=expected_score[c][i]){error(3);return 1;}
   if(XND_STATUS&0x301u){error(4);return 1;}
  }
  nr_puts("MLP64_CASE {\"case\":");nr_put_u32(c);nr_puts(",\"nonzero\":");nr_put_u32(nz);emit(",\"cpu_cycles\":",cc);emit(",\"xnd_cycles\":",hc);nr_puts(",\"engine_cycles\":");nr_put_u32(st.engine_cycles);nr_puts(",\"reads\":");nr_put_u32(st.dma_read_bytes);nr_puts(",\"writes\":");nr_put_u32(st.dma_write_bytes);nr_puts("}\n");
 }
 nr_semantic_stats_t bad;uint16_t invalid=1024;int code=nr_semantic_xnd_gemv(&nr_capacity_w1[0][0],nr_capacity_b1,&nr_capacity_w2[0][0],nr_capacity_b2,nr_ctx_counts,&invalid,1,64,16,scores_xnd,&bad);
 if(code!=-2||bad.used||bad.failures!=1){error(5);return 1;}nr_puts("MLP64_BAD_INDEX_PASS\n");
 code=nr_semantic_xnd_gemv((const int8_t*)(XND_AI_RAM_END-16),nr_capacity_b1,&nr_capacity_w2[0][0],nr_capacity_b2,nr_ctx_counts,nr_ctx_touched,0,64,16,scores_xnd,&bad);
 if(code!=-2||bad.used||bad.failures!=1){error(6);return 1;}nr_puts("MLP64_BAD_WEIGHT_PASS\n");
 static int8_t other_input[256] __attribute__((section(".ai_scratch"),aligned(4)));static int32_t other_raw[64] __attribute__((section(".ai_scratch"),aligned(4)));
 for(uint32_t i=0;i<256;i++)other_input[i]=8;
 xnd_job_t j={(uint32_t)(uintptr_t)other_input,(uint32_t)(uintptr_t)nr_capacity_w1,(uint32_t)(uintptr_t)other_raw,256,64,1024,0,0};
 xnd_ack();if(xnd_load_activation(&j)||xnd_wait(1000000u)){error(7);return 1;}xnd_ack();if(xnd_launch_gemv(&j)){error(8);return 1;}
 for(uint32_t i=0;i<16;i++)scores_xnd[i]=0x12345678;
 code=nr_semantic_xnd_gemv(&nr_capacity_w1[0][0],nr_capacity_b1,&nr_capacity_w2[0][0],nr_capacity_b2,nr_ctx_counts,nr_ctx_touched,0,64,16,scores_xnd,&bad);
 if(code!=-2||bad.used||bad.failures!=1){error(9);return 1;}for(uint32_t i=0;i<16;i++)if(scores_xnd[i]!=0x12345678){error(10);return 1;}
 if(xnd_wait(1000000u)){error(11);return 1;}for(uint32_t row=0;row<64;row++){int32_t want=0;for(uint32_t col=0;col<256;col++)want+=8*nr_capacity_w1[row][col];if(other_raw[row]!=want){error(12);return 1;}}
 nr_puts("MLP64_BUSY_FATAL_PASS\n");
 if(nr_ctx_features((const uint8_t*)texts[0],6)||nr_semantic_xnd_gemv(&nr_capacity_w1[0][0],nr_capacity_b1,&nr_capacity_w2[0][0],nr_capacity_b2,nr_ctx_counts,nr_ctx_touched,nr_ctx_touched[255],64,16,scores_xnd,&bad)){error(13);return 1;}
 for(uint32_t i=0;i<16;i++){if(scores_xnd[i]!=expected_score[0][i]){error(14);return 1;}}
 if(XND_STATUS&0x301u){error(15);return 1;}
 if(nr_semantic_xnd_workspace_bytes()!=2696){error(16);return 1;}
 nr_puts("MLP64_RECOVERY_PASS\nMLP64_WORKSPACE2696\nMLP64_PASS\n");NR_LED=0xc0;return 0;
}
