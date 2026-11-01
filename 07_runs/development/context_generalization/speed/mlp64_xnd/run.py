from pathlib import Path
import json,numpy as np,subprocess,re,statistics
R=Path('/work/LUO/NeedleRV-X');S=Path(__file__).resolve().parent;Q=R/'07_runs/development/context_generalization/capacity/frozen_candidate.npz';q=np.load(Q);hidden=q['w1'].shape[0];outputs=q['w2'].shape[0];assert(hidden,outputs)==(64,16)
texts=['led 37','请读取FPGA当前温度。','请将PWM占空比设置为20%。','演示如何编写读取计数器的命令','abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl','0'*64]
def features(t):
 cp=[];digits=False
 for c in t:
  x=ord(c)+32 if 'A'<=c<='Z' else ord(c)
  if 48<=x<=57:
   if digits:continue
   x=35;digits=True
  else:digits=False
  cp.append(x)
 f=np.zeros(1024,np.int32)
 for i in range(len(cp)):
  h=2166136261
  for width in range(1,min(4,len(cp)-i)+1):
   h=((h^cp[i+width-1])*16777619)&0xffffffff;v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff;f[v&1023]+= -1 if v&1024 else 1
 return (np.clip(f,-3,3)*8).astype(np.int8)
xs=[features(t)for t in texts];labels=texts.copy();xs.append(np.zeros(1024,np.int8));labels.append('zero_after_dense')
for nz in [13,20,22,23,24,32,48,64,100,250,13]:
 v=np.zeros(1024,np.int8);idx=np.linspace(0,1023,nz,dtype=int);v[idx]=np.where(np.arange(nz)%2==0,24,-24);xs.append(v);labels.append('synthetic_nz'+str(nz))
xs=np.stack(xs);raw1=xs.astype(np.int32)@q['w1'].astype(np.int32).T;ra=lambda z:np.sign(z)*((np.abs(z)+32)//64);hs=np.clip(ra(raw1)+q['b1'],0,127).astype(np.int8);raw2=hs.astype(np.int32)@q['w2'].astype(np.int32).T;scores=ra(raw2)+q['b2']
lines=['#include <stdint.h>','#define CASES '+str(len(xs))+'u','#define TEXT_CASES '+str(len(texts))+'u','#define HIDDEN64 64u','#define OUTPUTS16 16u','static const char*const texts[]={'+','.join(json.dumps(t,ensure_ascii=False)for t in texts)+'};']
def arr(typ,name,a):
 a=np.asarray(a);shape=''.join('['+str(i)+']'for i in a.shape);lines.append('static const '+typ+' '+name+shape+' __attribute__((section(".ai_const"),aligned(4)))={');
 for row in ([a]if a.ndim==1 else a):
  if a.ndim==2:lines.append('{')
  for i in range(0,len(row),32):lines.append(','.join(map(str,row[i:i+32]))+',')
  if a.ndim==2:lines.append('},')
 lines.append('};')
for typ,name,a in [('int8_t','nr_capacity_w1',q['w1']),('int32_t','nr_capacity_b1',q['b1']),('int8_t','nr_capacity_w2',q['w2']),('int32_t','nr_capacity_b2',q['b2']),('int8_t','expected_x',xs),('int32_t','expected_score',scores)]:arr(typ,name,a)
(S/'data.h').write_text('\n'.join(lines)+'\n');(S/'features.inc').write_text((R/'07_runs/development/context_generalization/speed/mlp_xnd/features.inc').read_text())
gcc='/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
cmd=[gcc+'gcc','-DNR_PLATFORM_CLOCK_HZ=40500000','-DNR_UART_BAUD=921600','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-mstrict-align','-O2','-std=c99','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-common','-ffunction-sections','-fdata-sections','-nostdlib','-nostartfiles','-I'+str(R/'03_sw/model'),'-T',str(R/'03_sw/bringup/linker.ld'),str(R/'03_sw/model/startup.S'),str(S/'test.c'),str(R/'03_sw/model/semantic_xnd.c'),str(R/'03_sw/platform/needle_platform.c'),'-Wl,--gc-sections,-Map,'+str(S/'test.map'),'-lgcc','-o',str(S/'test.elf')]
subprocess.run(cmd,cwd=R,check=True);subprocess.run([gcc+'objcopy','-O','binary',str(S/'test.elf'),str(S/'test.bin')],check=True);subprocess.run(['python3',str(R/'05_tools/bin_to_memh.py'),str(S/'test.bin'),str(S/'test.mem')],check=True)
obj=R/'07_runs/development/ai_pipeline/obj_soc'
subprocess.run(['g++','-std=c++17','-Os','-I'+str(obj),'-I/usr/local/share/verilator/include','-I/usr/local/share/verilator/include/vltstd',str(S/'runner.cpp'),str(obj/'Vneedle_soc__ALL.a'),str(obj/'verilated.o'),str(obj/'verilated_threads.o'),'-pthread','-o',str(S/'runner')],check=True)
p=subprocess.run([str(S/'runner'),str(S/'test.mem')],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
(S/'rtl.log').write_text(p.stdout);print(p.stdout);assert p.returncode==0and'MLP64_PASS'in p.stdout
rows=[json.loads(t.split('MLP64_CASE ',1)[1])for t in p.stdout.splitlines()if t.startswith('MLP64_CASE ')];assert len(rows)==len(xs)
probes=[json.loads(t.split('MLP64_PROBE ',1)[1])for t in p.stdout.splitlines()if t.startswith('MLP64_PROBE ')]
assert len(probes)==len(xs)and all(a['macs8']==66560*8and a['loads8']==40and a['jobs8']==40for a in probes)
for i,row in enumerate(rows):
 row['text']=labels[i];row['cpu_median_cycles']=statistics.median(row['cpu_cycles']);row['xnd_median_cycles']=statistics.median(row['xnd_cycles']);row['cpu_ms']=row['cpu_median_cycles']/40500;row['xnd_ms']=row['xnd_median_cycles']/40500;row['xnd_vs_cpu']=row['cpu_median_cycles']/row['xnd_median_cycles']
report=dict(passed=True,clock_hz=40500000,candidate_only=True,rtl_changed=False,production_source_bounds_updated=True,npz=str(Q.relative_to(R)),hidden=64,outputs=16,score_exact_values=len(rows)*8*16,repeats=8,workspace_bytes=2696,ai_scratch_bytes=2688,cpu_state_bytes=8,full_timing_scope='Same shared completecounts/touched. CPU includesclip,counttosparseaccumulation,firstquantReLUandall16outputdots/quant; XNDincludesdenseprepare,allMMIO/fence/poll,4partialmerge,allquantizationandentry/exit2slotinvalidations. SharedUnicodeextractionandUARTexcludedfromboth. DedicatedRTL shapeprofile,nothost/browserstatisticalmeasurement.',loads_per_request=5,jobs_per_request=5,actual_operator_macs=66560,actual_dma_read_bytes=int(rows[0]['reads']),actual_dma_write_bytes=int(rows[0]['writes']),poisoned_first_use=True,continuous_sparse_dense_zero=True,both_slots_invalid_after_success=True,bad_index_fatal=True,bad_weight_fatal=True,busy_fatal_no_fallback=True,recovery_verified=True,hardware_counter_probes=probes,counter_scope='ActualRTLenginecompletionedge MAC/read/write counters; not descriptorformulaguesses; invalidationsdo notcountasLOAD/GEMV',rows=rows)
(S/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
