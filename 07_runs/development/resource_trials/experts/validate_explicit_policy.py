from pathlib import Path
import ctypes as C,subprocess,itertools,json
R=Path('/work/LUO/NeedleRV-X');D=Path(__file__).resolve().parent
subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC','-I'+str(R/'03_sw/model'),str(D/'private_byte_tool_model.c'),'-o',str(D/'explicit_policy.so')],check=True)
class Req(C.Structure):_fields_=[('tool',C.c_int),('arg',C.c_int32),('status',C.c_int),('margin',C.c_int32),('op',C.c_int),('source',C.c_int)]
f=C.CDLL(str(D/'explicit_policy.so')).nr_tool_decode_machine;f.argtypes=[C.c_char_p,C.c_uint32,C.POINTER(Req)];f.restype=C.c_int
pos=[]
def put(t,tool,arg,op=0,status=0):
 if len(t.encode())<=64:pos.append((t,tool,arg,op,status))
for prefix,action,hw,noun,time,value,suffix in itertools.product(['','请','劳烦您','请把这次任务办好：'],['查看','读取','返回','读出'],['','硬件'],['计数器','计数寄存器'],['','目前的','当前的'],['读数','数值','值'],['','一下','好吗']):put(prefix+action+hw+noun+time+value+suffix,3,0)
for prefix,single,verb,bit,other,noun,keep,state in itertools.product(['','请'],['','只','单独'],['点亮','关闭'],range(8),['其他','其余'],['LED','位'],['保持','维持'],['不变','原状','原样']):put(prefix+single+verb+'LED'+str(bit)+'，'+other+noun+keep+state,4,bit,1 if verb=='点亮'else 2)
for prefix,pre,desc,verb,v,pct in itertools.product(['','请'],['把','将'],['','的占空比'],['改为','设置为','调整为'],[0,1,20,100,101],['','%']):put(prefix+pre+'PWM'+desc+verb+str(v)+pct,1 if v<=100 else 5,v if v<=100 else 0,status=0 if v<=100 else 3)
for prefix,v in itertools.product(['','please '],[0,1,7,99,255,256]):put(prefix+'write '+str(v)+' to led',4 if v<=255 else 5,v if v<=255 else 0,status=0 if v<=255 else 3)
for prefix,verb,noun,v in itertools.product(['','please '],['configure','write','set'],['led','pwm'],[0,1,7,99]):put(prefix+verb+' '+noun+' '+str(v),4 if noun=='led'else 1,v)
for t,tool,arg,op,status in pos:
 b=t.encode();r=Req();assert f(b,len(b),C.byref(r))==1,('miss',t)
 assert (r.tool,r.arg,r.op,r.status)==(tool,arg,op,status),('bad',t,(r.tool,r.arg,r.op,r.status),(tool,arg,op,status))
# Uniform forbidden frames are transformations,not handpicked model examples.
valid=[x[0]for x in pos if x[4]==0];seed=valid[::max(1,len(valid)//100)]
negative=[]
for t in seed:
 for pre,post in [('不要',''),('假如',''),('解释',''),('“','”'),('','，然后读取温度'),('','，并关闭LED1')]:
  s=pre+t+post
  if len(s.encode())<=64:negative.append(s)
negative+=['请把这次任务办好：假如读取计数器','请把这次任务办好：不要关闭LED0','请把这次任务办好：摘录下面的话：点亮LED0','点亮LED0，其他','点亮LED0，其他LED','点亮LED0，其他LED保持','点亮LED0，其他LED维持','查看硬件计数器目前的','把PWM频率改为20%','write 1 to led and read temp','write -1 to led','write 1.5 to led','把PWM改为20%并点亮LED0','单独点亮LED0，其余LED保持原状再关闭LED1']
for t in negative:
 b=t.encode();r=Req();assert f(b,len(b),C.byref(r))==0,('false_rule',t,r.tool,r.arg)
r=dict(passed=True,cartesian_positive=len(pos),uniform_negative_mutations=len(negative),scope='Finite explicit whole-input grammar/parser tests only,never neuralaccuracy. Negation,hypothesis,explanation,quoting,secondactionsandtruncatedpreserveclausescannotenterdirectroute.',production_modified=False)
(D/'explicit_policy_validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(r)
