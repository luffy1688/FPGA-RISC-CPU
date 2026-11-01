"""Necessary integer C/Python agreement on observed development sets only."""
from veto_train import *
import subprocess,ctypes,random
report=json.loads((D/'veto_report.json').read_text());assert report['complete']and report['selection_gate']
state=np.load(D/'context_int8.npz');bins=int(state['bins']);w=state['weight'];bias=state['bias'];threshold=int(state['threshold'])
rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'validation':read(D/'data/validation.jsonl')}
cmd=['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'03_sw/model'),str(D/'eval_context.c')]
for off in [False,True]:subprocess.run(cmd+(['-DNR_CONTEXT_ENABLED=0']if off else[])+['-o',str(D/('eval_context_off'if off else'eval_context'))],check=True)
result={};exact=0;offexact=0
for name,rs in rows.items():
 base=infer_base(rs);x=np.stack([features(z['text'],bins)for z in rs]);context=fixed(x,w,bias);met,joint=evaluate(base,context,rs,threshold)
 def run(exe):
  p=subprocess.run([str(D/exe)],input='\n'.join(z['text']for z in rs)+'\n',text=True,stdout=subprocess.PIPE,check=True);return[json.loads(z)for z in p.stdout.splitlines()]
 on=run('eval_context');off=run('eval_context_off');assert len(on)==len(off)==len(rs)
 for i,(a,b)in enumerate(zip(on,off)):
  assert a['encoder_logits']==base[i].tolist(),(name,i,'base')
  assert a['context_logits']==context[i].tolist(),(name,i,'context',a['context_logits'],context[i].tolist())
  assert a['logits']==joint[i].tolist(),(name,i,'joint')
  assert b['logits']==base[i].tolist()and b['context_used']==0,(name,i,'disabled')
 exact+=len(on);offexact+=len(off);result[name]=met
# Binary-safe wrapper verifies strict RFC3629 extraction, counts, signs and clipping.
(D/'context_boundary.c').write_text('#include <stdint.h>\n#include "byte_context.c.inc"\nint run_features(const uint8_t*b,uint32_t n,int16_t*out){int s=nr_ctx_features(b,n);if(!s)for(uint32_t i=0;i<NR_CONTEXT_BINS;i++)out[i]=nr_ctx_counts[i];return s;}\nint run_apply(const uint8_t*b,uint32_t n,int32_t*z){nr_context_result_t r;return nr_context_apply(b,n,z,&r);}\n')
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(D/'context_boundary.c'),'-o',str(D/'context_boundary.so')],check=True)
lib=ctypes.CDLL(str(D/'context_boundary.so'));lib.run_features.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_int16)];random.seed(20411)
cases=[b'',b'A'*64,b'0'*64,bytes([0xc0,0xaf]),b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\x80',b'\x00',b'\xf0\x9f\x92',b'9'*65]
for _ in range(1600):
 text=''.join(chr(random.choice([random.randrange(1,128),random.randrange(0x4e00,0x9fff),random.randrange(0x10000,0x10ffff)]))for _ in range(random.randrange(1,20)))
 raw=text.encode('utf-8');cases.append(raw[:64]if random.random()<.2 else raw)
for _ in range(1600):cases.append(bytes(random.randrange(256)for _ in range(random.randrange(1,65))))
for raw in cases:
 out=(ctypes.c_int16*bins)();s=lib.run_features(raw,len(raw),out)
 try:text=raw.decode('utf-8');valid=len(raw)<=64 and '\0'not in text
 except UnicodeDecodeError:valid=False
 assert (s==0)==valid,raw.hex()
 if valid:assert np.array_equal(np.clip(np.array(out),-3,3)*8,features(text,bins)),raw.hex()
proof=dict(candidate_only=True,production_changed=False,config={'bins':bins,'threshold':threshold},constant_bytes=int(w.size+bias.nbytes),scratch_bytes=bins*2,strict_utf8_cases=len(cases),c_python_exact_cases=exact,head_disabled_exact_cases=offexact,metrics=result,heldout_opened=False,feature_contract='Unicode scalars; ASCII lowercase; consecutive ASCII decimal digits collapsed; signed1..4gram counts clipped after accumulation to[-3,3] then times8; int8weights/64; biasINT32/32; half-away output rounding',fusion='finalreject=max(encoderreject,maxencoder_nonreject+contextdiff-threshold+1) only if diff>=threshold',runtime='CPU sparse signed integer dot; scalar_macs=2*nonzero_features; no fictitious XND jobs')
(D/'c_validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof,ensure_ascii=True))
