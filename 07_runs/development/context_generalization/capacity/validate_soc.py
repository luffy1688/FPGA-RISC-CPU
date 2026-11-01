from pathlib import Path
import json,re,subprocess
D=Path(__file__).resolve().parent;R=D.parents[3]

def records(text,tag='NR_RESULT '):
 return [json.loads(l[len(tag):]) for l in text.splitlines() if l.startswith(tag)]

st=(D/'selftest.log').read_text(errors='replace');ut=(D/'semantic_uart.log').read_text(errors='replace')
assert 'NR_MODEL_PASS' in st and 'INTEGRATED_MODEL_DONE' in st
assert 'SEMANTIC_UART_PASS' in ut and 'SEMANTIC_UART_FAIL' not in ut
assert 'COREMARK_START_ONLY not_benchmark_completion' in ut
sr=records(st);assert len(sr)==28
assert {(a['case'],a['config'])for a in sr}=={(i,c)for i in range(4)for c in range(7)}
keys=['logits','encoder_logits','context_logits','context_category_logits','context_tool_logits','intent_delta','intent_cascade_delta','intent_cascade_used','intent_repair_used','context_bucket','context_threshold','context_deny','tool','decode','argument','operation']
for a in sr:
 base=next(x for x in sr if x['case']==a['case']and x['config']==0)
 for k in keys:assert a[k]==base[k],('selftest_sw_hw_mismatch',a['case'],a['config'],k)

# Same production C on host, aligned with Python by the separate 5,170-case validation.
cmd=['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'03_sw/model'),str(R/'03_sw/model/byte_tool_model.c'),str(D/'integrated_eval.c'),'-o',str(D/'rtl_host_ref')]
subprocess.run(cmd,check=True)
texts=['led 37','pwm -1','hello','读取计数器']
p=subprocess.run([str(D/'rtl_host_ref')],input='\n'.join(texts)+'\n',text=True,stdout=subprocess.PIPE,check=True)
for i,l in enumerate(p.stdout.splitlines()):
 v=list(map(int,l.split()));assert len(v)==55
 expected={};at=16
 for key,n in [('logits',6),('encoder_logits',6),('context_logits',2),('context_category_logits',9),('intent_delta',5),('context_tool_logits',5),('intent_cascade_delta',5)]:expected[key]=v[at:at+n];at+=n
 expected['intent_cascade_used']=v[at];expected['context_bucket']=v[1];expected['context_threshold']=v[3];expected['context_deny']=v[4];expected['intent_repair_used']=v[6];expected['tool']=v[0]
 base=next(x for x in sr if x['case']==i and x['config']==0)
 for k,value in expected.items():assert base[k]==value,('RTLvsHostC',i,k,base[k],value)

ur=records(ut);fullpwm=[a for a in ur if a['encoder_used']==1 and a['selected_tool']==1 and a['argument']==20 and a['decode']==0]
assert len(fullpwm)==2,[(a['case'],a['config']) for a in fullpwm]
sw,hw=fullpwm
for k in keys:assert sw[k]==hw[k],('full_encoder_sw_hw',k)
assert sw['context_xnd_used']==0 and hw['context_xnd_used']==1
h=hw['context_hardware'];assert (h['loads'],h['jobs'],h['dma_read_bytes'],h['dma_write_bytes'],h['failures'])==(5,5,67648,1088,0)
assert hw['context_hardware_macs']==66560
formal=[a for a in ur if a['model_used']==0];assert len(formal)==4
assert all(a['context_used']==0 and a['encoder_used']==0 and a['cycles']==0 and a['jobs']==0 for a in formal)
assert len([a for a in formal if a['selected_tool']==3 and a['execute']==0])==3
fallback=[a for a in ur if a['encoder_used']==1 and a['selected_tool']==4 and a['execute']==0 and a['context_bucket']==5 and a['context_threshold']==192]
assert fallback,'ambiguous context branch not rerun'
branches=[a for a in ur if a['selected_tool']==3 and a['context_used']==1 and a['decode']==0]
assert any(a['context_threshold']==134 for a in branches)
cr=records(ut,'NR_ACTION ');assert len(cr)==1 and cr[0]['model_used']==0 and cr[0]['selected_tool']==2 and cr[0]['decode']==0
assert ut.count('BINARY_ACCEPT type=')==2
assert ut.count('AUDIT_GUARD_ACCEPT category=')==5

memory={}
for kind in ['interactive','selftest']:
 s=(D/'firmware'/(kind+'.map')).read_text();syms={}
 for l in s.splitlines():
  m=re.match(r'\s*(0x[0-9a-f]+)\s+(__bss_end|__stack_bottom|__stack_top|__ai_const_start|__ai_const_end|__ai_scratch_start|__ai_scratch_used_end)\b',l)
  if m:syms[m.group(2)]=int(m.group(1),16)
 assert len(syms)==7,syms
 assert syms['__bss_end']<=syms['__stack_bottom'] and syms['__stack_top']-syms['__stack_bottom']==8192
 assert syms['__ai_scratch_used_end']<=262144
 memory[kind]=dict(symbols=syms,cpu_margin_bytes=syms['__stack_bottom']-syms['__bss_end'],ai_constants_bytes=syms['__ai_const_end']-syms['__ai_const_start'],ai_scratch_used_bytes=syms['__ai_scratch_used_end']-syms['__ai_scratch_start'],ai_remaining_bytes=262144-syms['__ai_scratch_used_end'],stack_reserved_bytes=8192)

report=dict(passed=True,firmware='software_semantic_capacity_oct30',calibration_revision=2,context_hidden=64,context_outputs=16,selftest_paths=len(sr),case_configs_exact=True,selftest_vs_host_c_exact=True,context_encoder_hardware_software_pair_exact=True,protocol6_uart_pass=True,actual_hardware_dma=dict(loads=5,jobs=5,read_bytes=67648,write_bytes=1088,macs=66560),context_ambiguous_deny_fullencoder_fallback=True,counter_threshold_134_verified=True,strict_chinese_canonical_counter_count=3,canonical_coremark_start_only=True,coremark_benchmark_completed_in_this_harness=False,binary_crc_and_flags_cases=2,host_versus_hardware_scope='Actual RTL SoC with simulated UART divider41 (1M nominal at40.5MHz),firmware physical UART metadata921600; simulated ADC unavailable, no actual temperature measurement; no physical board claim.',selftest_source='selftest.log',selftest_build_scope='Retained pre_permission_guard capacity64 rev2 mathematical verification; weights,quantization and RTL unchanged; no rerun of28paths for permission-only change.',permission_guard_followup_reject_no_io_cases=5,uart_build_scope='Final permission_guard firmware after root rebuild; all UART cases rerun with this interactive.mem.',uart_source='semantic_uart.log',memory=memory,rtl_memory_capacity_changed=False)
(D/'rtl_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
