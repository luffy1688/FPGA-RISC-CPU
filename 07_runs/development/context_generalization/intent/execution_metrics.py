from train_intent import *
import subprocess
keys='index context_bucket context_bucket_source context_threshold context_deny context_used repair_used full full_status full_arg full_op fast fast_status fast_arg fast_op fast_handled'.split()
def run(exe,rows,csv=False):
 p=subprocess.run([str(exe)],input='\n'.join(x['text']for x in rows)+'\n',stdout=subprocess.PIPE,text=True,check=True)
 if not csv:return[json.loads(l)for l in p.stdout.splitlines()]
 return[dict(zip(keys,list(map(int,l.split()))[:16]))for l in p.stdout.splitlines()]
def metric(out,rows,mode,legacy=False):
 if legacy:
  out=[dict(full=x['selected'],full_status=x['status'],full_arg=x['argument'],full_op=x['operation'],fast=x['fast_selected']if x['fast_handled']else x['selected'],fast_status=x['fast_status']if x['fast_handled']else x['status'],fast_arg=x['fast_argument']if x['fast_handled']else x['argument'],fast_op=x['fast_operation']if x['fast_handled']else x['operation'])for x in out]
 candidate=np.array([x[mode]for x in out]);status=np.array([x[mode+'_status']for x in out]);pred=np.where(status==0,candidate,5);truth=np.array([TOOLS.index(x['intent'])for x in rows]);legal=truth!=5;correct=pred==truth;fa=(~legal)&(pred!=5);fr=legal&(pred==5)
 return dict(n=len(rows),correct=int(correct.sum()),legal_correct=int(correct[legal].sum()),legal_total=int(legal.sum()),false_execution_admission=int(fa.sum()),legal_over_refusal=int(fr.sum()),wrong_legal_tool=int(((pred!=truth)&(pred!=5)&legal).sum()),nonreject_tool_with_error_status=int(((candidate!=5)&(status!=0)).sum()),errors=[dict(text=row['text'],expected=row['intent'],effective_tool=int(v),candidate_tool=int(x[mode]),status=x[mode+'_status'],argument=x[mode+'_arg'],operation=x[mode+'_op'])for row,x,v,bad in zip(rows,out,pred,~correct)if bad])
sets={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'fresh_observed':read(P/'context_v2/data/fresh.jsonl')}
p=D/'integrated_validation.json';report=json.loads(p.read_text());execution={}
for name,rows in sets.items():
 out=run(D/'integrated_new',rows,True);execution[name]={mode:metric(out,rows,mode)for mode in ['full','fast']};print('EXECUTION',name,{m:{k:v for k,v in x.items()if k!='errors'}for m,x in execution[name].items()},flush=True)
report['selected_tool_only_metrics_scope']='Existing results count selected tool even if status was nonzero; retained as routing diagnostic only. Use execution_admission_results for actual eligible-action statistics.';report['execution_admission_results']=execution
report['previous_policy_execution_admission']={}
for name in ['validation','fresh_observed']:
 out=run(D/'system_combined',sets[name]);report['previous_policy_execution_admission'][name]={m:metric(out,sets[name],m)for m in ['full','fast']}
out=run(P/'integrated',sets['fresh_observed']);report['previous_accepted_system_same_fresh_execution_admission']={m:metric(out,sets['fresh_observed'],m,True)for m in ['full','fast']}
report['execution_metric_definition']='Only status=NR_TOOL_OK(0) and nonreject candidate is executable admission. Nonzero status is effective reject regardless selected-tool metadata. This is host admission,not physical sideeffect measurement.'
p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('BASELINE_EXEC',json.dumps({m:{k:v for k,v in x.items()if k!='errors'}for m,x in report['previous_accepted_system_same_fresh_execution_admission'].items()}))
