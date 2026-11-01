from pathlib import Path
import sys,json,subprocess
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));from train import read,TOOLS
import numpy as np
keys='index context_bucket context_bucket_source context_threshold context_deny context_used repair_used full full_status full_arg full_op fast fast_status fast_arg fast_op fast_handled'.split()
def run(rows,counter):
 p=subprocess.run([str(D/'revision2_eval'),str(counter)],input='\n'.join(x['text']for x in rows)+'\n',stdout=subprocess.PIPE,text=True,check=True);out=[dict(zip(keys,list(map(int,l.split()))[:16]))for l in p.stdout.splitlines()];assert len(out)==len(rows);return out
r=json.loads((D/'calibration_revision2.json').read_text());spec=json.loads((R/'07_runs/board/baseline/acceptance_cases.json').read_text());fourth=[c for c in spec['cases']if c.get('group')=='fourth'];guards=json.loads((R/'07_runs/development/semantic_branch/physical_context_cases.json').read_text());guards=guards if isinstance(guards,list)else guards['cases']
for rec in r['candidates']:
 threshold=rec['counter_threshold'];out=run(fourth,threshold);cases=[]
 for c,a in zip(fourth,out):
  h=c['expected'];passed=a['fast_status']!=0 if h['status']else a['fast_status']==0 and a['fast']==h['final_index']and a['fast_arg']==h['argument']and a['fast_op']==h['operation'];cases.append(dict(id=c['id'],passed=bool(passed),fallback=a['fast_handled']==0,status=a['fast_status']))
 out=run(guards,threshold);rec['host_fourth25']=cases;rec['host_guard35']={m:sum(a[m+'_status']!=0 for a in out)for m in ['full','fast']};print('HOST_CONTROL',threshold,'fourth',sum(c['passed']for c in cases),'guards',rec['host_guard35'],flush=True)
selected=next(a for a in r['candidates']if a['raw_old16_gate_passed']and all(x['passed']for x in a['host_fourth25'])and a['host_guard35']['fast']==35);r['recommended_counter_threshold']=selected['counter_threshold'];r['private_fast_fallback']='When fast hint-based context denial has margin<maximum class threshold,returnMISS and run unchanged fullencoder class decision. Margin>=maxthreshold alwaysdeny.';r['production_modified']=False;r['system_regression']={}
sets={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'old_validation':read(P/'data/validation.jsonl'),'validation':read(P/'context_v2/data/validation.jsonl'),'observed1138':read(P/'context_v2/data/fresh.jsonl'),'internal_audit_observed':read(D/'internal_audit.jsonl')}
for name,rows in sets.items():
 out=run(rows,selected['counter_threshold']);truth=np.array([TOOLS.index(x['intent'])for x in rows]);legal=truth!=5;d={}
 for mode in ['full','fast']:
  pred=np.array([a[mode]if a[mode+'_status']==0 else 5 for a in out]);correct=pred==truth;d[mode]=dict(correct=int(correct.sum()),n=len(rows),legal_correct=int(correct[legal].sum()),legal_total=int(legal.sum()),false_execution_admission=int(((pred!=5)&~legal).sum()),legal_over_refusal=int(((pred==5)&legal).sum()),wrong_legal_tool=int(((pred!=truth)&(pred!=5)&legal).sum()),errors=[dict(text=c['text'],expected=c['intent'],actual=int(a[mode]),status=a[mode+'_status'],argument=a[mode+'_arg'],operation=a[mode+'_op'])for c,a,error in zip(rows,out,~correct)if error])
 d['fullencoder_fallback_count']=sum(a['fast_handled']==0 for a in out);r['system_regression'][name]=d;print('REV2_SYSTEM',name,{m:{k:v for k,v in z.items()if k!='errors'}if isinstance(z,dict)else z for m,z in d.items()},flush=True)
(D/'calibration_revision2.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
