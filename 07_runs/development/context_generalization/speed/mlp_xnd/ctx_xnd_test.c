#include "/work/LUO/NeedleRV-X/03_sw/platform/needle_platform.h"
#include "/work/LUO/NeedleRV-X/03_sw/xnd_runtime/xnd_mmio.h"
#include "data.h"
#define NR_CONTEXT_SCRATCH_ATTR __attribute__((section(".ai_scratch"),aligned(4)))
#include "features.inc"
#define AI __attribute__((section(".ai_scratch"),aligned(4)))
static int8_t input[1024] AI,hidden[MLP_HIDDEN] AI;
static int32_t chunks[4][MLP_HIDDEN] AI,raw1[MLP_HIDDEN] AI,raw2[MLP_OUTPUTS] AI,software[MLP_HIDDEN] AI;
static uint16_t indices[1024] AI;
static uint32_t dense_ready,previous_nonzero;
static int8_t sw_hidden[MLP_HIDDEN] AI;
static int32_t sw_score[MLP_OUTPUTS] AI;
static uint32_t loads,jobs,engine_cycles,read_bytes,write_bytes,macs;
static int32_t round6(int32_t x){return x>=0?(x+32)/64:-((-x+32)/64);}
static int8_t quant(int32_t x,int32_t b){int32_t z=round6(x)+b;return z<0?0:z>127?127:(int8_t)z;}
static void error(uint32_t code){nr_puts("MLP_XND_FAIL ");nr_put_u32(code);nr_putc('\n');NR_LED=0xee;}
static int check(int status){if(status){error(1000u+(uint32_t)status);return 0;}return 1;}
static void collect(void){engine_cycles+=XND_CYCLES;read_bytes+=XND_DMA_READ_BYTES;write_bytes+=XND_DMA_WRITE_BYTES;macs+=XND_MACS;}
static int run_job(const int8_t*x,const int8_t*w,int32_t*y,uint32_t rows,uint32_t columns,uint32_t stride,uint32_t slot){
 xnd_job_t j={(uint32_t)(uintptr_t)x,(uint32_t)(uintptr_t)w,(uint32_t)(uintptr_t)y,columns,rows,stride,0,slot};
 XND_POST_CFG=0;xnd_ack();if(!check(xnd_load_activation(&j))||!check(xnd_wait(1000000u)))return 0;loads++;collect();
 xnd_ack();if(!check(xnd_launch_gemv(&j))||!check(xnd_wait(1000000u)))return 0;jobs++;collect();return 1;
}
static void scalar(const int8_t*x,uint32_t nz,int sparse,int32_t*out){
 for(uint32_t row=0;row<MLP_HIDDEN;row++){
  int32_t sum=0;if(sparse){for(uint32_t i=0;i<nz;i++){uint32_t k=indices[i];sum+=(int32_t)x[k]*mlp_w1[row][k];}}
  else{for(uint32_t k=0;k<1024;k++)sum+=(int32_t)x[k]*mlp_w1[row][k];}out[row]=sum;
 }
}
static void software_second(const int32_t*first) {
 for(uint32_t row=0;row<MLP_HIDDEN;row++)sw_hidden[row]=quant(first[row],mlp_b1[row]);
 for(uint32_t row=0;row<MLP_OUTPUTS;row++){int32_t sum=0;for(uint32_t col=0;col<MLP_HIDDEN;col++)sum+=(int32_t)sw_hidden[col]*mlp_w2[row][col];sw_score[row]=round6(sum)+mlp_b2[row];}
}
int main(void){
 for(uint32_t c=0;c<MLP_CASES;c++){
  uint32_t prep=nr_cycle(),nz=0;
  /* Shared dense vector is initialized once,then only the preceding request's
   * nonzero bins are reset. Do this before extracting the new touched list. */
  if(!dense_ready){for(uint32_t i=0;i<1024;i++)input[i]=0;dense_ready=1;}
  else{for(uint32_t i=0;i<previous_nonzero;i++)input[indices[i]]=0;}
  if(c<MLP_TEXT_CASES){uint32_t n=0;while(texts[c][n])n++;if(nr_ctx_features((const uint8_t*)texts[c],n)){error(1);return 1;}
   for(uint32_t i=0;i<nr_ctx_touched[255];i++){uint32_t k=nr_ctx_touched[i];int32_t v=nr_ctx_counts[k];v=v>3?3:v< -3?-3:v;input[k]=(int8_t)(v*8);if(v)indices[nz++]=(uint16_t)k;}
  }else for(uint32_t i=0;i<1024;i++){input[i]=expected_x[c][i];if(input[i])indices[nz++]=(uint16_t)i;}
  previous_nonzero=nz;uint32_t prepcycles=nr_cycle()-prep;
  for(uint32_t i=0;i<1024;i++)if(input[i]!=expected_x[c][i]){error(2);return 1;}
  uint32_t begin=nr_cycle();scalar(input,nz,0,software);software_second(software);uint32_t swdense=nr_cycle()-begin;
  for(uint32_t row=0;row<MLP_HIDDEN;row++)if(software[row]!=expected_raw1[c][row]){error(3);return 1;}
  begin=nr_cycle();scalar(input,nz,1,software);software_second(software);uint32_t swsparse=nr_cycle()-begin;
  for(uint32_t row=0;row<MLP_HIDDEN;row++)if(software[row]!=expected_raw1[c][row]||sw_hidden[row]!=expected_h[c][row]){error(4);return 1;}
  for(uint32_t row=0;row<MLP_OUTPUTS;row++)if(sw_score[row]!=expected_score[c][row]){error(8);return 1;}
  loads=jobs=engine_cycles=read_bytes=write_bytes=macs=0;begin=nr_cycle();
  for(uint32_t chunk=0;chunk<4;chunk++)if(!run_job(input+chunk*256,&mlp_w1[0][chunk*256],chunks[chunk],MLP_HIDDEN,256,1024,chunk&1))return 1;
  for(uint32_t row=0;row<MLP_HIDDEN;row++){int32_t sum=0;for(uint32_t chunk=0;chunk<4;chunk++)sum+=chunks[chunk][row];raw1[row]=sum;hidden[row]=quant(sum,mlp_b1[row]);}
  if(!run_job(hidden,&mlp_w2[0][0],raw2,MLP_OUTPUTS,MLP_HIDDEN,MLP_HIDDEN,0))return 1;
  int32_t scores[MLP_OUTPUTS];for(uint32_t row=0;row<MLP_OUTPUTS;row++)scores[row]=round6(raw2[row])+mlp_b2[row];
  uint32_t hwcycles=nr_cycle()-begin;
  for(uint32_t row=0;row<MLP_HIDDEN;row++)if(raw1[row]!=expected_raw1[c][row]||hidden[row]!=expected_h[c][row]){error(5);return 1;}
  for(uint32_t row=0;row<MLP_OUTPUTS;row++)if(raw2[row]!=expected_raw2[c][row]||scores[row]!=expected_score[c][row]){error(6);return 1;}
  if(loads!=5||jobs!=5||macs!=MLP_HIDDEN*1024+MLP_OUTPUTS*MLP_HIDDEN||read_bytes!=1024+MLP_HIDDEN*1024+MLP_HIDDEN+MLP_OUTPUTS*MLP_HIDDEN||write_bytes!=4*MLP_HIDDEN*4+MLP_OUTPUTS*4){error(7);return 1;}
  nr_puts("MLP_XND_CASE {\"case\":");nr_put_u32(c);nr_puts(",\"nonzero\":");nr_put_u32(nz);nr_puts(",\"prep_cycles\":");nr_put_u32(prepcycles);nr_puts(",\"sw_dense_cycles\":");nr_put_u32(swdense);nr_puts(",\"sw_sparse_cycles\":");nr_put_u32(swsparse);nr_puts(",\"xnd_cycles\":");nr_put_u32(hwcycles);nr_puts(",\"engine_cycles\":");nr_put_u32(engine_cycles);nr_puts(",\"loads\":");nr_put_u32(loads);nr_puts(",\"jobs\":");nr_put_u32(jobs);nr_puts(",\"read_bytes\":");nr_put_u32(read_bytes);nr_puts(",\"write_bytes\":");nr_put_u32(write_bytes);nr_puts(",\"macs\":");nr_put_u32(macs);nr_puts("}\n");
 }
 /* Guard proof uses the same actualMMIO engine. NoCPUfallback runs while busy. */
 for(uint32_t i=0;i<1024;i++)input[i]=expected_x[0][i];
 xnd_job_t fault={(uint32_t)(uintptr_t)input,(uint32_t)(uintptr_t)mlp_w1,(uint32_t)(uintptr_t)chunks[0],256,MLP_HIDDEN,1024,0,0};
 XND_POST_CFG=0;xnd_ack();if(xnd_load_activation(&fault)||xnd_wait(1000000u)){error(20);return 1;}
 fault.weight_addr=XND_AI_RAM_END-16u;xnd_ack();if(xnd_launch_gemv(&fault)){error(21);return 1;}
 int bad=xnd_wait(1000000u);if(bad!=XND_OUT_OF_RAM||(XND_STATUS&XND_BUSY_MASK)||XND_DMA_WRITE_BYTES||XND_MACS){error(22);return 1;}
 nr_puts("MLP_XND_BAD_RANGE_PASS\n");
 fault.weight_addr=(uint32_t)(uintptr_t)mlp_w1;xnd_ack();if(xnd_launch_gemv(&fault)){error(23);return 1;}
 int busy=xnd_launch_gemv(&fault);if(busy!=-2||!(XND_STATUS&XND_BUSY_MASK)){error(24);return 1;}
 int timeout=xnd_wait(0);if(timeout!=-1||!(XND_STATUS&XND_BUSY_MASK)){error(25);return 1;}
 nr_puts("MLP_XND_BUSY_GUARD_PASS\n");nr_puts("MLP_XND_TIMEOUT_FATAL_PASS\n");
 if(xnd_wait(1000000u)){error(26);return 1;}
 for(uint32_t row=0;row<MLP_HIDDEN;row++){int32_t want=0;for(uint32_t col=0;col<256;col++)want+=(int32_t)input[col]*mlp_w1[row][col];if(chunks[0][row]!=want){error(27);return 1;}}
 nr_puts("MLP_XND_ERROR_RECOVERY_PASS\n");
 nr_puts("MLP_XND_PASS\n");NR_LED=0xc0;return 0;
}
