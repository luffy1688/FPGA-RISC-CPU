from pathlib import Path
import sys,json,time,copy,collections
D=Path(__file__).resolve().parent;P=Path('/work/LUO/NeedleRV-X/07_runs/development/context_generalization');R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'context_v2'))
from train import read,TOOLS,metrics
from train_mlp import qweight,qbias,rounding,infer as infer_shared
from veto_train import fixed,ra
import numpy as np,torch
from torch import nn
import torch.nn.functional as F
torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
class Expert(nn.Module):
 def __init__(self,h,independent):
  super().__init__();self.h=h;self.independent=independent;self.a=nn.ModuleList([nn.Linear(1024,h)for _ in range(6 if independent else 1)]);self.b=nn.ModuleList([nn.Linear(h,16)for _ in range(6)])
  for l in list(self.a)+list(self.b):nn.init.normal_(l.weight,std=.04);nn.init.zeros_(l.bias)
 def lin(self,x,l):return ra(F.linear(x,qweight(l.weight),None)*32)/32+qbias(l.bias)
 def forward(self,x,route):
  if not self.independent:h=self.lin(x,self.a[0]).clamp(0,127/32)
  pieces=[];indices=[]
  for k in range(6):
   ix=torch.where(route==k)[0]
   if not len(ix):continue
   hk=self.lin(x[ix],self.a[k]).clamp(0,127/32)if self.independent else h[ix];pieces.append(self.lin(hk,self.b[k]));indices.append(ix)
  order=torch.cat(indices);out=torch.cat(pieces);return out[torch.argsort(order)]
 def arrays(self):
  w=lambda x:np.clip(np.sign(x.detach().numpy())*np.floor(np.abs(x.detach().numpy())*64+.5),-128,127).astype(np.int8)
  b=lambda x:(np.sign(x.detach().numpy())*np.floor(np.abs(x.detach().numpy())*32+.5)).astype(np.int32)
  return dict(w1=np.stack([w(l.weight)for l in self.a]),b1=np.stack([b(l.bias)for l in self.a]),w2=np.stack([w(l.weight)for l in self.b]),b2=np.stack([b(l.bias)for l in self.b]))
def infer(x,route,q):
 out=np.zeros((len(x),16),np.int32);independent=len(q['w1'])==6
 if not independent:h=np.clip(rounding(x.astype(np.int32)@q['w1'][0].astype(np.int32).T)+q['b1'][0],0,127)
 for k in range(6):
  ix=np.flatnonzero(route==k)
  if not len(ix):continue
  hk=np.clip(rounding(x[ix].astype(np.int32)@q['w1'][k].astype(np.int32).T)+q['b1'][k],0,127)if independent else h[ix]
  out[ix]=rounding(hk.astype(np.int32)@q['w2'][k].astype(np.int32).T)+q['b2'][k]
 return out

def detailed(z,rs):
 v=metrics(z,rs);truth=np.array([TOOLS.index(r['intent'])for r in rs]);pred=z.argmax(1);cm=np.zeros((6,6),np.int32)
 for a,b in zip(truth,pred):cm[a,b]+=1
 stats={}
 for k,t in enumerate(TOOLS):
  tp=int(cm[k,k]);support=int(cm[k].sum());called=int(cm[:,k].sum());pr=tp/max(1,called);re=tp/max(1,support);stats[t]=dict(precision=pr,recall=re,f1=2*pr*re/max(1e-12,pr+re),support=support,predicted=called,tp=tp)
 v.update(per_class=stats,confusion_true_rows_pred_columns=cm.tolist(),macro_f1=sum(v['f1']for v in stats.values())/6,legal_correct=int(cm[:5,:5].trace()),legal_total=int(cm[:5].sum()),context_recall={str(k):dict(correct=int(((pred==truth)&np.array([r.get('context',8)==k for r in rs])).sum()),n=sum(r.get('context',8)==k for r in rs))for k in sorted({r.get('context',8)for r in rs})});return v
