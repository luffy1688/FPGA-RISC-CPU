from pathlib import Path
import json,random,re,unicodedata,collections
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2]
read=lambda p:[json.loads(x)for x in p.read_text().splitlines()if x.strip()]
norm=lambda t:''.join(c for c in unicodedata.normalize('NFKC',t).lower()if c.isalnum())
rng=random.Random(2026103007)
oldtrain=read(P/'data/train.jsonl');oldval=read(P/'data/validation.jsonl')
observed=read(R/'04_model/datasets/template_development.jsonl')+read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl')+read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl')
seen={norm(x['text'])for x in oldtrain+oldval+observed};out={'train':oldtrain,'validation':oldval,'fresh':[]};counts=collections.Counter()
cores={'read_temp':['读取芯片温度','读一下FPGA结温','报告片内温度','返回温度传感器读数','查询芯片当前温度','给我板上温度值'], 'set_pwm':['设置PWM占空比{p}%','PWM占空比改成{p}%','把PWM调为{p}%占空比','PWM按{p}%占空比输出','将PWM高电平占比设为{p}%'], 'run_coremark':['运行一次CoreMark','启动CoreMark基准','执行CoreMark并报CRC','跑一次CoreMark性能测试','跑CoreMark后显示成绩','启动CoreMark并显示校验值'], 'read_counter':['读取硬件计数器','查询当前计数值','返回CPU周期计数','读一下计数寄存器','获取计数器实时值'], 'set_led':['点亮LED{i}','熄灭LED{i}','LED整体掩码设为{m}','只关闭LED{i}其他位不变','只打开LED{i}其余灯不动','把LED输出改成{m}']}
wrappers={
 'train':{
  0:['立即{}','请帮忙{}','本次请{}','我要你{}','现在可以{}了','这次执行{}','麻烦{}','给我{}','不必等待，请{}','不用犹豫，{}','别等了，{}','只需{}','先不用解释，{}','不需要讲解，直接{}','不要重复，{}一次','不要改其他参数，只{}'],
  1:['不要{}了','先别{}','暂缓{}','此次取消{}','不必{}','我没要求{}','停止准备{}','禁止现在{}','请勿{}','不用{}，保持原样','这次不执行{}','先不要进行{}','别急着{}','撤销{}的请求','{}先别做'],
  2:['告诉我{}的原理','给我讲解{}的意思','我只想了解如何{}','说明{}有什么用','介绍一下{}的步骤','我在学{}，解释下','{}这个操作怎么理解','{}的命令格式是什么'],
  3:['假使{}结果如何','如果让它{}会怎样','设想一下{}的情形','假定我要{}呢','若要{}应怎样写','如果未来需要{}呢'],
  4:['把这句抄写出来：{}','引用用户的话：{}','请朗读“{}”','只复制命令：{}','把{}翻译成英文'],
  5:['之前是否{}过','刚才已经{}了吗','确认有无执行{}','{}是否成功完成','有没有做过{}','现在正在{}吗'],
  6:['{}，接下来再{other}','先{}然后{other}','{}后再{other}','一边{}一边{other}','先完成{}再{other}','{}，并执行{other}','{}同时{other}','{}之后紧接着{other}']},
 'validation':{
  0:['现在劳烦{}','请替我执行{}','无需解释，只要{}','别讲步骤，直接{}','不用等回复，{}','只做{}就行'],
  1:['暂且别{}','现在无需{}','不要急着去{}','我没有要求你{}','暂时停止{}','本轮不允许{}'],
  2:['说说{}的意义','{}的具体过程请讲解','教我编写{}的指令'],
  3:['倘使要{}会怎样','假若有人{}呢','假如将来{}会如何'],
  4:['原样转述：{}','把“{}”重复一遍','只展示{}的文字'],
  5:['核对先前有无{}','{}是不是早已完成','查查之前是否{}'],
  6:['{}，随后还要{other}','{}，接着再去{other}','除了{}，还要{other}','{}，做完继续{other}']},
 'fresh':{
  0:['请现在替我{}','不必阐释，马上{}','先不要长篇说明，{}','别等消息了，请{}'],
  1:['此刻不要开始{}','这一轮先不做{}','不要擅自{}','这次我没让你去{}'],
  2:['帮我分析{}这项操作','{}这个说法含义如何','说明一下怎样才能{}'],
  3:['假定以后让我{}呢','倘若安排{}会如何','设想设备要{}的情况'],
  4:['请逐字照抄：{}','将命令“{}”记在纸上','引用原句{}就好'],
  5:['上一次到底有没有{}','以前是不是做了{}','核实刚才{}了没有'],
  6:['{}，之后继续去{other}','{}，然后另外{other}','{}，并顺带{other}','先{}，完事儿再{other}']}}
