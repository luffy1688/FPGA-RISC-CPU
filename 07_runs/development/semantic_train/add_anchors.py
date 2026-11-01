from pathlib import Path
import json,random,unicodedata,collections
R=Path('/work/LUO/NeedleRV-X');D=R/'07_runs/development/semantic_train'
def read(p):return [json.loads(x)for x in p.read_text().splitlines()if x]
def norm(t):return ''.join(c for c in unicodedata.normalize('NFKC',t).lower()if c.isalnum())
rows=read(D/'semantic_train.jsonl');base=read(R/'04_model/candidate_tool_contract/datasets/train.jsonl');orig=read(R/'04_model/datasets/template_development.jsonl');aug=read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl');diag=read(D/'semantic_diagnostic.jsonl')
seen={norm(x['text'])for x in rows+base+orig+aug+diag};rng=random.Random(20261030)
spec={
'read_temp':['fetch die temperature','report chip thermal reading','what is the chip temperature now','get current temperature value','tell me chip temperature'],
'set_pwm':['adjust pwm duty cycle to {p} percent','use {p} percent duty for pwm','drive pwm at {p}% duty','pwm duty cycle should be {p} percent','load pwm duty with {p} percent','设置PWM高电平百分比{p}%','把PWM的占比设成{p}%'],
'run_coremark':['execute a coremark benchmark','begin coremark performance test','do one coremark run','measure coremark performance','launch coremark test now'],
'read_counter':['report processor cycle count','fetch hardware counter value','what is the cycle count now','give me cpu counter value','get current cycle register'],
'set_led':['LED掩码设为{m}','将LED输出掩码写入{m}','把LED输出值改为{m}','LED寄存器写入{m}','更新LED位掩码到{m}','set led output mask to {m}','load led bit mask {m}','update led register value to {m}','assign {m} to led mask','make led mask equal {m}'],
'reject':['explain pwm duty {p} percent','what if pwm is set to {p} percent','is led{i} on now','how to turn led{i} off','do not set pwm to {p} percent','do not run coremark','tell me why coremark runs','show whether led{i} is enabled','read current pwm duty','run coremark then read temperature','write an email about fpga','open the internet browser','copy the phrase turn on led{i}','介绍PWM占空比{p}%的意思','说说LED{i}如何点亮','LED{i}亮了没有','当前PWM是百分之{p}吗','查询PWM有多少占空比','若是PWM变成{p}%会如何','假如LED{i}关闭将会怎样','不要把LED{i}点亮','先读取计数器再打开LED{i}','CoreMark得分增加{n}分','将硬件计数器设置为{n}','芯片结温调整到{p}度']}
added=[]
for label,templates in spec.items():
 for k,template in enumerate(templates):
  english=all(ord(c)<128 for c in template)
  target=48 if '{'in template else 14
  for j in range(2000):
   p=rng.randrange(101);m=rng.randrange(256);i=rng.randrange(8);n=rng.randrange(1000)
   pre=rng.choice(['','please ','now ','please help me '])if english else rng.choice(['','请','麻烦','帮我','现在请'])
   suf=rng.choice(['','.',' please'])if english else rng.choice(['','。','，谢谢'])
   text=pre+template.format(p=p,m=m,i=i,n=n)+suf;key=norm(text)
   if key in seen or len(text.encode())>64:continue
   seen.add(key)
   arg=p if label=='set_pwm'else m if label=='set_led'else None
   added.append({'text':text,'intent':label,'stratum':'mask_anchor'if label=='set_led'else'english_context'if english else'contract_context','family':'train:anchor:'+label+':'+str(k),'core_template':template,'source':'assistant-authored synthetic execution-contract coverage repair','tool':None if label=='reject'else label,'argument':arg,'operation':0,'contract_executable':label!='reject','split':'train'})
   target-=1
   if target==0:break
rows+=added
(D/'semantic_train.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in rows))
p=json.loads((D/'protocol.json').read_text());p['first_group_training_examples']=p['new_training_examples'];p['coverage_repair']='Add legitimate LED mask0..255, broad English supported commands/context contrasts; no observed user text used.';p['new_training_examples']=len(rows);p['new_training_families']=len({x['family']for x in rows});p['train_counts']=dict(collections.Counter(x['intent']for x in rows));p['train_strata']=dict(collections.Counter(x['stratum']for x in rows));(D/'protocol.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');print(json.dumps(p,ensure_ascii=False))
