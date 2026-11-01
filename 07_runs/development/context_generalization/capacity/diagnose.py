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
report=dict(scope='Capacity diagnostic observed development only; thresholds selected on observed1138/new2031,not blind; no production changed',baseline=baseline,profiles=[])
for path in sorted(D.glob('latest_*.npz')):
 q=np.load(path);outs={n:infer(ar[n],q)for n in names};modes=['oldrepair']if not q['toolhead']else['replace','cascade','oldrepair'];rec=dict(profile=path.stem,constant_bytes=sum(q[k].nbytes for k in ['w1','b1','w2','b2'])+24,modes={})
 for mode in modes:
  best=None
  for threshold in [0,8,16,24,32,48,64,96,128,192,256,384,512,768,1024,2048]:
   ev={}
   for n in names:
    if mode=='replace':de=outs[n][:,11:16]*(base[n].argmax(1)==5)[:,None];z=base[n].copy();z[:,:5]+=de
    else:
     z=unvetoed[n].copy()
     if mode=='cascade':z[:,:5]+=outs[n][:,11:16]*(z.argmax(1)==5)[:,None]
    diff=outs[n][:,1]-outs[n][:,0];deny=diff>=threshold;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-threshold+1);ev[n]=metrics(z,rows[n])
   score=.55*ev['observed1138']['macro_recall']+.45*ev['validation']['macro_recall'];r=dict(threshold=threshold,score=score,metrics=ev)
   if best is None or score>best['score']:best=r
  regressions={n:{tool:[baseline[n]['by_class'][tool][0],v['by_class'][tool][0]]for tool in TOOLS if v['by_class'][tool][0]<baseline[n]['by_class'][tool][0]}for n,v in best['metrics'].items()if n!='observed1138'};best['class_regressions']=regressions;rec['modes'][mode]=best
  print('PROFILE',path.stem,mode,best['threshold'],best['metrics']['observed1138']['correct'],best['metrics']['observed1138']['macro_recall'],'old',{n:v['correct']for n,v in best['metrics'].items()if n!='observed1138'},'regressions',regressions,flush=True)
 report['profiles'].append(rec)
(D/'diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
