from pathlib import Path
import sys,json,time,copy,collections,subprocess
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'context_v2'))
from train import read,TOOLS,metrics
from veto_train import features,fixed,ra
from train_mlp import infer,qweight,qbias
import numpy as np,torch
from torch import nn
import torch.nn.functional as F
torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
class Head(nn.Module):
 def __init__(self,h,outputs):
  super().__init__();self.a=nn.Linear(1024,h);self.b=nn.Linear(h,outputs);nn.init.normal_(self.a.weight,std=.04);nn.init.zeros_(self.a.bias);nn.init.zeros_(self.b.bias)
 def forward(self,x):
  h=(ra(F.linear(x,qweight(self.a.weight),None)*32)/32+qbias(self.a.bias)).clamp(0,127/32)
  return ra(F.linear(h,qweight(self.b.weight),None)*32)/32+qbias(self.b.bias)
 def arrays(self):
  w=lambda v:np.clip(np.sign(v.detach().numpy())*np.floor(np.abs(v.detach().numpy())*64+.5),-128,127).astype(np.int8)
  b=lambda v:(np.sign(v.detach().numpy())*np.floor(np.abs(v.detach().numpy())*32+.5)).astype(np.int32)
  return dict(w1=w(self.a.weight),b1=b(self.a.bias),w2=w(self.b.weight),b2=b(self.b.bias))
def summary(z,rs):
 m=metrics(z,rs);m['legal_correct']=sum(v[0]for k,v in m['by_class'].items()if k!='reject');return m
