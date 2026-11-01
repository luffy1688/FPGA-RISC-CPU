
from pathlib import Path
import json,ctypes as C,re,statistics
R=Path('/work/LUO/NeedleRV-X');S=Path(__file__).resolve().parent
selftext=(S/'selftest.log').read_text();assert 'NR_MODEL_PASS'in selftext and 'SELFTEST_TRAP'not in selftext
rows=[json.loads(l[10:])for l in selftext.splitlines()if l.startswith('NR_RESULT ')];assert len(rows)==28 and len({(v['case'],v['config'])for v in rows})==28
lib=C.CDLL(str(S/'host_boundary.so'));lib.integrated_cpu.argtypes=[C.c_char_p,C.c_uint32,C.POINTER(C.c_int32)]
texts=['led 37','pwm -1','hello','读取计数器'];gold=[]
keys=['encoder_logits','context_logits','context_category_logits','context_tool_logits','intent_delta','intent_cascade_delta','logits','fusion_delta']
for t in texts:
 out=(C.c_int32*48)();wire=t.encode();assert lib.integrated_cpu(wire,len(wire),out)==48;gold.append(list(out))
for v in rows:
 flat=[]
 for k in keys:flat+=v[k]
 flat += [v[k]for k in ['fusion_used','fusion_gate_margin','context_bucket','context_threshold','context_deny']]
 assert flat==gold[v['case']],(v['case'],v['config'],'selftestfields')
 if v['context_xnd_used']:
  h=v['context_hardware'];assert h['jobs']==1 and h['loads']in[0,1]and h['dma_read_bytes']==h['loads']*131072 and h['dma_write_bytes']==0 and h['failures']==0
  assert 0<v['context_hardware_macs']<=132096
uart=(S/'semantic_uart.log').read_text(errors='replace');assert 'RESOURCE_UART_PASS'in uart and 'RESOURCE_UART_FAIL'not in uart
blocks=[];text=None;records=[]
for line in uart.splitlines():
 if line.startswith('UART_REQUEST '):text=line[13:]
 if line.startswith('NR_RESULT '):
  v=json.loads(line[10:]);records.append(dict(text=text,result=v))
  if v['model_used']==1 and text and '[start only]'not in text:
   wire=text.encode();out=(C.c_int32*48)();assert lib.integrated_cpu(wire,len(wire),out)==48
   flat=[]
   for k in keys:flat+=v[k]
   flat += [v[k]for k in ['fusion_used','fusion_gate_margin','context_bucket','context_threshold','context_deny']]
   assert flat==list(out),('UARTfullCexact',text)
# Same original encoder/full pipeline with software and both hardware backends.
pairs=[v['result']for v in records if v['text']=='请将PWM占空比设置为20%。'and v['result']['model_used']==1]
assert len(pairs)==2 and pairs[0]['config']==0 and pairs[1]['config']==6
for k in keys+['fusion_used','fusion_gate_margin','context_bucket','context_threshold','context_deny']:assert pairs[0][k]==pairs[1][k],k
ui=[]
for v in records:
 a=v['result']
 ui.append(dict(text=v['text'],model_used=a['model_used'],cycles=a['cycles'],decision_cycles=a['decision_cycles'],context_cycles=a['context_cycles'],encoder_cycles=a['encoder_cycles'],execute=a['execute'],tool=a['selected_tool'],context_hardware=a['context_hardware']))
maptext=(S/'firmware/interactive.map').read_text()
def address(name):return int(re.search(r'0x([0-9a-fA-F]+)\s+'+name+r'\s*=',maptext).group(1),16)
used=address('__ai_scratch_used_end');bss=address('__bss_end');stack=address('__stack_bottom')
assert bss<=stack and used<=0x80000
report=dict(passed=True,scope='Server RTL/fullCPU observed regression only. No board download,physicaltiming,ADCtemperature,STA orvendorresourceclaim for this candidate.',firmware='experimental_position_fusion_oct30',model_weights_bytes=197816,sram_bytes=524288,semantic_cache_bytes=131072,mac_lanes=8,selftest=dict(paths=28,exact_fields=28*48,clock_cycles=int(re.search(r'clocks=(\d+)',selftext).group(1)),full_hardware_context_calls=sum(v['context_xnd_used']for v in rows),cache_cold_loads=sum(v['context_hardware']['loads']for v in rows if v['context_xnd_used'])),uart=dict(passed=True,clock_cycles=int(re.search(r'RESOURCE_UART_PASS clocks=(\d+)',uart).group(1)),real_full_records=len(records),all_full_scores_host_C_exact=True,original_encoder_and_sidecache_same_math=True,coremark_scope='Start only,not benchmark completion',examples=ui),full_pwm_comparison=dict(software_cycles=pairs[0]['cycles'],hardware_cycles=pairs[1]['cycles'],speedup=pairs[0]['cycles']/pairs[1]['cycles'],software_context_cycles=pairs[0]['context_cycles'],hardware_context_cycles=pairs[1]['context_cycles']),memory=dict(cpu_bss_end=bss,stack_bottom=stack,full_stack_bytes=8192,cpu_margin=stack-bss,ai_scratch_used_end=used,ai_remaining=0x80000-used),necessary_failure_fixes=['Expansionheader XND_BASE was incorrectlychangedto0x80000000; restored0x40000000 and compiletimeaddresschecksadded','DMAabort finalword successrace fixed and fault-injectionregression passed','OldUART expectedmodel3 forPWM becamewrongafterliteralgrammar model0; testedreal learnedtemperaturepath separately'])
(S/'rtl_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k in ['passed','selftest','full_pwm_comparison','memory']},ensure_ascii=False))
