from pathlib import Path
import sys,json,time,copy,collections
import numpy as np,torch
from torch import nn
import torch.nn.functional as F
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P))
from veto_train import Context,features,fixed,evaluate
from train import read,infer_base,metrics

torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
def ctxmetrics(z,rows,threshold):
 pred=z[:,1]-z[:,0]>=threshold;truth=np.array([x['intent']=='reject'for x in rows]);groups={}
 for ctx in range(9):
  ix=np.array([i for i,x in enumerate(rows)if x.get('context',8)==ctx]);
  if len(ix):groups[str(ctx)]=dict(n=int(len(ix)),correct=int((pred[ix]==truth[ix]).sum()),recall=float((pred[ix]==truth[ix]).mean()))
 return dict(n=len(rows),correct=int((pred==truth).sum()),legal_denied=int((pred&~truth).sum()),reject_allowed=int((~pred&truth).sum()),by_context=groups,macro_context=float(np.mean([x['recall']for x in groups.values()])))

def main():
 start=time.monotonic();names=['train','validation','old_validation','original80','aug192','observed288']
 rows={'train':read(D/'data/train.jsonl'),'validation':read(D/'data/validation.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
 old=np.load(P/'features.npz');oldlens={'train':10683,'validation':541};cache=D/'features.npz'
 if cache.exists():f=np.load(cache);ar={n:f[n+'_x']for n in names};base={n:f[n+'_base']for n in names}
 else:
  ar={};base={}
  for n in names:
   print('FEATURES',n,len(rows[n]),flush=True);ar[n]=np.stack([features(x['text'],1024)for x in rows[n]])
   if n in oldlens:base[n]=np.concatenate([old[n+'_base'],infer_base(rows[n][oldlens[n]:])],axis=0)
   elif n=='old_validation':base[n]=old['validation_base']
   else:base[n]=old[n+'_base']
  np.savez_compressed(cache,**{n+'_x':v for n,v in ar.items()},**{n+'_base':v for n,v in base.items()})
 oldarr=np.load(P/'context_int8.npz');print('OLD_KEYS',oldarr.files,flush=True)
 oldw=oldarr['weight'];oldb=oldarr['bias']if'bias'in oldarr else oldarr['b']
 oldcontext={n:fixed(ar[n],oldw,oldb).astype(np.int32)for n in names if n!='train'}
 baseline={n:dict(neural=evaluate(base[n],oldcontext[n],rows[n],64)[0],context=ctxmetrics(oldcontext[n],rows[n],64))for n in oldcontext}
 print('BASELINE',json.dumps(baseline),flush=True)
 y=torch.tensor([x['intent']=='reject'for x in rows['train']],dtype=torch.long);tx=torch.tensor(ar['train'].astype(np.float32)/32)
 oldtraincontext=torch.tensor(fixed(ar['train'],oldw,oldb).astype(np.float32)/32)
 groups={}
 for i,x in enumerate(rows['train']):groups.setdefault((x['intent']if x['intent']!='reject'else'reject',x.get('context',8)),[]).append(i)
 report=dict(scope='Context head training;new family separated development and fresh;no642 or user fourth used for selection',baseline=baseline,candidates=[],selected=None,complete=False,heldout642_opened=False,fresh_evaluated=False,feature_bins=1024,constant_bytes=2056)
 prev=json.loads((D/'train_report.json').read_text())if(D/'train_report.json').exists()else {}
 report['previous_failed_profiles']=[dict(profile=x['profile'],epoch=x['epoch'],gate=x['selected']is not None)for x in prev.get('candidates',[])]
 if prev.get('best_failed'):report['previous_best_failed']=prev['best_failed']
 best=-1;chosen=None;state=None;best_failed_score=-1
 profiles=[dict(name='warm_legal2',seed=20511,init='old',lr=.001,kd=.1,weak=1.,legal=2.,epochs=100),dict(name='scratch_legal3',seed=20512,init='zero',lr=.004,kd=0.,weak=1.,legal=3.,epochs=100),dict(name='warm_legal4',seed=20513,init='old',lr=.001,kd=.2,weak=1.2,legal=4.,epochs=120)]
 for cfg in profiles:
  torch.manual_seed(cfg['seed']);m=Context(1024)
  if cfg['init']=='old':
   with torch.no_grad():m.linear.weight.copy_(torch.tensor(oldw.astype(np.float32)/64));m.linear.bias.copy_(torch.tensor(oldb.astype(np.float32)/32))
  weights=torch.ones(len(y))
  for (tool,ctx),ix in groups.items():weights[ix]=len(y)/(len(groups)*len(ix))*(cfg['weak']if ctx in [1,6,7]else 1.)*(cfg['legal']if ctx==0 else 1.)
  opt=torch.optim.Adam(m.parameters(),lr=cfg['lr'],weight_decay=.0001)
  for epoch in range(1,cfg['epochs']+1):
   perm=torch.randperm(len(y))
   for st in range(0,len(y),256):
    ix=perm[st:st+256];out=m(tx[ix]);loss=(F.cross_entropy(out,y[ix],reduction='none')*weights[ix]).mean()
    if cfg['kd']:
     mask=ix<10683
     if mask.any():loss+=cfg['kd']*F.mse_loss(out[mask],oldtraincontext[ix[mask]])
    opt.zero_grad(set_to_none=True);loss.backward();opt.step()
   if epoch%10:continue
   w,b=m.arrays();out={n:fixed(ar[n],w,b)for n in names if n!='train'};selected=None
   for threshold in [0,8,16,24,32,48,64,96,128,160,192,256,320,384,512,768,1024]:
    ev={n:evaluate(base[n],out[n],rows[n],threshold)[0]for n in out};cm={n:ctxmetrics(out[n],rows[n],threshold)for n in out}
    gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=134 and ev['observed288']['correct']>=237 and ev['observed288']['false_accept']<=42 and ev['aug192']['false_accept']<=14 and cm['validation']['legal_denied']<=baseline['validation']['context']['legal_denied']
    score=.6*cm['validation']['macro_context']+.4*ev['validation']['macro_recall']
    if not gate:
     if score>best_failed_score:
      best_failed_score=score;report['best_failed']=dict(profile=cfg['name'],epoch=epoch,threshold=threshold,score=score,neural=ev,context=cm)
      np.savez(D/'failed_best_int8.npz',weights=w.astype(np.int8),bias=b.astype(np.int32),threshold=np.array(threshold,np.int32))
     continue
    if selected is None or score>selected['score']:selected=dict(threshold=threshold,score=score,neural=ev,context=cm)
   rec=dict(profile=cfg['name'],epoch=epoch,selected=selected);report['candidates'].append(rec)
   print('CANDIDATE',cfg['name'],epoch,json.dumps(selected),flush=True)
   if selected and selected['score']>best:
    best=selected['score'];state=copy.deepcopy(m.state_dict());chosen=dict(config=dict(cfg,bins=1024,epoch=epoch,threshold=selected['threshold']),state_dict=state);report['selected']=rec
    np.savez(D/'selected_int8.npz',weights=w.astype(np.int8),bias=b.astype(np.int32),threshold=np.array(selected['threshold'],np.int32))
   (D/'train_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if chosen:torch.save(chosen,D/'selected.pt')
 report['complete']=True;report['seconds']=time.monotonic()-start;report['selection_gate']=chosen is not None;(D/'train_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('COMPLETE',report['selection_gate'],report['seconds'],flush=True)
if __name__=='__main__':main()
