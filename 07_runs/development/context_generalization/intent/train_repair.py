from pathlib import Path
import sys,json,time,copy,subprocess
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2]
sys.path.insert(0,str(P))
from train import read,TOOLS,metrics
from veto_train import fixed
import numpy as np,torch
from torch import nn
import torch.nn.functional as F
torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
def ra(x):return x+(torch.sign(x)*torch.floor(x.abs()+.5)-x).detach()
def features(text,bins):
 chars=[];digit=False
 for c in text:
  cp=ord(c)+32 if 'A'<=c<='Z'else ord(c)
  if 48<=cp<=57:
   if digit:continue
   cp=35;digit=True
  else:digit=False
  chars.append(cp)
 f=np.zeros(bins,np.int32)
 for i in range(len(chars)):
  h=2166136261
  for width in range(1,min(4,len(chars)-i)+1):
   h=((h^chars[i+width-1])*16777619)&0xffffffff;v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff
   f[v&(bins-1)]+=1 if not(v&1024)else-1
 return (np.clip(f,-3,3)*8).astype(np.int8)
def fusion(z,context):
 z=z.copy();diff=context[:,1]-context[:,0];deny=diff>=64
 z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-64+1)
 return z
def fusion_t(z,context):
 diff=context[:,1]-context[:,0];bump=z[:,:5].max(1).values+diff-2+1/32
 reject=torch.where(diff>=2,torch.maximum(z[:,5],bump),z[:,5])
 return torch.cat([z[:,:5],reject[:,None]],1)
class Head(nn.Module):
 def __init__(self,cfg):
  super().__init__();self.cfg=cfg;out=5 if cfg['kind']in ['legal5','reject_repair5']else 6;self.out=out
  self.a=nn.Linear(cfg['bins'],out);nn.init.zeros_(self.a.weight);nn.init.zeros_(self.a.bias)
 def forward(self,x):
  w=ra((self.a.weight*64).clamp(-128,127))/64;b=ra(self.a.bias*32)/32
  z=ra(F.linear(x,w,None)*32)/32+b
  return torch.cat([z,torch.zeros_like(z[:,:1])],1)if self.out==5 else z
 def arrays(self):
  w=torch.sign(self.a.weight.detach())*torch.floor((self.a.weight.detach()*64).abs()+.5)
  b=torch.sign(self.a.bias.detach())*torch.floor((self.a.bias.detach()*32).abs()+.5)
  return w.clamp(-128,127).to(torch.int32).numpy(),b.to(torch.int32).numpy()
