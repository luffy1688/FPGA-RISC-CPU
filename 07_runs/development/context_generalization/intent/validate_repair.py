from train_intent import *
import subprocess,ctypes,random
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-shared','-fPIC','-I'+str(R/'03_sw/model'),str(D/'intent_boundary.c'),'-o',str(D/'intent_boundary.so')],check=True)
lib=ctypes.CDLL(str(D/'intent_boundary.so'));lib.run_intent.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_int32)];lib.run_repair.argtypes=[ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32)]
c=np.load(D/'selected_repair_int8.npz');bins=int(c['bins']);w=c['weight'];b=c['bias'];cached=np.load(P/'features.npz')
rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl')}
checks=0;kept=0;repaired=0
for name,rs in rows.items():
 base=np.load(P/'context_v2/features.npz')['validation_base']if name=='validation'else cached[name+'_base'];f=np.stack([features(x['text'],bins)for x in rs]);wanted=fixed(f,w,b)
 for i,z in enumerate(rs):
  raw=z['text'].encode();out=(ctypes.c_int32*5)();assert lib.run_intent(raw,len(raw),out)==0;assert list(out)==wanted[i].tolist(),(name,i)
  logits=(ctypes.c_int32*6)(*base[i]);delta=(ctypes.c_int32*5)();used=lib.run_repair(logits,delta)
  repair=int(base[i].argmax()==5);assert used==repair
  expect=base[i].copy()
  if repair:expect[:5]+=wanted[i];repaired+=1
  else:kept+=1
  assert list(logits)==expect.tolist();checks+=1
random.seed(30612);cases=[b'',b'A'*64,b'0'*64,b'9'*65,b'\xc0\xaf',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\x00',b'\x80']
for _ in range(1200):
 text=''.join(chr(random.choice([random.randrange(1,128),random.randrange(0x4e00,0x9fff),random.randrange(0x10000,0x10ffff)]))for _ in range(random.randrange(1,20)));raw=text.encode();cases.append(raw[:64]if random.random()<.3 else raw)
for _ in range(1200):cases.append(bytes(random.randrange(256)for _ in range(random.randrange(1,65))))
valid_count=0
for raw in cases:
 try:text=raw.decode();valid=len(raw)<=64 and '\0'not in text
 except UnicodeDecodeError:valid=False
 out=(ctypes.c_int32*5)();status=lib.run_intent(raw,len(raw),out);assert (status==0)==valid,raw.hex()
 if valid:
  want=fixed(features(text,bins)[None],w,b)[0];assert list(out)==want.tolist(),raw.hex();valid_count+=1
r=dict(scope='Candidate implementation only,not production or system acceptance; frozen repair checkpoint256bins; no fresh/642 accessed',constant_bytes=int(w.nbytes+b.nbytes),scratch_bytes=2*bins,c_python_delta_and_repair_exact_cases=checks,unchanged_base_legal_predictions=kept,base_reject_repair_candidates=repaired,utf8_boundary_cases=len(cases),valid_boundary_exact=valid_count,shared_feature_extraction=True,signed_collision_accumulation_before_clip=True,context_deny_priority='Integration must apply context veto AFTER these deltas; not performed by this helper')
(D/'repair_c_validation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
