from pathlib import Path
D=Path(__file__).resolve().parent
exec((D/'train_experts.py').read_text().split('profiles=[')[0])
DEV=names[:5];OBS=names[5:]
C=D.parent/'capacity';q64=np.load(C/'h64_f2048_position.npz');pc=np.load(C/'features_position_2048.npz');position_x={n:pc[n]for n in ['train']+DEV}
sys.path.insert(0,str(C));from feature_extract import position_features
for n in OBS:position_x[n]=np.stack([position_features(row['text'])for row in rows[n]])

hidden={n:np.clip(rounding(position_x[n].astype(np.int32)@q64['w1'].astype(np.int32).T)+q64['b1'],0,127)for n in ['train']+names}
heads={n:rounding(hidden[n]@q64['w2'].astype(np.int32).T)+q64['b2']for n in ['train']+names}
pre={n:unvetoed[n].copy()for n in ['train']+names}
for n in pre:pre[n][:,:5]+=heads[n][:,11:16]*(pre[n].argmax(1)==5)[:,None]
margin={n:np.sort(pre[n],axis=1)[:,-1]-np.sort(pre[n],axis=1)[:,-2]for n in pre}
# Protect every per-tool development result of the frozen position primary.
for n in names:
 b=pre[n].copy();diff=heads[n][:,1]-heads[n][:,0];th=q64['thresholds'][route[n]];deny=diff>=th;b[deny,5]=np.maximum(b[deny,5],b[deny,:5].max(1)+diff[deny]-th[deny]+1);baseline64[n]=detailed(b,rows[n])

class Fusion(nn.Module):
 def __init__(self,w):
  super().__init__();self.l=nn.Linear(w,5);nn.init.zeros_(self.l.weight);nn.init.zeros_(self.l.bias)
 def forward(self,x):return ra(F.linear(x,qweight(self.l.weight),None)*32)/32+qbias(self.l.bias)
 def arrays(self):
  a=self.l.weight.detach().numpy();b=self.l.bias.detach().numpy();return {'fusion_w':np.clip(np.sign(a)*np.floor(np.abs(a)*64+.5),-128,127).astype(np.int8),'fusion_b':(np.sign(b)*np.floor(np.abs(b)*32+.5)).astype(np.int32)}
