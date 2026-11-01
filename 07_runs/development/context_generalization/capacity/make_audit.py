from pathlib import Path
import sys,json,collections,random,unicodedata
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2];sys.path.insert(0,str(P));from train import read
norm=lambda t:''.join(c for c in unicodedata.normalize('NFKC',t).lower()if c.isalnum())
assert(D/'frozen_config.json').exists();seen={norm(x['text'])for path in [D/'train.jsonl',P/'context_v2/data/validation.jsonl',P/'context_v2/data/fresh.jsonl',P/'data/validation.jsonl',R/'04_model/datasets/template_development.jsonl',R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl',R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl']for x in read(path)};rng=random.Random(3011337)
cores={'read_temp':['读取FPGA当前温度','读出芯片当前结温','报告板内温度数据','查看温度寄存器数值','获取此刻FPGA结温','给我芯片现在的温度','查询片内温度传感器','读一下板卡结温'],'set_pwm':['PWM占空比改为{p}%','把PWM高电平占比设为{p}%','设置PWM占空比{p}%','将PWM输出调到{p}%占空比'],'run_coremark':['执行一遍CoreMark测试','启动CoreMark并报告CRC','运行一次CoreMark基准','让CPU跑一次CoreMark','完成CoreMark性能测试','进行一次CoreMark跑分','启动CoreMark基准程序','测量一次CoreMark成绩'],'read_counter':['读取CPU周期计数器','读出硬件计数器当前值','查看当前计数寄存器','查询硬件周期计数值','返回芯片计数器数值','获取硬件实时计数值','给我板内当前计数','读一下周期累计计数'],'set_led':['设置LED整体掩码为{m}','只点亮LED{i}其余不变','关闭LED{i}而其他位不动','把LED输出掩码改为{m}']}
wrappers={0:['劳烦现在{}吧','接下来请实际{}','我现在就要{}，请执行','劳驾马上{}','请把这次任务办好：{}'],1:['我并非要你{}','此刻暂不执行{}','不要着手{}','打住，别去{}','先取消本次{}'],2:['以文字讲清{}的含义','给初学者讲授{}的原理','{}该如何理解','请说明{}涉及哪些步骤'],3:['假想有人准备{}','若设定情境为{}会怎样','如果将来授权{}会如何','假设可能需要{}呢'],4:['把{}这几个字抄到报告里','请摘录下面的话：{}','将{}作为引用原文输出','请逐字复写命令：{}'],5:['此前那次{}是否完成','核对历史操作有没有{}','能确认刚刚已经{}了吗','查查先前{}了没有']}
rows=[];counts=collections.Counter()
def core(tool):return rng.choice(cores[tool]).format(p=rng.randrange(101),i=rng.randrange(8),m=hex(rng.randrange(256)))
def add(text,label,ctx,fam):
 z=norm(text)
 if z in seen or len(text.encode())>64:return False
 seen.add(z);rows.append(dict(text=text,intent=label,context=ctx,source='synthetic_capacity_postfreeze_internal_audit',family=fam,split='internal_audit'));counts[str(ctx)]+=1;return True
for tool in cores:
 attempts=0;added=0
 while added<40 and attempts<3000:
  attempts+=1;text=rng.choice(wrappers[0]).format(core(tool));added+=add(text,tool,0,'audit:execution:'+tool)
for ctx in range(1,6):
 attempts=0
 while counts[str(ctx)]<100 and attempts<5000:
  attempts+=1;t=rng.choice(list(cores));w=rng.choice(wrappers[ctx]);add(w.format(core(t)),'reject',ctx,'audit:context:'+str(ctx)+':'+str(wrappers[ctx].index(w)))
for ctx in [6,7]:
 attempts=0
 while counts[str(ctx)]<100 and attempts<10000:
  attempts+=1;t=rng.choice(list(cores))
  if ctx==6:
   a=core(t);b=core(rng.choice(list(cores)));w=rng.choice(['{a}，完成后顺手{b}','先办{a}，再处理{b}','同时办两件事：{a}及{b}']);text=w.format(a=a,b=b)
  else:
   text=rng.choice(['给FPGA设定目标温度为{p}度','将PWM工作频率调整成{n}Hz','让硬件计数从零重新开始','替CoreMark结果填写{n}分','只报告CoreMark满分别实测','把LED发光亮度设置到{p}%','更换开发板上的固件程序','将CPU运行频率提高到{n}MHz']).format(p=rng.randrange(101),n=rng.randrange(2,999))
  add(text,'reject',ctx,'audit:multi'if ctx==6 else'audit:unsupported')
(D/'internal_audit.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in rows));plan=dict(n=len(rows),context_counts=dict(counts),source='New internal generated wrapper/action families authored only after whole capacity candidate freeze; not independent-human blind. No checkpoint/threshold selection may use this audit.',exact_overlap_with_train_or_observed_sets=0,model_frozen_before_generation=True,model_frozen_config='frozen_config.json');(D/'internal_audit_protocol.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan))
