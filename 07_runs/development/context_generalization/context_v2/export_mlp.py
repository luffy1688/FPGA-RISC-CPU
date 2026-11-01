from pathlib import Path
import argparse,numpy as np,json
P=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('checkpoint');parser.add_argument('--prefix',default='byte_context_mlp');parser.add_argument('--layout',choices=['rowmajor','binmajor'],default='rowmajor');args=parser.parse_args();q=np.load(args.checkpoint)
def array(a):
 if a.ndim==1:return '{'+','.join(map(str,a.tolist()))+'}'
 return '{\n'+',\n'.join(array(x)for x in a)+'\n}'
w1=q['w1'].astype(np.int8);b1=q['b1'].astype(np.int32);w2=q['w2'].astype(np.int8);b2=q['b2'].astype(np.int32);h,bins=w1.shape;outputs=w2.shape[0]
s="""/* Learned context MLP, exact INT8 matrices /64, INT32 bias /32.
 * Hidden activations are integer[0,127] at /32; binary logits and auxiliary
 * speech-category9 logits are separate and uncalibrated. */
#ifndef NR_CTX_MLP_CONST_ATTR
#define NR_CTX_MLP_CONST_ATTR
#endif
"""
s+='#define NR_CONTEXT_MLP_BINS %du\n#define NR_CONTEXT_MLP_HIDDEN %du\n#define NR_CONTEXT_MLP_OUTPUTS %du\n#define NR_CONTEXT_MLP_RESIDUAL %du\n'%(bins,h,outputs,int(q['residual']))
s+='#define NR_CONTEXT_MLP_THRESHOLD %d\n'%int(q['threshold'])
s+='#define NR_CONTEXT_MLP_ROWMAJOR %du\n'%(args.layout=='rowmajor')
if args.layout=='rowmajor':s+='static const int8_t nr_ctx_mlp_w1[%d][%d] NR_CTX_MLP_CONST_ATTR=%s;\n'%(h,bins,array(w1))
else:s+='static const int8_t nr_ctx_mlp_w1[%d][%d] NR_CTX_MLP_CONST_ATTR=%s;\n'%(bins,h,array(w1.T))
s+='static const int32_t nr_ctx_mlp_b1[%d] NR_CTX_MLP_CONST_ATTR=%s;\n'%(h,array(b1))
s+='static const int8_t nr_ctx_mlp_w2[%d][%d] NR_CTX_MLP_CONST_ATTR=%s;\n'%(outputs,h,array(w2))
s+='static const int32_t nr_ctx_mlp_b2[%d] NR_CTX_MLP_CONST_ATTR=%s;\n'%(outputs,array(b2))
(P/(args.prefix+'_data.h')).write_text(s)
meta=dict(checkpoint=str(args.checkpoint),bins=bins,hidden=h,outputs=outputs,residual=bool(q['residual']),weights_bytes=int(w1.nbytes+w2.nbytes+b1.nbytes+b2.nbytes),layout='w1[hidden][bin] rowmajor for XND and CPU sparse fallback'if args.layout=='rowmajor'else'w1[bin][hidden] contiguous CPU sparsechannels',math='hidden=clip(round_away(dot(featureint,w1)/64)+b1,0,127);out=round_away(dot(hidden,w2)/64)+b2',scope='candidate only, no production file changed')
(P/(args.prefix+'_export.json')).write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