def scaled(v,den):return (np.sign(v)*((np.abs(v)+den//2)//den)).astype(np.int32)
def feature(n,mode):
 if mode==0:return hidden[n].astype(np.int8)
 return np.concatenate([hidden[n],np.clip(scaled(base[n],mode),-127,127)],axis=1).astype(np.int8)
def apply(n,f,q,alpha,gate):
 delta=rounding(f.astype(np.int32)@q['fusion_w'].astype(np.int32).T)+q['fusion_b']
 z=pre[n].copy();use=(pre[n].argmax(1)!=5)&(margin[n]<=gate) # only rerank actual legal candidate; no new reject rescue
 z[use,:5]+=scaled(delta[use]*alpha,4)
 # Identity correction must not become an untrained reject head. Preserve
 # the original legal/reject state; only the original context head may veto.
 z[use,5]=np.minimum(z[use,5],z[use,:5].max(1)-1)
 diff=heads[n][:,1]-heads[n][:,0];th=q64['thresholds'][route[n]];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1)
 return z
def summarize(m):return {n:{k:v[k]for k in ['correct','legal_correct','false_accept','false_reject','macro_f1']}for n,v in m.items()}
def evaluate(features,q):
 best=None;diagnostic=None
 for alpha in [1,2,4,8,16]:
  for gate in [8,16,32,64,128,256,512,2**30]:
   met={n:detailed(apply(n,features[n],q,alpha,gate),rows[n])for n in DEV}
   strict=lambda b:all(met[n]['correct']>=b[n]['correct']and met[n]['false_accept']<=b[n]['false_accept']and all(met[n]['by_class'][t][0]>=b[n]['by_class'][t][0]for t in TOOLS[:5])for n in DEV)
   s16,s64=strict(baseline16),strict(baseline64)
   score=sum(met[n]['macro_f1']+.15*met[n]['legal_correct']/met[n]['legal_total']for n in DEV)/len(DEV)
   rec=dict(alpha_quarters=alpha,margin_gate=gate,strict16=s16,strict64=s64,dev_score=score,metrics=met)
   if diagnostic is None or score>diagnostic['dev_score']:diagnostic=rec
   if s64 and(best is None or score>best['dev_score']):best=rec
 return best,diagnostic
trainy=np.array([TOOLS.index(r['intent'])for r in rows['train']]);legal_ix=np.flatnonzero(trainy!=5)
records=[];chosen=None;diagnostic=None;start=time.monotonic()
for mode in [0,8,16]:
 fs={n:feature(n,mode)for n in ['train']+DEV};x=torch.tensor(fs['train'][legal_ix].astype(np.float32)/32);y=torch.tensor(trainy[legal_ix]);old=torch.tensor(pre['train'][legal_ix].astype(np.float32)/32)
 torch.manual_seed(31008+mode);model=Fusion(x.shape[1]);opt=torch.optim.Adam(model.parameters(),lr=.003,weight_decay=.00005)
 for ep in range(1,181):
  perm=torch.randperm(len(y))
  for st in range(0,len(y),256):
   ix=perm[st:st+256];delta=model(x[ix]);loss=F.cross_entropy(old[ix,:5]+delta,y[ix])+.001*delta.square().mean();opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(model.parameters(),4.);opt.step()
  if ep%15:continue
  q=model.arrays();sel,diag=evaluate(fs,q)
  for key,rec in [('selected',sel),('diagnostic',diag)]:
   if rec is None:continue
   rec.update(encoder_scale_divisor=mode,epoch=ep,extra_constant_bytes=sum(v.nbytes for v in q.values()),extra_active_macs=int(q['fusion_w'].size),input_features=int(q['fusion_w'].shape[1]))
   cur=chosen if key=='selected'else diagnostic
   if cur is None or rec['dev_score']>cur['dev_score']:
    if key=='selected':chosen=copy.deepcopy(rec)
    else:diagnostic=copy.deepcopy(rec)
    np.savez(D/('fusion_position_'+key+'.npz'),**q,encoder_scale_divisor=mode,alpha_quarters=rec['alpha_quarters'],margin_gate=rec['margin_gate'])
  records.append(dict(mode=mode,epoch=ep,selected=None if sel is None else{k:v for k,v in sel.items()if k!='metrics'},diagnostic={k:v for k,v in diag.items()if k!='metrics'}))
  print('FUSION',mode,ep,'selected',None if sel is None else(sel['dev_score'],summarize(sel['metrics'])),'diag',(diag['dev_score'],summarize(diag['metrics'])),flush=True)
# Freeze selected checkpoint using DEV only; now and only now replay observed sets.
for key,rec in [('selected',chosen),('diagnostic',diagnostic)]:
 if rec is None:continue
 q=np.load(D/('fusion_position_'+key+'.npz'));fs={n:feature(n,rec['encoder_scale_divisor'])for n in OBS}
 rec['observed_metrics']={n:detailed(apply(n,fs[n],q,rec['alpha_quarters'],rec['margin_gate']),rows[n])for n in OBS}
 # Independent Torch/NumPy quantized score check on frozen model, all7sets; no threshold tuning.
 count=0;m=Fusion(rec['input_features'])
 with torch.no_grad():m.l.weight.copy_(torch.tensor(q['fusion_w'].astype(np.float32)/64));m.l.bias.copy_(torch.tensor(q['fusion_b'].astype(np.float32)/32))
 for n in names:
  f=feature(n,rec['encoder_scale_divisor']);target=rounding(f.astype(np.int32)@q['fusion_w'].astype(np.int32).T)+q['fusion_b']
  with torch.no_grad():v=(m(torch.tensor(f.astype(np.float32)/32))*32).numpy();actual=np.sign(v)*np.floor(np.abs(v)+.5)
  assert np.array_equal(target,actual),(key,n,np.max(abs(target-actual)));count+=len(f)
 rec['quantized_torch_numpy_exact_cases']=count
report=dict(scope='Frozen position2048x64 hidden + bounded quantized encoder logits,5-output identity-only reranking residual; originalprelegalstate preserved before unchanged contextveto. Only legal training rows; actual pre-veto candidate and margin gate,not label or schema. Context permission unchanged. Checkpoint/alpha/gate selection only5development sets;1138/900observed replay only after freeze. No production adoption.',training_rows=len(rows['train']),legal_training_rows=len(legal_ix),baseline_position_primary={n:baseline64[n]for n in names},candidates=records,selected=chosen,best_diagnostic=diagnostic,complete=True,seconds=time.monotonic()-start,production_modified=False,cost_note='Requires complete immutable encoder before fusion; added350MAC at70features plus five bias/quant outputs; cannot replace context-onlyfast route.')
(D/'fusion_position_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('FUSION_POSITION_DONE',None if chosen is None else chosen['observed_metrics'],flush=True)
