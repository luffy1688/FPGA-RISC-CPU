from pathlib import Path
import time,sys,subprocess,json,re
def finish_position_candidate(r):
 d=r/'07_runs/development/resource_trials/integrated/full_model';tool=r/'05_tools/board';end=time.monotonic()+7200
 h=Path(sys.argv[3])if len(sys.argv)>3 else d
 assert d.resolve()==h.resolve()or d.resolve()in h.resolve().parents,'Hardware output must stay within the selected candidate'
 while time.monotonic()<end:
  log=(h/'flow_stdout.log').read_text(encoding='utf-8',errors='replace')
  runtime=log
  if 'Analyzing project file'in log:
   pre,runtime=log.split('Analyzing project file',1)
   pre_errors=[x for x in pre.splitlines()if x.startswith('E:')]
   if pre_errors:
    assert len(pre_errors)==6 and all(('taskMap'in x or 'device_map/pangu_200pro_clocked_board.dmr'in x or('E: Flow-0163: Failed to parse file'in x and re.search(r'at line (33|34|35)\.',x)))for x in pre_errors),'Unexpected PDS preparse error'
  if any(x.startswith('E:')for x in runtime.splitlines()):raise RuntimeError('PDS runtime error; not programming')
  if 'Process "Generate Bitstream" done.'in log:
   for action in ['compile','synthesize','dev_map','pnr','report_timing','gen_bit_stream']:
    assert re.search(r'Executing : '+action+r'[^\n]*successfully\.',runtime),action
   break
  time.sleep(1)
 else:raise TimeoutError('PDS still running; not programmed')
 sta=(h/'report_timing/pangu_200pro_clocked_board.rtr').read_text(encoding='utf-8',errors='replace')
 rows=re.findall(r'^ system_clk\s+system_clk\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(\d+)\s+(\d+)',sta,re.M)
 assert 'Design Summary : All Constraints Met.'in sta and len(rows)==4 and all(float(a)>=0 and float(b)==0 and int(c)==0 for a,b,c,_ in rows),'STA failed'
 print('FINAL_PDS_STA_PASS',rows,flush=True)
 assert not(d/'bootstrap_921600.json').exists()and not(d/'program_ram.log').exists(),'Refusing overwrite of physical evidence'
 boot=subprocess.Popen([sys.executable,str(tool/'bootstrap_link.py'),str(d/'bootstrap_921600.json'),'experimental_position_fusion_oct30'],cwd=str(tool),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);time.sleep(.6)
 if boot.poll()is not None:
  early,_=boot.communicate();raise RuntimeError('Serial listener failed before RAM programming: '+early)
 try:
  with(d/'program_ram.log').open('w')as out:
   p=subprocess.run(['D:/Tool/PDS/PDS_2022.2-SP6.4/bin/cdt_cfg_shell.exe','-file',str(d/'program_ram.tcl')],cwd=str(d),stdout=out,stderr=subprocess.STDOUT,timeout=900)
  plog=(d/'program_ram.log').read_text(encoding='utf-8',errors='replace');assert p.returncode==0 and 'Executing : cfg_program -device_index 0 successfully.'in plog,plog[-2000:]
  status=int(re.findall(r'Status Register: 0x([0-9a-fA-F]+)',plog)[-1],16);assert status&(1<<12)and status&(1<<19)and not status&((1<<27)|(1<<21)|31),hex(status)
  out,_=boot.communicate(timeout=100);print(out.strip(),flush=True);assert boot.returncode==0 and json.loads((d/'bootstrap_921600.json').read_text(encoding='utf-8'))['passed']
 except BaseException:
  if boot.poll()is None:boot.terminate();boot.wait(10)
  raise
 print('FINAL_RAM_BOOTSTRAP_PASS',hex(status),flush=True)
 from native_latency import Win32Serial,Runner
 e=dict(samples=[],rx_chunks=[],initial_rx=[],source='physical_adc_readiness',failures=[]);serial=Win32Serial('COM10',921600)
 try:
  runner=Runner(serial,e,10,'text');runner.ready=True
  for _ in range(10):
   value=runner.request('read temp','adc_readiness')['result']
   if value.get('execute')==0:break
   time.sleep(.1)
  assert value.get('execute')==0,value
  e['passed']=True;e['driver_status']=serial.errors()
 finally:
  serial.close();(d/'adc_readiness.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('PHYSICAL_ADC_READY',flush=True)
 for proto in ['text','framed']:
  subprocess.run([sys.executable,str(tool/'native_latency.py'),'--port','COM10','--baud','921600','--assume-ready','--protocol',proto,'--commands-json',str(d/'benchmark_commands.json'),'--repeat','10','--output',str(d/('native_'+proto+'_921600.json'))],cwd=str(r),check=True)
  print('FINAL_NATIVE_'+proto.upper()+'_PASS',flush=True)
 subprocess.run([sys.executable,str(tool/'verify_link_board.py'),str(r),'1200','--candidate','position_fusion','--bootstrap-json',str(d/'bootstrap_921600.json')],cwd=str(r),check=True)
 print('FINAL_PHYSICAL_ACCEPTANCE_PASS',flush=True)

r=Path(sys.argv[1]);candidate=sys.argv[2] if len(sys.argv)>2 else 'link_kernel'
if candidate=='position_fusion':
 finish_position_candidate(r)
 sys.exit(0)
assert candidate in ['link_kernel','ai_pipeline']
d=r/'07_runs/development'/candidate;lat=d if candidate=='ai_pipeline' else r/'07_runs/development/link_latency'
end=time.monotonic()+1000
while time.monotonic()<end:
 log=(d/'flow_stdout.log').read_text(encoding='utf-8',errors='replace')
 if any(x.startswith('E:')for x in log.splitlines()):raise RuntimeError('PDS error; inspect flow_stdout')
 if 'Process "Generate Bitstream" done.'in log:break
 time.sleep(1)
else:raise TimeoutError('PDS did not complete')
sta=(d/'report_timing/pangu_200pro_clocked_board.rtr').read_text(encoding='utf-8',errors='replace')
assert 'Design Summary : All Constraints Met.'in sta,'Candidate failed STA'
clock_rows=re.findall(r'^ system_clk\s+system_clk\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(\d+)\s+(\d+)',sta,re.M)
assert len(clock_rows)==4 and all(float(a)>=0 and float(b)==0 and int(c)==0 for a,b,c,_ in clock_rows),'Setup/hold corner failed'
cmd=[str(d/'program_ram.tcl')]
with (d/'program_stdout.log').open('w')as out,(d/'program_stderr.log').open('w')as err:
 subprocess.run(['D:/Tool/PDS/PDS_2022.2-SP6.4/bin/cdt_cfg_shell.exe','-file',str(d/'program_ram.tcl')],cwd=str(r),stdout=out,stderr=err,check=True,timeout=900)
log=(d/'program_stdout.log').read_text(encoding='utf-8',errors='replace');assert 'Executing : cfg_program -device_index 0 successfully.'in log and 'Status Register: 0x001ffca0.'in log,log[-2500:]
end=time.monotonic()+30
while time.monotonic()<end and not(lat/'bootstrap_921600.json').exists():time.sleep(.2)
boot=json.loads((lat/'bootstrap_921600.json').read_text(encoding='utf-8'));assert boot['passed'],boot['failures']
py=sys.executable;tool=r/'05_tools/board';common=['--port','COM10','--baud','921600','--assume-ready']
for proto in ['text','framed']:
 dest=lat/('native_'+proto+'_921600.json')
 subprocess.run([py,str(tool/'native_latency.py'),*common,'--protocol',proto,'--commands-json',str(lat/'benchmark_commands.json'),'--repeat','10','--output',str(dest)],cwd=str(r),check=True)
if candidate=='link_kernel':
 subprocess.run([py,str(tool/'check_framed_rpc.py'),*common,'--output',str(lat/'framed_rpc_acceptance.json')],cwd=str(r),check=True)
subprocess.run([py,str(tool/'verify_link_board.py'),str(r)],cwd=str(r),check=True)
(lat/'physical_workflow.json').write_text(json.dumps(dict(passed=True,ram_only=True,status_hex='0x001ffca0',clock_hz=40500000,uart_baud=921600,no_driver_changes=True,scope='Candidate image verified; formal materials unchanged',candidate=candidate,coremark_iterations=1200 if candidate=='ai_pipeline'else 900),indent=2)+'\n')
print('CANDIDATE_PHYSICAL_PASS',flush=True)
