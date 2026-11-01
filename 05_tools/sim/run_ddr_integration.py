#!/usr/bin/env python3
"""Run optional SoC DDR word-path simulation in success and fault modes.
The HMIC model is a simplified UI behavior model, never a PHY or bandwidth test."""
from pathlib import Path
import json, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'07_runs'/'ddr'; out.mkdir(parents=True,exist_ok=True)
rtl=[*sorted((ROOT/'01_rtl'/'cpu').glob('*.sv')),*sorted((ROOT/'01_rtl'/'mem').glob('*.sv')),*sorted((ROOT/'01_rtl'/'periph').glob('*.sv')),*sorted((ROOT/'01_rtl'/'xnd').glob('*.sv')),(ROOT/'01_rtl'/'soc'/'needle_soc.sv'),(ROOT/'02_tb'/'system'/'tb_needle_ddr.sv')]
rtl=[str(x) for x in rtl]
results=[]
build=subprocess.run(['make','-C',str(ROOT/'03_sw'/'ddr_bringup'),'all'],cwd=ROOT,text=True,capture_output=True)
(ROOT/'07_runs'/'ddr'/'firmware_build.log').write_text(build.stdout+build.stderr,encoding='utf-8')
if build.returncode:
    report={'scope':'RTL SoC optional DDR word path with HMIC UI behavior model','physical_board':False,'real_ddr_phy':False,'firmware_build_passed':False,'tests':[],'common_reset_scope':'startup common reset only; post-fault recovery is not claimed'}
    (out/'integration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'integration_report.md').write_text('# Optional DDR integration report\n\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2)); sys.exit(1)
for name,flag in [('bringup',0),('fault',1)]:
    vvp=out/f'tb_needle_ddr_{name}.vvp'; log=out/f'tb_needle_ddr_{name}.log'
    cmd=['iverilog','-g2012','-s','tb_needle_ddr',f'-Ptb_needle_ddr.FAULT_TEST={flag}','-o',str(vvp),*rtl]
    started=time.time(); cp=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    if cp.returncode:
        log.write_text('compile failed\n'+cp.stdout+cp.stderr,encoding='utf-8'); results.append({'name':name,'passed':False,'stage':'compile','log':str(log)}); continue
    run=subprocess.run(['vvp',str(vvp)],cwd=ROOT,text=True,capture_output=True,timeout=90)
    log.write_text(cp.stdout+cp.stderr+'\n'+run.stdout+run.stderr,encoding='utf-8')
    text=run.stdout+run.stderr; passed=run.returncode==0 and 'PASS DDR integration' in text
    results.append({'name':name,'passed':passed,'exit_code':run.returncode,'elapsed_s':round(time.time()-started,3),'log':str(log),'summary':next((line for line in text.splitlines() if line.startswith('PASS DDR integration')), '')})
report={'scope':'RTL SoC optional DDR word path with HMIC UI behavior model','physical_board':False,'real_ddr_phy':False,'firmware_build_passed':True,'common_reset_scope':'startup common reset only; post-fault recovery is not claimed','clock_contract':{'cpu_hz':27000000,'ui_hz':142857143,'cpu_period_ns':37.037,'ui_period_ns':7.0,'async':True},'memory_contract':{'model_words':262144,'model_bytes':1048576,'native_beat_words':8,'last_valid_native_address':262136,'out_of_range_rejected':True,'storage':'full dense 1MiB array; read snapshot at accepted native AR'},'tests':results,'contract':['CPU/XND owner-locked arbitration','one-word mailbox CDC on unrelated clocks','256-bit HMIC model with 32-bit lane and byte strobes','init gating','backpressure','address/alignment metadata','timeout and late-response quarantine','startup common reset only']}
(out/'integration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'integration_report.md').write_text('# Optional DDR integration report\n\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2)); sys.exit(0 if all(x['passed'] for x in results) else 1)
