from train import R,D,read,TOOLS,infer_base,metrics,ra
import torch,numpy as np,json,time,copy
from torch import nn
import torch.nn.functional as F
torch.set_num_threads(4)
def ra(x):
 q=torch.sign(x)*torch.floor(torch.abs(x)+.5)
 return q.detach()+(x-x.detach())
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
 for at in range(len(chars)):
  h=2166136261
  for width in range(1,5):
   if at+width>len(chars):break
   h=((h^chars[at+width-1])*16777619)&0xffffffff;v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff
   f[v&(bins-1)]+=1 if not(v&bins)else-1
 return (np.clip(f,-3,3)*8).astype(np.int8)
class Context(nn.Module):
 def __init__(self,bins):super().__init__();self.bins=bins;self.linear=nn.Linear(bins,2);nn.init.zeros_(self.linear.weight);nn.init.zeros_(self.linear.bias)
 def forward(self,x):
  w=ra((self.linear.weight*64).clamp(-128,127))/64;b=ra(self.linear.bias*32)/32
  return ra(F.linear(x,w,None)*32)/32+b
 def arrays(self):return (torch.sign(self.linear.weight.detach())*torch.floor((self.linear.weight.detach()*64).abs()+.5)).clamp(-128,127).to(torch.int32).numpy(),(torch.sign(self.linear.bias.detach())*torch.floor((self.linear.bias.detach()*32).abs()+.5)).to(torch.int32).numpy()
def fixed(x,w,b):
 z=x.astype(np.int32)@w.astype(np.int32).T
 return np.sign(z)*((np.abs(z)+32)//64)+b

def evaluate(base,context,rows,threshold):
 z=base.copy();diff=context[:,1]-context[:,0];deny=diff>=threshold
 # Hierarchical neural fusion; transparent base logits and binary context remain separately reportable.
 z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+np.maximum(1,diff[deny]-threshold+1))
 return metrics(z,rows),z

def main():
 t=time.monotonic();names=['train','validation','original80','aug192','observed288'];rows={'train':read(D/'data/train.jsonl'),'validation':read(D/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')};cache=np.load(D/'features.npz');base={n:cache[n+'_base']for n in names}
 y=torch.tensor([x['intent']=='reject'for x in rows['train']],dtype=torch.long)
 # Balance speech categories as well as execute/nonexecute, not only the easy public OOD cases.
 groups={}
 for i,x in enumerate(rows['train']):groups.setdefault((x['intent'],x.get('context',8)),[]).append(i)
 gp=[torch.tensor(ix)for ix in groups.values()];weights=torch.ones(len(y))
 for key,ix in groups.items():weights[ix]=len(y)/(len(groups)*len(ix))
 report={'candidate_only':True,'production_changed':False,'architecture':'learned signed Unicode1..4gram sparse INT8 binary context head + frozen production6way intent encoder; hierarchical neural fusion','selection_gate':False,'candidates':[],'complete':False,'baseline':{n:metrics(base[n],rows[n])for n in names if n!='train'},'heldout_evaluated':False};best=-1;chosen=None
 for bins,seed in [(1024,20401),(2048,20402)]:
  torch.manual_seed(seed);m=Context(bins);opt=torch.optim.Adam(m.parameters(),lr=.012,weight_decay=.0001);ar={n:np.stack([features(x['text'],bins)for x in rows[n]])for n in names};tx=torch.tensor(ar['train'].astype(np.float32)/32)
  for epoch in range(1,101):
   perm=torch.randperm(len(y))
   for st in range(0,len(y),256):
    ix=perm[st:st+256];pred=m(tx[ix]);loss=(F.cross_entropy(pred,y[ix],reduction='none')*weights[ix]).mean();opt.zero_grad(set_to_none=True);loss.backward();opt.step()
   if epoch%20:continue
   w,b=m.arrays();out={n:fixed(ar[n],w,b)for n in names if n!='train'}
   with torch.no_grad():actual=np.sign(m(torch.tensor(ar['validation'].astype(np.float32)/32)).numpy())*np.floor(np.abs(m(torch.tensor(ar['validation'].astype(np.float32)/32)).numpy())*32+.5)
   assert np.array_equal(actual.astype(np.int32),out['validation']),int(np.max(np.abs(actual-out['validation'])))
   selected=None
   for threshold in [0,8,16,24,32,48,64,96,128,160,192,256,320]:
    ev={n:evaluate(base[n],out[n],rows[n],threshold)[0]for n in out}
    gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=129 and ev['observed288']['correct']>=218 and ev['observed288']['false_accept']<=61 and ev['aug192']['false_accept']<=19
    if not gate:continue
    score=ev['validation']['macro_recall']
    if selected is None or score>selected['score']:selected=dict(threshold=threshold,score=score,metrics=ev)
   rec=dict(bins=bins,seed=seed,epoch=epoch,selected=selected);report['candidates'].append(rec);print('VETO',bins,epoch,selected,flush=True)
   if selected and selected['score']>best:
    best=selected['score'];chosen=dict(config=dict(bins=bins,seed=seed,epoch=epoch,threshold=selected['threshold']),state_dict=copy.deepcopy(m.state_dict()));report['selection_gate']=True;report['selected']=rec
   (D/'veto_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if chosen:torch.save(chosen,D/'best.pt')
 report['complete']=True;report['seconds']=time.monotonic()-t;(D/'veto_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('VETO_COMPLETE',report['selection_gate'],report['seconds'],flush=True)
if __name__=='__main__':main()
