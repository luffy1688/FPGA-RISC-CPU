from pathlib import Path
import sys,json,time,collections,copy
import numpy as np,torch
from torch import nn
import torch.nn.functional as F
R=Path('/work/LUO/NeedleRV-X');P=R/'07_runs/development/context_generalization';C=P/'capacity';D=Path(__file__).resolve().parent
sys.path.insert(0,str(P));sys.path.insert(0,str(P/'context_v2'))
from train import read,TOOLS
from veto_train import features as base_features,fixed,ra
from feature_extract import position_features
FEATURE_MODE="hash"
def features(text,bins):
 return position_features(text,bins)if FEATURE_MODE=="position"and bins==2048 else base_features(text,bins)
from train_mlp import qweight,qbias,infer

torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
rows={'train':read(C/'train.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl')}
names=list(rows)[1:];cache=np.load(P/'context_v2/features.npz');traincache=np.load(C/'features.npz');ar1024={n:cache[n+'_x']for n in names};base={n:cache[n+'_base']for n in names};ar1024['train']=traincache['x'];base['train']=traincache['base']
q64=dict(np.load(C/'deployment_revision2.npz'));q16=dict(np.load(P/'intent/combined_candidate.npz'))
y={n:np.array([TOOLS.index(x['intent'])for x in rs])for n,rs in rows.items()};bucket={n:base[n].argmax(1)for n in rows};oldrepair={n:fixed(ar1024[n],q64['oldrepair_weight'],q64['oldrepair_bias'])*(bucket[n]==5)[:,None]for n in rows};oldjoint={n:base[n].copy()for n in rows}
for n in rows:oldjoint[n][:,:5]+=oldrepair[n]
cascade={n:oldjoint[n].argmax(1)==5 for n in rows}

def evaluate(pred,rs):
 truth=np.array([TOOLS.index(x['intent'])for x in rs]);cm=np.zeros((6,6),np.int64);np.add.at(cm,(truth,pred),1);diag=cm.diagonal();rec=np.divide(diag,cm.sum(1),out=np.zeros(6,float),where=cm.sum(1)!=0);prec=np.divide(diag,cm.sum(0),out=np.zeros(6,float),where=cm.sum(0)!=0);f1=np.divide(2*rec*prec,rec+prec,out=np.zeros(6,float),where=rec+prec!=0);legal=truth!=5
 return dict(n=len(rs),correct=int((truth==pred).sum()),accuracy=float((truth==pred).mean()),macro_f1=float(f1.mean()),macro_recall=float(rec.mean()),legal_correct=int(((truth==pred)&legal).sum()),legal_n=int(legal.sum()),legal_recall=float(((truth==pred)&legal).sum()/legal.sum())if legal.any()else 0.0,false_accept=int(((pred!=5)&~legal).sum()),false_reject=int(((pred==5)&legal).sum()),wrong_legal_tool=int(((pred!=5)&(pred!=truth)&legal).sum()),by_class={name:dict(precision=float(prec[i]),recall=float(rec[i]),f1=float(f1[i]),correct=int(diag[i]),n=int(cm[i].sum()))for i,name in enumerate(TOOLS)},confusion=cm.tolist())

def joint(ct,n,thresholds):
 z=oldjoint[n].copy();z[:,:5]+=ct[:,11:16]*cascade[n][:,None];diff=ct[:,1]-ct[:,0];th=thresholds[bucket[n]];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1);return z

refout={n:infer(ar1024[n],q64)for n in rows};baseline={n:evaluate(joint(refout[n],n,q64['thresholds']).argmax(1),rows[n])for n in names}
old16={}
for n in names:
 ct=infer(ar1024[n],q16);z=base[n].copy();z[:,:5]+=fixed(ar1024[n],q16['repair_weight'],q16['repair_bias'])*(bucket[n]==5)[:,None];diff=ct[:,1]-ct[:,0];th=q16['thresholds'][bucket[n]];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1);old16[n]=evaluate(z.argmax(1),rows[n])

def score(ev):return float(np.mean([ev[n]['macro_f1']+.15*ev[n]['legal_recall'] for n in names]))
def gate(ev,ref):
 return all(ev[n]['correct']>=ref[n]['correct']and ev[n]['false_accept']<=ref[n]['false_accept']and all(ev[n]['by_class'][k]['correct']>=ref[n]['by_class'][k]['correct']for k in TOOLS[:5])for n in names)

