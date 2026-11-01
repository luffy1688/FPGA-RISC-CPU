from pathlib import Path
import sys,json,time,copy,collections
import numpy as np,torch
from torch import nn
import torch.nn.functional as F
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(D))
from veto_train import features,fixed,evaluate,ra
from train import read,metrics
from train_context import ctxmetrics

torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
def qweight(x):return ra((x*64).clamp(-128,127))/64
def qbias(x):return ra(x*32)/32
def qact(x):return ra((x*32).clamp(0,127))/32
def rounding(z):return np.sign(z)*((np.abs(z)+32)//64)
class Head(nn.Module):
 def __init__(self,h,aux):
  super().__init__();self.a=nn.Linear(4096,h);self.b=nn.Linear(h,11 if aux else 2)
  nn.init.normal_(self.a.weight,std=.05);nn.init.zeros_(self.a.bias);nn.init.zeros_(self.b.bias)
 def forward(self,x):
  h=(ra(F.linear(x,qweight(self.a.weight),None)*32)/32+qbias(self.a.bias)).clamp(0,127/32)
  return ra(F.linear(h,qweight(self.b.weight),None)*32)/32+qbias(self.b.bias)
 def arrays(self):
  quant=lambda w:np.clip(np.sign(w.detach().numpy())*np.floor(np.abs(w.detach().numpy())*64+.5),-128,127).astype(np.int8)
  bias=lambda b:(np.sign(b.detach().numpy())*np.floor(np.abs(b.detach().numpy())*32+.5)).astype(np.int32)
  return dict(w1=quant(self.a.weight),b1=bias(self.a.bias),w2=quant(self.b.weight),b2=bias(self.b.bias))
def infer(x,q,old=None):
 h=np.clip(rounding(x.astype(np.int32)@q['w1'].astype(np.int32).T)+q['b1'],0,127).astype(np.int32)
 z=rounding(h@q['w2'].astype(np.int32).T)+q['b2']
 if old is not None:z[:,:2]+=old
 return z.astype(np.int32)
def main():
 start=time.monotonic();names=['train','validation','old_validation','original80','aug192','observed288']
 rows={'train':read(D/'data/train.jsonl'),'validation':read(D/'data/validation.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
 cache=np.load(D/'features.npz');base={n:cache[n+'_base']for n in names};oq=np.load(P/'context_int8.npz');old={n:fixed(cache[n+'_x'],oq['weight'],oq['bias']).astype(np.int32)for n in names}
 newcache=D/'features4096.npz'
 if newcache.exists():nc=np.load(newcache);ar={n:nc[n]for n in names}
 else:
  ar={}
  for n in names:
   print('FEATURES4096',n,flush=True);ar[n]=np.stack([features(x['text'],4096)for x in rows[n]])
  np.savez_compressed(newcache,**ar)
 baseline={n:dict(neural=evaluate(base[n],old[n],rows[n],64)[0],context=ctxmetrics(old[n],rows[n],64))for n in names if n!='train'}
 y=torch.tensor([x['intent']=='reject'for x in rows['train']],dtype=torch.long);tx=torch.tensor(ar['train'].astype(np.float32)/32)
 cy=torch.tensor([x.get('context',8)if 'synthetic'in x.get('source','')or'MASSIVE'in x.get('source','')else -1 for x in rows['train']],dtype=torch.long)
 oldtrain=torch.tensor(old['train'].astype(np.float32)/32)
 groups={}
 for i,x in enumerate(rows['train']):groups.setdefault((x['intent'],x.get('context',8)),[]).append(i)
 report=dict(architecture='signedUnicode4096 shared INT8 MLP context2 plus optional auxiliarycontext9; oldlinear optional additive residual',baseline=baseline,candidates=[],selected=None,complete=False,fresh_evaluated=False,heldout642_opened=False)
 chosen=None;best=-1;best_failed=-1
 profiles=[dict(name='wide_binary8',hidden=8,aux=0,residual=0,lr=.003,legal=4.,auxloss=0.,epochs=180,seed=20801,kd=.005),dict(name='wide_shared8',hidden=8,aux=1,residual=0,lr=.003,legal=4.,auxloss=.2,epochs=180,seed=20802,kd=.005),dict(name='wide_shared16',hidden=16,aux=1,residual=0,lr=.002,legal=4.,auxloss=.2,epochs=180,seed=20803,kd=.005)]
 for cfg in profiles:
  torch.manual_seed(cfg['seed']);m=Head(cfg['hidden'],cfg['aux']);
  if cfg['residual']:
   with torch.no_grad():m.b.weight[:2].zero_();m.b.bias[:2].zero_()
  opt=torch.optim.Adam(m.parameters(),lr=cfg['lr'],weight_decay=.00003);weights=torch.ones(len(y))
  for (tool,ctx),ix in groups.items():weights[ix]=len(y)/(len(groups)*len(ix))*(cfg['legal']if ctx==0 else 1.)
  localbest=-1
  for epoch in range(1,cfg['epochs']+1):
   perm=torch.randperm(len(y))
   for st in range(0,len(y),256):
    ix=perm[st:st+256];out=m(tx[ix]);binary=out[:,:2]+(oldtrain[ix]if cfg['residual']else 0);loss=(F.cross_entropy(binary,y[ix],reduction='none')*weights[ix]).mean()
    legalmask=y[ix]==0
    if legalmask.any():
     diff=binary[legalmask,1]-binary[legalmask,0];oldiff=oldtrain[ix[legalmask],1]-oldtrain[ix[legalmask],0]
     loss+=cfg['kd']*F.mse_loss(diff,oldiff)+.1*F.relu(diff+2).mean()
    if cfg['aux']:
     mask=cy[ix]>=0
     if mask.any():loss+=cfg['auxloss']*F.cross_entropy(out[mask,2:],cy[ix][mask])
    opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),4.);opt.step()
   if epoch%10:continue
   q=m.arrays();out={n:infer(ar[n],q,old[n]if cfg['residual']else None)for n in names if n!='train'}
   with torch.no_grad():exact=(m(torch.tensor(ar['old_validation'].astype(np.float32)/32))*32).numpy();exact=np.sign(exact)*np.floor(np.abs(exact)+.5)
   assert np.array_equal(exact.astype(np.int32)+(np.pad(old['old_validation'],((0,0),(0,9)))if cfg['residual']and cfg['aux']else old['old_validation']if cfg['residual']else 0),out['old_validation'])
   sel=None
   for threshold in [0,8,16,24,32,48,64,96,128,160,192,256,320,512]:
    ev={n:evaluate(base[n],out[n][:,:2],rows[n],threshold)[0]for n in out};cm={n:ctxmetrics(out[n][:,:2],rows[n],threshold)for n in out}
    score=.6*cm['validation']['macro_context']+.4*ev['validation']['macro_recall']
    gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=134 and ev['observed288']['correct']>=237 and ev['observed288']['false_accept']<=42 and ev['aug192']['false_accept']<=14 and cm['validation']['legal_denied']<=baseline['validation']['context']['legal_denied']
    rec=dict(threshold=threshold,score=score,gate=gate,neural=ev,context=cm)
    if score>localbest:
     localbest=score;np.savez(D/('profile_'+cfg['name']+'.npz'),**q,threshold=np.array(threshold,np.int32),hidden=np.array(cfg['hidden']),aux=np.array(cfg['aux']),residual=np.array(cfg['residual']))
    if not gate:
     if score>best_failed:best_failed=score;report['best_failed']=dict(config=cfg,epoch=epoch,metrics=rec)
     continue
    if sel is None or score>sel['score']:sel=rec
   report['candidates'].append(dict(profile=cfg['name'],epoch=epoch,selected=sel));print('MLP',cfg['name'],epoch,None if sel is None else dict(score=sel['score'],threshold=sel['threshold'],raw={n:e['correct']for n,e in sel['neural'].items()},legal_denied=sel['context']['validation']['legal_denied']),flush=True)
   if sel and sel['score']>best:
    best=sel['score'];chosen=dict(config=dict(cfg,epoch=epoch,threshold=sel['threshold']),state_dict=copy.deepcopy(m.state_dict()));report['selected']=dict(config=chosen['config'],metrics=sel)
    np.savez(D/'mlp4096_selected.npz',**q,threshold=np.array(sel['threshold'],np.int32),hidden=np.array(cfg['hidden']),aux=np.array(cfg['aux']),residual=np.array(cfg['residual']))
   (D/'mlp4096_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if chosen:torch.save(chosen,D/'mlp4096_selected.pt')
 report['complete']=True;report['selection_gate']=chosen is not None;report['seconds']=time.monotonic()-start;(D/'mlp4096_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('MLP_COMPLETE',report['selection_gate'],report['seconds'],flush=True)
if __name__=='__main__':main()
