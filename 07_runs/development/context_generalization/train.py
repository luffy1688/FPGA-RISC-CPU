from pathlib import Path
import json,subprocess,time,copy,sys,math
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
R=Path('/work/LUO/NeedleRV-X');D=Path(__file__).resolve().parent
torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
TOOLS=['read_temp','set_pwm','run_coremark','read_counter','set_led','reject']
def read(p):return[json.loads(l)for l in p.read_text().splitlines()if l]
def ra(x):
 q=torch.sign(x)*torch.floor(torch.abs(x)+.5);return x+(q-x).detach()
def aq(x):return ra(x.mul(32).clamp(-128,127))/32.
def wq(x):return ra(x.mul(32).clamp(-8,7))/32.
def features(text):
 # Char order1..4, normalize a contiguous decimal run to one abstract digit.
 chars=[];digit=False
 for c in text:
  cp=ord(c)+32 if 'A'<=c<='Z'else ord(c)
  if 48<=cp<=57:
   if digit:continue
   cp=35;digit=True
  else:digit=False
  chars.append(cp)
 f=np.zeros(512,np.int32)
 for at in range(len(chars)):
  h=2166136261
  for width in range(1,5):
   if at+width>len(chars):break
   h=((h^chars[at+width-1])*16777619)&0xffffffff
   v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff
   ix=v&511;f[ix]+=1 if not(v&512)else-1
 return np.clip(f,-3,3).astype(np.int8)*8
class Context(nn.Module):
 def __init__(self,hidden):
  super().__init__();self.hidden=hidden
  if hidden:
   self.a=nn.Linear(512,hidden);self.b=nn.Linear(hidden,8);nn.init.normal_(self.a.weight,std=.08);nn.init.zeros_(self.a.bias);nn.init.zeros_(self.b.weight);nn.init.zeros_(self.b.bias)
  else:self.a=nn.Linear(512,8);nn.init.zeros_(self.a.weight);nn.init.zeros_(self.a.bias)
 def linear(self,x,l):return F.linear(x,wq(l.weight),ra(l.bias*32)/32)
 def forward(self,x,base):
  y=self.linear(x,self.a)
  if self.hidden:y=self.linear(aq(F.relu(y)),self.b)
  residual=ra(y*32)/32
  final=base+residual[:,:6]
  final=torch.cat([final[:,:5],final[:,5:6]+residual[:,7:8]-residual[:,6:7]],-1)
  return final,residual[:,6:8]
def infer_base(rows):
 p=subprocess.run([str(D/'baseline')],input='\n'.join(x['text']for x in rows)+'\n',text=True,stdout=subprocess.PIPE,check=True)
 out=[json.loads(l)for l in p.stdout.splitlines()];assert len(out)==len(rows)
 return np.array([x['logits']for x in out],np.int32)
def metrics(logits,rows):
 pred=logits.argmax(-1);truth=np.array([TOOLS.index(x['intent'])for x in rows]);cm=np.zeros((6,6),int)
 for a,b in zip(truth,pred):cm[a,b]+=1
 return dict(n=len(rows),correct=int(cm.trace()),by_class={TOOLS[k]:[int(cm[k,k]),int(cm[k].sum())]for k in range(6)},false_accept=int(cm[5,:5].sum()),false_reject=int(cm[:5,5].sum()),macro_recall=float(np.mean([cm[k,k]/max(1,cm[k].sum())for k in range(6)])))
def main():
 t=time.monotonic();rows={'train':read(D/'data/train.jsonl'),'validation':read(D/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
 (D/'eval.c').write_text((R/'07_runs/development/engram_lite/eval.c').read_text())
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'03_sw/model'),str(R/'03_sw/model/byte_tool_model.c'),str(D/'eval.c'),'-o',str(D/'baseline')],check=True)
 cache=D/'features.npz'
 if cache.exists():data=np.load(cache)
 else:
  ar={}
  for name,z in rows.items():
   print('FEATURES',name,len(z),flush=True);ar[name+'_base']=infer_base(z);ar[name+'_x']=np.stack([features(x['text'])for x in z])
  np.savez_compressed(cache,**ar);data=ar
 bases={k:torch.tensor(data[k+'_base'].astype(np.float32)/32.)for k in rows};xs={k:torch.tensor(data[k+'_x'].astype(np.float32)/32.)for k in rows}
 ys={k:torch.tensor([TOOLS.index(z['intent'])for z in v])for k,v in rows.items()};speech=(ys['train']==5).long();ixs=[torch.where(ys['train']==k)[0]for k in range(6)]
 report={'scope':'all observed development sets, no heldout accessed; no production modification','baseline':{k:metrics(data[k+'_base'],v)for k,v in rows.items()if k!='train'},'candidates':[],'selected':None,'selection_gate':False}
 best=-1;state=None;config=None
 profiles=[dict(hidden=0,lr=.008,kd=.04,epochs=60,seed=20301),dict(hidden=16,lr=.004,kd=.06,epochs=80,seed=20302),dict(hidden=16,lr=.002,kd=.15,epochs=80,seed=20303)]
 for cfg in profiles:
  torch.manual_seed(cfg['seed']);m=Context(cfg['hidden']);opt=torch.optim.Adam(m.parameters(),lr=cfg['lr'])
  for epoch in range(1,cfg['epochs']+1):
   for step in range(32):
    ix=torch.cat([a[torch.randint(len(a),(32,))]for a in ixs]);out,act=m(xs['train'][ix],bases['train'][ix]);orig=ix<2352
    loss=F.cross_entropy(out,ys['train'][ix])+.35*F.cross_entropy(act,speech[ix])
    if orig.any():loss+=cfg['kd']*F.mse_loss(out[orig],bases['train'][ix][orig])
    opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),3.);opt.step()
   if epoch%10:continue
   with torch.no_grad():ev={k:metrics(m(xs[k],bases[k])[0].numpy(),z)for k,z in rows.items()if k!='train'}
   gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=129 and ev['observed288']['correct']>=218 and ev['observed288']['false_accept']<=61 and ev['aug192']['false_accept']<=19
   score=ev['validation']['macro_recall'] if gate else-1
   rec=dict(config=cfg,epoch=epoch,gate=gate,metrics=ev);report['candidates'].append(rec);print('CANDIDATE',cfg['hidden'],epoch,gate,{k:v['correct']for k,v in ev.items()},'valmacro',score,flush=True)
   if score>best:
    best=score;state=copy.deepcopy(m.state_dict());config=dict(cfg,selected_epoch=epoch);report['selected']=rec;report['selection_gate']=True
  (D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if state is not None:torch.save(dict(state_dict=state,config=config),D/'best.pt')
 report['seconds']=time.monotonic()-t;report['complete']=True;(D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('TRAIN_COMPLETE',report['selection_gate'],report['seconds'],flush=True)
if __name__=='__main__':main()
