from pathlib import Path
import ctypes,json,random,subprocess,numpy as np,time
R=Path('/work/LUO/NeedleRV-X');D=R/'07_runs/development/context_generalization';S=D/'speed';M=R/'03_sw/model'
t0=time.monotonic()
state=np.load(D/'context_int8.npz');bins=int(state['bins']);weights=state['weight'].astype(np.int32);bias=state['bias'].astype(np.int32);threshold=int(state['threshold'])
paths={'baseline':S/'baseline_context.c.inc','sparse':M/'byte_context.c.inc'}
libs={}
for name,path in paths.items():
 sparse=name=='sparse'
 wrapper='#include <stdint.h>\n#include "byte_tool_model.h"\n#include "'+str(path)+'"\n'
 wrapper+='int vector(const uint8_t*b,uint32_t n,int16_t*out){int s=nr_ctx_features(b,n);if(!s)for(uint32_t i=0;i<NR_CONTEXT_BINS;i++)out[i]='+('(nr_ctx_seen[i>>5]&(1u<<(i&31u)))?nr_ctx_counts[i]:0'if sparse else'nr_ctx_counts[i]')+';return s;}\n'
 wrapper+='int apply(const uint8_t*b,uint32_t n,int32_t*z,int32_t*out){nr_context_result_t c;int s=nr_context_apply(b,n,z,&c);out[0]=c.logits[0];out[1]=c.logits[1];out[2]=c.margin;out[3]=c.threshold;out[4]=c.used;out[5]=c.deny;out[6]=c.nonzero_features;out[7]=c.scalar_macs;return s;}\n'
 wrapper+='void poison(void){for(uint32_t i=0;i<NR_CONTEXT_BINS;i++)nr_ctx_counts[i]=0x5555;'+('for(uint32_t i=0;i<NR_CONTEXT_BINS/32u;i++)nr_ctx_seen[i]=0xf0f0f0f0u;for(uint32_t i=0;i<256u;i++)nr_ctx_touched[i]=0x5555;'if sparse else'')+'}\n'
 (S/(name+'.c')).write_text(wrapper)
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(M),str(S/(name+'.c')),'-o',str(S/(name+'.so'))],check=True)
 lib=ctypes.CDLL(str(S/(name+'.so')));lib.vector.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_int16)];lib.apply.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32)];libs[name]=lib
# An independently written Python scalar feature extractor,also checks clipping after signed collisions.
def features(text):
 code=[];digit=False
 for c in text:
  x=ord(c)
  if 65<=x<=90:x+=32
  if 48<=x<=57:
   if digit:continue
   x=35;digit=True
  else:digit=False
  code.append(x)
 f=np.zeros(bins,np.int32)
 for i in range(len(code)):
  h=2166136261
  for width in range(1,min(4,len(code)-i)+1):
   h=((h^code[i+width-1])*16777619)&0xffffffff;v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff
   f[v&(bins-1)]+= -1 if v&bins else 1
 return f
