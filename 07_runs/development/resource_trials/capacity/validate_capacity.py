from pathlib import Path
import json,ctypes as C,sys,subprocess,time
import numpy as np
R=Path('/work/LUO/NeedleRV-X');P=R/'07_runs/development/context_generalization';D=Path(__file__).resolve().parent
sys.path.insert(0,str(P));sys.path.insert(0,str(D))
from veto_train import features as hash_features
from feature_extract import position_features
read=lambda p:[json.loads(s)for s in p.read_text().splitlines()if s.strip()]
paths={'original80':R/'04_model/datasets/template_development.jsonl','aug192':R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl','observed288':R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl','old_validation':P/'data/validation.jsonl','validation':P/'context_v2/data/validation.jsonl','observed1138':P/'context_v2/data/fresh.jsonl','observed900':P/'capacity/internal_audit.jsonl'}
rows={n:read(p)for n,p in paths.items()};cache=np.load(P/'context_v2/features.npz');base={n:cache[n+'_base'].astype(np.int32)for n in list(paths)[:5]};base['observed1138']=np.load(P/'intent/fresh_features.npz')['base'].astype(np.int32);base['observed900']=np.load(P/'capacity/audit_features.npz')['base'].astype(np.int32)
subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(D/'validate_capacity.c'),'-o',str(D/'validate_capacity.so')],check=True)
lib=C.CDLL(str(D/'validate_capacity.so'));p8=C.POINTER(C.c_int8);p32=C.POINTER(C.c_int32)
lib.features_c.argtypes=[C.c_char_p,C.c_uint32,C.c_uint32,C.c_uint32,p8];lib.infer_c.argtypes=[C.c_char_p,C.c_uint32,C.c_uint32,C.c_uint32,C.c_uint32,p8,p32,p8,p32,p8,p32,p32,p32,p32]
def ptr(a,t):return a.ctypes.data_as(t)
def ra(z):return np.sign(z)*((np.abs(z)+32)//64)
def sparse_head(x,q):
 h=np.empty((len(x),q['w1'].shape[0]),np.int32)
 for i,v in enumerate(x):
  nz=np.flatnonzero(v);s=q['w1'][:,nz].astype(np.int32)@v[nz].astype(np.int32);h[i]=np.clip(ra(s)+q['b1'],0,127)
 return ra(h@q['w2'].astype(np.int32).T)+q['b2']
report=dict(scope='Independent C UTF8decoder+signed Unicodefeatures+all16head+oldrepair5+toolcascade5+6classcontextfusion. Originalencoder logits are previously validated frozen cache inputs. All7sets areobserveddevelopment/regression; this is numerical validation,notnewfirstaccuracy.',production_source_changed=False,model_weights_changed=False,candidates={},passed=False)
began=time.monotonic()
for selection in sorted(D.glob('*_selection.json')):
 d=json.loads(selection.read_text());name=d['config']['name'];q={k:np.ascontiguousarray(v)for k,v in dict(np.load(D/(name+'.npz'))).items()};bins=q['w1'].shape[1];hidden=q['w1'].shape[0];position=int(d['config'].get('feature_mode')=='position');res={};expected_saved=np.load(D/(name+'_predictions.npz'))
 for n,rs in rows.items():
  pyx=np.stack([(position_features(a['text'])if position else hash_features(a['text'],bins))for a in rs]);old=np.stack([hash_features(a['text'],1024)for a in rs]);head=sparse_head(pyx,q);bucket=base[n].argmax(1);rep=ra(old.astype(np.int32)@q['oldrepair_weight'].astype(np.int32).T)+q['oldrepair_bias'];rep*= (bucket==5)[:,None];joint=base[n].copy();joint[:,:5]+=rep;cascade=joint.argmax(1)==5;delta=head[:,11:16]*cascade[:,None];joint[:,:5]+=delta;th=q['thresholds'][bucket];diff=head[:,1]-head[:,0];deny=diff>=th;joint[deny,5]=np.maximum(joint[deny,5],joint[deny,:5].max(1)+diff[deny]-th[deny]+1);expected=np.column_stack([joint,head,rep,delta,bucket,th,deny,cascade]).astype(np.int32)
  for i,a in enumerate(rs):
   wire=a['text'].encode('utf-8');cx=np.zeros(bins,np.int8);assert lib.features_c(wire,len(wire),bins,position,ptr(cx,p8))==0;assert np.array_equal(cx,pyx[i]),(name,n,i,'feature',a['text']);out=np.zeros(36,np.int32)
   rc=lib.infer_c(wire,len(wire),bins,hidden,position,ptr(q['w1'],p8),ptr(q['b1'],p32),ptr(q['w2'],p8),ptr(q['b2'],p32),ptr(q['oldrepair_weight'],p8),ptr(q['oldrepair_bias'],p32),ptr(q['thresholds'],p32),ptr(base[n][i],p32),ptr(out,p32));assert rc==0 and np.array_equal(out,expected[i]),(name,n,i,rc,out.tolist(),expected[i].tolist(),a['text'])
  if n.startswith('observed')and n in ['observed1138','observed900']:
   assert np.array_equal(head,expected_saved[n+'_head'])and np.array_equal(joint.argmax(1),expected_saved[n+'_pred']),(name,n,'previousgolden')
  res[n]=dict(cases=len(rs),feature_values_exact=len(rs)*bins,score_and_fusion_fields_exact=len(rs)*36,max_utf8_bytes=max(len(a['text'].encode())for a in rs))
 report['candidates'][name]=dict(passed=True,hidden=hidden,bins=bins,feature_mode='position'if position else'hash',results=res,total_cases=sum(v['cases']for v in res.values()))
 print('C_EXACT_PASS',name,sum(v['cases']for v in res.values()),flush=True)
report.update(passed=True,seconds=time.monotonic()-began);(D/'c_validation.json').write_text(json.dumps(report,indent=2)+'\n');print('ALL_C_CAPACITY_PASS',report['seconds'],flush=True)
