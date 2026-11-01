#!/usr/bin/env python3
"""Actual RV32 RTL acceptance; frozen board images and prior reports untouched."""
from pathlib import Path
import json,subprocess,hashlib,re
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'07_runs/model/tool_contract_20261027'
EVAL=ROOT/'07_runs/eval/tool_contract_20261027'
def run(command,log):
 with log.open('w') as f:p=subprocess.run(command,cwd=ROOT,text=True,stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(str(command[0])+' failed; '+str(log))
def main():
 import sys
 uart_only="--uart-only" in sys.argv
 sources=[]
 for d in ['01_rtl/cpu','01_rtl/mem','01_rtl/periph','01_rtl/xnd']:sources+=sorted(str(p)for p in (ROOT/d).glob('*.sv'))
 obj=OUT/'obj_soc'
 cmd=['verilator','--cc','--exe','--build','-j','2','--top-module','needle_soc','-GCLK_HZ=27000000','-GBAUD=1000000','-GINIT_FILE="'+str(OUT/'current.mem')+'"','-Wno-UNUSEDSIGNAL','-Wno-UNUSEDPARAM','-Wno-PINCONNECTEMPTY','--Mdir',str(obj)]+sources+[str(ROOT/'01_rtl/soc/needle_soc.sv'),str(ROOT/'05_tools/sim/soc_contract_run.cpp')]
 run(cmd,EVAL/'verilator_build.log');print('RTL_BUILD_COMPLETE',flush=True)
 if not uart_only:
  (OUT/'current.mem').write_bytes((OUT/'selftest.mem').read_bytes())
  run([str(obj/'Vneedle_soc'),'MODEL_DONE','1200000000'],OUT/'selftest.log')
 text=(OUT/'selftest.log').read_text();assert 'NR_MODEL_PASS' in text and 'MODEL_DONE sim_cycles='in text and 'MODEL_ERROR'not in text
 rows=[json.loads(x[10:])for x in text.splitlines()if x.startswith('NR_RESULT ')]
 assert len(rows)==28 and all(x['failures']==0 for x in rows)
 for case in range(4):
  by=[x for x in rows if x['case']==case];assert [x['config']for x in by]==list(range(7))
  assert all(x['logits']==by[0]['logits']for x in by)
  assert all(x['decode']==by[0]['decode'] and x['operation']==by[0]['operation']for x in by)
 print('RTL_MODEL_28_PATHS_PASS',flush=True)
 (OUT/'current.mem').write_bytes((OUT/'interactive.mem').read_bytes())
 run([str(obj/'Vneedle_soc'),'MODEL_UART','1400000000'],OUT/'interactive.log')
 text=(OUT/'interactive.log').read_text()
 assert 'MODEL_UART_DONE' in text and 'NR_BACKEND_ERROR'not in text and 'RTL_TRAP'not in text
 assert text.count('NR_INPUT_ERROR too_long')==1 and text.count('NR_INPUT_ERROR empty')==1
 assert 'Correct operation validated.'in text and 'NR_COREMARK_RETURN'in text and 'ERROR!'not in text
 assert 'PWM_LINE_PASS clocks=27000 high=8100'in text
 result=[json.loads(x[10:])for x in text.splitlines()if x.startswith('NR_RESULT ')]
 assert len(result)==16 and all(x['failures']==0 for x in result),len(result)
 states={x['after']:x for x in [json.loads(t[13:])for t in text.splitlines()if t.startswith('NR_SIM_STATE ')]}
 # after is the one-based command position; after=0 is initial boot.
 expected={i:(37 if i in (1,18,19,20) else 39 if i==2 else 38 if i==3 else 6 if i==4 else 165)for i in range(1,21)}
 for at,value in expected.items():assert states[at]['led']==value,(at,states[at])
 for i,op,arg,val in [(1,1,1,39),(2,2,0,38),(3,2,5,6),(4,0,165,165)]:
  x=result[i];assert x['execute']==0 and x['operation']==op and x['argument']==arg and x['value']==val,(i,x)
 assert result[5]['execute']==0 and result[5]['value']==30 and result[5]['selection_source']==4
 assert result[6]['execute']==0 and result[6]['value']==90 and result[6]['selection_source']==4
 assert result[7]['execute']==2 and result[7]['argument']==7
 for i in [8,9,13]:assert result[i]['selected_tool']==5 and result[i]['execute']==1
 assert result[10]['execute']==0 and result[10]['selected_tool']==3 and result[10]['value']>0
 assert result[11]['execute']==2 and result[11]['value']==0
 assert result[12]['execute']==0 and result[12]['selected_tool']==2
 assert result[14]['config']==0 and result[15]['config']==6 and result[14]['logits']==result[15]['logits']
 core=re.search(r'NR_CYCLES=(\d+) NR_HZ=(\d+) NR_ITERATIONS=(\d+)',text);assert core and int(core[1])/int(core[2])>=10
 report={'schema':'needlervx.tool_contract.rtl.v1','passed':True,'physical_board_verified':False,'model_stage':'tool_contract_20261027','model_selftest_paths':28,'uart_requests':16,'uart_commands':20,'pwm_duty_percent':30,'explicit_pwm_schema_verified':True,'single_led_preservation':True,'pwm_owned_led7_denied':True,'unsupported_commands_have_no_side_effects':True,'empty_and_overlong_recovery':True,'coremark':{'cycles':int(core[1]),'hz_reference':int(core[2]),'iterations':int(core[3]),'crc_valid':True},'config0_config6_led37_inference_cycles':[result[14]['cycles'],result[15]['cycles']],'selftest_results':rows,'uart_results':result,'gpio_states':list(states.values()),'input_manifest':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'interactive.mem',OUT/'selftest.mem',ROOT/'03_sw/model/byte_tool_model.c',ROOT/'03_sw/model/byte_model_data.h',ROOT/'03_sw/model/tool_dispatch.c',ROOT/'03_sw/model/main.c']}}
 (EVAL/'rtl_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('RTL_UART_16_REQUESTS_PASS',json.dumps(report['coremark']),flush=True)
if __name__=='__main__':main()
