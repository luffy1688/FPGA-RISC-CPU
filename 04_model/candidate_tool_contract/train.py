#!/usr/bin/env python3
"""Fixed warm-start candidate; user acceptance set is never evaluated here."""
import os,sys,json,time,hashlib,tarfile,io,importlib.util
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[2];DEST=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'04_model/train'))
from byte_model import ByteToolModel,TOOLS,tokenize
SEEDS={
'read_temp':['读出芯片温度','读取器件结温','我想知道芯片有多热','查询温度传感读数','这块板的温度有多高','给我现在的温度','获取器件温度','measure chip temperature','read internal temp'],
'set_led':['点亮LED{k}','打开LED{k}','关闭LED{k}','熄灭LED{k}','把第{ordinal}颗LED打开','把第{ordinal}颗LED关闭','设置LED掩码{led}','LED输出掩码{led}','set led {led}','turn on LED{k}','turn off LED{k}'],
'set_pwm':['把PWM占空比设到{pwm}%','占空比改为{pwm}%','设置PWM输出为{pwm}','PWM输出占空比{pwm}','设定PWM为{pwm}%','set pwm {pwm}','change duty to {pwm}','PWM高电平比例{pwm}%'],
'read_counter':['显示一下计数寄存器','把计数值读给我','现在CPU累计周期是多少','硬件计数值查询','读出周期计数器','查看CPU时钟计数','返回当前计数值','读一下累计计数','read hardware counter'],
'run_coremark':['跑一次CoreMark','执行CoreMark性能评估','请启动CoreMark','测量CoreMark得分','给CPU做CoreMark基准','CoreMark现在开始跑','测试一下CoreMark性能','调用CoreMark计时','run coremark benchmark'],
'reject':['将计数器复位','温度设置为{pwm}度','修改CoreMark分数到{led}','不要点亮LED{k}','不要设置PWM{pwm}','关闭摄像头','更新固件','让芯片降温','设置工作时钟为{led}MHz','请把硬件计数清零','温度维持{pwm}度','reset counter now','set temperature {pwm}','tell me a story','天气如何']
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 torch.set_num_threads(4);torch.manual_seed(103);np.random.seed(103)
 torch.use_deterministic_algorithms(True)
 rng=np.random.RandomState(103)
 data=[json.loads(x) for x in (ROOT/'04_model/datasets/train.jsonl').read_text().splitlines() if x.strip()]
 # These are assistant-authored developmental variations, not new human data.
 generated=[]
 for intent,seeds in SEEDS.items():
  seen=set()
  while len(seen)<200:
   k=int(rng.randint(8));text=seeds[int(rng.randint(len(seeds)))].format(k=k,ordinal='一二三四五六七八'[k],led=int(rng.randint(256)),pwm=int(rng.randint(101)))
   zh=any(ord(c)>127 for c in text)
   before=['','请','麻烦','现在','帮我','我需要'] if zh else ['','please ','now ','could you ']
   after=['','。','吧','，谢谢','一下'] if zh else ['',' please','.',' now']
   text=before[int(rng.randint(len(before)))]+text+after[int(rng.randint(len(after)))]
   if len(text.encode())<=64:seen.add(text)
  generated.extend({'text':text,'intent':intent,'source':'assistant developmental augmentation'} for text in sorted(seen))
 data.extend(generated)
 acceptance={json.loads(x)['text'] for x in (ROOT/'07_runs/eval/user25_second_20261027/frozen_commands.jsonl').read_text().splitlines()}
 assert not any(x['text'] in acceptance for x in data),'Acceptance text leaked into training'
 (DEST/'datasets').mkdir(exist_ok=True)
 path=DEST/'datasets/train.jsonl';path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data))
 protocol={'seed':103,'epochs':24,'batch_size':64,'lr':0.0003,'end_lr':0.00006,'threads':4,'device':'cpu','init_archive':'07_runs/eval/tool_contract_20261027/baseline_sources.tar.gz','architecture':'unchanged d64, 2 layers, 4 heads, INT4/INT8 export','training_examples':len(data),'new_synthetic_examples':1200,'dataset_sha256':sha(path),'acceptance_exact_overlap':0,'checkpoint_selection':'fixed final epoch; no second-user-set predictions during training or selection'}
 (DEST/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
 with tarfile.open(ROOT/protocol['init_archive'],'r:gz')as tar:
  checkpoint=torch.load(io.BytesIO(tar.extractfile('04_model/train/current.pt').read()),map_location='cpu')
 model=ByteToolModel(64);model.load_state_dict(checkpoint['state_dict'])
 tokens,lengths=zip(*(tokenize(row['text']) for row in data))
 tx=torch.tensor(tokens);tl=torch.tensor(lengths);ty=torch.tensor([TOOLS.index(x['intent']) for x in data])
 opt=torch.optim.Adam(model.parameters(),lr=protocol['lr'])
 schedule=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=24,eta_min=protocol['end_lr'])
 history=[];started=time.monotonic()
 for epoch in range(24):
  model.train();order=torch.randperm(len(ty));total=0
  for start in range(0,len(ty),64):
   idx=order[start:start+64];loss=torch.nn.functional.cross_entropy(model(tx[idx],tl[idx]),ty[idx])
   opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step();total+=float(loss.detach())
  schedule.step()
  if epoch%4==0 or epoch==23:
   row={'epoch':epoch+1,'train_loss_sum':total,'elapsed_seconds':time.monotonic()-started};history.append(row);print(json.dumps(row),flush=True)
 model.eval();torch.save({'d_model':64,'state_dict':model.state_dict(),'seed':103,'epochs':24},DEST/'candidate.pt')
 # Reuse the existing INT4 exporter, in an isolated destination.
 src=ROOT/'04_model/candidate_generalization/train_candidate.py'
 spec=importlib.util.spec_from_file_location('exporter',src);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.CANDIDATE=DEST
 (DEST/'export').mkdir(exist_ok=True);(DEST/'c_model').mkdir(exist_ok=True)
 manifest=module.export_candidate(model)
 report={'protocol':protocol,'history':history,'torch':torch.__version__,'elapsed_seconds':time.monotonic()-started,'candidate_only':True,'production_weights_changed':False,'second_acceptance_inferences':0,'deployment':manifest,'checkpoint_sha256':sha(DEST/'candidate.pt')}
 (DEST/'export/training_report.json').write_text(json.dumps(report,indent=2)+'\n')
 print('CANDIDATE_TRAINING_COMPLETE',round(report['elapsed_seconds'],2),flush=True)
if __name__=='__main__':main()
