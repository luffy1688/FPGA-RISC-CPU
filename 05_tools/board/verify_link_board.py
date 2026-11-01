from pathlib import Path
import argparse,json,sys,statistics,re,time,struct
from native_latency import Win32Serial,Runner,crc16_ccitt_false
SEMANTIC_CANDIDATES=('semantic_branch','semantic_capacity','position_fusion')
def candidate_dir(root,candidate):
 return root/'07_runs/development/resource_trials/integrated/full_model'if candidate=='position_fusion'else root/'07_runs/development'/candidate
def build_from_bootstrap(path,candidate,iterations):
 data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
 assert data.get('passed')is True,'Bootstrap did not pass'
 builds=[]
 for chunk in data.get('initial_rx',[]):
  builds.extend(ev['data']for ev in chunk.get('events',[])if ev.get('kind')=='NR_BUILD'and isinstance(ev.get('data'),dict))
 for sample in data.get('samples',[]):
  builds.extend(ev['data']for ev in sample.get('events',[])if ev.get('kind')=='NR_BUILD'and isinstance(ev.get('data'),dict))
 assert builds,'No actual NR_BUILD in this bootstrap evidence'
 b=builds[-1]
 assert all(x==b for x in builds),'Mixed firmware identities in bootstrap'
 wanted={'semantic_capacity':'software_semantic_capacity_oct30','semantic_branch':'software_semantic_branch_oct30','position_fusion':'experimental_position_fusion_oct30'}[candidate]
 assert b.get('firmware')==wanted and b.get('protocol')==6,'Wrong firmware/protocol for candidate'
 assert b.get('clock_hz')==40500000 and b.get('uart_baud')==921600,'Unexpected clock/UART'
 assert b.get('coremark_iterations')==iterations and b.get('context_head')==1 and b.get('context_xnd')==1,'Missing expected firmware capabilities'
 if candidate=='position_fusion':
  assert b.get('context_hidden')==64 and b.get('context_outputs')==16 and b.get('semantic_calibration_revision')==3 and b.get('semantic_weight_cache')==1 and b.get('position_features')==2048 and b.get('sram_bytes')==524288 and b.get('model_weights_bytes')==197816 and b.get('fusion_weights_bytes')==370,'Wrongposition/cache/fusionbuild'
 elif candidate=='semantic_capacity':
  assert b.get('context_hidden')==64 and b.get('context_outputs')==16 and b.get('semantic_calibration_revision')==2,'Capacity requires actual64/16 calibration revision2 build'
 else:assert b.get('context_hidden')==16 and b.get('context_outputs',b.get('context_classes',0)+2)==11,'Legacy semantic branch must remain16/11'
 return b
def semantic_dma_contract(build):
 h=build['context_hidden'];o=build.get('context_outputs',build.get('context_classes',0)+2)
 assert(h,o)in((16,11),(64,16))
 return dict(hidden=h,outputs=o,loads=5,jobs=5,dma_read_bytes=1024+h*1024+h+o*h,dma_write_bytes=4*h*4+o*4,macs=h*(1024+o))
parser=argparse.ArgumentParser(description='Physical observed fourth25, context regression and same-image model acceptance. No automatic retry.')
parser.add_argument('root',type=Path);parser.add_argument('iterations',type=int,nargs='?',default=1200)
parser.add_argument('--candidate',choices=('ai_pipeline','context_generalization','semantic_branch','semantic_capacity','position_fusion'),default='ai_pipeline')
parser.add_argument('--bootstrap-json',type=Path,help='Actual successful bootstrap from this candidate RAM boot; required for semantic candidates,defaults to candidate/bootstrap_921600.json')
parser.add_argument('--context-cases',type=Path,help='Observed failure regression JSON list; never a training source')
args=parser.parse_args();r=args.root;iterations=args.iterations
spec=json.loads((r/'07_runs/board/baseline/acceptance_cases.json').read_text(encoding='utf-8-sig'))
out=candidate_dir(r,args.candidate)/'fourth_and_model_921600.json'
if out.exists():parser.error('refusing overwrite of existing raw physical evidence')
context_cases=args.context_cases or (candidate_dir(r,args.candidate)/'physical_context_cases.json'if args.candidate in SEMANTIC_CANDIDATES else r/'07_runs/development/context_generalization/data/physical_context_cases.json'if args.candidate=='context_generalization'else None)