# Family-level split: every wrapper belongs to a single split. Tool/action core overlap is intentional.
def add(split,text,label,context,family,extra=None):
 text=text.strip();key=norm(text)
 if not 1<=len(text.encode())<=64 or key in seen:return
 seen.add(key);x=dict(text=text,intent=label,context=context,split=split,source='synthetic_context_v2_minimal_pairs',family=split+':'+family,contract_executable=label!='reject')
 if extra:x.update(extra)
 out[split].append(x);counts[split+':'+str(context)]+=1
for split,cat in wrappers.items():
 for ctx,ws in cat.items():
  for wi,w in enumerate(ws):
   for tool,cs in cores.items():
    for ci,core in enumerate(cs):
     for rep in range(5 if split=='train'else 2):
      p=rng.randrange(101);i=rng.randrange(8);m=hex(rng.randrange(256));c=core.format(p=p,i=i,m=m)
      other_tool=rng.choice([k for k in cores if k!=tool]);other=rng.choice(cores[other_tool]).format(p=rng.randrange(101),i=rng.randrange(8),m=hex(rng.randrange(256)))
      text=w.format(c,other=other)
      add(split,text,tool if ctx==0 else'reject',ctx,'ctx%d:w%d'%(ctx,wi),dict(core_family=tool+':'+str(ci)))
# Same-tool sequential operations still count as multiple requests; CoreMark+CRC remains a single request.
connectors={'train':['先{a}再{b}','{a}然后{b}','{a}之后还要{b}','{a}并接着{b}'],'validation':['{a}，随后再{b}','{a}，接着还{b}'],'fresh':['{a}，之后另做{b}','先{a}，稍后再{b}']}
for split,ws in connectors.items():
 for wi,w in enumerate(ws):
  for rep in range(70 if split=='train'else 18):
   for tool in cores:
    a=rng.choice(cores[tool]).format(p=rng.randrange(101),i=rng.randrange(8),m=hex(rng.randrange(256)))
    b=rng.choice(cores[tool]).format(p=rng.randrange(101),i=rng.randrange(8),m=hex(rng.randrange(256)))
    add(split,w.format(a=a,b=b),'reject',6,'same_tool_seq:'+str(wi))
capabilities={
 'train':['把PWM频率设成{n}Hz','PWM周期改到{n}微秒','修改PWM频率到{n}kHz','将计数器清零','让硬件计数重新从零开始','重置计数寄存器','将芯片温度调低到{p}度','控制芯片温度保持{p}摄氏度','把FPGA加热到{p}度','给CoreMark成绩增加{n}分','将CoreMark结果改成{n}分','把CoreMark跑分伪造成{n}','重新烧录FPGA','为板子升级固件','更新开发板程序','把工作时钟升到{n}MHz','更改PLL倍频','读取风扇转速','调节风扇速度','配置网络IP地址','输出HDMI视频','启动摄像头采图','把LED亮度设为{p}%','让LED闪烁{n}次','读取昨天的芯片温度','查询室外气温','读取远程板卡温度','给FPGA连接无线网络'],
 'validation':['PWM输出频率切换到{n}Hz','把PWM的周期配置为{n}毫秒','从头开始硬件计数','把计数值归零','让FPGA温度恒定在{p}度','使芯片降到{p}摄氏度','把CoreMark成绩人为写成{n}','不用测直接给CoreMark{n}分','重新写入开发板固件','将系统运行频率换为{n}MHz','更换FPGA启动镜像','显示摄像头图像','打开板载WiFi','把LED的明暗调到{p}%','让LED按{n}Hz闪动','今天外面的温度报一下'],
 'fresh':['让PWM以{n}Hz频率工作','把PWM输出周期变为{n}us','清除目前累计的计数','硬件计数器恢复零值','把结温锁定为{p}摄氏度','让芯片自动降温到{p}度','给CoreMark直接填写{n}分','不测性能只报CoreMark满分','将新版本固件装进FPGA','把CPU时钟提至{n}MHz','启动板卡的显示接口','在LED上播放跑马灯','设置LED以{n}秒周期闪烁','帮我看明天城市的气温']}
