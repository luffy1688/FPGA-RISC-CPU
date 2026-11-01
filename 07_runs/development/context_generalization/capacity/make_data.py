from pathlib import Path
import json,random,unicodedata,collections
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2]
read=lambda p:[json.loads(l)for l in p.read_text().splitlines()if l.strip()]
norm=lambda t:''.join(c for c in unicodedata.normalize('NFKC',t).lower()if c.isalnum())
train=read(P/'context_v2/data/train_legal_aug.jsonl');observed=read(P/'context_v2/data/fresh.jsonl')+read(P/'context_v2/data/validation.jsonl')+read(P/'data/validation.jsonl')+read(R/'04_model/datasets/template_development.jsonl')+read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl')+read(R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl');reserved={norm(x['text'])for x in observed};seen=reserved|{norm(x['text'])for x in train};rng=random.Random(2026103019)
cores={'read_temp':['取出片内结温采样值','读出开发板温度测量结果','告诉我当前FPGA内部温度','获取芯片此刻结温数据','返回片内温度寄存器读数','查询本芯片温度采样','显示FPGA当前结温'], 'set_pwm':['令PWM占空比为{p}%','把PWM的高电平比例调整为{p}%','PWM按{p}%占空比输出','修改PWM占空比到{p}%','把PWM脉冲占比设到{p}%'],'run_coremark':['开始一次CoreMark并给CRC','测一下CoreMark性能','完成本轮CoreMark性能测量','执行一遍CoreMark基准程序','给我CoreMark实测结果','运行一次CoreMark测试并回报','让处理器跑CoreMark基准'],'read_counter':['取得板内硬件计数值','读出CPU的周期计数','返回实时自由运行计数器值','查询芯片内计数寄存器','读取当前周期累计值','显示板内计数器数据','给我硬件周期计数的读数'],'set_led':['使LED{i}点亮并保留其余位','将LED{i}熄灭且保留其余位','关闭LED{i}而别的灯不变','把LED的整体掩码设成{m}','点亮第{i}号LED其余不变','只点亮LED{i}不要动其他灯','仅熄灭LED{i}其他位保留']}
wraps={0:['请现在替我{}','不必阐释，马上{}','先不要长篇说明，{}','别等消息了，请{}','请替我直接{}吧','不用介绍，实际执行{}','我现在需要{}，谢谢'],1:['这次我没让你去{}','此刻不要开始{}','禁止你现在{}','撤回要求你{}的指令','我并没有请你{}','这轮先不做{}','不打算真的{}'],2:['帮我分析{}这项操作','{}这个说法含义如何','说明一下怎样才能{}','我只是学习{}的写法','请讲述{}的意义','不用动硬件，说明{}'],3:['设想设备要{}的情况','假定以后让我{}呢','倘若安排{}会如何','如果有一天需要{}，会怎样','仅讨论假使{}的情形'],4:['请逐字照抄：{}','将命令“{}”记在纸上','引用原句{}就好','请抄录{}的文字','这只是引用：“{}”','请复制而非执行{}'],5:['核实刚才{}了没有','上一次到底有没有{}','以前是不是做了{}','检查早些时候是否{}过','请确认{}已经发生了吗'],6:['{}，然后另外{other}','{}，之后继续去{other}','先{}，完事儿再{other}','{}，并顺带{other}']}
added=[]
def add(t,intent,ctx,family):
 z=norm(t)
 if z in seen or len(t.encode())>64:return
 seen.add(z);added.append(dict(text=t,intent=intent,context=ctx,source='synthetic_capacity_observed_error_family',split='train',family=family,contract_executable=intent!='reject'))
for ctx,ws in wraps.items():
 for wi,w in enumerate(ws):
  for tool,cs in cores.items():
   for ci,core in enumerate(cs):
    for rep in range(5):
     a=core.format(p=rng.randrange(101),i=rng.randrange(8),m=hex(rng.randrange(256)));other_tool=rng.choice(list(cores));b=rng.choice(cores[other_tool]).format(p=rng.randrange(101),i=rng.randrange(8),m=hex(rng.randrange(256)));add(w.format(a,other=b),tool if ctx==0 else'reject',ctx,'capacity:ctx%d:w%d'%(ctx,wi))
for core in ['给CoreMark直接填写{n}分','不测性能只报CoreMark满分','将计数器恢复到零','给FPGA结温锁定为{p}度','让PWM变成{n}Hz频率','修改板卡的固件镜像','把LED亮度调成{p}%']:
 for prefix in ['请立即','麻烦你帮我','我希望现在','请这次','本次需要','']:
  for rep in range(40):add(prefix+core.format(n=rng.randrange(3,999),p=rng.randrange(101)),'reject',7,'capacity:unsupported')
allrows=train+added;(D/'train.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in allrows));plan=dict(train_rows=len(allrows),original_train=len(train),added=len(added),classcounts=dict(collections.Counter(x['intent']for x in allrows)),contextcounts=dict(collections.Counter(x.get('context',8)for x in allrows)),old1138_status='Observed development regression target; NOT heldout or blind; error families informed augmentation and checkpoint/threshold selection',old1138_exact_train_overlap=0,old80_192_288_541_2031_exact_train_overlap=0,old_first_evaluations_immutable=True,new_wrappers_independent=False,scope='New action cores and parameter draws combined with observed error-family wrappers. No exact old1138 sentences added, but template knowledge leaks intentionally; not independent generalization.')
(D/'lineage.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');print(json.dumps(plan))
