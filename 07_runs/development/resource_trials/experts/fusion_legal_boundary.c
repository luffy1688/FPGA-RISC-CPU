#include <stdint.h>
static const int8_t W[5][70]={{4,13,42,-29,-10,0,-18,-15,-10,-16,-7,-26,-4,30,-12,-13,7,1,-9,-29,30,-21,0,29,-15,-2,5,-7,16,-16,2,-16,-2,-16,-2,3,-7,-10,-25,-9,29,-19,-20,0,-6,-22,-30,4,8,-31,-12,-29,-20,-4,36,-28,-29,18,-18,21,1,-18,18,16,-35,2,26,3,29,-7},{-1,3,-17,8,-23,16,19,20,13,-10,19,3,-15,21,-23,-2,-1,-8,13,-10,5,14,-1,-23,28,-16,-1,19,-26,-2,21,-7,-18,27,28,-18,-21,-23,3,8,16,-8,-20,-28,-27,-9,18,-12,27,1,-16,25,-5,13,-1,-3,-25,18,-21,-11,23,1,-8,-25,29,-39,18,10,5,-8},{6,2,-27,19,-13,31,-39,22,28,-37,-2,28,20,-42,-2,-8,-16,20,9,44,-11,-36,34,-29,-22,33,33,-33,26,-26,-47,-7,28,-6,-27,-45,14,-37,-3,22,-17,-3,37,-47,-17,25,28,33,-19,46,-41,41,3,-17,-28,6,26,-32,41,15,6,1,12,28,46,35,-65,38,-45,-21},{-11,-18,-16,21,22,-42,30,-4,-22,31,-8,16,-11,-16,21,20,7,3,8,-28,-20,28,-43,-4,23,-17,-26,21,-20,26,26,22,-8,21,-20,26,-4,27,26,7,-20,23,-8,26,21,13,15,-45,-18,-38,27,-12,20,17,-38,25,19,15,-23,-22,-9,18,-12,-29,15,-22,11,-46,-3,21},{18,6,-42,20,-32,-41,-4,-19,2,-27,-8,-5,22,-38,-27,15,6,-14,-11,25,13,16,21,24,-63,17,12,-14,27,14,-53,18,13,-61,-16,13,29,24,17,-19,0,20,2,23,24,19,16,22,-13,25,20,-36,21,0,21,20,25,-18,23,0,-21,14,-7,19,-19,34,-21,41,-81,9}};
static const int32_t B[5]={-4,-4,-2,7,9};

static int32_t halfaway(int32_t a,int32_t den){return a>=0?(a+den/2)/den:-((-a+den/2)/den);}
static unsigned best(const int32_t *z,unsigned n){unsigned b=0;for(unsigned i=1;i<n;i++)if(z[i]>z[b])b=i;return b;}
int fusion_one(const int32_t *hidden,const int32_t *encoder,const int32_t *pre,const int32_t *context,const int32_t *thresholds,int32_t *joint,int8_t *feature,int32_t *delta){
 for(unsigned j=0;j<64;j++){if(hidden[j]<0||hidden[j]>127)return -1;feature[j]=(int8_t)hidden[j];}
 for(unsigned j=0;j<6;j++){int32_t v=halfaway(encoder[j],8);feature[64+j]=(int8_t)(v< -127?-127:v>127?127:v);joint[j]=pre[j];}
 unsigned first=best(pre,6),second=first?0:1;
 for(unsigned j=0;j<6;j++)if(j!=first&&pre[j]>pre[second])second=j;
 int use=first!=5 && pre[first]-pre[second]<=512;
 for(unsigned i=0;i<5;i++){int32_t sum=0;for(unsigned j=0;j<70;j++)sum+=(int32_t)feature[j]*(int32_t)W[i][j];delta[i]=halfaway(sum,64)+B[i];if(use)joint[i]+=halfaway(delta[i]*8,4);}
 if(use){int32_t legal=joint[best(joint,5)];if(joint[5]>=legal)joint[5]=legal-1;}
 unsigned bucket=best(encoder,6);int32_t diff=context[1]-context[0],threshold=thresholds[bucket];
 if(diff>=threshold){int32_t legal=joint[best(joint,5)],needed=legal+diff-threshold+1;if(joint[5]<needed)joint[5]=needed;}
 return 0;
}
