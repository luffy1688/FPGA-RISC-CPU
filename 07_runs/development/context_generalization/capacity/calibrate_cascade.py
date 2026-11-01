from pathlib import Path
import sys,json,collections
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'context_v2'))
from train import read,TOOLS,metrics
from train_mlp import infer
from veto_train import fixed
import numpy as np
names=['original80','aug192','observed288','old_validation','validation','observed1138'];rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'observed1138':read(P/'context_v2/data/fresh.jsonl')};cache=np.load(P/'context_v2/features.npz');fc=np.load(P/'intent/fresh_features.npz');ar={n:fc['x']if n=='observed1138'else cache[n+'_x']for n in names};base={n:fc['base']if n=='observed1138'else cache[n+'_base']for n in names};qold=np.load(P/'intent/combined_candidate.npz');baseline={};unvetoed={};oldrepair={}
for n in names:
 de=fixed(ar[n],qold['repair_weight'],qold['repair_bias'])*(base[n].argmax(1)==5)[:,None];oldrepair[n]=de;z=base[n].copy();z[:,:5]+=de;unvetoed[n]=z.copy();ct=infer(ar[n],qold);diff=ct[:,1]-ct[:,0];th=qold['thresholds'][base[n].argmax(1)];mask=diff>=th;z[mask,5]=np.maximum(z[mask,5],z[mask,:5].max(1)+diff[mask]-th[mask]+1);baseline[n]=metrics(z,rows[n])

import ast
script=(D/'train_diagnose.py').read_text();node=next(x for x in ast.parse(script).body if isinstance(x,ast.FunctionDef)and x.name=='calibrate');source=ast.get_source_segment(script,node)
truth={n:np.array([TOOLS.index(r['intent'])for r in rows[n]])for n in names};buckets={n:base[n].argmax(1)for n in names}
def summary(z,rs):
 m=metrics(z,rs);m['legal_correct']=sum(v[0]for k,v in m['by_class'].items()if k!='reject');return m
exec(source)
report=dict(scope='Observed development class-preserving capacity calibration;1138 already observed and augmentation family-informed;not heldout',baseline=baseline,profiles=[],selected=None);best=-1
for path in sorted(D.glob('latest_*.npz')):
 q=np.load(path);out={n:infer(ar[n],q)for n in names};modes=['oldrepair']if not q['toolhead']else['cascade','oldrepair']
 for mode in modes:
  zs={}
  for n in names:
   zs[n]=unvetoed[n].copy()
   if mode=='cascade':zs[n][:,:5]+=out[n][:,11:16]*(zs[n].argmax(1)==5)[:,None]
  sel=calibrate(zs,{n:v[:,1]-v[:,0]for n,v in out.items()});rec=dict(profile=path.stem,mode=mode,selected=sel);report['profiles'].append(rec);print('CALIBRATED',path.stem,mode,None if sel is None else dict(gate=sel['gate'],score=sel['score'],thresholds=sel['thresholds'],counts={n:(v['correct'],v['legal_correct'],v['false_accept'])for n,v in sel['metrics'].items()}),flush=True)
  if sel and sel['gate']and sel['score']>best:best=sel['score'];report['selected']=rec;np.savez(D/'calibrated_selected.npz',**{k:q[k]for k in q.files},thresholds=np.array(sel['thresholds']),cascade=np.array(mode=='cascade'))
(D/'calibrated_report.json').write_text(json.dumps(report,indent=2)+'\n')
