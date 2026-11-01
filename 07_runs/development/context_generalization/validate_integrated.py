from pathlib import Path
import json,subprocess,numpy as np
from veto_train import *
rows={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl'),'observed288':read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl'),'validation':read(D/'data/validation.jsonl')}
cmd=['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'03_sw/model'),str(R/'03_sw/model/byte_tool_model.c'),str(D/'eval_integrated.c')]
for off in [False,True]:subprocess.run(cmd+(['-DNR_MODEL_CONTEXT_ENABLED=0']if off else[])+['-o',str(D/('integrated_off'if off else'integrated'))],check=True)
proof={};total=0
for name,rs in rows.items():
 def run(exe):return[json.loads(x)for x in subprocess.check_output([str(D/exe)],input='\n'.join(x['text']for x in rs)+'\n',text=True).splitlines()]
 expected=run('eval_context');got=run('integrated');off=run('integrated_off');base=infer_base(rs)
 for i,(a,b,c)in enumerate(zip(expected,got,off)):
  for k in ['index','margin','logits','encoder_logits','context_logits','context_deny','context_threshold','context_used']:assert a[k]==b[k],(name,i,k)
  assert c['logits']==base[i].tolist()and c['context_used']==0
  if b['context_deny']:assert b['source']==b['fast_source']==5 and b['selected']==b['fast_selected']==5 and b['status']==b['fast_status']==8
 def acc(predictions,fast):
  corr=fa=fr=0
  for z,g in zip(rs,predictions):
   pre='fast_'if fast and g['fast_handled']else'';status=g[pre+'status'];sel=g[pre+'selected'];want=z['intent'];ok=(status!=0)if want=='reject'else(status==0 and sel==TOOLS.index(want))
   if want=='reject'and status==0:fa+=1
   if want!='reject'and status!=0:fr+=1
   corr+=ok
  return dict(correct=corr,total=len(rs),false_accept=fa,false_reject=fr)
 total+=len(rs);proof[name]={'fast':acc(got,True),'full':acc(got,False)}
# Replay the previously scored heldout failures only: this is observed debugging, not a second blind score.
observed=json.loads((D/'heldout_first_evaluation.json').read_text())
print('heldout keys',list(observed))
controls=[dict(text=t,intent='reject')for t in ['打开温度','开启温度','请帮我将CoreMark结果提高300分。','假如PWM占空比为20%会怎么样？','请解释PWM占空比设置为20%的含义。','怎么理解温度读数？','演示如何编写读取计数器的命令']]
p=subprocess.run([str(D/'integrated')],input='\n'.join(z['text']for z in controls)+'\n',text=True,stdout=subprocess.PIPE,check=True);gs=[json.loads(x)for x in p.stdout.splitlines()];assert all(g['status']!=0 and g['fast_status']!=0 for g in gs)
proof=dict(exact_nn_cases=total,context_disabled_exact_cases=total,admission=proof,targeted_negative_controls=len(controls),production_integrated=True,heldout_rescored=False)
(D/'integration_validation.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
