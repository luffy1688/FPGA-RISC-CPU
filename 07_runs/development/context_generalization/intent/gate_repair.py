from train_intent import *
rows={'validation':read(P/'context_v2/data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')}
old=np.load(P/'features.npz');new=np.load(P/'context_v2/features.npz');ctx=np.load(P/'context_int8.npz');data={}
for n,rs in rows.items():
 base=new['validation_base']if n=='validation'else old[n+'_base'];cx=np.stack([features(x['text'],1024)for x in rs]);c=fixed(cx,ctx['weight'],ctx['bias']);data[n]=(base,c)
report=[];best=None
for name in ['profile_reject_repair5_256.pt','profile_reject_repair5_1024.pt']:
 ck=torch.load(D/name,map_location='cpu');cfg=ck['config'];deltas={n:np.column_stack([fixed(np.stack([features(x['text'],cfg['bins'])for x in rs]),ck['weight'],ck['bias']),np.zeros(len(rs),np.int32)])for n,rs in rows.items()}
 for threshold in [0,8,16,24,32,48,64,96,128,192,256]:
  ev={}
  for n,(base,c)in data.items():
   cand=base+deltas[n];mask=(base.argmax(1)==5)&(cand[:,:5].max(1)-cand[:,5]>=threshold);z=np.where(mask[:,None],cand,base);ev[n]=metrics(fusion(z,c),rows[n]);ev[n]['legal_correct']=legal(ev[n])
  gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=134 and ev['observed288']['correct']>=237 and ev['aug192']['false_accept']<=14 and ev['observed288']['false_accept']<=42
  rec=dict(checkpoint=name,threshold=threshold,gate=gate,metrics=ev);report.append(rec);score=ev['validation']['macro_recall']
  if gate and (best is None or score>best['metrics']['validation']['macro_recall']):best=rec
  print('REPAIR_GATE',cfg['bins'],threshold,gate,{n:(m['correct'],m['legal_correct'],m['false_accept'])for n,m in ev.items()},score)
(D/'repair_confidence_gate.json').write_text(json.dumps(dict(scope='Observed development thresholds; no642/fresh accessed',candidates=report,selected=best),indent=2)+'\n')
