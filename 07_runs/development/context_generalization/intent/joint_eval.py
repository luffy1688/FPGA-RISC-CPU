from train_intent import *
sys.path.insert(0,str(P/'context_v2'))
from train_mlp import infer
from train_context import ctxmetrics
rows={'validation':read(P/'context_v2/data/validation.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
cache=np.load(P/'context_v2/features.npz');base={n:cache[n+'_base']for n in rows};ar={n:cache[n+'_x']for n in rows};oldctx=np.load(P/'context_int8.npz');old={n:fixed(ar[n],oldctx['weight'],oldctx['bias'])for n in rows}
baseline={n:metrics(fusion(base[n],old[n]),rr)for n,rr in rows.items()}
checkpoints=['profile_reject_repair5_256.pt','profile_reject_repair5_1024.pt']
report=dict(scope='Joint observed development evaluation only,642/fresh never read; contextprofiles not individually production accepted',baseline=baseline,candidates=[],selected=None)
best=-1
for cp in checkpoints:
 ck=torch.load(D/cp,map_location='cpu');bins=ck['config']['bins'];delta={}
 for n,rr in rows.items():
  f=ar[n]if bins==1024 else np.stack([features(x['text'],bins)for x in rr]);delta[n]=np.column_stack([fixed(f,ck['weight'],ck['bias']),np.zeros(len(rr),np.int32)])*(base[n].argmax(1)==5)[:,None]
 for profile in ['binary8','shared8','residual_shared16']:
  q=np.load(P/'context_v2'/('profile_'+profile+'.npz'));z={n:infer(ar[n],q,old[n]if q['residual']else None)[:,:2]for n in rows}
  local=None
  for threshold in [0,8,16,24,32,48,64,96,128,160,192,256,320,512]:
   ev={};context={}
   for n,rr in rows.items():
    vals=base[n]+delta[n];diff=z[n][:,1]-z[n][:,0];deny=diff>=threshold;vals[deny,5]=np.maximum(vals[deny,5],vals[deny,:5].max(1)+diff[deny]-threshold+1);ev[n]=metrics(vals,rr);ev[n]['legal_correct']=legal(ev[n]);context[n]=ctxmetrics(z[n],rr,threshold)
   gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=134 and ev['observed288']['correct']>=237 and ev['aug192']['false_accept']<=14 and ev['observed288']['false_accept']<=42
   score=.6*context['validation']['macro_context']+.4*ev['validation']['macro_recall']
   rec=dict(repair=cp,context_profile=profile,threshold=threshold,gate=gate,score=score,metrics=ev,context=context)
   if local is None or score>local['score']:local=rec
   if gate:
    report['candidates'].append(rec)
    if score>best:best=score;report['selected']=rec
  report.setdefault('best_even_failed',[]).append(local);print('JOINT',cp,profile,'best_score',local['score'],'oldcounts',{n:local['metrics'][n]['correct']for n in rows},'gate',local['gate'],flush=True)
(D/'joint_report.json').write_text(json.dumps(report,indent=2)+'\n');print('JOINT_COMPLETE',None if report['selected']is None else {k:report['selected'][k]for k in ['repair','context_profile','threshold','score']})
