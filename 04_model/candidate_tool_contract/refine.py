#!/usr/bin/env python3
"""Post-observation numeral robustness refinement; never claim a new blind test."""
from pathlib import Path
import json,sys,time,hashlib,tarfile,io,importlib.util
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).resolve().parent;DEST=BASE/'refinement'
sys.path.insert(0,str(ROOT/'04_model/train'))
from byte_model import ByteToolModel,TOOLS,tokenize
def cn(n):
 d='零一二三四五六七八九'
 if n<10:return d[n]
 if n==100:return'一百'
 return (d[n//10]if n>=20 else'')+'十'+(d[n%10]if n%10 else'')
SEEDS={
'read_temp':['读一个片内温度值','查验温度采集值','报告器件结温读数','当前温度传感结果','测一测FPGA摄氏温度','芯片的结温读一下'],
'set_pwm':['PWM高电平比例为{t}成','设置PWM到百分之{c}','让PWM输出保持{t}成占比','PWM工作时以{t}成作为高电平','PWM占空比取百分之{c}','将PWM高电平的比例改为{t}成','PWM占空比设置{p}%'],
'set_led':['把LED掩码写入{h}','LED整组输出设为{h}','第{ordinal}盏LED开启','LED{k}熄灭','将LED掩码改为{n}','开启LED{k}'],
'read_counter':['我需要时钟计数读数','计数寄存器读一下','显示当前计数值','返回硬件计数器的数','读取CPU累计周期','查验周期计数器'],
'run_coremark':['请实际测量CoreMark得分','执行一次CoreMark评测','CPU做CoreMark基准','CoreMark性能现在测试','运行CoreMark并返回周期','CoreMark实测结果'],
'reject':['设定结温至{c}摄氏度','将温度锁定在{p}度','清空硬件周期数','将计数值重新设置{n}','请替换芯片程序','开始播放电影','set pwm {p} and read temp','不运行CoreMark却修改成绩','取消LED{k}点亮']
}
def main():
 torch.set_num_threads(4);torch.manual_seed(109);np.random.seed(109);torch.use_deterministic_algorithms(True)
 DEST.mkdir(exist_ok=True);(DEST/'datasets').mkdir(exist_ok=True)
 rows=[json.loads(x)for x in (BASE/'datasets/train.jsonl').read_text().splitlines()if x];rng=np.random.RandomState(109)
 for intent,seeds in SEEDS.items():
  seen=set();attempts=0
  while len(seen)<160:
   attempts+=1;assert attempts<40000,('augmentation exhaustion',intent)
   k=int(rng.randint(8));p=int(rng.randint(101));n=int(rng.randint(256));t=int(rng.randint(11))
   text=seeds[int(rng.randint(len(seeds)))].format(k=k,ordinal='一二三四五六七八'[k],p=p,n=n,h=hex(n),t=cn(t),c=cn(p))
   text=['','请','现在','麻烦','帮我'][int(rng.randint(5))]+text+['','。','吧','一下','，谢谢','一下吧'][int(rng.randint(6))]
   if len(text.encode())<=64:seen.add(text)
  rows.extend({'text':x,'intent':intent,'source':'assistant-authored general numeral/proportion augmentation; second set now observed, exact texts excluded'}for x in sorted(seen))
 accepted={json.loads(x)['text']for x in (ROOT/'07_runs/eval/user25_second_20261027/frozen_commands.jsonl').read_text().splitlines()}
 assert not any(x['text']in accepted for x in rows)
 data=DEST/'datasets/train.jsonl';data.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in rows))
 plan={'seed':109,'epochs':12,'lr':0.0002,'end_lr':0.00004,'batch':64,'threads':4,'device':'cpu','examples':len(rows),'dataset_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),'initialization_archive':'07_runs/eval/tool_contract_20261027/first_release_sources.tar.gz','purpose':'Post-observation developmental refinement; user second set is now observed; not new independent accuracy.','second_user_exact_train_overlap':0,'checkpoint_selection':'fixed final epoch 12'}
 (DEST/'protocol.json').write_text(json.dumps(plan,indent=2)+'\n')
 with tarfile.open(ROOT/plan['initialization_archive'],'r:gz')as tar:prior=torch.load(io.BytesIO(tar.extractfile('04_model/train/current.pt').read()),map_location='cpu')
 model=ByteToolModel(64);model.load_state_dict(prior['state_dict'])
 tx,tl=zip(*(tokenize(x['text'])for x in rows));tx=torch.tensor(tx);tl=torch.tensor(tl);ty=torch.tensor([TOOLS.index(x['intent'])for x in rows])
 opt=torch.optim.Adam(model.parameters(),lr=plan['lr']);schedule=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=12,eta_min=plan['end_lr'])
 history=[];start=time.monotonic()
 for epoch in range(12):
  model.train();order=torch.randperm(len(ty));loss_sum=0
  for at in range(0,len(ty),64):
   idx=order[at:at+64];loss=torch.nn.functional.cross_entropy(model(tx[idx],tl[idx]),ty[idx])
   opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step();loss_sum+=float(loss.detach())
  schedule.step()
  if epoch%3==0 or epoch==11:
   h={'epoch':epoch+1,'loss_sum':loss_sum,'seconds':time.monotonic()-start};history.append(h);print(json.dumps(h),flush=True)
 model.eval();torch.save({'d_model':64,'state_dict':model.state_dict(),'seed':109,'epochs':12},DEST/'candidate.pt')
 spec=importlib.util.spec_from_file_location('exporter',ROOT/'04_model/candidate_generalization/train_candidate.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.CANDIDATE=DEST
 (DEST/'c_model').mkdir(exist_ok=True);(DEST/'export').mkdir(exist_ok=True);deployment=mod.export_candidate(model)
 (DEST/'export/training_report.json').write_text(json.dumps({'plan':plan,'history':history,'deployment':deployment,'seconds':time.monotonic()-start,'candidate_only':True},indent=2)+'\n')
 print('REFINEMENT_COMPLETE',flush=True)
if __name__=='__main__':main()