def legal(m):return sum(v[0]for k,v in m['by_class'].items()if k!='reject')
def main():
 t=time.monotonic();names=['train','validation','original80','aug192','observed288']
 rows={'train':read(P/'context_v2/data/train.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
 old=np.load(P/'features.npz');bases={n:old[n+'_base']for n in names[2:]}
 cache=D/'expanded_bases.npz'
 if cache.exists():
  cached=np.load(cache);bases.update({n:cached[n]for n in names[:2]})
 else:
  for n in names[:2]:
   print('BASE',n,len(rows[n]),flush=True);z=subprocess.run([str(P/'baseline')],input='\n'.join(q['text']for q in rows[n])+'\n',text=True,stdout=subprocess.PIPE,check=True);bases[n]=np.array([json.loads(l)['logits']for l in z.stdout.splitlines()],np.int32);assert len(bases[n])==len(rows[n])
  np.savez_compressed(cache,**{n:bases[n]for n in names[:2]})
 ctx=np.load(P/'context_int8.npz')
 cx={n:np.stack([features(x['text'],1024)for x in rows[n]])for n in names};context={n:fixed(cx[n],ctx['weight'],ctx['bias'])for n in names}
 baseline={n:metrics(fusion(bases[n],context[n]),rows[n])for n in names if n!='train'}
 report=dict(scope='Development-only repair profiles saved under relaxed legal-retention gate,NOT production safety accepted; must jointly re-evaluate frozen stronger context before adoption; no642 or fourth25 accessed',baseline=baseline,candidates=[],selected=None,selection_gate=False,complete=False)
 y=torch.tensor([TOOLS.index(x['intent'])for x in rows['train']],dtype=torch.long);ixs=[torch.where(y==k)[0]for k in range(6)]
 baset=torch.tensor(bases['train'].astype(np.float32)/32);ct=torch.tensor(context['train'].astype(np.float32)/32)
 configs=[dict(kind='reject_repair5',bins=256,lr=.010,kd=.002,seed=30601,epochs=75),dict(kind='reject_repair5',bins=1024,lr=.008,kd=.002,seed=30603,epochs=75)]
 best=(-1,-1);checkpoint=None
 for cfg in configs:
  profile_best=(-1,-1)
  torch.manual_seed(cfg['seed']);m=Head(cfg);opt=torch.optim.Adam(m.parameters(),lr=cfg['lr'],weight_decay=.0002)
  ar={n:np.stack([features(x['text'],cfg['bins'])for x in rows[n]])for n in names};tx=torch.tensor(ar['train'].astype(np.float32)/32)
  for epoch in range(1,cfg['epochs']+1):
   for step in range(32):
    ix=torch.cat([q[torch.randint(len(q),(32,))]for q in ixs]);res=m(tx[ix]);res=res*((baset[ix].argmax(1)==5)[:,None]if cfg['kind']=='reject_repair5'else 1);z=fusion_t(baset[ix]+res,ct[ix]);loss=F.cross_entropy(z,y[ix])+cfg['kd']*res.square().mean();opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),3);opt.step()
   if epoch%15:continue
   w,b=m.arrays();ev={}
   for n in names[1:]:
    delta=fixed(ar[n],w,b)
    if cfg['kind']in ['legal5','reject_repair5']:delta=np.column_stack([delta,np.zeros(len(delta),np.int32)])
    if cfg['kind']=='reject_repair5':delta=delta*(bases[n].argmax(1)==5)[:,None]
    pred=fusion(bases[n]+delta,context[n]);ev[n]=metrics(pred,rows[n]);ev[n]['legal_correct']=legal(ev[n])
    if n=='validation':
     original={q['text']for q in read(P/'data/validation.jsonl')};mask=np.array([q['text']in original for q in rows[n]]);ev[n]['old541']=metrics(pred[mask],[q for q,k in zip(rows[n],mask)if k]);ev[n]['expanded_only']=metrics(pred[~mask],[q for q,k in zip(rows[n],mask)if not k]);ev[n]['by_context']={str(k):metrics(pred[np.array([q.get('context',8)==k for q in rows[n]])],[q for q in rows[n]if q.get('context',8)==k])for k in sorted({q.get('context',8)for q in rows[n]})}
   gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=134 and ev['observed288']['legal_correct']>=151
   score=(ev['validation']['macro_recall'],ev['validation']['legal_correct'])
   rec=dict(config=cfg,epoch=epoch,gate=gate,metrics=ev,constant_bytes=int(w.size+b.nbytes));report['candidates'].append(rec)
   print('INTENT',cfg['kind'],cfg['bins'],epoch,gate,{n:(v['correct'],v['legal_correct'],v['false_accept'])for n,v in ev.items()},score,flush=True)
   if gate and score>profile_best:
    profile_best=score;torch.save(dict(config=dict(cfg,selected_epoch=epoch),state_dict=copy.deepcopy(m.state_dict()),weight=w,bias=b),D/('profile_'+cfg['kind']+'_'+str(cfg['bins'])+'.pt'))
   if gate and score>best:
    best=score;checkpoint=dict(config=dict(cfg,selected_epoch=epoch),state_dict=copy.deepcopy(m.state_dict()),weight=w,bias=b);report['selected']=rec;report['selection_gate']=True
   (D/'repair_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if checkpoint:
  torch.save(checkpoint,D/'repair_best.pt');np.savez_compressed(D/'repair_intent_int8.npz',weight=checkpoint['weight'],bias=checkpoint['bias'],bins=checkpoint['config']['bins'],kind=checkpoint['config']['kind'])
 report.update(complete=True,seconds=time.monotonic()-t);(D/'repair_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('COMPLETE',report['selection_gate'],report['seconds'],flush=True)
if __name__=='__main__':main()
