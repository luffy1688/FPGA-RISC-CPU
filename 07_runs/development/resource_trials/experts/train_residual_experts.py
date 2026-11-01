from pathlib import Path
D=Path(__file__).resolve().parent
exec((D/'train_experts.py').read_text().split('profiles=[')[0])
# Frozen strong global64 shared representation; learn only tool-conditioned output corrections.
class ResidualExpert(nn.Module):
 def __init__(self):
  super().__init__();self.b=nn.ModuleList([nn.Linear(64,16)for _ in range(6)])
  for l in self.b:nn.init.zeros_(l.weight);nn.init.zeros_(l.bias)
 def forward(self,h,route):
  pieces=[];indices=[]
  for k in range(6):
   ix=torch.where(route==k)[0]
   if not len(ix):continue
   pieces.append(ra(F.linear(h[ix],qweight(self.b[k].weight),None)*32)/32+qbias(self.b[k].bias));indices.append(ix)
  order=torch.cat(indices);return torch.cat(pieces)[torch.argsort(order)]
 def arrays(self):
  w=lambda x:np.clip(np.sign(x.detach().numpy())*np.floor(np.abs(x.detach().numpy())*64+.5),-128,127).astype(np.int8)
  b=lambda x:(np.sign(x.detach().numpy())*np.floor(np.abs(x.detach().numpy())*32+.5)).astype(np.int32)
  return dict(residual_w2=np.stack([w(l.weight)for l in self.b]),residual_b2=np.stack([b(l.bias)for l in self.b]))
h={n:np.clip(rounding(ar[n].astype(np.int32)@q64['w1'].astype(np.int32).T)+q64['b1'],0,127)for n in ['train']+names};frozenout={n:rounding(h[n]@q64['w2'].astype(np.int32).T)+q64['b2']for n in ['train']+names};th=torch.tensor(h['train'].astype(np.float32)/32);fo=torch.tensor(frozenout['train'].astype(np.float32)/32)
report=dict(scope='Frozen successful global64 -> per-encoder-tool residual experts6x16x64,conditional compute. Same25014train;1138and900observed selection;not first/heldout. Production untouched.',baseline64_revision2=baseline64,candidates=[],selected=None,complete=False);best=-1;torch.manual_seed(31004);m=ResidualExpert();opt=torch.optim.Adam(m.parameters(),lr=.003,weight_decay=.00003);start=time.monotonic()
for epoch in range(1,121):
 perm=torch.randperm(len(ty))
 for st in range(0,len(ty),256):
  ix=perm[st:st+256];res=m(th[ix],tr[ix]);out=fo[ix]+res;loss=(F.cross_entropy(out[:,:2],execy[ix],reduction='none')*weights[ix]).mean()+.25*F.cross_entropy(out[:,2:11],cy[ix]);legal=ty[ix]!=5
  if legal.any():loss+=.08*F.relu(out[legal,1]-out[legal,0]+2).mean()+.02*res[legal,:2].square().mean()+.3*F.cross_entropy(out[legal,11:16],ty[ix][legal])
  add=torch.cat([out[:,11:16]*repairmask[ix,None],torch.zeros_like(out[:,:1])],1);loss+=F.cross_entropy(tb[ix]+add,ty[ix]);opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),4.);opt.step()
 if epoch%15:continue
 q=m.arrays();outs={}
 for n in names:
  res=np.zeros((len(h[n]),16),np.int32)
  for k in range(6):
   ix=np.flatnonzero(route[n]==k)
   if len(ix):res[ix]=rounding(h[n][ix].astype(np.int32)@q['residual_w2'][k].astype(np.int32).T)+q['residual_b2'][k]
  outs[n]=frozenout[n]+res
 sel=evaluate(outs);rec=dict(epoch=epoch,selected=sel,constant_bytes=78572,active_dense_macs=67584,activation_bytes=1152);report['candidates'].append(rec);print('RESIDUAL_EXPERT',epoch,None if sel is None else dict(gate=sel['gate'],score=sel['score'],th=sel['thresholds'],values={n:(v['correct'],v['legal_correct'],v['false_accept'])for n,v in sel['metrics'].items()}),flush=True)
 if sel and sel['gate']and sel['score']>best:
  best=sel['score'];report['selected']=rec;np.savez(D/'residual_selected.npz',**q,w1=q64['w1'],b1=q64['b1'],w2=q64['w2'],b2=q64['b2'],thresholds=np.array(sel['thresholds'],np.int32),oldrepair_weight=q16['repair_weight'],oldrepair_bias=q16['repair_bias'])
 # Retain one best diagnostic candidate without representing a failed gate as accepted.
 if sel and(sel['score']>report.get('best_diagnostic_score',-1)):
  report['best_diagnostic_score']=sel['score'];report['best_diagnostic']=rec;np.savez(D/'residual_best_diagnostic.npz',**q,w1=q64['w1'],b1=q64['b1'],w2=q64['w2'],b2=q64['b2'],thresholds=np.array(sel['thresholds'],np.int32),oldrepair_weight=q16['repair_weight'],oldrepair_bias=q16['repair_bias'])
 (D/'residual_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
report.update(complete=True,seconds=time.monotonic()-start);(D/'residual_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('RESIDUAL_COMPLETE',best,report['seconds'],flush=True)
