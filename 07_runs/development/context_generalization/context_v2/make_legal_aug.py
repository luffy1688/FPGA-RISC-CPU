from pathlib import Path
import sys,json,random,unicodedata,collections
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2]
read=lambda p:[json.loads(x)for x in p.read_text().splitlines()if x.strip()]
norm=lambda t:''.join(c for c in unicodedata.normalize('NFKC',t).lower()if c.isalnum())
rows=read(D/'data/train.jsonl');val=read(D/'data/validation.jsonl');old=read(R/'04_model/datasets/template_development.jsonl')+read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl')+read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')
# No fresh file is opened. Wrapper families remain disjoint; this augmentation is explicitly informed by observed-development failures.
seen={norm(x['text'])for x in rows+val+old};rng=random.Random(2026103017);added=[]
objects={'read_temp':['FPGA芯片结温','片内温度寄存器数值','当前板卡结温','此刻芯片的温度值','FPGA温度采样数据','芯片此时结温','芯片温度寄存器的数据'], 'read_counter':['硬件周期计数值','CPU计数寄存器数值','当前计数器的读数','硬件计数寄存器读数','自由运行计数器值','板内周期计数','实时硬件计数值']}
verbs=['读取','读出','查询','返回','获取','报告','查看','给出','提供'];prefix=['请您','烦请','麻烦帮我','能否帮忙','可否现在','劳烦您帮我','帮个忙请','请替我','我现在想','想麻烦你'];tails=['即可','就好','给我看看','给我瞧一下','告诉我就行','请直接报数','麻烦返回结果','谢谢啦']
cores=[]
for tool,obs in objects.items():
 for v in verbs:
  for o in obs:cores.append((v+o,tool))
for v in ['跑完','完成','执行','启动','运行']:
 for obj in ['一次CoreMark性能基准','一次CoreMark跑分','一轮CoreMark基准测试','本次CoreMark性能测试','一次CoreMark并返回CRC','一遍CoreMark并给出得分']:cores.append((v+obj,'run_coremark'))
for p in [3,8,17,23,31,46,52,67,74,89]:
 for x in ['把PWM占空比设置成%d%%','将PWM高电平比例改为%d%%','把PWM调成%d%%占空比']:cores.append((x%p,'set_pwm'))
for i in range(8):
 for x in ['只关闭LED%d保持其他位','单独点亮LED%d','将LED%d熄灭','让LED%d亮起来']:cores.append((x%i,'set_led'))
for core,tool in cores:
 for k in range(12):
  text=rng.choice(prefix)+core+'，'+rng.choice(tails)
  if k%4==0:text=rng.choice(['无需分析，请','不用说明，请','不必介绍原理，'])+core
  key=norm(text)
  if key in seen or len(text.encode())>64:continue
  seen.add(key);added.append(dict(text=text,intent=tool,context=0,split='train',source='synthetic_context_v2_legal_grammar',family='train:legal_compositional:'+tool,contract_executable=True))
  # Semantic counterpart uses execution negation / explanation / status with the same device words.
  if k%3==0:
   neg=rng.choice(['本次不要{}','暂时别{}，保持原样','我想了解{}的原理','先解释{}的方法','如果{}会怎样','之前有{}吗']).format(core)
   nk=norm(neg)
   if nk not in seen and len(neg.encode())<=64:
    seen.add(nk);ctx=2 if any(t in neg for t in ['原理','解释'])else 3 if'如果'in neg else 5 if'之前'in neg else 1
    added.append(dict(text=neg,intent='reject',context=ctx,split='train',source='synthetic_context_v2_legal_grammar_counterpart',family='train:legal_compositional_negative:'+str(ctx),contract_executable=False))
allrows=rows+added;(D/'data/train_legal_aug.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in allrows));plan=dict(original_train=len(rows),added=len(added),total=len(allrows),addedclasscounts=dict(collections.Counter(x['intent']for x in added)),observed_error_informed=True,normalized_exact_overlap_with_observed_or_validation=0,fresh_opened=False,scope='Observed-development-informed compositional legal grammar enhancement; not independent language generation or human-blind. No fresh/642 opened; exact observed/dev sentences excluded.')
(D/'legal_aug_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');print(json.dumps(plan))
