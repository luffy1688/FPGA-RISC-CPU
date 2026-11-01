from pathlib import Path
import sys,json
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'context_v2'))
from train import read,TOOLS,metrics
from train_mlp import infer
from veto_train import fixed
import numpy as np
rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'observed1138':read(P/'context_v2/data/fresh.jsonl'),'internal_audit_observed':read(D/'internal_audit.jsonl')};cache=np.load(P/'context_v2/features.npz');fc=np.load(P/'intent/fresh_features.npz');ac=np.load(D/'audit_features.npz');q=np.load(D/'frozen_candidate.npz');base16=json.loads((P/'intent/classwise_joint_final_report.json').read_text())['selected']['metrics'];data={}
for n,rr in rows.items():
 c=fc if n=='observed1138'else ac if n=='internal_audit_observed'else cache;x=c['x']if n in ['observed1138','internal_audit_observed']else c[n+'_x'];b=c['base']if n in ['observed1138','internal_audit_observed']else c[n+'_base'];ct=infer(x,q);bucket=b.argmax(1);de=fixed(x,q['oldrepair_weight'],q['oldrepair_bias'])*(bucket==5)[:,None];z=b.copy();z[:,:5]+=de;z[:,:5]+=ct[:,11:16]*(z.argmax(1)==5)[:,None];data[n]=(z,ct[:,1]-ct[:,0],bucket)
report=dict(scope='Deployment calibration revision2 candidate scan; only counter threshold changes,weights frozen. 1138 and900 are now observed replay; neither is a new first evaluation. Original frozen1066/1138 and first900656 remain immutable.',original_thresholds=q['thresholds'].tolist(),candidates=[])
for counter in [134,144,160,192]:
 th=q['thresholds'].copy();th[3]=counter;ev={}
 for n,rr in rows.items():
  z,diff,bucket=data[n];z=z.copy();v=th[bucket];deny=diff>=v;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-v[deny]+1);m=metrics(z,rr);m['legal_correct']=sum(v[0]for k,v in m['by_class'].items()if k!='reject');ev[n]=m
 gate=all(ev[n]['correct']>=base16[n]['correct']and ev[n]['false_accept']<=base16[n]['false_accept']and all(ev[n]['by_class'][tool][0]>=base16[n]['by_class'][tool][0]for tool in TOOLS[:5])for n in ['original80','aug192','observed288','old_validation','validation'])and ev['observed1138']['correct']>=1025
 report['candidates'].append(dict(counter_threshold=counter,thresholds=th.tolist(),raw_old16_gate_passed=gate,metrics=ev));print('REVISION2',counter,gate,{n:(v['correct'],v['legal_correct'],v['false_accept'])for n,v in ev.items()},flush=True)
(D/'calibration_revision2.json').write_text(json.dumps(report,indent=2)+'\n')
