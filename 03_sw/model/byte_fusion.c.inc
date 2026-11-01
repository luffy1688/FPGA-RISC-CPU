/* Frozen toolidentity-only residual; no schema or contextcalibration change. */
static const int8_t nr_fusion_weight[5][70] __attribute__((section(".ai_const"),aligned(4)))={
{
-6,-8,68,-45,15,32,-21,-30,-3,-9,-29,-28,21,66,11,-5,-4,7,-1,-18,2,-34,41,27,-17,-22,-10,-16,1,-16,23,-5,
3,-8,-13,18,6,-2,-36,5,16,-7,-4,23,23,-1,-40,46,-15,-35,-24,-27,-13,1,65,-35,-43,16,-42,43,-11,-3,24,1,
-128,20,57,70,38,16,
},
{
-5,-1,-32,17,-53,-8,13,25,3,-16,19,7,-20,12,-59,0,-2,-26,3,-5,30,28,-8,-27,41,-16,-2,22,-10,19,4,-7,
-5,28,28,-17,-10,-2,11,9,21,-7,-1,-41,-40,-24,19,-24,42,11,6,9,-13,23,15,8,-37,15,-14,-24,25,0,-13,-36,
95,-119,31,-15,41,1,
},
{
-11,2,-6,30,-13,34,-38,19,5,-24,2,1,-11,-52,6,-2,-13,22,-1,52,-5,-43,24,-27,-29,36,40,-14,-2,-20,-54,-5,
11,-14,-10,-39,-8,-7,9,12,-20,-2,3,-56,-15,6,34,23,-8,49,-32,41,1,-17,-37,13,43,-18,61,23,-6,-3,0,34,
81,43,-128,87,-8,-37,
},
{
20,13,-23,15,24,-41,39,4,1,41,16,28,1,-8,20,14,20,7,4,-56,-26,37,-62,-12,35,-7,-23,28,-28,24,38,18,
-18,31,6,26,-1,5,22,-11,-3,16,4,29,7,13,4,-55,-7,-61,23,7,16,5,-70,18,12,7,-34,-30,15,3,-6,-5,
31,5,28,-128,41,33,
},
{
3,-3,-10,19,-21,-14,-22,-14,-2,-18,-9,-7,13,-21,-13,1,-3,-11,-4,31,21,11,20,32,-41,15,13,-34,32,-5,-41,7,
14,-56,-4,-6,14,8,8,-8,-6,13,-1,18,29,3,10,16,-9,42,18,-25,24,-6,28,11,36,-18,32,-11,-19,2,-2,22,
-5,50,9,82,-107,-28,
},
};
static const int32_t nr_fusion_bias[5] __attribute__((section(".ai_const"),aligned(4)))={
2,-9,-3,7,9,
};
static void nr_fusion_apply(nr_prediction_t *p,const nr_context_t *context) {
    int8_t feature[70];uint32_t i,j,first=0,second;int32_t v,sum,maximum;
    for(j=0;j<64;j++)feature[j]=context->hidden[j];
    for(j=0;j<6;j++){v=rounded_div(p->encoder_logits[j],8);feature[64+j]=(int8_t)(v< -127?-127:v>127?127:v);}
    for(j=1;j<6;j++)if(p->logits[j]>p->logits[first])first=j;
    second=first?0u:1u;
    for(j=0;j<6;j++)if(j!=first&&p->logits[j]>p->logits[second])second=j;
    p->fusion_gate_margin=p->logits[first]-p->logits[second];p->fusion_used=first!=5u&&p->fusion_gate_margin<=256;
    for(i=0;i<5;i++){
        sum=0;for(j=0;j<70;j++)sum+=(int32_t)feature[j]*nr_fusion_weight[i][j];
        p->fusion_delta[i]=rounded_div(sum,64)+nr_fusion_bias[i];
        if(p->fusion_used)p->logits[i]+=p->fusion_delta[i];
    }
    if(p->fusion_used){
        maximum=p->logits[0];for(j=1;j<5;j++)if(p->logits[j]>maximum)maximum=p->logits[j];
        if(p->logits[5]>=maximum)p->logits[5]=maximum-1;
    }
}