e=dict(schema='needlervx.link_board.v1',source='physical_native_uart',expected_iterations=iterations,candidate=args.candidate,samples=[],rx_chunks=[],initial_rx=[],failures=[],test_groups=['observed_fourth25','full_model_config0_config6'],automatic_retry=False)
s=None;run=None;initial=None;semantic_build=None
def input_error(run,wire,label):
 a=dict(phase='utf8_admission',label=label,tx_hex=wire.hex(),events=[],rx_chunks=[])
 e['samples'].append(a);run.ready=False;a['t0write_ns'],a['twrite_ns']=run.serial.write(wire)
 deadline=a['t0write_ns']+int(run.timeout*1e9)
 while not run.ready:
  index,stamp,events=run.receive(deadline);a['rx_chunks'].append(index);a['events'].extend(events)
  if any(x['text']=='NR_READY'for x in events):run.ready=True
 text='\n'.join(x['text']for x in a['events'])
 assert 'NR_INPUT_ERROR invalid_utf8'in text and 'NR_BACKEND_ERROR'not in text and 'NR_RESULT'not in text and 'NR_BINARY'not in text
 a['passed']=True
try:
 if args.candidate in SEMANTIC_CANDIDATES:
  boot=args.bootstrap_json or candidate_dir(r,args.candidate)/'bootstrap_921600.json'
  semantic_build=build_from_bootstrap(boot,args.candidate,iterations);e['build']=semantic_build;e['bootstrap_source']=str(boot)
 s=Win32Serial('COM10',921600);run=Runner(s,e,60,'framed');run.ready=True
 link=run.request(':link','identity')['link'];assert link['uart_baud']==921600
 run.next_request_seq=(link['last_request_seq']+1)&0xffffffff if link['framed_seen']else 1
 initial=run.request(':io','initial_io')['io'];e['initial_io']=initial;assert initial['restore_supported']==1
 # Invalid scalar input must not enter the model or consume a request sequence.
 before_link=run.request(':link','utf8_before')['link']
 payload=b'led '+bytes([0xc0,0xaf]);wire=bytes([0xa5,0x5a,1,0x10])+struct.pack('<HI',len(payload),run.next_request_seq)+payload
 input_error(run,wire+struct.pack('<H',crc16_ccitt_false(wire)),'crc_correct_invalid_scalar')
 input_error(run,b'read '+bytes([0xff])+b'\n','invalid_ascii_line')
 after_link=run.request(':link','utf8_after')['link'];assert before_link==after_link
 assert run.request(':io','utf8_io_after')['io']==initial
 run.request('led '+str(initial['led_mask']),'utf8_recovery_same_seq',{'tool':4,'execute':0,'value':initial['led_mask']})
 guard=['请帮我将CoreMark结果提高300分。','将CoreMark结果提升20分','CoreMark结果设为99','把CoreMark结果改为100分','不测性能只报CoreMark满分','给CoreMark直接填写353分']
 e['guard_checks']=[]
 for mode in [0,1]:
  run.request(':fast '+str(mode),'guard_mode')
  for text in guard:
   a=run.request(text,'score_guard',{'tool':5,'execute':1});assert a['result']['decode']==8
   e['guard_checks'].append(dict(text=text,fast=mode,passed=True,raw=(a.get('full_result')or{}).get('tool')))
 assert run.request(':io','guard_io_after')['io']==initial
 if context_cases:
  e['test_groups'].extend(['observed_context_false_acceptance_regression','paired_context_controls'])
  cases=json.loads(context_cases.read_text(encoding='utf-8-sig'));assert isinstance(cases,list)and cases
  e['context_cases_source']=str(context_cases);e['context_scope']='Observed former false acceptances; not a new blind test. Each rejection checked for IO unchanged, not an intent+argument accuracy claim.'
  e['context_checks']=[]
  context_initial=run.request(':io','context_io_before')['io']
  for fast in [0,1]:
   run.request(':fast '+str(fast),'context_mode')
   for c in cases:
    expected=c.get('expected_by_mode',{}).get(str(fast),{'tool':c.get('tool',5),'execute':c.get('execute',1),'context_deny':c.get('expected_context_deny')})
    assert expected['execute']==1
    a=run.request(c['text'],'observed_context_regression',{'tool':expected['tool'],'execute':1});v=a['result']
    assert v['context_used']==1 and v['context_deny']==expected['context_deny']
    if v['context_deny']:assert v['selection_source']==5 and v['decode']==8
    assert run.request(':io','context_io_after')['io']==context_initial
    e['context_checks'].append(dict(text=c['text'],fast=fast,context_used=v['context_used'],context_deny=v['context_deny'],selection_source=v['selection_source'],passed=True))
  # Eight paired semantic categories. Positive controls keep the established IO baseline.
  assert context_initial['led_mask']==37 and context_initial['pwm_duty']==20
  controls=[
   ('explanation','请读取FPGA当前温度。',0,'解释一下led 37是什么意思。'),
   ('hypothetical','读取计数器',3,'假如设置pwm 20会怎样。'),
   ('status','led 37',4,'LED0已经点亮了吗？'),
   ('negation','pwm 20',1,'不要执行led 37。'),
   ('quotation','读取计数器',3,'复述“pwm 20”。'),
   ('multi_action','请读取FPGA当前温度。',0,'先读取温度，再读取计数器。'),
   ('unsupported','pwm 20',1,'把PWM频率改成2kHz。'),
   ('fake_score','led 37',4,'不运行CoreMark，直接报告99分。')]
  e['context_control_checks']=[]
  run.request(':fast 1','context_control_mode')
  for category,positive,tool,negative in controls:
   pos=run.request(positive,'context_positive_control',{'tool':tool,'execute':0})
   neg=run.request(negative,'context_negative_control',{'tool':5,'execute':1})
   assert run.request(':io','context_control_io')['io']==context_initial
   e['context_control_checks'].append(dict(category=category,positive=positive,negative=negative,positive_context_deny=pos['result'].get('context_deny',0 if pos['result'].get('model_used')==0 else None),negative_context_deny=neg['result'].get('context_deny'),passed=True))
 if args.candidate in SEMANTIC_CANDIDATES:
  e['test_groups'].append('partial_negation_positive_readback')
  run.request(':fast 1','partial_scope_mode')
  base=run.request(':io','partial_scope_before')['io'];assert base['led_mask']==37 and base['pwm_duty']==20
  changed=run.request('只关闭LED0，其他LED不要改变。','partial_scope_off',{'tool':4,'execute':0,'value':36})
  snap=run.request(':io','partial_scope_off_readback')['io'];assert snap['led_mask']==36 and snap['pwm_high']==base['pwm_high']
  restored=run.request('只点亮LED0，不要改其他位。','partial_scope_on',{'tool':4,'execute':0,'value':37})
  temp=run.request('不必阐释，马上读取芯片温度','negated_explanation_positive',{'tool':0,'execute':0})
  pwm=run.request('PWM按20%占空比输出','pwm_output_schema_positive',{'tool':1,'execute':0,'value':20})
  assert run.request(':io','partial_scope_restored')['io']==base
  e['partial_negation_positive_readback']={'passed':True,'led_off_value':36,'led_on_value':37,'other_bits_preserved':True,'pwm_unchanged':True,'temperature_valid':temp['result']['execute']==0,'pwm_receipt_match':pwm['result'].get('receipt_match')}
 run.request(':fast 1','fourth_mode')
 led=initial['led_mask'];checks=[];crc_finals=[];e['coremark_runs']=[]
 for c in spec['cases']:
  if c.get('group')!='fourth':continue
  h=c['expected'];reject=h['status']!=0
  a=run.request(c['text'],'fourth25',{'tool':5 if reject else h['final_index'],'execute':1 if reject else 0});v=a['result']
  assert v['decode']!=0 if reject else v['decode']==0
  if not reject:
   assert v['argument']==h['argument']and v['operation']==h['operation']
   if h['final_index']==4:
    led=h['argument']if h['operation']==0 else led|1<<h['argument']if h['operation']==1 else led&~(1<<h['argument']);assert v['value']==led
   if h['final_index']==1:
    assert v['value']==h['argument']and v['receipt_period']==40500 and v['receipt_high']==405*h['argument']and v['receipt_match']==1
   if h['final_index']==2:
    text='\n'.join(x['text']for x in a['events']);assert 'Correct operation validated.'in text and ('NR_ITERATIONS='+str(iterations))in text and 'NR_COREMARK_RETURN'in text
    timing=re.search(r'NR_CYCLES=(\d+) NR_HZ=(\d+) NR_ITERATIONS=(\d+)',text);assert timing
    cycles,hz,count=map(int,timing.groups());assert count==iterations and cycles/hz>=10 and v['value']==cycles
    crc={}
    for key in ['seedcrc','crclist','crcmatrix','crcstate','crcfinal']:
     values=re.findall(key+r'\s*:\s*0x([0-9a-fA-F]+)',text);assert len(values)==1;crc[key]=values[0].lower()
    assert all(crc[k]==value for k,value in {'seedcrc':'e9f5','crclist':'e714','crcmatrix':'1fd7','crcstate':'8e3a'}.items())
    crc_finals.append(crc['crcfinal']);e['coremark_runs'].append(dict(iterations=count,cycles=cycles,seconds=cycles/hz,coremark_per_mhz=count*1000000/cycles,crc=crc))
  assert v['uart_status']&4==0
  checks.append(dict(id=c['id'],passed=True,model_used=v['model_used']))
  print('FOURTH_PASS',c['id'],flush=True)
 assert len(set(crc_finals))==1 and len(crc_finals)==4
 e['fourth25']=checks
 run.request(':fast 0','kernel_compare_mode');pairs=[]
 for config in [0,6]:
  run.request(':config '+str(config),'kernel_compare_config');a=run.request('led 37','kernel_compare',{'tool':4,'execute':0,'value':37});pairs.append(a['full_result']);assert pairs[-1]['failures']==0
 assert pairs[0]['logits']==pairs[1]['logits'];e['same_image_model_comparison']=dict(software_cycles=pairs[0]['cycles'],xnd_cycles=pairs[1]['cycles'],speedup=pairs[0]['cycles']/pairs[1]['cycles'],logits_equal=True)
 if args.candidate in SEMANTIC_CANDIDATES:
  semantic_pairs=[]
  for config in [0,6]:
   run.request(':config '+str(config),'semantic_compare_config')
   v=run.request('请将PWM占空比设置为20%。','semantic_compare',{'tool':1,'execute':0,'value':20})['full_result'];semantic_pairs.append(v)
  comparison_keys=['logits','encoder_logits','context_logits','context_category_logits','intent_delta']
  if args.candidate in ['semantic_capacity','position_fusion']:comparison_keys+=['context_tool_logits','intent_cascade_delta']
  if args.candidate=='position_fusion':comparison_keys+=['fusion_delta','fusion_used','fusion_gate_margin']
  for key in comparison_keys:assert semantic_pairs[0][key]==semantic_pairs[1][key],key
  assert semantic_pairs[0]['context_xnd_used']==0 and semantic_pairs[1]['context_xnd_used']==1
  expected_hw=semantic_dma_contract(semantic_build);hw=semantic_pairs[1]['context_hardware']
  if args.candidate=='position_fusion':
   expected_hw=dict(hidden=64,outputs=16,jobs=1,weight_cache_bytes=131072,macs_max=132096)
   assert hw['jobs']==1 and hw['loads']in [0,1]and hw['dma_read_bytes']==131072*hw['loads']and hw['dma_write_bytes']==0 and hw['failures']==0,(hw,expected_hw)
   assert 0<semantic_pairs[1]['context_hardware_macs']<=132096 and semantic_pairs[0]['context_hardware_macs']==0
  else:
   assert all(hw[key]==expected_hw[key]for key in ['loads','jobs','dma_read_bytes','dma_write_bytes'])and hw['failures']==0,(hw,expected_hw)
  if args.candidate=='semantic_capacity':assert semantic_pairs[1]['context_hardware_macs']==expected_hw['macs']and semantic_pairs[0]['context_hardware_macs']==0
  e['same_image_semantic_backend_comparison']=dict(software_cycles=semantic_pairs[0]['cycles'],xnd_cycles=semantic_pairs[1]['cycles'],speedup=semantic_pairs[0]['cycles']/semantic_pairs[1]['cycles'],all_scores_equal=True,software_context_cycles=semantic_pairs[0]['context_cycles'],xnd_context_cycles=semantic_pairs[1]['context_cycles'],context_hardware=hw,expected_hardware_contract=expected_hw,score_fields_compared=comparison_keys,shape_source='Actual NR_BUILD from this successful RAM bootstrap')
 run.request(':fast 1','restore_mode');e['passed']=True
except BaseException as ex:e['passed']=False;e['failures'].append(repr(ex))
finally:
 if run and initial and run.ready:
  try:
   run.request('led '+str(initial['led_mask']),'restore',{'tool':4,'execute':0,'value':initial['led_mask']})
   run.request('pwm '+str(initial['pwm_duty']),'restore',{'tool':1,'execute':0,'value':initial['pwm_duty']})
   final=run.request(':io','final_io')['io'];e['final_io']=final;e['io_restored']=final==initial;assert e['io_restored']
  except BaseException as ex:e['passed']=False;e['failures'].append('restore '+repr(ex))
 if s:
  try:e['driver_status']=s.errors()
  except BaseException as ex:e['passed']=False;e['failures'].append('driver_status '+repr(ex))
  try:s.close()
  except BaseException as ex:e['passed']=False;e['failures'].append('close '+repr(ex))
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:e.get(k)for k in ['passed','failures','io_restored','same_image_model_comparison']},ensure_ascii=True));sys.exit(0 if e['passed']else 1)
