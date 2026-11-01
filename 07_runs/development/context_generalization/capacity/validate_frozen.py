from pathlib import Path
import sys,json,ctypes,subprocess
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'context_v2'))
from train import read,TOOLS,metrics
from train_mlp import infer
from veto_train import fixed,features
import numpy as np
q=np.load(D/'frozen_candidate.npz');qold=np.load(P/'intent/combined_candidate.npz');cache=np.load(P/'context_v2/features.npz');fc=np.load(P/'intent/fresh_features.npz');rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'observed1138':read(P/'context_v2/data/fresh.jsonl'),'internal_audit':read(D/'internal_audit.jsonl')}
assert not(D/'internal_audit_first.json').exists(),'Audit immutable,refusing overwrite'
lib=ctypes.CDLL(str(D/'capacity_boundary.so'));lib.run_capacity.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32)]
report=dict(scope='Capacity64 frozen candidate numerical proof; observed1138 is development target,not blind;internal900 audit firstonce held apart from selection;no production changes',constant_bytes=72068,c_python_all_scores_exact_cases=0,results={});audit_scores=None
for n,rr in rows.items():
 if n=='internal_audit':
  x=np.stack([features(r['text'],1024)for r in rr]);p=subprocess.run([str(P/'baseline')],input='\n'.join(z['text']for z in rr)+'\n',stdout=subprocess.PIPE,text=True,check=True);base=np.array([json.loads(l)['logits']for l in p.stdout.splitlines()],np.int32);np.savez_compressed(D/'audit_features.npz',x=x,base=base)
 elif n=='observed1138':x=fc['x'];base=fc['base']
 else:x=cache[n+'_x'];base=cache[n+'_base']
 ct=infer(x,q);bucket=base.argmax(1);oldde=fixed(x,q['oldrepair_weight'],q['oldrepair_bias'])*(bucket==5)[:,None];z=base.copy();z[:,:5]+=oldde;used=z.argmax(1)==5;newde=ct[:,11:16]*used[:,None];z[:,:5]+=newde;th=q['thresholds'][bucket];diff=ct[:,1]-ct[:,0];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1)
 for i,row in enumerate(rr):
  raw=row['text'].encode();e=(ctypes.c_int32*6)(*base[i]);out=(ctypes.c_int32*36)();assert lib.run_capacity(raw,len(raw),e,out)==0
  expected=z[i].tolist()+ct[i].tolist()+oldde[i].tolist()+newde[i].tolist()+[int(bucket[i]),int(th[i]),int(deny[i]),int(used[i])];assert list(out)==expected,(n,i,list(out),expected)
 report['c_python_all_scores_exact_cases']+=len(rr);m=metrics(z,rr);m['legal_correct']=sum(v[0]for k,v in m['by_class'].items()if k!='reject');m['legal_total']=sum(r['intent']!='reject'for r in rr);m['legal_wrong_tool']=m['legal_total']-m['legal_correct']-m['false_reject'];m['by_context']={str(k):dict(n=sum(r.get('context',8)==k for r in rr),correct=sum(int(a==TOOLS.index(r['intent']))for a,r in zip(z.argmax(1),rr)if r.get('context',8)==k))for k in sorted({r.get('context',8)for r in rr})};report['results'][n]=m
 if n=='internal_audit':
  oldct=infer(x,qold);oldb=fixed(x,qold['repair_weight'],qold['repair_bias'])*(bucket==5)[:,None];bz=base.copy();bz[:,:5]+=oldb;bth=qold['thresholds'][bucket];bd=oldct[:,1]-oldct[:,0];mask=bd>=bth;bz[mask,5]=np.maximum(bz[mask,5],bz[mask,:5].max(1)+bd[mask]-bth[mask]+1);audit_scores=dict(scope='Single firstpass postfreeze internally generated900 wrapperfamily audit;not humanblind;never used to choose or alter weights,thresholds,cascade',model_constant_bytes=72068,baseline16=metrics(bz,rr),candidate64=m,protocol=json.loads((D/'internal_audit_protocol.json').read_text()),rows=[dict(text=r['text'],truth=r['intent'],encoder=base[i].tolist(),head=ct[i].tolist(),oldrepair=oldde[i].tolist(),newrepair=newde[i].tolist(),joint=z[i].tolist(),bucket=int(bucket[i]),threshold=int(th[i]))for i,r in enumerate(rr)])
 print('VALIDATED',n,m['correct'],m['n'],m['legal_correct'],m['false_accept'],m['macro_recall'],flush=True)
(D/'c_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(D/'internal_audit_first.json').write_text(json.dumps(audit_scores,ensure_ascii=False,indent=2)+'\n');print('EXACT',report['c_python_all_scores_exact_cases'])
