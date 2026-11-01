from pathlib import Path
import ctypes as C,subprocess,json,sys,random
import numpy as np
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(D))
from train_mlp import infer
from veto_train import features
from train import read
q=np.load(D/'profile_grammar_shared16.npz');bins=q['w1'].shape[1];outputs=q['w2'].shape[0];p=R/'03_sw/model/byte_context.c.inc'
s=p.read_text();s=s[:s.index('static int32_t nr_ctx_round')];s=s[s.index('static int16_t nr_ctx_counts'):];s=s.replace('typedef nr_context_t nr_context_result_t;','')
c='#include <stdint.h>\n#define NR_CONTEXT_BINS %du\n#define NR_CONTEXT_SCRATCH_ATTR\n#include "byte_context_mlp_data.h"\n'%bins+s+'\n#include "byte_context_mlp_kernel.c.inc"\nint mlp(const uint8_t*b,uint32_t n,int32_t*out,uint32_t*nonzero,uint32_t*macs){if(nr_ctx_features(b,n))return -1;*macs=nr_ctx_mlp_scores(out,nonzero);return 0;}\n'
(D/'mlp_boundary.c').write_text(c);subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(D/'mlp_boundary.c'),'-o',str(D/'mlp_boundary.so')],check=True)
lib=C.CDLL(str(D/'mlp_boundary.so'));lib.mlp.argtypes=[C.c_char_p,C.c_uint32,C.POINTER(C.c_int32),C.POINTER(C.c_uint32),C.POINTER(C.c_uint32)];lib.mlp.restype=C.c_int
rows=read(D/'data/validation.jsonl')+read(R/'04_model/datasets/template_development.jsonl')+read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl')+read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')
texts=[x['text']for x in rows];rng=random.Random(90211);alphabet=list('不必不要先后读写打开运行结果温度计数器灯占空比pwmledCoreMark01238 %？，。“”')+['𠮷','😀','é','\t']
for i in range(2000):
 t=''.join(rng.choice(alphabet)for _ in range(rng.randrange(1,50)))
 while len(t.encode())>64:t=t[:-1]
 texts.append(t)
actual=[];maxmacs=0
for text in texts:
 out=(C.c_int32*outputs)();nz=C.c_uint32();mac=C.c_uint32();b=text.encode();assert lib.mlp(b,len(b),out,C.byref(nz),C.byref(mac))==0
 z=np.array(list(out),np.int32);gold=infer(np.stack([features(text,bins)]),q)[0];assert np.array_equal(z,gold),(text,z,gold)
 assert mac.value==int(q['hidden'])*(nz.value+outputs);maxmacs=max(maxmacs,mac.value)
invalid=[b'\xff',b'\xc0\xaf',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xe4\xb8',b'a\x00b',b'x'*65]
for b in invalid:
 out=(C.c_int32*outputs)();nz=C.c_uint32();mac=C.c_uint32();assert lib.mlp(b,len(b),out,C.byref(nz),C.byref(mac))==-1
 # Extractor must recover on the next legal input after a malformed request.
 good=b'led 37';assert lib.mlp(good,len(good),out,C.byref(nz),C.byref(mac))==0;assert np.array_equal(np.array(out),infer(np.stack([features('led 37',bins)]),q)[0])
report=dict(candidate='profile_grammar_shared16.npz',feature_bins=bins,hidden=int(q['hidden']),outputs=outputs,c_python_exact_cases=len(texts),malformed_recovery_cases=len(invalid),max_scalar_macs=maxmacs,all11_logits_exact=True,rounding='round dot away from zero before adding bias; do not round(dot+bias)',production_modified=False,fresh_opened=False,heldout642_opened=False)
(D/'mlp_c_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