names=['original80','aug192','observed288','old_validation','validation','observed1138']
rows={'train':read(D/'train.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'observed1138':read(P/'context_v2/data/fresh.jsonl')}
cache=np.load(P/'context_v2/features.npz');fc=np.load(P/'intent/fresh_features.npz');ar={n:fc['x']if n=='observed1138'else cache[n+'_x']for n in names};base={n:fc['base']if n=='observed1138'else cache[n+'_base']for n in names}
f=D/'features.npz'
if f.exists():v=np.load(f);ar['train']=v['x'];base['train']=v['base']
else:
 ar['train']=np.stack([features(x['text'],1024)for x in rows['train']]);p=subprocess.run([str(P/'baseline')],input='\n'.join(x['text']for x in rows['train'])+'\n',stdout=subprocess.PIPE,text=True,check=True);base['train']=np.array([json.loads(l)['logits']for l in p.stdout.splitlines()],np.int32);np.savez_compressed(f,x=ar['train'],base=base['train'])
qold=np.load(P/'intent/combined_candidate.npz');baseline={};oldrepair={}
for n in names:
 ct=infer(ar[n],qold);de=fixed(ar[n],qold['repair_weight'],qold['repair_bias']);bucket=base[n].argmax(1);de=de*(bucket==5)[:,None];z=base[n].copy();z[:,:5]+=de;diff=ct[:,1]-ct[:,0];th=qold['thresholds'][bucket];mask=diff>=th;z[mask,5]=np.maximum(z[mask,5],z[mask,:5].max(1)+diff[mask]-th[mask]+1);baseline[n]=summary(z,rows[n]);oldrepair[n]=de
truth={n:np.array([TOOLS.index(x['intent'])for x in rows[n]])for n in names};buckets={n:base[n].argmax(1)for n in names};y=torch.tensor([TOOLS.index(x['intent'])for x in rows['train']]);cy=torch.tensor([x.get('context',8)for x in rows['train']]);execy=(y==5).long();tx=torch.tensor(ar['train'].astype(np.float32)/32);tb=torch.tensor(base['train'].astype(np.float32)/32);trainmask=(tb.argmax(1)==5)[:,None]
groups={}
for i,x in enumerate(rows['train']):groups.setdefault((x['intent'],x.get('context',8)),[]).append(i)
weights=torch.ones(len(y))
for (tool,ctx),ix in groups.items():weights[ix]=len(y)/(len(groups)*len(ix))*(2.5 if ctx==0 else 1.)
# Calibration protects class counts of all existing development sets;1138 is now an observed target.
def calibrate(zs,diffs):
 best=None
 for th5 in [0,8,16,24,32,48,64,96,128,160,192,256,320,512,768,1024]:
  th=np.zeros(6,np.int32);th[5]=th5;possible=True
  for k in range(5):
   for n in names[:-1]:
    target=baseline[n]['by_class'][TOOLS[k]][0];pred=zs[n].argmax(1);repaircorrect=(truth[n]==k)&(pred==k)&(buckets[n]==5)&(diffs[n]<th5);need=target-int(repaircorrect.sum());avail=np.sort(diffs[n][(truth[n]==k)&(pred==k)&(buckets[n]==k)])
    if need>len(avail):possible=False;break
    if need>0:th[k]=max(th[k],int(avail[need-1])+1)
   if not possible:break
  if not possible:continue
  ev={}
  for n in names:
   z=zs[n].copy();v=th[buckets[n]];deny=diffs[n]>=v;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diffs[n][deny]-v[deny]+1);ev[n]=summary(z,rows[n])
  gate=all(ev[n]['correct']>=baseline[n]['correct']and ev[n]['false_accept']<=baseline[n]['false_accept']for n in names[:-1])
  if not gate:continue
  score=.55*ev['observed1138']['macro_recall']+.45*ev['validation']['macro_recall'];rec=dict(thresholds=th.tolist(),score=score,metrics=ev)
  if best is None or score>best['score']:best=rec
 return best
report=dict(scope='capacity v3 development;1138 target is already observed and family-informed augmentation used;NOT a new heldout evaluation. Frozen16 first scores preserved elsewhere.',lineage=json.loads((D/'lineage.json').read_text()),baseline=baseline,candidates=[],selected=None,complete=False);best=-1
profiles=[dict(name='shared32_tool5',hidden=32,outputs=16,epochs=180,seed=301101,lr=.003,tool=1.),dict(name='shared64_tool5',hidden=64,outputs=16,epochs=180,seed=301102,lr=.0025,tool=1.),dict(name='shared128_tool5',hidden=128,outputs=16,epochs=180,seed=301103,lr=.002,tool=1.),dict(name='shared64_binary',hidden=64,outputs=11,epochs=180,seed=301104,lr=.0025,tool=0.)]
start=time.monotonic()
for cfg in profiles:
 torch.manual_seed(cfg['seed']);m=Head(cfg['hidden'],cfg['outputs']);opt=torch.optim.Adam(m.parameters(),lr=cfg['lr'],weight_decay=.00003);local=-1
 for epoch in range(1,cfg['epochs']+1):
  perm=torch.randperm(len(y))
  for st in range(0,len(y),256):
   ix=perm[st:st+256];out=m(tx[ix]);loss=(F.cross_entropy(out[:,:2],execy[ix],reduction='none')*weights[ix]).mean()+.2*F.cross_entropy(out[:,2:11],cy[ix]);legal=y[ix]!=5
   if legal.any():loss+=.08*F.relu(out[legal,1]-out[legal,0]+2).mean()
   if cfg['tool']:
    residual=torch.cat([out[:,11:16]*trainmask[ix],torch.zeros_like(out[:,:1])],1);joint=tb[ix]+residual
    loss+=cfg['tool']*F.cross_entropy(joint,y[ix])+.3*F.cross_entropy(out[legal,11:16],y[ix][legal])if legal.any()else cfg['tool']*F.cross_entropy(joint,y[ix])
   opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),4.);opt.step()
  if epoch%20:continue
  q=m.arrays();out={n:infer(ar[n],q)for n in names};zs={}
  for n in names:
   de=(out[n][:,11:16]*(buckets[n]==5)[:,None])if cfg['tool']else oldrepair[n];z=base[n].copy();z[:,:5]+=de;zs[n]=z
  sel=calibrate(zs,{n:v[:,1]-v[:,0]for n,v in out.items()});rec=dict(config=cfg,epoch=epoch,selected=sel,constant_bytes=sum(a.nbytes for a in q.values())+24+(0 if cfg['tool']else 5140),dense_macs_per_call=cfg['hidden']*(1024+cfg['outputs']))
  report['candidates'].append(rec);print('CAPACITY',cfg['name'],epoch,None if sel is None else dict(score=sel['score'],thresholds=sel['thresholds'],counts={n:(v['correct'],v['legal_correct'],v['false_accept'])for n,v in sel['metrics'].items()}),flush=True)
  if sel and sel['score']>local:
   local=sel['score'];np.savez(D/('profile_'+cfg['name']+'.npz'),**q,thresholds=np.array(sel['thresholds']),hidden=np.array(cfg['hidden']),outputs=np.array(cfg['outputs']),toolhead=np.array(bool(cfg['tool'])))
  if sel and sel['score']>best:
   best=sel['score'];report['selected']=rec;np.savez(D/'selected.npz',**q,thresholds=np.array(sel['thresholds']),hidden=np.array(cfg['hidden']),outputs=np.array(cfg['outputs']),toolhead=np.array(bool(cfg['tool'])))
  (D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
report.update(complete=True,seconds=time.monotonic()-start);(D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('CAPACITY_COMPLETE',best,report['seconds'],flush=True)
