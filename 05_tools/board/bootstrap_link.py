from pathlib import Path
import sys,json,datetime,time
from native_latency import Win32Serial,Runner
out=Path(sys.argv[1]);e=dict(samples=[],rx_chunks=[],initial_rx=[],source='native_physical_bootstrap',failures=[])
s=None
try:
 s=Win32Serial('COM10',921600);run=Runner(s,e,900,'text')
 expected=sys.argv[2]if len(sys.argv)>2 else None
 if expected:
  e['expected_firmware']=expected;seen_build=False;deadline=time.perf_counter_ns()+900000000000
  while not run.ready:
   index,stamp,events=run.receive(deadline);e['initial_rx'].append({'chunk':index,'events':events})
   for event in events:
    if event.get('kind')=='NR_BUILD'and event.get('data',{}).get('firmware')==expected:seen_build=True;e['boot_build']=event['data']
    if event['text']=='NR_READY'and seen_build:run.ready=True
 else:run.wait_ready()
 # Initial evidence stores RX chunk indexes in some runner versions; use all decoded events if needed.
 e['link']=run.request(':link','identity')['link'];assert e['link']['uart_baud']==921600
 e['manifest']=run.request(':tools','manifest')
 e['initial_io']=run.request(':io','initial_io')['io']
 run.request('led 37','establish_demo_baseline',{'tool':4,'execute':0,'value':37})
 run.request('pwm 20','establish_demo_baseline',{'tool':1,'execute':0,'value':20})
 e['final_io']=run.request(':io','final_io')['io'];assert e['final_io']['restore_supported']==1
 e['passed']=True
except BaseException as ex:e['passed']=False;e['failures'].append(repr(ex))
finally:
 if s:
  try:e['driver_status']=s.errors()
  except BaseException as ex:e['passed']=False;e['failures'].append('driver_status '+repr(ex))
  try:s.close()
  except BaseException as ex:e['passed']=False;e['failures'].append('close '+repr(ex))
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:e[k]for k in ['passed','failures']},ensure_ascii=True));sys.exit(0 if e['passed']else 1)
