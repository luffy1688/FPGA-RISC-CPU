/* Candidate-only helper. Requires current context full counts and touched list.
 * Runs only when the unmodified encoder's argmax is reject (strict greater,
 * so ties remain with the earlier legal index). Context veto is applied AFTER.
 * Unvisited count slots can be stale; only touched unique indices are folded.
 */
#include "byte_intent_repair_data.h"
#ifndef NR_INTENT_SCRATCH_ATTR
#define NR_INTENT_SCRATCH_ATTR
#endif
static int16_t nr_intent_counts[NR_INTENT_BINS] NR_INTENT_SCRATCH_ATTR;
static int32_t nr_intent_round(int32_t v){return v>=0?(v+32)/64:-((-v+32)/64);}
static void nr_intent_delta(int32_t out[5]){
 uint32_t i,j,count=nr_ctx_touched[255];int32_t s[5]={0,0,0,0,0},v;
 for(i=0;i<NR_INTENT_BINS;i++)nr_intent_counts[i]=0;
 for(i=0;i<count;i++){j=nr_ctx_touched[i];nr_intent_counts[j&(NR_INTENT_BINS-1u)]+=nr_ctx_counts[j];}
 for(i=0;i<NR_INTENT_BINS;i++){
  v=nr_intent_counts[i];if(!v)continue;if(v>3)v=3;else if(v< -3)v=-3;v*=8;
  for(j=0;j<5;j++)s[j]+=v*nr_intent_weights[j][i];
 }
 for(j=0;j<5;j++)out[j]=nr_intent_round(s[j])+nr_intent_bias[j];
}
static int nr_intent_repair(int32_t logits[6],int32_t delta[5]){
 uint32_t j;for(j=0;j<5;j++){delta[j]=0;if(logits[j]>=logits[5])return 0;}
 nr_intent_delta(delta);for(j=0;j<5;j++)logits[j]+=delta[j];return 1;
}
