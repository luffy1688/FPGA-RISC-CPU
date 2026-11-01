import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
import sys,json,time,subprocess,importlib.util,copy,collections
import numpy as np
import torch
import torch.nn.functional as F
R=Path('/work/LUO/NeedleRV-X');D=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'04_model/train'))
from byte_model import ByteToolModel,TOOLS,tokenize
torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
DEVICE=torch.device('cuda:0'if torch.cuda.is_available()else'cpu')
if DEVICE.type=='cuda':torch.cuda.set_per_process_memory_fraction(.12,0)
def read(p):return [json.loads(x)for x in p.read_text().splitlines()if x]
base=read(R/'04_model/candidate_tool_contract/datasets/train.jsonl');novel=read(D/'semantic_train.jsonl')
devs={'original80':read(R/'04_model/datasets/template_development.jsonl'),'aug192':read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl')}
for n in ['export','c_model']:(D/n).mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('exporter',R/'04_model/candidate_generalization/train_candidate.py');exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter);exporter.CANDIDATE=D
(D/'eval.c').write_text((R/'07_runs/development/nlu_candidate/eval.c').read_text())
def compile_c(candidate):
 exe=D/('candidate_eval'if candidate else'baseline_eval')
 cmd=['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'03_sw/model')]
 if candidate:cmd+=['-DNR_MODEL_DATA_HEADER="'+str(D/'c_model/byte_model_data.h')+'"']
 cmd+=[str(R/'03_sw/model/byte_tool_model.c'),str(D/'eval.c'),'-o',str(exe)]
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);assert p.returncode==0,p.stdout
 return exe
