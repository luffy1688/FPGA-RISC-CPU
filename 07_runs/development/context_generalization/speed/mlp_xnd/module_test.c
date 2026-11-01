#include "/work/LUO/NeedleRV-X/03_sw/platform/needle_platform.h"
#include "/work/LUO/NeedleRV-X/03_sw/xnd_runtime/xnd_mmio.h"
#include "semantic_xnd.h"
#include "data.h"
#define NR_CONTEXT_SCRATCH_ATTR __attribute__((section(".ai_scratch"),aligned(4)))
#include "features.inc"
static int32_t out[MLP_OUTPUTS];
extern uint32_t __ai_scratch_start[],__ai_scratch_used_end[];
static void error(uint32_t x){nr_puts("MODULE_FAIL ");nr_put_u32(x);nr_putc('\n');NR_LED=0xee;}
int main(void){uint32_t completed=0;
 /* Poison everyNOLOAD shared buffer before its first use. */
 for(uint32_t*p=__ai_scratch_start;p<__ai_scratch_used_end;p++)*p=0x55555555u;
 for(uint32_t c=0;c<MLP_CASES;c++){
  if(c==MLP_TEXT_CASES)continue; /* independent denseINT8stress is not a valid clippedcountfeature */
  if(c<MLP_TEXT_CASES){uint32_t n=0;while(texts[c][n])n++;if(nr_ctx_features((const uint8_t*)texts[c],n)){error(1);return 1;}}
  else {uint32_t k=0;for(uint32_t i=0;i<1024;i++)if(expected_x[c][i]){nr_ctx_counts[i]=expected_x[c][i]/8;nr_ctx_touched[k++]=(uint16_t)i;}nr_ctx_touched[255]=(uint16_t)k;}
  nr_semantic_stats_t st;uint32_t start=nr_cycle();int code=nr_semantic_xnd_gemv(&mlp_w1[0][0],mlp_b1,&mlp_w2[0][0],mlp_b2,nr_ctx_counts,nr_ctx_touched,nr_ctx_touched[255],MLP_HIDDEN,MLP_OUTPUTS,out,&st);uint32_t cycles=nr_cycle()-start;
  if(code||!st.used||st.failures||st.loads!=5||st.jobs!=5||st.dma_read_bytes!=1024+MLP_HIDDEN*1024+MLP_HIDDEN+MLP_OUTPUTS*MLP_HIDDEN||st.dma_write_bytes!=4*MLP_HIDDEN*4+MLP_OUTPUTS*4){error(2);return 1;}
  for(uint32_t row=0;row<MLP_OUTPUTS;row++)if(out[row]!=expected_score[c][row]){error(3);return 1;}
  if(XND_STATUS&0x301u){error(4);return 1;} /* idle,neitheractivation remainsvalid */
  nr_puts("MODULE_CASE {\"case\":");nr_put_u32(c);nr_puts(",\"cycles\":");nr_put_u32(cycles);nr_puts(",\"engine_cycles\":");nr_put_u32(st.engine_cycles);nr_puts(",\"loads\":");nr_put_u32(st.loads);nr_puts(",\"jobs\":");nr_put_u32(st.jobs);nr_puts(",\"reads\":");nr_put_u32(st.dma_read_bytes);nr_puts(",\"writes\":");nr_put_u32(st.dma_write_bytes);nr_puts("}\n");completed++;
 }
 nr_semantic_stats_t bad;int code;
 uint16_t invalid=1024;code=nr_semantic_xnd_gemv(&mlp_w1[0][0],mlp_b1,&mlp_w2[0][0],mlp_b2,nr_ctx_counts,&invalid,1,MLP_HIDDEN,MLP_OUTPUTS,out,&bad);
 if(code!=-2||bad.used||bad.failures!=1||XND_STATUS&1u){error(5);return 1;}nr_puts("MODULE_BAD_INDEX_PASS\n");
 code=nr_semantic_xnd_gemv((const int8_t*)(XND_AI_RAM_END-16u),mlp_b1,&mlp_w2[0][0],mlp_b2,nr_ctx_counts,nr_ctx_touched,0,MLP_HIDDEN,MLP_OUTPUTS,out,&bad);
 if(code!=-2||bad.used||bad.failures!=1){error(6);return 1;}nr_puts("MODULE_BAD_WEIGHT_PASS\n");
 /* A live first-layer job is owned elsewhere. The module must not touch its
  * buffers or start a CPU fallback when the physicalengine is stillbusy. */
 static int8_t other_input[256] __attribute__((section(".ai_scratch"),aligned(4)));
 static int32_t other_raw[MLP_HIDDEN] __attribute__((section(".ai_scratch"),aligned(4)));
 for(uint32_t i=0;i<256;i++)other_input[i]=8;
 xnd_job_t j={(uint32_t)(uintptr_t)other_input,(uint32_t)(uintptr_t)mlp_w1,(uint32_t)(uintptr_t)other_raw,256,MLP_HIDDEN,1024,0,0};
 xnd_ack();if(xnd_load_activation(&j)||xnd_wait(1000000u)){error(7);return 1;}xnd_ack();if(xnd_launch_gemv(&j)){error(8);return 1;}
 for(uint32_t i=0;i<MLP_OUTPUTS;i++)out[i]=0x12345678;
 code=nr_semantic_xnd_gemv(&mlp_w1[0][0],mlp_b1,&mlp_w2[0][0],mlp_b2,nr_ctx_counts,nr_ctx_touched,0,MLP_HIDDEN,MLP_OUTPUTS,out,&bad);
 if(code!=-2||bad.used||bad.failures!=1){error(9);return 1;}
 for(uint32_t i=0;i<MLP_OUTPUTS;i++)if(out[i]!=0x12345678){error(10);return 1;}
 if(xnd_wait(1000000u)){error(11);return 1;}
 for(uint32_t row=0;row<MLP_HIDDEN;row++){int32_t sum=0;for(uint32_t col=0;col<256;col++)sum+=8*mlp_w1[row][col];if(other_raw[row]!=sum){error(12);return 1;}}
 nr_puts("MODULE_BUSY_FATAL_PASS\n");
 /* The next validrequest recovers and invalidates both externalresidences. */
 if(nr_ctx_features((const uint8_t*)texts[0],6)||nr_semantic_xnd_gemv(&mlp_w1[0][0],mlp_b1,&mlp_w2[0][0],mlp_b2,nr_ctx_counts,nr_ctx_touched,nr_ctx_touched[255],MLP_HIDDEN,MLP_OUTPUTS,out,&bad)){error(13);return 1;}
 for(uint32_t i=0;i<MLP_OUTPUTS;i++)if(out[i]!=expected_score[0][i]){error(14);return 1;}
 if(XND_STATUS&0x301u){error(15);return 1;}
 nr_puts("MODULE_RECOVERY_PASS\nMODULE_WORKSPACE ");nr_put_u32(nr_semantic_xnd_workspace_bytes());nr_puts("\nMODULE_PASS ");nr_put_u32(completed);nr_putc('\n');NR_LED=0xc0;return 0;
}
