from pathlib import Path
import json,random,re,unicodedata,collections
R=Path('/work/LUO/NeedleRV-X');D=Path(__file__).resolve().parent
read=lambda p:[json.loads(l)for l in p.read_text().splitlines()if l.strip()]
norm=lambda t:''.join(c for c in unicodedata.normalize('NFKC',t).lower()if c.isalnum())
tools=['read_temp','set_pwm','run_coremark','read_counter','set_led','reject']
base=read(R/'04_model/candidate_tool_contract/datasets/train.jsonl')+read(R/'07_runs/development/semantic_train/semantic_train.jsonl')
observed=read(R/'04_model/datasets/template_development.jsonl')+read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl')+read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')
seen={norm(x['text'])for x in observed};base=[dict(x,split='train',source=x.get('source','prior_training'),family=x.get('family','prior'))for x in base if norm(x['text'])not in seen]
seen.update(norm(x['text'])for x in base)
cores={'read_temp':['读取FPGA温度','把当前芯片结温报给我','获取片内温度读数','读一下板卡温度'], 'set_pwm':['将PWM占空比设为{p}%','PWM高电平占比改为{p}%','把PWM调成{p}%占空比','设置PWM占空比{p}%'], 'run_coremark':['运行一次CoreMark','启动CoreMark基准','让CPU跑一轮CoreMark','执行CoreMark并报告CRC'], 'read_counter':['读取硬件计数器','给我当前周期计数','读一下CPU计数寄存器','返回当前硬件计数值'], 'set_led':['点亮LED{i}','关闭LED{i}而其他位不变','将LED整体掩码设为{m}','把LED{i}熄灭']}
# Entire wrapper families are separated; parameter draws also use disjoint intervals.
wrappers={
 'train':[(0,'{}'),(0,'请{}'),(0,'麻烦你{}，谢谢'),(0,'现在就{}'),(0,'这次需要{}'),(0,'{}，好吗'),(0,'{}，可以吗'),(1,'不要{}'),(1,'请先别{}'),(1,'我不需要{}'),(1,'禁止{}'),(1,'取消{}'),(2,'解释一下{}的含义'),(2,'讲讲如何{}'),(2,'请说明{}的方法'),(2,'{}是什么意思'),(3,'假如{}会怎样'),(3,'如果{}会发生什么'),(3,'假设有人要{}'),(4,'复述这句话：{}'),(4,'翻译：{}'),(4,'请引用命令“{}”'),(5,'是否已经{}'),(5,'现在是在{}吗'),(5,'查询有没有{}'),(6,'先{}再打开LED0'),(6,'{}之后读取温度'),(7,'给CoreMark成绩加{n}分'),(7,'把PWM频率改成{n}Hz'),(7,'把计数器清零'),(7,'让温度固定在{p}度')],
 'validation':[(0,'劳驾{}一下'),(0,'{}，行吗'),(0,'为我{}'),(1,'这会儿不用{}'),(1,'切勿{}'),(2,'教教我怎样{}'),(2,'描述{}的步骤'),(3,'倘若{}会如何'),(4,'把“{}”原话重复给我'),(5,'检查是不是已经{}'),(6,'{}然后再启动CoreMark'),(7,'将CoreMark得分改到{n}')],
 'heldout':[(0,'烦请{}'),(0,'{}，行不行'),(0,'这次请替我{}'),(1,'暂时无需{}'),(1,'我没有让你{}'),(2,'{}这几个字怎么理解'),(2,'演示如何编写{}的指令'),(3,'要是我提出{}呢'),(4,'有人说“{}”，把原文抄一遍'),(5,'确认一下之前是不是{}了'),(6,'{}并且再把LED1关掉'),(7,'将CoreMark跑分伪造成{n}')]
}
out={'train':base,'validation':[],'heldout':[]};rng=random.Random(20261030)
for split,wraps in wrappers.items():
 for wi,(speech,w)in enumerate(wraps):
  for tool,templates in cores.items():
   for ci,core in enumerate(templates):
    for k in range(5 if split=='train'else 2):
     ps={'train':(0,60),'validation':(61,80),'heldout':(81,100)}[split];p=rng.randint(*ps);i=(k+ci)%8;m=hex(rng.randrange(256));n=rng.randrange(100,900)
     text=w.replace("{}",core).replace('{p}',str(p)).replace('{i}',str(i)).replace('{m}',m).replace('{n}',str(n))
     z=norm(text)
     if len(text.encode())>64 or z in seen:continue
     seen.add(z);label=tool if speech==0 else'reject'
     out[split].append(dict(text=text,intent=label,context=speech,split=split,source='synthetic_context_minimal_pairs',family=split+':wrapper:'+str(wi),core_family=tool+':'+str(ci),argument=p if tool=='set_pwm'else i if tool=='set_led'else 0,contract_executable=speech==0))
raw=read(D/'data/massive_zh_original.jsonl');domains={'calendar','email','weather','transport','news','recommendation','datetime','social','music','audio','takeaway','cooking','alarm','lists','play'}
counts={};public_ids={};reserved={norm(x['text'])for x in observed}
for split,partition,limit in [('train','train',1600),('validation','dev',200),('heldout','test',300)]:
 rows=[x for x in raw if x['partition']==partition and x['scenario']in domains and 2<=len(x['utt'].encode())<=64 and not re.search(r'(?i)(coremark|fpga|pwm|led|芯片|计数器)',x['utt'])]
 rng.shuffle(rows);added=[]
 for x in rows:
  z=norm(x['utt'])
  if z in seen:continue
  seen.add(z);added.append(dict(text=x['utt'],intent='reject',context=8,split=split,source='MASSIVE1.1/zh-CN',source_id=x['id'],source_partition=partition,family='MASSIVE:'+partition+':'+x['scenario'],contract_executable=False))
  if len(added)==limit:break
 out[split]+=added;counts[split]=len(added);public_ids[split]=[x['source_id']for x in added]
for split,rows in out.items():
 for x in rows:
  x.setdefault('context',0 if x['intent']!='reject'else 8)
 (D/'data'/(split+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in rows))
plan={'dataset':{'rows':{k:len(v)for k,v in out.items()},'class_counts':{k:dict(collections.Counter(x['intent']for x in v))for k,v in out.items()},'public_rows':counts,'normalized_exact_overlap':0,'max_bytes':64},'provenance':{'url':'https://github.com/alexa/massive','archive':'https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz','license':'CC-BY-4.0','citation':'FitzGerald et al., MASSIVE, arXiv2204.08582','original_partition_preserved':True,'task_mapping':'Only non-board domains mapped to reject; no claim original labels are FPGA intents.'},'protocol':{'existing80_192_288':'Observed development only; never training gradient','heldout':'Synthetic unseen wrapper families + official MASSIVE test partition; final single first evaluation, not independent-human blind data','selection':'validation raw correct, reject falseaccept; original80>=73,192>=129,observed288>=218; no user25/99/163 for training or selection','architecture':'frozen production unicode Engram encoder + learned multi-task context residual, intent6 + executable2; no lexical execution rules added'}}
(D/'protocol.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');print(json.dumps(plan['dataset']))
