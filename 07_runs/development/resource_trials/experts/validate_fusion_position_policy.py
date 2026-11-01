from pathlib import Path
D=Path(__file__).resolve().parent
exec((D/'train_fusion_position.py').read_text().split('trainy=')[0])
import subprocess
q=np.load(D/'fusion_position_selected.npz');rec=json.loads((D/'fusion_position_report.json').read_text())['selected']
keys='index context_bucket context_bucket_source context_threshold context_deny context_used repair_used full full_status full_arg full_op fast fast_status fast_arg fast_op fast_handled'.split()
def run(rs):
 p=subprocess.run([str(D/'fusion_position_policy')],input='\n'.join(r['text']for r in rs)+'\n',stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=240)
 if p.returncode:raise RuntimeError((p.returncode,p.stderr[-600:],p.stdout[-200:]))
 out=[]
 for line in p.stdout.splitlines():
  a=list(map(int,line.split()));assert len(a)==49,(len(a),line);x=dict(zip(keys,a[:16]));x['joint']=a[16:22];x['encoder']=a[22:28];x['head16']=a[28:44];x['fusion_delta']=a[44:49];out.append(x)
 assert len(out)==len(rs);return out
baseline=json.loads((P/'capacity/integrated_revision2.json').read_text())['policy_fix_before_after']['after_results']
report=dict(scope='Privatehost integration of actualposition2048x64+Cfusion with currentproductionpermission decoder/fast path andcandidatecalibration. EveryrequestencoderisactualimmutableCencoder;production64contextheadisnotcalled. fast1handledpaths do not usefusion;fastMISSfallsbacktofullcandidate. Allsetsobservedregression,notheldout;NNscoreexact is separatefromsystemtoolparameters.',weights_changed=False,system={},nn_exact=0)
# Controls first,so a default-demo regression is known before the long replay.
spec=json.loads((R/'07_runs/board/baseline/acceptance_cases.json').read_text());rs=[c for c in spec['cases']if c.get('group')=='fourth'];a=run(rs);cases=[]
for c,v in zip(rs,a):
 h=c['expected'];checks={}
 for m in ['full','fast']:
  ok=v[m+'_status']!=0 if h['status']else v[m+'_status']==0 and v[m]==h['final_index']and v[m+'_arg']==h['argument']and v[m+'_op']==h['operation'];checks[m]=dict(passed=bool(ok),tool=v[m],status=v[m+'_status'],argument=v[m+'_arg'],operation=v[m+'_op'])
 cases.append(dict(id=c['id'],text=c['text'],**checks))
report['fourth25']=cases;print('FUSION_POLICY_FOURTH',{m:sum(c[m]['passed']for c in cases)for m in ['full','fast']},flush=True)
rs=json.loads((R/'07_runs/development/semantic_capacity/physical_context_cases.json').read_text());assert len(rs)==40;a=run(rs);report['guard40']=[dict(text=c['text'],full_refused=v['full_status']!=0,fast_refused=v['fast_status']!=0)for c,v in zip(rs,a)];print('FUSION_POLICY_GUARD40',{m:sum(c[m+'_refused']for c in report['guard40'])for m in ['full','fast']},flush=True)
rs=[dict(text='只关闭LED0，其他LED不要改变。',tool=4,arg=0,op=2),dict(text='只点亮LED0，不要改其他位。',tool=4,arg=0,op=1),dict(text='不必阐释，马上读取芯片温度',tool=0,arg=0,op=0),dict(text='PWM按20%占空比输出',tool=1,arg=20,op=0)];a=run(rs);report['positive4']=[dict(text=c['text'],**{m:dict(passed=v[m+'_status']==0 and v[m]==c['tool']and v[m+'_arg']==c['arg']and v[m+'_op']==c['op'],tool=v[m],status=v[m+'_status'],argument=v[m+'_arg'],operation=v[m+'_op'])for m in ['full','fast']})for c,v in zip(rs,a)];print('FUSION_POLICY_POSITIVE',{m:sum(c[m]['passed']for c in report['positive4'])for m in ['full','fast']},flush=True)
for n in names:
 rs=rows[n];a=run(rs);fs=feature(n,rec['encoder_scale_divisor']);expect=apply(n,fs,q,rec['alpha_quarters'],rec['margin_gate']);delta=rounding(fs.astype(np.int32)@q['fusion_w'].astype(np.int32).T)+q['fusion_b']
 for i,v in enumerate(a):
  assert v['encoder']==base[n][i].tolist(),('encoder',n,i)
  assert v['head16']==heads[n][i].tolist(),('candidatehead',n,i,v['head16'],heads[n][i].tolist())
  assert v['joint']==expect[i].tolist(),('fusionjoint',n,i)
  assert v['fusion_delta']==delta[i].tolist(),('fusiondelta',n,i)
  assert v['context_bucket']==route[n][i]and v['context_threshold']==q64['thresholds'][route[n][i]]
 report['nn_exact']+=len(rs);truth=np.array([TOOLS.index(c['intent'])for c in rs]);legal=truth!=5;result={}
 for m in ['full','fast']:
  actual=np.array([v[m]if v[m+'_status']==0 else 5 for v in a]);correct=actual==truth;bounds=all(v[m+'_status']!=0 or(v[m]!=1 or 0<=v[m+'_arg']<=100)and(v[m]!=4 or(0<=v[m+'_arg']<=255 if v[m+'_op']==0 else 0<=v[m+'_arg']<=7))for v in a)
  result[m]=dict(n=len(rs),correct=int(correct.sum()),legal_correct=int(correct[legal].sum()),legal_total=int(legal.sum()),false_execution_admission=int(((actual!=5)&~legal).sum()),legal_over_refusal=int(((actual==5)&legal).sum()),wrong_legal_tool=int(((actual!=truth)&(actual!=5)&legal).sum()),all_parameter_bounds_valid=bounds,errors=[dict(text=c['text'],expected=c['intent'],actual=v[m],status=v[m+'_status'],argument=v[m+'_arg'],operation=v[m+'_op'],fast_handled=v['fast_handled'])for c,v,ok in zip(rs,a,correct)if not ok])
  bname='internal_audit_observed'if n=='observed900'else n;b=baseline[bname][m];result[m]['previous64_system_correct']=b['correct'];result[m]['correct_delta']=result[m]['correct']-b['correct'];result[m]['false_execution_delta']=result[m]['false_execution_admission']-b['false_execution_admission']
 report['system'][n]=result;print('FUSION_POLICY_SYSTEM',n,{m:{k:v for k,v in r.items()if k!='errors'}for m,r in result.items()},flush=True)
(D/'fusion_position_policy_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('FUSION_POLICY_COMPLETE',report['nn_exact'],flush=True)
