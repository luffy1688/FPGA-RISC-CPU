from pathlib import Path
D=Path(__file__).resolve().parent
exec((D/'train_fusion_legal.py').read_text().split('trainy=')[0])
import ctypes,subprocess
q=np.load(D/'fusion_legal_selected.npz');report=json.loads((D/'fusion_legal_report.json').read_text());rec=report['selected'];assert rec['encoder_scale_divisor']==8 and rec['input_features']==70
w=q['fusion_w'];b=q['fusion_b'];alpha=rec['alpha_quarters'];gate=rec['margin_gate']
c='#include <stdint.h>\nstatic const int8_t W[5][70]={'+','.join('{'+','.join(map(str,row))+'}'for row in w)+'};\nstatic const int32_t B[5]={'+','.join(map(str,b))+'};\n'
c+=r"""
static int32_t halfaway(int32_t a,int32_t den){return a>=0?(a+den/2)/den:-((-a+den/2)/den);}
static unsigned best(const int32_t *z,unsigned n){unsigned b=0;for(unsigned i=1;i<n;i++)if(z[i]>z[b])b=i;return b;}
int fusion_one(const int32_t *hidden,const int32_t *encoder,const int32_t *pre,const int32_t *context,const int32_t *thresholds,int32_t *joint,int8_t *feature,int32_t *delta){
 for(unsigned j=0;j<64;j++){if(hidden[j]<0||hidden[j]>127)return -1;feature[j]=(int8_t)hidden[j];}
 for(unsigned j=0;j<6;j++){int32_t v=halfaway(encoder[j],8);feature[64+j]=(int8_t)(v< -127?-127:v>127?127:v);joint[j]=pre[j];}
 unsigned first=best(pre,6),second=first?0:1;
 for(unsigned j=0;j<6;j++)if(j!=first&&pre[j]>pre[second])second=j;
 int use=first!=5 && pre[first]-pre[second]<=GATE;
 for(unsigned i=0;i<5;i++){int32_t sum=0;for(unsigned j=0;j<70;j++)sum+=(int32_t)feature[j]*(int32_t)W[i][j];delta[i]=halfaway(sum,64)+B[i];if(use)joint[i]+=halfaway(delta[i]*ALPHA,4);}
 if(use){int32_t legal=joint[best(joint,5)];if(joint[5]>=legal)joint[5]=legal-1;}
 unsigned bucket=best(encoder,6);int32_t diff=context[1]-context[0],threshold=thresholds[bucket];
 if(diff>=threshold){int32_t legal=joint[best(joint,5)],needed=legal+diff-threshold+1;if(joint[5]<needed)joint[5]=needed;}
 return 0;
}
""".replace('GATE',str(gate)).replace('ALPHA',str(alpha))
(D/'fusion_legal_boundary.c').write_text(c)
subprocess.run(['gcc','-O2','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',str(D/'fusion_legal_boundary.c'),'-o',str(D/'fusion_legal_boundary.so')],check=True)
lib=ctypes.CDLL(str(D/'fusion_legal_boundary.so'));f=lib.fusion_one;i32=ctypes.POINTER(ctypes.c_int32);i8=ctypes.POINTER(ctypes.c_int8);f.argtypes=[i32,i32,i32,i32,i32,i32,i8,i32];f.restype=ctypes.c_int
ptr=lambda a:a.ctypes.data_as(i32);const=np.ascontiguousarray(q64['thresholds'],np.int32);counts={};count=0
for n in names:
 feats=feature(n,rec['encoder_scale_divisor']);deltas=rounding(feats.astype(np.int32)@w.astype(np.int32).T)+b;expected=apply(n,feats,q,alpha,gate)
 for k in range(len(feats)):
  h=np.ascontiguousarray(hidden[n][k],np.int32);e=np.ascontiguousarray(base[n][k],np.int32);p=np.ascontiguousarray(pre[n][k],np.int32);ctx=np.ascontiguousarray(heads[n][k,:2],np.int32);z=np.zeros(6,np.int32);x=np.zeros(70,np.int8);delta=np.zeros(5,np.int32)
  assert f(ptr(h),ptr(e),ptr(p),ptr(ctx),ptr(const),ptr(z),x.ctypes.data_as(i8),ptr(delta))==0
  assert np.array_equal(x,feats[k]),('feature',n,k)
  assert np.array_equal(delta,deltas[k]),('delta',n,k)
  assert np.array_equal(z,expected[k]),('joint',n,k,z,expected[k])
 count+=len(feats);counts[n]=len(feats)
report['c_integer_validation']=dict(passed=True,cases=count,feature_values_exact=count*70,delta_values_exact=count*5,joint_values_exact=count*6,sets=counts,scope='IndependentC encoderquantization,INT8linear,halfaway6,scaledresidual,actualmarginroute,legalstatepreservationandunchangedcontextveto. Originalglobal64encoder/head testedseparately;notRTLorphysical.')
(D/'fusion_legal_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('FUSION_LEGAL_C_EXACT',count,flush=True)