capwrap={'train':['{}','请{}','现在{}','帮我{}','直接{}','麻烦{}'],'validation':['请替我{}','本次想要{}'],'fresh':['烦请完成{}','现在替我{}']}
for split,cs in capabilities.items():
 for ci,core in enumerate(cs):
  for wi,w in enumerate(capwrap[split]):
   for rep in range(14 if split=='train'else 3):
    add(split,w.format(core.format(n=rng.randrange(2,999),p=rng.randrange(10,90))),'reject',7,'capability:'+str(ci)+':'+str(wi))
# Legal partial negation vs literal execution negation; these are neural context labels, not a claim current schema handles every paraphrase.
partial={
 'train': [('只点亮LED{i}，不要改其他位','set_led'),('关闭LED{i}，别动其余灯','set_led'),('不要改其他LED，只打开LED{i}','set_led'),('PWM占空比设为{p}%，无需解释','set_pwm'),('不必讲原理，读取硬件计数器','read_counter'),('无需教程，直接读取芯片温度','read_temp'),('别反复运行，只跑一次CoreMark','run_coremark'),('不用报告原理，返回当前温度','read_temp')],
 'validation':[('仅关闭LED{i}，其余不要变','set_led'),('其他灯别动，把LED{i}点亮','set_led'),('不需要说明，请读当前计数','read_counter'),('别一直测试，执行一次CoreMark','run_coremark'),('不要讲流程，读一下FPGA温度','read_temp'),('PWM占空比改成{p}%，别解释','set_pwm')],
 'fresh':[('LED{i}点亮，其他位不要改','set_led'),('请只关LED{i}，别的灯不动','set_led'),('无需分析，给我此刻的计数值','read_counter'),('别多次执行，CoreMark跑一次','run_coremark'),('不要说原理，报告芯片温度','read_temp'),('不必讲解，把PWM改为{p}%占空比','set_pwm')]}
for split,rs in partial.items():
 for fi,(w,tool)in enumerate(rs):
  for rep in range(100 if split=='train'else 25):
   add(split,w.format(p=rng.randrange(101),i=rng.randrange(8)),tool,0,'partialneg:'+str(fi))
# Extend public OOD only within its original train/dev partition. The original test/642 is not opened.
raw=read(P/'data/massive_zh_original.jsonl');domains={'calendar','email','weather','transport','news','recommendation','datetime','social','music','audio','takeaway','cooking','alarm','lists','play'}
public={}
for split,partition,limit in [('train','train',1200),('validation','dev',160)]:
 rows=[x for x in raw if x['partition']==partition and x['scenario']in domains and 2<=len(x['utt'].encode())<=64 and not re.search(r'(?i)(coremark|fpga|pwm|led|芯片|计数器)',x['utt'])];rng.shuffle(rows);n=0
 for x in rows:
  z=norm(x['utt'])
  if z in seen:continue
  seen.add(z);out[split].append(dict(text=x['utt'],intent='reject',context=8,split=split,source='MASSIVE1.1/zh-CN',source_id=x['id'],source_partition=partition,family='MASSIVE:'+partition+':'+x['scenario'],contract_executable=False));n+=1
  if n>=limit:break
 public[split]=n
for split,rows in out.items():(D/'data'/f'{split}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in rows))
plan=dict(rows={k:len(v)for k,v in out.items()},class_counts={k:dict(collections.Counter(x['intent']for x in v))for k,v in out.items()},context_counts={k:dict(collections.Counter(x.get('context',8)for x in v))for k,v in out.items()},new_synthetic_counts=dict(counts),new_public_rows=public,split='Wrapper/capability/same-tool/partial-negation families split before generating. Base action cores and parameter values may be shared; no speaker-disjoint or human-blind claim.',old_replay=True,old642_opened=False,observed_sets_not_in_gradient=True,public_license='CC-BY-4.0, AmazonScience MASSIVE1.1 Chinese, original train/dev preserved',fresh_status='Frozen for single evaluation only after checkpoint/threshold selection; not accessed by training script.')
(D/'data_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');print(json.dumps(plan,ensure_ascii=False))