# CPU BLAS uses integral-valued float32; all integer accumulated magnitudes must
# remain <2^24. Final selected candidate receives independent int32 replay.
def fastinfer(x,q):
 with torch.no_grad():
  a=torch.from_numpy(x.astype(np.float32));w=torch.from_numpy(q['w1'].astype(np.float32));v=a@w.T
  assert float(v.abs().max())<2**24
  h=(torch.sign(v)*torch.floor((v.abs()+32)/64)+torch.from_numpy(q['b1'])).clamp(0,127);v=h@torch.from_numpy(q['w2'].astype(np.float32)).T;assert float(v.abs().max())<2**24
  return (torch.sign(v)*torch.floor((v.abs()+32)/64)+torch.from_numpy(q['b2'])).numpy().astype(np.int32)

# Threshold calibration uses only existing developer selection sets. No1138/900
# samples or scores are opened until a checkpoint is chosen and frozen.
def calibrate(outs,ref):
 zs={n:oldjoint[n].copy()for n in names};diffs={n:outs[n][:,1]-outs[n][:,0]for n in names}
 for n in names:zs[n][:,:5]+=outs[n][:,11:16]*cascade[n][:,None]
 best=None
 for t5 in list(range(0,513,16))+[768,1024,2048,4096]:
  thresholds=np.zeros(6,np.int32);thresholds[5]=t5;possible=True
  for k in range(5):
   for n in names:
    pred=zs[n].argmax(1);rescued=((y[n]==k)&(pred==k)&(bucket[n]==5)&(diffs[n]<t5)).sum();need=ref[n]['by_class'][TOOLS[k]]['correct']-int(rescued);avail=np.sort(diffs[n][(y[n]==k)&(pred==k)&(bucket[n]==k)])
    if need>len(avail):possible=False;break
    if need>0:thresholds[k]=max(thresholds[k],int(avail[need-1])+1)
   if not possible:break
  if not possible:continue
  ev={}
  for n in names:ev[n]=evaluate(joint(outs[n],n,thresholds).argmax(1),rows[n])
  rec=dict(thresholds=thresholds.tolist(),score=score(ev),strict64=gate(ev,baseline),strict16=gate(ev,old16),metrics=ev)
  quality=(int(rec['strict16']),rec['score'],int(rec['strict64']))
  if best is None or quality>best[0]:best=(quality,rec)
 return best[1]if best else None

class Head(nn.Module):
 def __init__(self,bins,hidden,warm):
  super().__init__();self.a=nn.Linear(bins,hidden);self.b=nn.Linear(hidden,16);nn.init.normal_(self.a.weight,std=.025);nn.init.zeros_(self.a.bias);nn.init.zeros_(self.b.bias)
  if warm:
   with torch.no_grad():
    self.a.weight[:64].zero_();self.a.weight[:64,:1024].copy_(torch.from_numpy(q64['w1'].astype(np.float32)/64));self.a.bias[:64].copy_(torch.from_numpy(q64['b1'].astype(np.float32)/32));self.b.weight.zero_();self.b.weight[:,:64].copy_(torch.from_numpy(q64['w2'].astype(np.float32)/64));self.b.bias.copy_(torch.from_numpy(q64['b2'].astype(np.float32)/32))
 def forward(self,x):
  h=(ra(F.linear(x,qweight(self.a.weight),None)*32)/32+qbias(self.a.bias)).clamp(0,127/32)
  return ra(F.linear(h,qweight(self.b.weight),None)*32)/32+qbias(self.b.bias)
 def arrays(self):
  def w(x):
   v=x.detach().numpy();return np.clip(np.sign(v)*np.floor(np.abs(v)*64+.5),-128,127).astype(np.int8)
  def b(x):
   v=x.detach().numpy();return (np.sign(v)*np.floor(np.abs(v)*32+.5)).astype(np.int32)
  return dict(w1=w(self.a.weight),b1=b(self.a.bias),w2=w(self.b.weight),b2=b(self.b.bias))

cy=torch.tensor([r.get('context',8)for r in rows['train']]);ty=torch.tensor(y['train']);binary=(ty==5).long();groups={}
for i,r in enumerate(rows['train']):groups.setdefault((r['intent'],r.get('context',8)),[]).append(i)
weights=torch.ones(len(ty))
for (tool,ctx),ix in groups.items():weights[ix]=len(ty)/(len(groups)*len(ix))*(2.5 if ctx==0 else 1)
teacher=torch.tensor(refout['train'].astype(np.float32)/32);tb=torch.tensor(oldjoint['train'].astype(np.float32)/32);mask=torch.tensor(cascade['train'])[:,None]
configs=[dict(name='h96_f1024_warm',hidden=96,bins=1024,warm=True,epochs=160,lr=.0008,seed=301201),dict(name='h128_f1024_warm',hidden=128,bins=1024,warm=True,epochs=160,lr=.0008,seed=301202),dict(name='h256_f1024_warm',hidden=256,bins=1024,warm=True,epochs=160,lr=.0006,seed=301203),dict(name='h64_f2048_distill',hidden=64,bins=2048,warm=False,epochs=200,lr=.002,seed=301204),dict(name='h64_f4096_distill',hidden=64,bins=4096,warm=False,epochs=200,lr=.002,seed=301205)]
if '--phase2'in sys.argv:
 configs=[dict(name='h64_f2048_position',hidden=64,bins=2048,warm=True,feature_mode='position',epochs=200,lr=.0008,seed=301206),dict(name='h128_f2048_distill',hidden=128,bins=2048,warm=False,epochs=200,lr=.002,seed=301207)]
