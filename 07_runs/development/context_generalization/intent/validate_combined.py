from train_intent import *
import subprocess,ctypes
sys.path.insert(0,str(P/'context_v2'));from train_mlp import infer
q=np.load(D/'combined_candidate.npz');cache=np.load(P/'context_v2/features.npz');oldq=np.load(P/'context_int8.npz')
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-shared','-fPIC','-I'+str(R/'03_sw/model'),str(D/'combined_boundary.c'),'-o',str(D/'combined_boundary.so')],check=True)
lib=ctypes.CDLL(str(D/'combined_boundary.so'));lib.run_combined.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32)]
rows={'validation':read(P/'context_v2/data/validation.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
count=0
for n,rr in rows.items():
 x=cache[n+'_x'];base=cache[n+'_base'];ct=infer(x,q);de=fixed(x,q['repair_weight'],q['repair_bias']);bucket=base.argmax(1);de=de*(bucket==5)[:,None];th=q['thresholds'][bucket];denied=ct[:,1]-ct[:,0]>=th;z=base.copy();z[:,:5]+=de;z[denied,5]=np.maximum(z[denied,5],z[denied,:5].max(1)+ct[denied,1]-ct[denied,0]-th[denied]+1)
 for i,row in enumerate(rr):
  raw=row['text'].encode();e=(ctypes.c_int32*6)(*base[i]);o=(ctypes.c_int32*25)();assert lib.run_combined(raw,len(raw),e,o)==0
  expected=z[i].tolist()+ct[i].tolist()+de[i].tolist()+[int(bucket[i]),int(th[i]),int(denied[i])];assert list(o)==expected,(n,i,list(o),expected);count+=1
r=dict(scope='Candidate full encoder fusion,not production/system acceptance; no642/fresh accessed',constant_bytes=sum(q[k].nbytes for k in ['w1','b1','w2','b2','repair_weight','repair_bias','thresholds']),c_python_all_scores_exact_cases=count,encoder_bucket='Immutable raw six-way encoder argmax; ties earlier class',order='shared Unicode1024 counts -> context11 score + only-if-encoderreject repair5 -> classconditional threshold -> jointreject dominance',original_encoder_retained=True,neural_context_logits_uncalibrated=True,fast_path_validated=False,fast_path_warning='Using schemahint bucket instead of encoder bucket would be hybrid and needs separate system validation')
(D/'combined_c_validation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
