/* Kernel only. Caller provides existing exact sparse extractor arrays:
 * nr_ctx_counts[NR_CONTEXT_BINS], nr_ctx_touched[256] with count at255.
 * NR_CONTEXT_BINS must match NR_CONTEXT_MLP_BINS. No production file changed.
 * Include byte_context_mlp_data.h before this file; its matrix/bias arrays can
 * use an initialized .ai_const section. All accumulators fit INT32 at64bytes.
 */
static int32_t nr_ctx_mlp_round(int32_t v) {
    return v>=0?(v+32)/64:-((-v+32)/64);
}
static uint32_t nr_ctx_mlp_scores(int32_t scores[NR_CONTEXT_MLP_OUTPUTS],uint32_t *nonzero) {
    int32_t sums[NR_CONTEXT_MLP_HIDDEN]={0};
    int32_t hidden[NR_CONTEXT_MLP_HIDDEN],v,sum;
    uint32_t at,bin,k,j,n=0;
    for(at=0;at<nr_ctx_touched[255];at++) {
        bin=nr_ctx_touched[at];v=nr_ctx_counts[bin];if(!v)continue;
        if(v>3)v=3;else if(v< -3)v=-3;v*=8;n++;
        #if NR_CONTEXT_MLP_ROWMAJOR
        for(k=0;k<NR_CONTEXT_MLP_HIDDEN;k++)sums[k]+=v*nr_ctx_mlp_w1[k][bin];
#else
        for(k=0;k<NR_CONTEXT_MLP_HIDDEN;k++)sums[k]+=v*nr_ctx_mlp_w1[bin][k];
#endif
    }
    for(k=0;k<NR_CONTEXT_MLP_HIDDEN;k++) {
        v=nr_ctx_mlp_round(sums[k])+nr_ctx_mlp_b1[k];
        hidden[k]=v<0?0:v>127?127:v;
    }
    for(j=0;j<NR_CONTEXT_MLP_OUTPUTS;j++) {
        sum=0;for(k=0;k<NR_CONTEXT_MLP_HIDDEN;k++)sum+=hidden[k]*nr_ctx_mlp_w2[j][k];
        scores[j]=nr_ctx_mlp_round(sum)+nr_ctx_mlp_b2[j];
    }
    *nonzero=n;
    return NR_CONTEXT_MLP_HIDDEN*(n+NR_CONTEXT_MLP_OUTPUTS);
}