report=dict(scope='Server-only resource-for-accuracy development experiments; fixed25014training rows unchanged; old80/192/288/541/2031 selection;1138/900 observed regression only after frozen checkpoint; no production changes. Select strict16 protection then mean developer macroF1+0.15legalrecall; strict64 separately recorded rather than hiding tradeoffs.',train_rows=len(rows['train']),train_fields=['text','intent','context','source','family','split'],baseline64=baseline,baseline16=old16,configs=configs,experiments=[],completed=False)
if '--phase2'in sys.argv:
 previous=json.loads((D/'results.json').read_text());previous['configs']+=configs;previous['completed']=False;report=previous
(D/'matrix.json').write_text(json.dumps(dict(scope=report['scope'],configs=configs,selection_sets=names,observed_regression=['observed1138','observed900']),indent=2)+'\n')
start=time.monotonic();lastbins=None
for cfg in configs:
 began=time.monotonic();torch.manual_seed(cfg['seed']);bins=cfg['bins'];h=cfg['hidden'];FEATURE_MODE=cfg.get('feature_mode','hash')
 if bins==1024:ar=ar1024
 else:
  fp=D/('features_%s_%d.npz'%(FEATURE_MODE,bins))if FEATURE_MODE=='position'else D/('features_%d.npz'%bins)
  if fp.exists():a=np.load(fp);ar={n:a[n]for n in rows}
  else:ar={n:np.stack([features(r['text'],bins)for r in rs])for n,rs in rows.items()};np.savez_compressed(fp,**ar)
 tx=torch.tensor(ar['train'].astype(np.float32)/32);m=Head(bins,h,cfg['warm']);opt=torch.optim.Adam(m.parameters(),lr=cfg['lr'],weight_decay=.00001);best=None;history=[]
 for epoch in range(cfg['epochs']+1):
  if epoch:
   for st in range(0,len(ty),256):
    if st==0:perm=torch.randperm(len(ty))
    ix=perm[st:st+256];out=m(tx[ix]);legal=ty[ix]!=5;loss=(F.cross_entropy(out[:,:2],binary[ix],reduction='none')*weights[ix]).mean()+.2*F.cross_entropy(out[:,2:11],cy[ix]);joint_logits=tb[ix]+torch.cat([out[:,11:16]*mask[ix],torch.zeros_like(out[:,:1])],1);loss+=.8*F.cross_entropy(joint_logits,ty[ix])
    if legal.any():loss+=.3*F.cross_entropy(out[legal,11:16],ty[ix][legal])+.05*F.relu(out[legal,1]-out[legal,0]+2).mean()
    loss+=.12*F.smooth_l1_loss(out,teacher[ix])+ .2*F.kl_div(F.log_softmax(out[:,:2]/2,dim=1),F.softmax(teacher[ix,:2]/2,dim=1),reduction='batchmean')*4
    opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),4);opt.step()
  if epoch%20:continue
  q=m.arrays();outs={n:fastinfer(ar[n],q)for n in names};rec=calibrate(outs,baseline)
  if rec is None:rec=calibrate(outs,old16)
  if rec is None:print('NO_CALIBRATION',cfg['name'],epoch,flush=True);continue
  quality=(int(rec['strict16']),rec['score'],int(rec['strict64']));small=dict(epoch=epoch,strict64=rec['strict64'],strict16=rec['strict16'],score=rec['score'],counts={n:[v['correct'],v['legal_correct'],v['false_accept'],v['false_reject']]for n,v in rec['metrics'].items()});history.append(small);print('RESOURCE_CHECKPOINT',cfg['name'],small,flush=True)
  if best is None or quality>best[0]:best=(quality,copy.deepcopy(rec),copy.deepcopy(q),epoch,copy.deepcopy(m.state_dict()))
 assert best is not None,cfg
 _,rec,q,epoch,state=best;m.load_state_dict(state);q['thresholds']=np.array(rec['thresholds'],np.int32);q['oldrepair_weight']=q64['oldrepair_weight'];q['oldrepair_bias']=q64['oldrepair_bias'];q['hidden']=np.array(h);q['bins']=np.array(bins);q['outputs']=np.array(16);q['feature_mode']=np.array(FEATURE_MODE)
 np.savez(D/(cfg['name']+'.npz'),**q)
 # Freeze before reading the observed regression files; they cannot change
 # selected checkpoint or calibration. Preserve first evaluations elsewhere.
 selected=dict(feature_extraction=('global1024+front512+back512;ASCIIlower+digitrunfold;split=(normalizedUnicodeCodepoints+1)//2;positiongrams do not cross midpoint;globalgrams unchanged'if FEATURE_MODE=='position'else 'global signedUnicode1..4gram bins%d'%bins),config=cfg,selected_epoch=epoch,selection=rec,history=history,frozen_before_observed_replay=True,seconds_train=time.monotonic()-began)
 frozen_path=D/(cfg['name']+'_selection.json');frozen_path.write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
 sources={'observed1138':P/'context_v2/data/fresh.jsonl','observed900':C/'internal_audit.jsonl'}
 replay={};predsave={}
 for n,f in sources.items():
  rs=read(f);xx=np.stack([features(r['text'],bins)for r in rs]);xxold=np.stack([features(r['text'],1024)for r in rs]);cache_n=np.load(P/'intent/fresh_features.npz'if n=='observed1138'else C/'audit_features.npz');bb=cache_n['base'];ct=fastinfer(xx,q);bucket_n=bb.argmax(1);z=bb.copy();z[:,:5]+=fixed(xxold,q64['oldrepair_weight'],q64['oldrepair_bias'])*(bucket_n==5)[:,None];z[:,:5]+=ct[:,11:16]*(z.argmax(1)==5)[:,None];diff=ct[:,1]-ct[:,0];th=q['thresholds'][bucket_n];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1);pred=z.argmax(1);replay[n]=evaluate(pred,rs);replay[n]['context_categories']={str(k):evaluate(pred[np.array([a.get('context',8)==k for a in rs])],[a for a in rs if a.get('context',8)==k])for k in sorted(set(a.get('context',8)for a in rs))};predsave[n+'_pred']=pred;predsave[n+'_head']=ct
 # Numerical export verification uses direct int32 sums, not float reference.
 probe=np.concatenate([ar['train'][:64],ar['validation'][:64]])
 zint=infer(probe,q);zfast=fastinfer(probe,q)
 with torch.no_grad():
  zqat=np.sign(m(torch.tensor(probe.astype(np.float32)/32)).numpy())*np.floor(np.abs(m(torch.tensor(probe.astype(np.float32)/32)).numpy())*32+.5)
  xx=torch.tensor(probe.astype(np.float32)/32);zz=(m.a(xx).clamp(0,127/32));zfp=(m.b(zz)*32).numpy()
 assert np.array_equal(zint,zfast)and np.array_equal(zint,zqat),('numerical export mismatch',cfg['name'])
 err=np.abs(zfp-zint);numeric=dict(integer_export_vs_QAT_max_error=0,blas_vs_int32_max_error=0,probe_cases=len(probe),unquantized_float_vs_int8_mean_abs_logits=float(err.mean()),unquantized_float_vs_int8_max_abs_logits=float(err.max()),unquantized_float_vs_int8_argmax_agreement=float((zfp.argmax(1)==zint.argmax(1)).mean()))
 weights_bytes=sum(q[k].nbytes for k in ['w1','b1','w2','b2','oldrepair_weight','oldrepair_bias','thresholds']);nz=np.count_nonzero(ar['validation'],axis=1)
 resource=dict(head_and_oldrepair_constant_bytes=weights_bytes,head_weight_bytes=int(q['w1'].nbytes+q['w2'].nbytes),hidden_activation_bytes=h,feature_count_bytes=2*bins,previous_touch_bitmap_bytes=(bins+7)//8,dense_macs_per_head=h*(bins+16),sparse_macs_head_median=int(h*(np.median(nz)+16)),feature_nonzero_median=float(np.median(nz)),oldrepair_dense_macs_optional=5120,arithmetic_activation_bits=8,weights_bits=8,accumulator_bits=32)
 selected.update(observed_regression=replay,numerical=numeric,resources=resource,total_seconds=time.monotonic()-began);np.savez_compressed(D/(cfg['name']+'_predictions.npz'),**predsave);frozen_path.write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n');report['experiments'].append(selected);(D/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('RESOURCE_CANDIDATE_DONE',cfg['name'],dict(epoch=epoch,strict64=rec['strict64'],strict16=rec['strict16'],dev_score=rec['score'],counts={n:[v['correct'],v['legal_correct'],v['false_accept']]for n,v in replay.items()},weights=weights_bytes,seconds=selected['total_seconds']),flush=True)
 del tx,m,opt
report.update(completed=True,seconds=report.get('seconds',0)+time.monotonic()-start);(D/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('RESOURCE_CAPACITY_DONE',report['seconds'],flush=True)