names=['original80','aug192','observed288','old_validation','validation','observed1138','observed900'];rows={'train':read(P/'capacity/train.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'observed1138':read(P/'context_v2/data/fresh.jsonl'),'observed900':read(P/'capacity/internal_audit.jsonl')};cache=np.load(P/'context_v2/features.npz');fc=np.load(P/'intent/fresh_features.npz');ac=np.load(P/'capacity/audit_features.npz');traincache=np.load(P/'capacity/features.npz');ar={};base={}
for n in ['train']+names:
 c=traincache if n=='train'else fc if n=='observed1138'else ac if n=='observed900'else cache;ar[n]=c['x']if n in ['train','observed1138','observed900']else c[n+'_x'];base[n]=c['base']if n in ['train','observed1138','observed900']else c[n+'_base']
q16=np.load(P/'intent/combined_candidate.npz');q64=np.load(P/'capacity/deployment_revision2.npz');route={n:base[n].argmax(1)for n in ['train']+names};unvetoed={};baseline16={};baseline64={};teachertrain=None
for n in ['train']+names:
 de=fixed(ar[n],q16['repair_weight'],q16['repair_bias'])*(route[n]==5)[:,None];z=base[n].copy();z[:,:5]+=de;unvetoed[n]=z
 if n=='train':teachertrain=infer_shared(ar[n],q16)[:,:2];continue
 ct=infer_shared(ar[n],q16);diff=ct[:,1]-ct[:,0];th=q16['thresholds'][route[n]];deny=diff>=th;b=z.copy();b[deny,5]=np.maximum(b[deny,5],b[deny,:5].max(1)+diff[deny]-th[deny]+1);baseline16[n]=detailed(b,rows[n])
 ct=infer_shared(ar[n],q64);b=z.copy();b[:,:5]+=ct[:,11:16]*(b.argmax(1)==5)[:,None];diff=ct[:,1]-ct[:,0];th=q64['thresholds'][route[n]];deny=diff>=th;b[deny,5]=np.maximum(b[deny,5],b[deny,:5].max(1)+diff[deny]-th[deny]+1);baseline64[n]=detailed(b,rows[n])
truth={n:np.array([TOOLS.index(r['intent'])for r in rows[n]])for n in names};tx=torch.tensor(ar['train'].astype(np.float32)/32);ty=torch.tensor([TOOLS.index(r['intent'])for r in rows['train']]);cy=torch.tensor([r.get('context',8)for r in rows['train']]);tr=torch.tensor(route['train']);execy=(ty==5).long();tb=torch.tensor(unvetoed['train'].astype(np.float32)/32);repairmask=tb.argmax(1)==5;teach=torch.tensor(teachertrain.astype(np.float32)/32)
groups={}
for i,r in enumerate(rows['train']):groups.setdefault((r['intent'],r.get('context',8)),[]).append(i)
weights=torch.ones(len(ty))
for (tool,c),ix in groups.items():weights[ix]=len(ty)/(len(groups)*len(ix))*(2.5 if c==0 else 1.)
def evaluate(outs):
 zs={n:unvetoed[n].copy()for n in names}
 for n in names:zs[n][:,:5]+=outs[n][:,11:16]*(zs[n].argmax(1)==5)[:,None]
 best=None;failed=None
 for th5 in [0,8,16,24,32,48,64,96,128,160,192,256,320,512,768,1024,2048,4096]:
  thresholds=np.zeros(6,np.int32);thresholds[5]=th5;possible=True
  for k in range(5):
   for n in names[:5]:
    target=baseline16[n]['by_class'][TOOLS[k]][0];pre=zs[n].argmax(1);diff=outs[n][:,1]-outs[n][:,0];repaircorrect=(truth[n]==k)&(pre==k)&(route[n]==5)&(diff<th5);need=target-int(repaircorrect.sum());avail=np.sort(diff[(truth[n]==k)&(pre==k)&(route[n]==k)])
    if need>len(avail):possible=False;break
    if need>0:thresholds[k]=max(thresholds[k],int(avail[need-1])+1)
   if not possible:break
  if not possible:continue
  ev={}
  for n in names:
   z=zs[n].copy();diff=outs[n][:,1]-outs[n][:,0];th=thresholds[route[n]];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1);ev[n]=detailed(z,rows[n])
  gate=all(ev[n]['correct']>=baseline16[n]['correct']and ev[n]['false_accept']<=baseline16[n]['false_accept']for n in names[:5]);score=.35*ev['observed1138']['macro_recall']+.30*ev['validation']['macro_recall']+.2*ev['observed900']['macro_recall']+.15*sum(ev[n]['macro_recall']for n in names[:3])/3;rec=dict(gate=gate,thresholds=thresholds.tolist(),score=score,metrics=ev)
  if gate:
   if best is None or score>best['score']:best=rec
  elif failed is None or score>failed['score']:failed=rec
 return best if best else failed
profiles=[dict(name='shared64_sixexperts',hidden=64,independent=False,epochs=160,lr=.0025,seed=31001),dict(name='shared128_sixexperts',hidden=128,independent=False,epochs=160,lr=.002,seed=31002),dict(name='independent32_sixexperts',hidden=32,independent=True,epochs=160,lr=.0025,seed=31003)]
report=dict(scope='Server-private tool-conditioned neural experts. Routing is immutable encoder argmax6,not groundtruthtool or schemahint. All1138/900 are observed development and used for selection,never heldout; unchanged capacity25014 training only; no demo filtering. Frozen16/64 production unchanged.',training_rows=len(rows['train']),route_train_counts=dict(collections.Counter(route['train'].tolist())),baseline16=baseline16,baseline64_revision2=baseline64,candidates=[],selected=None,complete=False);best=-1;start=time.monotonic()
for cfg in profiles:
 torch.manual_seed(cfg['seed']);m=Expert(cfg['hidden'],cfg['independent']);opt=torch.optim.Adam(m.parameters(),lr=cfg['lr'],weight_decay=.00003);local=-1
 for epoch in range(1,cfg['epochs']+1):
  perm=torch.randperm(len(ty))
  for st in range(0,len(ty),256):
   ix=perm[st:st+256];out=m(tx[ix],tr[ix]);loss=(F.cross_entropy(out[:,:2],execy[ix],reduction='none')*weights[ix]).mean()+.25*F.cross_entropy(out[:,2:11],cy[ix]);legal=ty[ix]!=5
   if legal.any():loss+=.08*F.relu(out[legal,1]-out[legal,0]+2).mean()+.008*F.mse_loss(out[legal,1]-out[legal,0],teach[ix[legal],1]-teach[ix[legal],0])+.3*F.cross_entropy(out[legal,11:16],ty[ix][legal])
   add=torch.cat([out[:,11:16]*repairmask[ix,None],torch.zeros_like(out[:,:1])],1);loss+=F.cross_entropy(tb[ix]+add,ty[ix]);opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),4.);opt.step()
  if epoch%20:continue
  q=m.arrays();outs={n:infer(ar[n],route[n],q)for n in names};sel=evaluate(outs);const=sum(x.nbytes for x in q.values())+5140+24;mac=cfg['hidden']*(1024+16);rec=dict(config=cfg,epoch=epoch,selected=sel,constant_bytes=const,active_dense_macs=mac,activation_bytes=1024+cfg['hidden']+16*4);report['candidates'].append(rec)
  print('EXPERT',cfg['name'],epoch,None if sel is None else dict(gate=sel['gate'],score=sel['score'],th=sel['thresholds'],values={n:(v['correct'],v['legal_correct'],v['false_accept'])for n,v in sel['metrics'].items()}),flush=True)
  if sel and sel['score']>local:
   local=sel['score'];np.savez(D/('profile_'+cfg['name']+'.npz'),**q,thresholds=np.array(sel['thresholds'],np.int32),hidden=np.array(cfg['hidden']),independent=np.array(cfg['independent']),oldrepair_weight=q16['repair_weight'],oldrepair_bias=q16['repair_bias'])
  if sel and sel['gate']and sel['score']>best:
   best=sel['score'];report['selected']=rec;np.savez(D/'selected.npz',**q,thresholds=np.array(sel['thresholds'],np.int32),hidden=np.array(cfg['hidden']),independent=np.array(cfg['independent']),oldrepair_weight=q16['repair_weight'],oldrepair_bias=q16['repair_bias'])
  (D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
report.update(complete=True,seconds=time.monotonic()-start);(D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('EXPERT_COMPLETE',best,report['seconds'],flush=True)
