from pathlib import Path
import subprocess,json,re
R=Path('/work/LUO/NeedleRV-X');D=R/'07_runs/development/context_generalization';S=D/'speed';M=R/'03_sw/model';gcc='/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
cases=['led 37','请将PWM占空比设置为20%。','请解释PWM占空比设置为20%的含义。','假设把LED0点亮会发生什么？','0123456789012345678901234567890123456789012345678901234567890123','请读取FPGA当前温度。','abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl','LED0已经点亮了吗？','读取计数器','a'*64]
base=(D/'context_benchmark.c').read_text();start=base.index('static const char *const cases[]');end=base.index(';',start)+1;base=base[:start]+'static const char *const cases[]={'+','.join(json.dumps(x,ensure_ascii=False)for x in cases)+'};'+base[end:]
res={}
for name,inc in [('baseline',S/'baseline_context.c.inc'),('sparse',M/'byte_context.c.inc')]:
 text=base.replace('#define NR_CONTEXT_SCRATCH_ATTR','#include "byte_tool_model.h"\n#define NR_CONTEXT_SCRATCH_ATTR').replace('#include "byte_context.c.inc"','#include "'+str(inc)+'"')
 src=S/(name+'_benchmark.c');src.write_text(text)
 cmd=[gcc+'gcc','-DNR_PLATFORM_CLOCK_HZ=40500000','-DNR_UART_BAUD=921600','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-mstrict-align','-O2','-std=c99','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-common','-ffunction-sections','-fdata-sections','-nostdlib','-nostartfiles','-I'+str(M),'-T',str(R/'03_sw/bringup/linker.ld'),str(R/'03_sw/model/startup.S'),str(src),str(R/'03_sw/platform/needle_platform.c'),'-Wl,--gc-sections,-Map,'+str(S/(name+'.map')),'-lgcc','-o',str(S/(name+'.elf'))]
 subprocess.run(cmd,cwd=R,check=True);subprocess.run([gcc+'objcopy','-O','binary',str(S/(name+'.elf')),str(S/(name+'.bin'))],check=True)
 subprocess.run(['python3',str(R/'05_tools/bin_to_memh.py'),str(S/(name+'.bin')),str(S/(name+'.mem'))],check=True)
 p=subprocess.run([str(R/'07_runs/development/ai_pipeline/obj_soc/Vneedle_soc'),str(S/(name+'.mem'))],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True,timeout=120)
 (S/(name+'_rtl.log')).write_text(p.stdout)
 rows=[json.loads(x.split('CONTEXT_COST ',1)[1])for x in p.stdout.splitlines()if x.startswith('CONTEXT_COST ')];assert len(rows)==len(cases)
 res[name]=rows
 report=json.loads((S/'report.json').read_text());report['rtl_partial']=name;(S/'report.json').write_text(json.dumps(report,indent=2)+'\n')
rows=[]
for i,(a,b)in enumerate(zip(res['baseline'],res['sparse'])):
 for k in ['case','length','nonzero','margin']:assert a[k]==b[k],(i,k,a,b)
 rows.append(dict(text=cases[i],utf8_bytes=a['length'],nonzero=a['nonzero'],baseline_scalar_macs=a['scalar_macs'],sparse_scalar_macs=b['scalar_macs'],baseline_cycles_per_call=a['cycles16']/16,sparse_cycles_per_call=b['cycles16']/16,baseline_ms=a['cycles16']/16/40500,sparse_ms=b['cycles16']/16/40500,speedup=a['cycles16']/b['cycles16'],cycles_reduction=1-b['cycles16']/a['cycles16']))
report=json.loads((S/'report.json').read_text());report.pop('rtl_partial',None);report['rtl']=dict(clock_hz=40500000,method='Actual SoC RTL clock execution,16sequential calls percase,includesfeaturehash/count/reset/sparseintegerdot andoutputrounding; noUART time in measured interval. Same firmwareplatform/cache implementation andcompilerflags; no fabricated acceleratorjobs.',cases=rows,all_context_outputs_equal=True,all_cases_faster=all(x['speedup']>1for x in rows))
(S/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=True))