def evaluate(exe,rows):
 p=subprocess.run([str(exe)],input='\n'.join(x['text']for x in rows)+'\n',text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
 pred=[json.loads(x)for x in p.stdout.splitlines()];assert len(pred)==len(rows)
 cm=[[0]*6 for _ in range(6)];bad=[]
 for x,y in zip(rows,pred):
  t=TOOLS.index(x['intent']);assert'error'not in y;cm[t][y['index']]+=1
  if t!=y['index']:bad.append({'text':x['text'],'expected':x['intent'],'raw':TOOLS[y['index']],'logits':y['logits'],'margin':y['margin'],'decoder_status':y['status'],'decoder_source':y['source']})
 neg=[y for x,y in zip(rows,pred)if x['intent']=='reject']
 return {'examples':len(rows),'raw_correct':sum(cm[k][k]for k in range(6)),'raw_by_class':{TOOLS[k]:{'correct':cm[k][k],'total':sum(cm[k])}for k in range(6)},'raw_reject_false_accepts':sum(y['index']!=5 for y in neg),'decoder_reject_accepts':sum(y['status']==0 for y in neg),'raw_legitimate_false_rejects':sum(cm[k][5]for k in range(5)),'confusion':cm,'errors':bad,'predictions':pred}
def compact(ev):return{k:{n:v[n]for n in ['examples','raw_correct','raw_by_class','raw_reject_false_accepts','decoder_reject_accepts','raw_legitimate_false_rejects']}for k,v in ev.items()}
def tensor(rows):
 x,l=zip(*(tokenize(z['text'])for z in rows));return torch.tensor(x,device=DEVICE),torch.tensor(l,device=DEVICE),torch.tensor([TOOLS.index(z['intent'])for z in rows],device=DEVICE)
initial=torch.load(R/'04_model/train/current.pt',map_location='cpu',weights_only=False)['state_dict']
def model():
 m=ByteToolModel(64).to(DEVICE);m.load_state_dict(initial);return m
bx,bl,by=tensor(base);nx,nl,ny=tensor(novel);teacher=model().eval()
with torch.no_grad():targets=torch.cat([teacher(bx[i:i+64],bl[i:i+64])for i in range(0,len(base),64)])
del teacher
base_ix=[torch.where(by==k)[0]for k in range(6)]
# Equal intent sampling; reject examples additionally balanced by semantic stratum.
novel_ix=[[torch.tensor([i for i,x in enumerate(novel)if x['intent']==label and (label!='reject'or x['stratum']==s)],device=DEVICE)for s in (sorted({x['stratum']for x in novel if x['intent']=='reject'})if label=='reject'else['all'])]for label in TOOLS]
base_exe=compile_c(False);baseline={k:evaluate(base_exe,v)for k,v in devs.items()};print('BASELINE',json.dumps(compact(baseline)),flush=True)
profiles=[{'name':'last_block_balanced','seed':10291,'lr':8e-5,'novel_weight':.70,'distill':.5,'trainable':'blocks.1/head','epochs':12},{'name':'full_conservative','seed':10292,'lr':4e-5,'novel_weight':.70,'distill':1.,'trainable':'all','epochs':12},{'name':'full_replay','seed':10293,'lr':1e-4,'novel_weight':.50,'distill':1.,'trainable':'all','epochs':12}]
def passed(ev):
 a=ev['original80'];b=ev['aug192'];old=baseline['aug192']
 return a['raw_correct']>=73 and b['raw_correct']>=max(129,old['raw_correct']+11) and b['raw_by_class']['set_pwm']['correct']>old['raw_by_class']['set_pwm']['correct'] and b['raw_by_class']['reject']['correct']>old['raw_by_class']['reject']['correct'] and a['raw_reject_false_accepts']<=baseline['original80']['raw_reject_false_accepts'] and b['raw_reject_false_accepts']<=old['raw_reject_false_accepts'] and a['decoder_reject_accepts']==b['decoder_reject_accepts']==0
summaries=[];best=None;beststate=None;start=time.monotonic()
for profile in profiles:
 torch.manual_seed(profile['seed']);np.random.seed(profile['seed']);m=model()
 for name,p in m.named_parameters():p.requires_grad_(profile['trainable']=='all'or name.startswith('head.')or(profile['trainable']=='blocks.1/head'and name.startswith('blocks.1.')))
 params=[p for p in m.parameters()if p.requires_grad];opt=torch.optim.Adam(params,lr=profile['lr']);hist=[]
 for epoch in range(1,profile['epochs']+1):
  m.train();losses=[0.,0.,0.]
  for step in range(49):
   bi=torch.cat([ix[torch.randint(len(ix),(8,),device=DEVICE)]for ix in base_ix]);parts=[]
   for groups in novel_ix:
    for j in range(8):
     ix=groups[(epoch*49+step*8+j)%len(groups)];parts.append(ix[torch.randint(len(ix),(1,),device=DEVICE)])
   ni=torch.cat(parts);z=m(bx[bi],bl[bi]);zn=m(nx[ni],nl[ni]);lb=F.cross_entropy(z,by[bi]);ln=F.cross_entropy(zn,ny[ni]);kd=F.kl_div(F.log_softmax(z/2,dim=-1),F.softmax(targets[bi]/2,dim=-1),reduction='batchmean')*4
   loss=lb+profile['novel_weight']*ln+profile['distill']*kd;opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(params,1.);opt.step()
   for j,l in enumerate([lb,ln,kd]):losses[j]+=float(l.detach())
  entry={'epoch':epoch,'base_ce':losses[0]/49,'novel_ce':losses[1]/49,'teacher_kl':losses[2]/49};hist.append(entry)
  if epoch in [4,8,12]:
   m.eval();deployment=exporter.export_candidate(m);assert deployment['total_model_bytes']==47066;exe=compile_c(True);ev={k:evaluate(exe,v)for k,v in devs.items()};gate=passed(ev)
   summary={'profile':profile,'epoch':epoch,'history':copy.deepcopy(hist),'selection_gate':gate,'metrics':compact(ev)};summaries.append(summary);print('CANDIDATE',json.dumps(summary),flush=True)
   key=(int(gate),int(ev['original80']['raw_correct']>=73),int(ev['aug192']['raw_reject_false_accepts']<=baseline['aug192']['raw_reject_false_accepts']),ev['aug192']['raw_correct'],ev['original80']['raw_correct'],-ev['aug192']['raw_reject_false_accepts'])
   if best is None or key>best['key']:best={'key':key,'profile':profile,'epoch':epoch,'gate':gate,'evaluation':ev};beststate={k:v.detach().cpu().clone()for k,v in m.state_dict().items()}
   # Update one report in place; no checkpoint pile.
   report={'candidate_only':True,'production_weights_changed':False,'data':json.loads((D/'protocol.json').read_text()),'baseline':baseline,'candidates':summaries,'selected_profile':best['profile'],'selected_epoch':best['epoch'],'selection_gate':best['gate'],'selected':best['evaluation'],'seconds':time.monotonic()-start,'complete':False,'device':str(DEVICE)}
   (D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 del m,opt
m=model();m.load_state_dict(beststate);m.eval();deployment=exporter.export_candidate(m);exe=compile_c(True)
torch.save({'d_model':64,'state_dict':beststate,'candidate_only':True,'profile':best['profile'],'epochs':best['epoch']},D/'best.pt')
# Diagnostic is accessed for inference only once after development selection is frozen.
diag=read(D/'semantic_diagnostic.jsonl');diagnostic=evaluate(exe,diag);diagnostic_baseline=evaluate(base_exe,diag)
strata={}
for row,pred,bpred in zip(diag,diagnostic['predictions'],diagnostic_baseline['predictions']):
 s=row['stratum'];a=strata.setdefault(s,{'examples':0,'candidate_raw_correct':0,'baseline_raw_correct':0,'candidate_decoder_reject_accepts':0});a['examples']+=1;a['candidate_raw_correct']+=pred['index']==TOOLS.index(row['intent']);a['baseline_raw_correct']+=bpred['index']==TOOLS.index(row['intent']);a['candidate_decoder_reject_accepts']+=(row['intent']=='reject'and pred['status']==0)
# Exact integer Python/C check over original80, separate from QAT forward approximation.
spec=importlib.util.spec_from_file_location('fixed',R/'04_model/golden/fixed_reference.py');fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed);fm=fixed.FixedModel(D/'export/candidate_int4.npz');alignment=[]
for row,pred in zip(devs['original80'],best['evaluation']['original80']['predictions']):
 q=fm.infer(row['text']);assert q['logits']==pred['logits'],(row['text'],q,pred);alignment.append(row['text'])
report.update({'complete':True,'selected_diagnostic':diagnostic,'baseline_diagnostic':diagnostic_baseline,'diagnostic_strata':strata,'python_c_exact_logits_checked':len(alignment),'deployment':deployment,'seconds':time.monotonic()-start,'adopt_recommendation':bool(best['gate']),'pending':'Root must complete candidate RTL/firmware numerical and observed regression before deployment. No production file modified.','diagnosis':'Existing six labels miss action/context distinctions; novel data use hard negative speech-act families and separate tool/argument/operation metadata. Counts balanced during sampling; reject strata sampled evenly. Prefix and numeric variants are not claimed independent tests.'})
(D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('COMPLETE',json.dumps({'profile':best['profile']['name'],'epoch':best['epoch'],'selection_gate':best['gate'],'selected':compact(best['evaluation']),'diagnostic':{'candidate':diagnostic['raw_correct'],'baseline':diagnostic_baseline['raw_correct'],'examples':len(diag),'strata':strata},'python_c_alignment':len(alignment),'seconds':report['seconds']}),flush=True)
