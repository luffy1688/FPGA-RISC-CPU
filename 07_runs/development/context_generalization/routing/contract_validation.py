from pathlib import Path
import json,subprocess,sys
R=Path('/work/LUO/NeedleRV-X');D=R/'07_runs/development/context_generalization';O=D/'routing'
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'03_sw/model'),str(R/'03_sw/model/byte_tool_model.c'),str(D/'eval_integrated.c'),'-o',str(O/'policy_check')],check=True)
sets={'original80':R/'04_model/datasets/template_development.jsonl','aug192':R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl','observed288':R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl','old_validation541':D/'data/validation.jsonl'}
TOOL=['read_temp','set_pwm','run_coremark','read_counter','set_led','reject'];report={}
for name,path in sets.items():
 rows=[json.loads(l)for l in path.read_text().splitlines()if l.strip()]
 pred=[json.loads(l)for l in subprocess.check_output([str(O/'policy_check')],input='\n'.join(z['text']for z in rows)+'\n',text=True).splitlines()]
 stats={}
 for mode in ['full','fast']:
  correct=fa=fr=0
  for z,g in zip(rows,pred):
   pre='fast_'if mode=='fast'and g['fast_handled']else'';sel=g[pre+'selected'];status=g[pre+'status'];w=TOOL.index(z['intent'])
   correct+=int(status!=0 if w==5 else status==0 and sel==w);fa+=int(w==5 and status==0);fr+=int(w!=5 and status!=0)
  stats[mode]=dict(correct=correct,total=len(rows),false_accept=fa,false_reject=fr)
 report[name]=stats
(O/'current_contract_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
