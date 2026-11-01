from train_intent import *
import subprocess,collections
sys.path.insert(0,str(P/'context_v2'));from train_mlp import infer
cache=np.load(P/'context_v2/features.npz');q=np.load(D/'combined_candidate.npz');frozen=json.loads((D/'fresh_first_evaluation.json').read_text());oldsystem=json.loads((D/'system_combined_report.json').read_text())
keys='index context_bucket context_bucket_source context_threshold context_deny context_used repair_used full full_status full_arg full_op fast fast_status fast_arg fast_op fast_handled'.split()
def run(name,rs):
 p=subprocess.run([str(D/name)],input='\n'.join(x['text']for x in rs)+'\n',stdout=subprocess.PIPE,text=True,check=True);out=[]
 for line in p.stdout.splitlines():
  a=list(map(int,line.split()));assert len(a)==44,(len(a),line);x=dict(zip(keys,a[:16]));at=16
  for key,n in [('logits',6),('encoder_logits',6),('context_logits',2),('category_logits',9),('intent_delta',5)]:x[key]=a[at:at+n];at+=n
  out.append(x)
 assert len(out)==len(rs);return out
rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'fresh_observed':read(P/'context_v2/data/fresh.jsonl')}
report=dict(scope='Necessary integrated C validation of frozen candidate and current policy fixes. Prior1138 first scores retained unchanged; its replay here is observed regression. Host/offline only,not physical or general-neural accuracy.',constants=21832,nn_exact_cases=0,disabled_exact_cases=0,results={},failures=[],production_source_modified=False)
for name,rs in rows.items():
 data=np.load(D/'fresh_features.npz')if name=='fresh_observed'else cache;x=data['x']if name=='fresh_observed'else data[name+'_x'];base=data['base']if name=='fresh_observed'else data[name+'_base'];context=infer(x,q);bucket=base.argmax(1);threshold=q['thresholds'][bucket];deny=context[:,1]-context[:,0]>=threshold;de=fixed(x,q['repair_weight'],q['repair_bias'])*(bucket==5)[:,None];joint=base.copy();joint[:,:5]+=de;joint[deny,5]=np.maximum(joint[deny,5],joint[deny,:5].max(1)+context[deny,1]-context[deny,0]-threshold[deny]+1)
 on=run('integrated_new',rs);off=run('integrated_new_off',rs)
 for i,(a,b)in enumerate(zip(on,off)):
  assert a['encoder_logits']==base[i].tolist(),(name,i,'encoder')
  assert a['logits']==joint[i].tolist(),(name,i,'joint',a['logits'],joint[i].tolist())
  assert a['context_logits']==context[i,:2].tolist()and a['category_logits']==context[i,2:].tolist(),(name,i,'context')
  assert a['intent_delta']==de[i].tolist(),(name,i,'repair')
  assert a['context_bucket']==bucket[i]and a['context_threshold']==threshold[i]and a['context_deny']==deny[i]and a['context_bucket_source']==0,(name,i,'calibration')
  assert a['repair_used']==int(bucket[i]==5)
  assert b['logits']==base[i].tolist()and b['encoder_logits']==base[i].tolist()and b['context_used']==0 and b['repair_used']==0,(name,i,'disabled')
 report['nn_exact_cases']+=len(rs);report['disabled_exact_cases']+=len(rs);r={};truth=np.array([TOOLS.index(x['intent'])for x in rs]);legal=truth!=5
 for mode in ['full','fast']:
  pred=np.array([x[mode]for x in on]);correct=pred==truth;fa=(~legal)&(pred!=5);fr=legal&(pred==5);wrong=legal&(pred!=truth)&(pred!=5);bounds=all((x[mode]!=1 or 0<=x[mode+'_arg']<=100)and(x[mode]!=4 or(0<=x[mode+'_arg']<=255 if x[mode+'_op']==0 else 0<=x[mode+'_arg']<=7))for x in on)
  r[mode]=dict(correct=int(correct.sum()),n=len(rs),legal_correct=int(correct[legal].sum()),legal_total=int(legal.sum()),false_accept=int(fa.sum()),false_reject=int(fr.sum()),wrong_legal_tool=int(wrong.sum()),all_selected_parameter_bounds_valid=bounds,errors=[dict(text=row['text'],expected=row['intent'],actual=int(a[mode]),status=a[mode+'_status'],argument=a[mode+'_arg'],operation=a[mode+'_op'],context_margin=a['context_logits'][1]-a['context_logits'][0],context_threshold=a['context_threshold'],context_bucket=a['context_bucket'])for row,a,error in zip(rs,on,~correct)if error])
  oldname='fresh'if name=='fresh_observed'else name;prev=oldsystem['results'][oldname][mode];r[mode]['vs_previous_policy_correct_delta']=r[mode]['correct']-prev['correct'];r[mode]['vs_previous_policy_false_accept_delta']=r[mode]['false_accept']-prev['false_accept'];r[mode]['vs_previous_policy_legal_correct_delta']=r[mode]['legal_correct']-prev['legal_correct']
 report['results'][name]=r;print('INTEGRATED',name,{m:{k:v for k,v in z.items()if k!='errors'}for m,z in r.items()},flush=True)
(D/'integrated_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('EXACT',report['nn_exact_cases'],report['disabled_exact_cases'])
