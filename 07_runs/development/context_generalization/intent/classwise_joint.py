from train_intent import *
sys.path.insert(0,str(P/'context_v2'));from train_mlp import infer
from train_context import ctxmetrics
rows={'validation':read(P/'context_v2/data/validation.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
cache=np.load(P/'context_v2/features.npz');base={n:cache[n+'_base']for n in rows};ar={n:cache[n+'_x']for n in rows};oldq=np.load(P/'context_int8.npz');old={n:fixed(ar[n],oldq['weight'],oldq['bias'])for n in rows};baseline={n:fusion(base[n],old[n])for n in rows}
truth={n:np.array([TOOLS.index(x['intent'])for x in rr])for n,rr in rows.items()}
oldmetrics={n:metrics(baseline[n],rr)for n,rr in rows.items()};report=dict(scope='Observed development class-conditional threshold candidate; no642/fresh accessed; minima protect every previously correct legal development item',baseline=oldmetrics,candidates=[],selected=None)
for cp in ['profile_reject_repair5_256.pt','profile_reject_repair5_1024.pt']:
 ck=torch.load(D/cp,map_location='cpu');bins=ck['config']['bins'];delta={n:np.column_stack([fixed(ar[n]if bins==1024 else np.stack([features(x['text'],bins)for x in rr]),ck['weight'],ck['bias']),np.zeros(len(rr),np.int32)])*(base[n].argmax(1)==5)[:,None]for n,rr in rows.items()}
 for prof in ['shared8','residual_shared16']:
  q=np.load(P/'context_v2'/('profile_'+prof+'.npz'));z={n:infer(ar[n],q,old[n]if q['residual']else None)[:,:2]for n in rows};diff={n:z[n][:,1]-z[n][:,0]for n in rows};minimum=np.zeros(6,np.int32)
  for n in ['original80','aug192','observed288']:
   pred=base[n].argmax(1);protected=(baseline[n].argmax(1)==truth[n])&(truth[n]!=5)
   for bucket in range(6):
    mask=protected&(pred==bucket)
    if mask.any():minimum[bucket]=max(minimum[bucket],diff[n][mask].max()+1)
  # Tools whose encoders already produced a legal action are protected. Reject bucket
  # may still abstain or repair at a separately calibrated threshold.
  best=None
  for reject_threshold in [0,8,16,24,32,48,64,96,128,160,192,256,320,512,1024]:
   thresholds=minimum.copy();thresholds[5]=max(thresholds[5],reject_threshold);ev={};cs={}
   for n,rr in rows.items():
    th=thresholds[base[n].argmax(1)];deny=diff[n]>=th;out=base[n]+delta[n];out[deny,5]=np.maximum(out[deny,5],out[deny,:5].max(1)+diff[n][deny]-th[deny]+1);ev[n]=metrics(out,rr);ev[n]['legal_correct']=legal(ev[n]);ev[n]['legal_total']=sum(x['intent']!='reject'for x in rr);ev[n]['legal_wrong_tool']=ev[n]['legal_total']-ev[n]['legal_correct']-ev[n]['false_reject'];cs[n]=dict(legal_denied=int(deny[truth[n]!=5].sum()),reject_allowed=int((~deny[truth[n]==5]).sum()))
   gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=134 and ev['observed288']['correct']>=237 and ev['aug192']['false_accept']<=14 and ev['observed288']['false_accept']<=42
   strict=all(ev[n]['by_class'][tool][0]>=oldmetrics[n]['by_class'][tool][0]for n in ['original80','aug192','observed288']for tool in TOOLS[:5])
   rec=dict(repair=cp,context_profile=prof,thresholds=thresholds.tolist(),gate=gate and strict,global_gate=gate,legal_class_gate=strict,metrics=ev,context=cs)
   if rec['gate']and(best is None or ev['validation']['macro_recall']>best['metrics']['validation']['macro_recall']):best=rec
  report['candidates'].append(best or dict(repair=cp,context_profile=prof,minimum=minimum.tolist(),gate=False))
  print('CLASSWISE',cp,prof,None if best is None else dict(thresholds=best['thresholds'],counts={n:(m['correct'],m['legal_correct'],m['false_accept'])for n,m in best['metrics'].items()}),flush=True)
  if best and(report['selected']is None or best['metrics']['validation']['macro_recall']>report['selected']['metrics']['validation']['macro_recall']):report['selected']=best
(D/'classwise_joint_report.json').write_text(json.dumps(report,indent=2)+'\n')
