#include <stdint.h>
#include <string.h>
#define MAX_BINS 4096
#define MAX_HIDDEN 256
static int norm(const uint8_t*s,uint32_t n,uint32_t*cp,uint32_t*count){uint32_t p=0,k=0,u,v,need,i;int digits=0;
 while(p<n){u=s[p++];if(u<128){}else{if(u>=194&&u<=223){need=1;u&=31;}else if(u>=224&&u<=239){need=2;u&=15;}else if(u>=240&&u<=244){need=3;u&=7;}else return -1;
  if(p+need>n)return -1;for(i=0;i<need;i++){v=s[p++];if((v&192)!=128)return -1;u=(u<<6)|(v&63);}if((need==1&&u<128)||(need==2&&u<2048)||(need==3&&u<65536)||u>0x10ffff||(u>=0xd800&&u<=0xdfff))return -1;}
  if(u>='A'&&u<='Z')u+=32;if(u>='0'&&u<='9'){if(digits)continue;u='#';digits=1;}else digits=0;if(k>=256)return -1;cp[k++]=u;
 }*count=k;return 0;
}
int features_c(const uint8_t*s,uint32_t n,uint32_t bins,uint32_t position,int8_t*out){uint32_t cp[256],count,at,width,h,v,mid;int32_t c[MAX_BINS]={0};if(bins>MAX_BINS||bins<512||(bins&(bins-1))||(position&&bins!=2048))return -1;if(norm(s,n,cp,&count))return -2;mid=(count+1)/2;
 for(at=0;at<count;at++){h=2166136261u;for(width=1;width<=4&&at+width<=count;width++){h=(h^cp[at+width-1])*16777619u;v=h^(h>>16)^(width*0x9e3779b9u);
  if(position){c[v&1023]+=(v&1024)?-1:1;if(at<mid&&at+width<=mid)c[1024+(v&511)]+=(v&512)?-1:1;else if(at>=mid)c[1536+(v&511)]+=(v&512)?-1:1;}
  else c[v&(bins-1)]+=(v&bins)?-1:1;
 }}for(at=0;at<bins;at++){int z=c[at];if(z>3)z=3;if(z< -3)z=-3;out[at]=(int8_t)(z*8);}return 0;}
static int32_t ra(int32_t v){return v>=0?(v+32)/64:-((-v+32)/64);}
static uint32_t best(const int32_t*z){uint32_t i,b=0;for(i=1;i<6;i++)if(z[i]>z[b])b=i;return b;}
/* Full6 + head16 + oldrepair5 + newrepair5 + bucket/threshold/deny/cascade. */
int infer_c(const uint8_t*s,uint32_t n,uint32_t bins,uint32_t hidden,uint32_t position,const int8_t*w1,const int32_t*b1,const int8_t*w2,const int32_t*b2,const int8_t*repair,const int32_t*rb,const int32_t*threshold,const int32_t*encoder,int32_t*out){int8_t x[MAX_BINS],old[1024];int32_t sums[MAX_HIDDEN]={0},h[MAX_HIDDEN],r[5]={0},v,z,m;uint32_t i,j,bucket=best(encoder);
 if(hidden>MAX_HIDDEN||!hidden||features_c(s,n,bins,position,x)||features_c(s,n,1024,0,old))return -1;
 for(i=0;i<bins;i++)if(x[i])for(j=0;j<hidden;j++)sums[j]+=(int32_t)x[i]*w1[j*bins+i];
 for(j=0;j<hidden;j++){v=ra(sums[j])+b1[j];h[j]=v<0?0:v>127?127:v;}
 for(i=0;i<16;i++){z=0;for(j=0;j<hidden;j++)z+=h[j]*w2[i*hidden+j];out[6+i]=ra(z)+b2[i];}
 if(bucket==5)for(i=0;i<1024;i++)if(old[i])for(j=0;j<5;j++)r[j]+=(int32_t)old[i]*repair[j*1024+i];
 for(j=0;j<5;j++)out[22+j]=bucket==5?ra(r[j])+rb[j]:0;
 for(j=0;j<6;j++)out[j]=encoder[j]+(j<5?out[22+j]:0);out[35]=best(out)==5;
 for(j=0;j<5;j++){out[27+j]=out[35]?out[17+j]:0;out[j]+=out[27+j];}
 out[32]=(int32_t)bucket;out[33]=threshold[bucket];v=out[7]-out[6];out[34]=v>=out[33];
 if(out[34]){m=out[0];for(j=1;j<5;j++)if(out[j]>m)m=out[j];z=m+v-out[33]+1;if(out[5]<z)out[5]=z;}return 0;
}
