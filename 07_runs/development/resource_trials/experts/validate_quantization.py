from pathlib import Path
D=Path(__file__).resolve().parent
exec((D/'train_experts.py').read_text().split('profiles=[')[0])
profiles=[]
for cfgname in ['shared64_sixexperts','shared128_sixexperts','independent32_sixexperts']:
 q=np.load(D/('profile_'+cfgname+'.npz'));h=int(q['hidden']);m=Expert(h,bool(q['independent']))
 with torch.no_grad():
  for i,l in enumerate(m.a):l.weight.copy_(torch.tensor(q['w1'][i].astype(np.float32)/64));l.bias.copy_(torch.tensor(q['b1'][i].astype(np.float32)/32))
  for i,l in enumerate(m.b):l.weight.copy_(torch.tensor(q['w2'][i].astype(np.float32)/64));l.bias.copy_(torch.tensor(q['b2'][i].astype(np.float32)/32))
 count=0
 for n in names:
  target=infer(ar[n],route[n],q)
  with torch.no_grad():actual=(m(torch.tensor(ar[n].astype(np.float32)/32),torch.tensor(route[n]))*32).numpy();actual=np.sign(actual)*np.floor(np.abs(actual)+.5)
  assert np.array_equal(actual.astype(np.int32),target),(cfgname,n);count+=len(target)
 profiles.append(dict(name=cfgname,quantized_torch_numpy_exact_cases=count,constant_bytes=sum(q[k].nbytes for k in ['w1','b1','w2','b2','oldrepair_weight','oldrepair_bias','thresholds']),active_dense_macs=h*(1024+16),activation_bytes=1024+h+64))
# Residual weight proof shares exact fixed frozen global features and output matrix.
for name,learned_route in [('residual_selected',False),('candidate_route_selected',True)]:
 q=np.load(D/(name+'.npz'));count=0
 for n in names:
  h=np.clip(rounding(ar[n].astype(np.int32)@q['w1'].astype(np.int32).T)+q['b1'],0,127);baseout=rounding(h@q['w2'].astype(np.int32).T)+q['b2'];r=route[n].copy()
  if learned_route:
   candidate=unvetoed[n].copy();candidate[:,:5]+=baseout[:,11:16]*(candidate.argmax(1)==5)[:,None];r=candidate.argmax(1)
  actual=np.zeros_like(baseout);expected=np.zeros_like(baseout)
  for k in range(6):
   ix=np.flatnonzero(r==k)
   if not len(ix):continue
   expected[ix]=rounding(h[ix].astype(np.int32)@q['residual_w2'][k].astype(np.int32).T)+q['residual_b2'][k]
   with torch.no_grad():v=(ra(F.linear(torch.tensor(h[ix].astype(np.float32)/32),torch.tensor(q['residual_w2'][k].astype(np.float32)/64),None)*32)/32+torch.tensor(q['residual_b2'][k].astype(np.float32)/32))*32;v=v.numpy();actual[ix]=(np.sign(v)*np.floor(np.abs(v)+.5)).astype(np.int32)
  assert np.array_equal(actual,expected),(name,n);count+=len(actual)
 profiles.append(dict(name=name,quantized_torch_numpy_exact_cases=count,constant_bytes=sum(q[k].nbytes for k in ['w1','b1','w2','b2','residual_w2','residual_b2','oldrepair_weight','oldrepair_bias','thresholds']),active_dense_macs=67584,activation_bytes=1152))
r=dict(scope='Private server quantized Torch/NumPy mathematical agreement only;not C/RTL/physical adoption;all5170rowsobserved development,unchanged training25014,no new labels or demos',profiles=profiles,production_modified=False)
(D/'quantization_validation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
# Condense best-per-profile with full underlying P/R/F1/confusions retained.
reports=[('direct',json.loads((D/'report.json').read_text())),('residual',json.loads((D/'residual_report.json').read_text())),('candidate_route',json.loads((D/'candidate_route_report.json').read_text()))];summary=[]
for group,rp in reports:
 if group=='direct':
  for name in ['shared64_sixexperts','shared128_sixexperts','independent32_sixexperts']:
   c=[x for x in rp['candidates']if x['config']['name']==name and x['selected']];best=max(c,key=lambda c:c['selected']['score']);summary.append(dict(group=group,profile=name,best=best))
 else:summary.append(dict(group=group,profile=group,best=rp['selected']or rp.get('best_diagnostic')))
result=dict(scope='Same25014train,all1138/900observed-development selection,neuralrouter only,not schema/groundtruthoracle. PerclassP/R/F1 and confusion in eachbest.metrics. Not a deployment recommendation.',baseline64=baseline64,best_profiles=summary,quantization_profiles=profiles,production_modified=False)
(D/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
for x in summary:
 b=x['best'];s=b['selected'];print('SUMMARY',x['profile'],b.get('epoch'),s['gate'],{n:(m['correct'],m['false_accept'],m['false_reject'])for n,m in s['metrics'].items()},'CORE',s['metrics']['observed1138']['per_class']['run_coremark'],'COUNTER',s['metrics']['observed1138']['per_class']['read_counter'])
