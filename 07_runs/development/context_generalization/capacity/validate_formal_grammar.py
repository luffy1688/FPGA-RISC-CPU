from pathlib import Path
import sys,json,subprocess,itertools
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2]
prefix=['','麻烦您','劳烦您','帮个忙','麻烦','劳烦','帮我','请'];counter_actions=['读取一下','查询一下','读一下','读取','返回','查询','获取'];counter_objects=['硬件计数寄存器读数','硬件计数器当前值','计数器当前值','当前计数器数值','硬件计数器','计数器'];core_actions=['完成一次','运行一次','执行一次','启动一次','运行','执行','启动'];core_objects=['CoreMark性能基准测试','CoreMark性能测试','CoreMark基准测试','CoreMark测试','CoreMark跑分','CoreMark'];suffix=['','一下吧','一下','可以吗','好吗','吧'];punct=['','。','！','？'];positive=[]
for tool,actions,objects in [(3,counter_actions,counter_objects),(2,core_actions,core_objects)]:
 for p,a,o,t,z in itertools.product(prefix,actions,objects,suffix,punct):
  text=p+a+o+t+z
  if len(text.encode())<=64:positive.append(dict(text=text,tool=tool))
# Negative transformations add semantic content that the formal whole-input path must not consume.
seeds=['请返回硬件计数寄存器读数一下','劳烦您查询硬件计数器好吗','帮个忙完成一次CoreMark跑分好吗','请执行CoreMark基准测试']
negative=[]
for seed in seeds:
 for p in ['不要','假如','解释一下','引用原话：','如果','请逐字照抄：','这次我没让你']:
  t=p+seed
  if len(t.encode())<=64:negative.append(t)
 for tail in ['然后读取温度','，再读温度','；设置PWM20%','这是什么意思','的原理','仅作为假设','，别执行']:
  t=seed+tail
  if len(t.encode())<=64:negative.append(t)
 for a,b in [('“','”'),('"','"'),("'","'"),('（','）')]:
  t=a+seed+b
  if len(t.encode())<=64:negative.append(t)
def run(ts):
 p=subprocess.run([str(D/'formal_grammar_eval')],input='\n'.join(ts)+'\n',stdout=subprocess.PIPE,text=True,check=True);r=[list(map(int,l.split()))for l in p.stdout.splitlines()];assert len(r)==len(ts);return r
pr=run([a['text']for a in positive]);fails=[dict(case=a,actual=v)for a,v in zip(positive,pr)if not(v[0]==1 and v[1]==a['tool']and v[2]==0 and v[3]==0 and v[4]==0 and v[5]==1)]
nr=run(negative);nfail=[dict(text=t,actual=v)for t,v in zip(negative,nr)if v[0]!=0]
r=json.loads((D/'integrated_revision2.json').read_text());r['strict_chinese_formal_grammar']=dict(scope='Whole-input bounded Chinese Cartesian formal grammar; explicitly rule route/model0,not neural accuracy or heldoutgeneralization',positive_cartesian_count=len(positive),positive_passed=len(positive)-len(fails),negative_context_transformations=len(negative),negative_all_miss=not nfail,positive_failures=fails[:20],negative_failures=nfail[:20]);(D/'integrated_revision2.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r['strict_chinese_formal_grammar'],ensure_ascii=True))
