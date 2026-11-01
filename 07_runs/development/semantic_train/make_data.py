from pathlib import Path
import json,random,re,collections,unicodedata
R=Path('/work/LUO/NeedleRV-X');D=R/'07_runs/development/semantic_train'
def norm(t):return ''.join(c for c in unicodedata.normalize('NFKC',t).lower()if c.isalnum())
def read(p):return [json.loads(x)for x in p.read_text().splitlines()if x]
base=read(R/'04_model/candidate_tool_contract/datasets/train.jsonl')
orig=read(R/'04_model/datasets/template_development.jsonl');aug=read(R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl')
train={
'read_temp':[
('synonym','获取芯片结温'),('synonym','读一下片内温度'),('synonym','查询FPGA的结温'),('synonym','看看板上现在多热'),('synonym','给我此刻的温度读数'),('question','芯片此时温度多少'),('question','FPGA现在有多热'),('question','当前的芯片结温是多少'),('imperative','把温度传感器数值告诉我'),('imperative','显示片上温度读数'),('imperative','报一下芯片结温'),('imperative','读取当前结温'),('polite','读一下板子温度好吗'),('polite','返回结温数值可以吗')],
'set_pwm':[
('synonym','PWM占空比设定为{p}%'),('synonym','把PWM调整成{p}%占空比'),('synonym','PWM占空比改成百分之{p}'),('synonym','将PWM输出设为{p}%占空比'),('synonym','把PWM的高电平占比调到{p}%'),('synonym','PWM高电平比例改成{p}%'),('imperative','调整PWM的占空比至{p}%'),('imperative','设PWM占空比为{p}%'),('imperative','PWM占空比取{p}%'),('imperative','让PWM保持{p}%占空比'),('imperative','PWM输出占空比更新为{p}%'),('polite','设置PWM占空比{p}%好吗'),('polite','把PWM调到{p}%可以吗'),('polite','让PWM占空比等于{p}%行吗')],
'run_coremark':[
('synonym','开始CoreMark基准'),('synonym','执行CoreMark性能测试'),('synonym','启动一次CoreMark跑分'),('synonym','测一下CoreMark性能'),('imperative','运行CoreMark测试程序'),('imperative','帮CPU跑CoreMark'),('imperative','执行一次真实CoreMark基准'),('imperative','CoreMark跑一轮'),('imperative','启动CoreMark并报告结果'),('imperative','给处理器运行CoreMark'),('imperative','把CoreMark测试跑起来'),('polite','跑CoreMark一次好吗'),('polite','执行CoreMark可以吗'),('polite','启动CoreMark评测行吗')],
'read_counter':[
('synonym','读取CPU的周期数'),('synonym','给出硬件计数器读数'),('synonym','查一下当前周期计数'),('synonym','读出处理器累计周期'),('imperative','告诉我计数器当前数值'),('imperative','获取周期寄存器读数'),('imperative','显示硬件计数器数值'),('imperative','报告当前CPU周期计数'),('question','周期计数现在是多少'),('question','计数器目前计了多少'),('question','硬件累计多少周期'),('question','CPU周期数是多少'),('polite','读取周期计数好吗'),('polite','报告计数器读数可以吗')],
'set_led':[
('synonym','开启LED{i}'),('synonym','点亮编号为{i}的LED'),('synonym','让LED{i}亮起来'),('synonym','将LED{i}点亮'),('imperative','打开LED{i}灯'),('imperative','LED{i}打开'),('imperative','LED{i}开启'),('imperative','把LED{i}熄灭'),('imperative','关掉LED{i}'),('imperative','让LED{i}灭掉'),('imperative','LED{i}关闭'),('imperative','熄灭编号为{i}的LED'),('polite','打开LED{i}好吗'),('polite','关闭LED{i}可以吗')],
'reject':[
('explanation','解释PWM占空比设成{p}%的含义'),('explanation','说明打开LED{i}的方法'),('explanation','CoreMark运行原理是什么'),('explanation','什么是芯片结温'),('explanation','读取周期计数是什么意思'),('explanation','教我如何设置PWM占空比{p}%'),('hypothetical','假如PWM占空比为{p}%会怎样'),('hypothetical','如果点亮LED{i}会如何'),('hypothetical','假设运行CoreMark会发生什么'),('hypothetical','要是计数器归零会怎样'),('status_query','LED{i}已经打开了吗'),('status_query','PWM占空比是不是{p}%'),('status_query','现在CoreMark在运行吗'),('status_query','查看LED{i}的状态'),('status_query','读取PWM当前占空比'),('status_query','查询CoreMark成绩'),('negation','不要打开LED{i}'),('negation','别把PWM设为{p}%'),('negation','取消CoreMark运行'),('negation','不要读取温度'),('negation','别读取计数器'),('negation','不用关闭LED{i}'),('multi_action','打开LED{i}并读取温度'),('multi_action','读取温度再跑CoreMark'),('multi_action','设PWM{p}%然后点亮LED{i}'),('multi_action','读取周期计数后清零'),('capability','把PWM频率设置为{n}Hz'),('capability','让温度保持{p}度'),('capability','重置硬件计数器'),('capability','把CoreMark成绩改成{n}'),('capability','给CoreMark分数加{n}'),('capability','更新芯片固件'),('ood','打开厨房的窗帘'),('ood','播放新闻广播'),('ood','关闭车库大门'),('ood','解锁卧室门锁'),('ood','今天会不会下雨'),('ood','为我编写一段诗歌'),('quotation','翻译打开LED{i}这句话'),('quotation','复述PWM设为{p}%这条指令')]
}
diag={
'read_temp':[('synonym','把芯片现在的热度报出来'),('question','这块FPGA当前结温为多少'),('imperative','从片内温度传感器取一次读数'),('polite','把板卡结温反馈给我好吗')],
'set_pwm':[('synonym','将PWM占空比换成{p}%'),('imperative','我要PWM按{p}%的占空比输出'),('imperative','为PWM写入{p}%的高电平占比'),('polite','把PWM的占空比设到{p}%好吗')],
'run_coremark':[('synonym','让处理器完成一遍CoreMark测试'),('imperative','做一轮CoreMark性能评测'),('imperative','CoreMark基准现在开始跑'),('polite','给我运行一次CoreMark好吗')],
'read_counter':[('question','处理器周期计数器现在是多少'),('imperative','把硬件累计的周期数给我'),('synonym','采集一次CPU计数器值'),('polite','给我周期计数的读数好吗')],
'set_led':[('synonym','使LED{i}亮起'),('imperative','把LED{i}打开一下好吗'),('imperative','LED{i}给我关掉'),('polite','让LED{i}熄灭好吗')],
'reject':[('explanation','请讲解LED{i}关闭的步骤'),('explanation','为什么PWM要设成{p}%'),('hypothetical','倘若CoreMark启动会发生什么'),('hypothetical','要是LED{i}关闭会如何'),('status_query','LED{i}有没有被点亮'),('status_query','确认PWM是不是{p}%占空比'),('negation','禁止执行CoreMark'),('negation','不必把PWM改成{p}%'),('multi_action','先关闭LED{i}再启动CoreMark'),('multi_action','读出温度后调整PWM{p}%'),('capability','PWM输出频率改为{n}Hz'),('capability','将CoreMark结果提高{n}分'),('ood','打开客厅的灯带'),('ood','启动智能空调制冷'),('quotation','举例说明打开LED{i}的指令'),('quotation','引用运行CoreMark这条命令')]
}
reserved={norm(x['text'])for x in base+orig+aug};seen=set(reserved);rng=random.Random(20261029)
def build(spec,split):
 out=[]
 for label,templates in spec.items():
  for k,(stratum,template)in enumerate(templates):
   target=(48 if ('{p}'in template or'{i}'in template or'{n}'in template)else 24)if split=='train'else 8
   candidates=[]
   for j in range(900):
    p=rng.randrange(101);i=rng.randrange(8);n=rng.randrange(10,1000)
    prefix=rng.choice(['','请','帮我','麻烦','请帮我','现在请','麻烦你','劳驾'])
    suffix=rng.choice(['','。','，谢谢'])
    t=prefix+template.format(p=p,i=i,n=n)+suffix
    z=norm(t)
    if len(t.encode())>64 or z in seen:continue
    seen.add(z)
    arg=p if label=='set_pwm'else i if label=='set_led'else None
    op=(2 if any(v in template for v in ['熄灭','关闭','关掉','灭掉'])else 1)if label=='set_led'else 0
    candidates.append({'text':t,'intent':label,'stratum':stratum,'family':split+':'+label+':'+str(k),'core_template':template,'source':'assistant-authored synthetic execution-contract data','tool':None if label=='reject'else label,'argument':arg,'operation':op,'contract_executable':label!='reject','split':split})
    if len(candidates)>=target:break
   out+=candidates
 return out
new=build(train,'train');diagnostic=build(diag,'diagnostic')
# No observed user data are opened or used. Base training is existing authorized training data.
for name,rows in [('semantic_train',new),('semantic_diagnostic',diagnostic)]:
 (D/(name+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in rows))
plan={'scope':'Synthetic family-isolated diagnostics, not external blind test. Original80 and augmentation192 are observed development gates. User25/99/163 sets are not opened for training or model selection.','base_examples':len(base),'base_unique':len({norm(x['text'])for x in base}),'new_training_examples':len(new),'new_training_families':sum(map(len,train.values())),'diagnostic_examples':len(diagnostic),'diagnostic_families':sum(map(len,diag.values())),'train_counts':dict(collections.Counter(x['intent']for x in new)),'train_strata':dict(collections.Counter(x['stratum']for x in new)),'diagnostic_counts':dict(collections.Counter(x['intent']for x in diagnostic)),'architecture':'unchanged d64, 2 blocks,4 heads,64 byte tokens,INT4/INT8,47066 bytes','tool_argument_operation':'metadata separate; raw six-way classifier is only supervised on intent, decoder supplies argument/operation. Invalid capability/context labels reject.'}
(D/'protocol.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');print(json.dumps(plan,ensure_ascii=False))
