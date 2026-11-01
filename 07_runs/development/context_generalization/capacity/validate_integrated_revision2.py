from pathlib import Path
import sys,json,subprocess,collections
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'context_v2'))
from train import read,TOOLS,metrics
from train_mlp import infer
from veto_train import fixed
import numpy as np
keys='index context_bucket context_bucket_source context_threshold context_deny context_used repair_used full full_status full_arg full_op fast fast_status fast_arg fast_op fast_handled'.split()
def run(exe,rs):
 p=subprocess.run([str(D/exe)],input='\n'.join(r['text']for r in rs)+'\n',stdout=subprocess.PIPE,text=True,check=True);out=[]
 for line in p.stdout.splitlines():
  a=list(map(int,line.split()));assert len(a)==55,(len(a),line);x=dict(zip(keys,a[:16]));at=16
  for k,n in [('logits',6),('encoder',6),('context',2),('category',9),('oldrepair',5),('tool_logits',5),('cascade',5)]:x[k]=a[at:at+n];at+=n
  x['cascade_used']=a[at];out.append(x)
 assert len(out)==len(rs);return out
rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'observed1138':read(P/'context_v2/data/fresh.jsonl'),'internal_audit_observed':read(D/'internal_audit.jsonl')};cache=np.load(P/'context_v2/features.npz');fc=np.load(P/'intent/fresh_features.npz');ac=np.load(D/'audit_features.npz');q=np.load(D/'deployment_revision2.npz');report=dict(scope='Necessary host integrated capacity64 deployment calibration revision2 validation; old1138 and new900 are observed replay here. First evaluations remain unchanged. No weights/threshold adjustment. Exacttoolparameter accuracy claimed only Fourth25 and explicit positive controls,syntheticallsets evaluate intent/admission and bounds.',nn_exact_cases=0,disabled_exact_cases=0,results={})
for name,rs in rows.items():
 if name=='observed1138':x=fc['x'];base=fc['base']
 elif name=='internal_audit_observed':x=ac['x'];base=ac['base']
 else:x=cache[name+'_x'];base=cache[name+'_base']
 ct=infer(x,q);bucket=base.argmax(1);oldde=fixed(x,q['oldrepair_weight'],q['oldrepair_bias'])*(bucket==5)[:,None];z=base.copy();z[:,:5]+=oldde;used=z.argmax(1)==5;newde=ct[:,11:16]*used[:,None];z[:,:5]+=newde;th=q['thresholds'][bucket];diff=ct[:,1]-ct[:,0];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1)
 on=run('integrated_new',rs);off=run('integrated_new_off',rs)
 for i,(a,b)in enumerate(zip(on,off)):
  assert a['encoder']==base[i].tolist(),(name,i,'encoder');assert a['logits']==z[i].tolist(),(name,i,'joint',a['logits'],z[i].tolist());assert a['context']==ct[i,:2].tolist()and a['category']==ct[i,2:11].tolist()and a['tool_logits']==ct[i,11:16].tolist(),(name,i,'head16');assert a['oldrepair']==oldde[i].tolist()and a['cascade']==newde[i].tolist()and a['cascade_used']==used[i],(name,i,'cascade');assert a['context_bucket']==bucket[i]and a['context_threshold']==th[i]and a['context_deny']==deny[i]and a['context_bucket_source']==0,(name,i,'calibration');assert b['logits']==base[i].tolist()and b['encoder']==base[i].tolist()and b['context_used']==0 and b['repair_used']==0 and b['cascade_used']==0,(name,i,'disabled')
 report['nn_exact_cases']+=len(rs);report['disabled_exact_cases']+=len(rs);truth=np.array([TOOLS.index(r['intent'])for r in rs]);legal=truth!=5;result={}
 for mode in ['full','fast']:
  candidate=np.array([a[mode]for a in on]);status=np.array([a[mode+'_status']for a in on]);pred=np.where(status==0,candidate,5);correct=pred==truth;fa=(pred!=5)&~legal;fr=(pred==5)&legal;bounds=all(a[mode+'_status']!=0 or(a[mode]!=1 or 0<=a[mode+'_arg']<=100)and(a[mode]!=4 or(0<=a[mode+'_arg']<=255 if a[mode+'_op']==0 else 0<=a[mode+'_arg']<=7))for a in on)
  result[mode]=dict(n=len(rs),correct=int(correct.sum()),legal_correct=int(correct[legal].sum()),legal_total=int(legal.sum()),false_execution_admission=int(fa.sum()),legal_over_refusal=int(fr.sum()),wrong_legal_tool=int(((pred!=truth)&(pred!=5)&legal).sum()),all_parameter_bounds_valid=bounds,errors=[dict(text=r['text'],expected=r['intent'],context=r.get('context'),effective_tool=int(v),candidate=a[mode],status=a[mode+'_status'],argument=a[mode+'_arg'],operation=a[mode+'_op'])for r,a,v,error in zip(rs,on,pred,~correct)if error])
 report['results'][name]=result;print('CAPACITY_INTEGRATED',name,{m:{k:v for k,v in z.items()if k!='errors'}for m,z in result.items()},flush=True)
spec=json.loads((R/'07_runs/board/baseline/acceptance_cases.json').read_text());rs=[c for c in spec['cases']if c.get('group')=='fourth'];on=run('integrated_new',rs);fourth=[]
for c,a in zip(rs,on):
 h=c['expected'];passed=a['fast_status']!=0 if h['status']else a['fast_status']==0 and a['fast']==h['final_index']and a['fast_arg']==h['argument']and a['fast_op']==h['operation'];fourth.append(dict(id=c['id'],passed=bool(passed)))
report['fourth25_tool_arg_operation']=fourth;report['fourth25_passed']=all(c['passed']for c in fourth);print('FOURTH',json.dumps(fourth),flush=True)
path=R/'07_runs/development/semantic_branch/physical_context_cases.json';spec=json.loads(path.read_text());rs=spec if isinstance(spec,list)else spec['cases'];assert len(rs)==35;on=run('integrated_new',rs);guards=[dict(text=c['text'],full_status=a['full_status'],fast_status=a['fast_status'],full_refused=a['full_status']!=0,fast_refused=a['fast_status']!=0)for c,a in zip(rs,on)];report['physical35_guard_host']=guards
rs=[dict(text='只关闭LED0，其他LED不要改变。',tool=4,arg=0,op=2),dict(text='只点亮LED0，不要改其他位。',tool=4,arg=0,op=1),dict(text='不必阐释，马上读取芯片温度',tool=0,arg=0,op=0),dict(text='PWM按20%占空比输出',tool=1,arg=20,op=0)];on=run('integrated_new',rs);controls=[]
for c,a in zip(rs,on):controls.append(dict(text=c['text'],**{m:dict(passed=a[m+'_status']==0 and a[m]==c['tool']and a[m+'_arg']==c['arg']and a[m+'_op']==c['op'],tool=a[m],status=a[m+'_status'],arg=a[m+'_arg'],op=a[m+'_op'])for m in ['full','fast']}))
report['bounded_positive_controls']=controls;report['weights_changed']=False;report['thresholds_changed']=False;report['first_evaluations_modified']=False;(D/'integrated_revision2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('EXACT',report['nn_exact_cases'],'GUARDS',sum(a['full_refused']for a in guards),sum(a['fast_refused']for a in guards),'POSITIVE',json.dumps(controls,ensure_ascii=True))
