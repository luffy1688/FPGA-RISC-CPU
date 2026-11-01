from train_intent import *
ck=torch.load(D/'best.pt',map_location='cpu');old=np.load(P/'features.npz');ctx=np.load(P/'context_int8.npz');cfg=ck['config'];rows={'validation':read(P/'data/validation.jsonl'),'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')};data={}
for n,rr in rows.items():
 base=old[n+'_base'];cx=np.stack([features(x['text'],1024)for x in rr]);c=fixed(cx,ctx['weight'],ctx['bias']);x=np.stack([features(z['text'],cfg['bins'])for z in rr]);delta=fixed(x,ck['weight'],ck['bias']);sort=np.sort(base,axis=1);margin=sort[:,-1]-sort[:,-2];data[n]=(base,c,delta,margin)
report=[]
for threshold in [16,32,64,96,128,192,256,384,512,768,1024]:
 ev={}
 for n,(base,c,delta,margin)in data.items():
  z=base+delta*(margin<threshold)[:,None];v=metrics(fusion(z,c),rows[n]);v['legal_correct']=legal(v);ev[n]=v
 gate=ev['original80']['correct']>=73 and ev['aug192']['correct']>=134 and ev['observed288']['correct']>=237 and ev['aug192']['false_accept']<=14 and ev['observed288']['false_accept']<=42
 r=dict(threshold=threshold,gate=gate,metrics=ev);report.append(r);print('GATE',threshold,gate,{k:(v['correct'],v['legal_correct'],v['false_accept'],v['by_class']['read_temp'][0])for k,v in ev.items()},ev['validation']['macro_recall'])
(D/'confidence_gate.json').write_text(json.dumps(report,indent=2)+'\n')