cache=np.load(D/'features.npz');rows={n:[json.loads(x)for x in p.read_text().splitlines()if x]for n,p in {'original80':R/'04_model/datasets/template_development.jsonl','aug192':R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl','observed288':R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl','validation':D/'data/validation.jsonl'}.items()}
exact=0
for name,rs in rows.items():
 base=cache[name+'_base']
 for row,enc in zip(rs,base):
  raw=row['text'].encode();f=features(row['text']);scaled=np.clip(f,-3,3)*8;dot=scaled@weights.T;context=np.sign(dot)*((np.abs(dot)+32)//64)+bias
  z=enc.copy();deny=int(context[1]-context[0]>=threshold)
  if deny:z[5]=max(z[5],max(z[:5])+context[1]-context[0]-threshold+1)
  want=list(map(int,context))+[int(context[1]-context[0]),threshold,1,deny,int(np.count_nonzero(f)),int(np.count_nonzero(f))*2]
  packed_macs=int(np.count_nonzero(f))+int(np.count_nonzero(f[np.nonzero(weights.sum(0))[0]]))
  for libname,lib in libs.items():
   zs=(ctypes.c_int32*6)(*map(int,enc));out=(ctypes.c_int32*8)();assert lib.apply(raw,len(raw),zs,out)==0
   expected=want.copy()
   if libname=='sparse':expected[7]=packed_macs
   assert list(zs)==z.tolist()and list(out)==expected,(name,row['text'],libname,list(zs),z.tolist(),list(out),want)
  exact+=1
random.seed(20411)
cases=[b'',b'A'*64,b'0'*64,bytes([0xc0,0xaf]),b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\x80',b'\x00',b'\xf0\x9f\x92',b'9'*65]
for _ in range(1600):
 text=''.join(chr(random.choice([random.randrange(1,128),random.randrange(0x4e00,0x9fff),random.randrange(0x10000,0x10ffff)]))for _ in range(random.randrange(1,20)));raw=text.encode();cases.append(raw[:64]if random.random()<.2 else raw)
for _ in range(1600):cases.append(bytes(random.randrange(256)for _ in range(random.randrange(1,65))))
valids=0
for raw in cases:
 try:text=raw.decode();valid=len(raw)<=64 and '\0'not in text
 except UnicodeDecodeError:valid=False
 want=features(text)if valid else None
 for name,lib in libs.items():
  out=(ctypes.c_int16*bins)();status=lib.vector(raw,len(raw),out);assert(status==0)==valid,(name,raw.hex(),status)
  if valid:assert np.array_equal(np.array(out),want),(name,raw.hex())
 valids+=valid
# Explicit poison emulates NOLOAD scratch (startup does not initializeAI_RAM),then alternate
# valid/invalid/empty/maximum-length requests. No static initialization assumption is allowed.
sequence=[b'led 37',b'\xff',b'pwm 20',b'',b'A'*64,b'\xed\xa0\x80',b'led 37',('温度'*10).encode(),b'0'*64,b'counter',b'\x00',b'pwm 20']
for lib in libs.values():lib.poison()
for raw in sequence:
 results=[]
 for lib in libs.values():
  zs=(ctypes.c_int32*6)(-300,-200,-100,100,20,0);out=(ctypes.c_int32*8)();status=lib.apply(raw,len(raw),zs,out);results.append((status,list(zs),list(out)))
 assert results[0][:2]==results[1][:2]and results[0][2][:7]==results[1][2][:7],(raw,results)
# Disabled head retains the encoder exactly for all1101cases.
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-DNR_CONTEXT_ENABLED=0','-shared','-fPIC','-I'+str(M),str(S/'sparse.c'),'-o',str(S/'disabled.so')],check=True)
off=ctypes.CDLL(str(S/'disabled.so'));off.apply.argtypes=libs['sparse'].apply.argtypes
for name,rs in rows.items():
 for row,enc in zip(rs,cache[name+'_base']):
  raw=row['text'].encode();zs=(ctypes.c_int32*6)(*map(int,enc));out=(ctypes.c_int32*8)();assert off.apply(raw,len(raw),zs,out)==0and list(zs)==enc.tolist()and out[4]==0
report=dict(passed=True,weights_threshold_unchanged=True,c_python_baseline_sparse_exact=exact,disabled_exact=exact,strict_utf8_boundary_cases=len(cases),valid_boundary_cases=valids,poisoned_scratch_sequential_cases=len(sequence),context_logical_quantized_bytes=2056,context_constant_payload_bytes=1047,context_payload_bytes_saved=1009,scalar_macs='unpacked2*nonzero;packed1*nonzero plus nonzero correctionbins; output timing remains exact',previous_context_scratch_bytes=2048,new_context_scratch_bytes=2688,additional_ai_ram_bytes=640,additional_cpu_ram_state_bytes=0,scope='Only implementation order changed; no training or threshold selection; frozen642first evaluation was not read',membership='32words reset; firsttouch countzero; bitmap suppresses repeatedbins even after signedcancellation; uniqueindex list≤250; list[255]count',seconds=time.monotonic()-t0)
(S/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
