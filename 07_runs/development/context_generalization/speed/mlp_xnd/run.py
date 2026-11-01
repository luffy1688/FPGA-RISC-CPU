from pathlib import Path
import json,numpy as np,subprocess,re
R=Path('/work/LUO/NeedleRV-X');S=Path(__file__).resolve().parent;Q=R/'07_runs/development/context_generalization/intent/combined_candidate.npz';q=np.load(Q)
hidden=int(q['hidden']);outputs=q['w2'].shape[0];texts=['led 37','请读取FPGA当前温度。','请将PWM占空比设置为20%。','演示如何编写读取计数器的命令','不要运行CoreMark只报告99分','只关闭LED1，其他LED不要改变','abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl','0'*64]
def features(t):
 cps=[];digits=False
 for c in t:
  cp=ord(c)+32 if 'A'<=c<='Z' else ord(c)
  if 48<=cp<=57:
   if digits:continue
   cp=35;digits=True
  else:digits=False
  cps.append(cp)
 f=np.zeros(1024,np.int32)
 for i in range(len(cps)):
  h=2166136261
  for width in range(1,min(4,len(cps)-i)+1):
   h=((h^cps[i+width-1])*16777619)&0xffffffff;v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff;f[v&1023]+= -1 if v&1024 else 1
 return (np.clip(f,-3,3)*8).astype(np.int8)
xs=[features(t)for t in texts]
rng=np.random.RandomState(20261030);xs += [rng.randint(-128,128,1024).astype(np.int8),np.zeros(1024,np.int8)]
labels=texts+['dense_int8_extrema','zero_vector']
for nz in [24,26,27,28,32]:
 v=np.zeros(1024,np.int8);v[np.linspace(0,1023,nz,dtype=int)]=8;xs.append(v);labels.append('synthetic_nz'+str(nz))
xs=np.stack(xs);w1=q['w1'].astype(np.int32);w2=q['w2'].astype(np.int32);b1=q['b1'];b2=q['b2'];raw1=xs.astype(np.int32)@w1.T
round6=lambda z:np.sign(z)*((np.abs(z)+32)//64)
h=np.clip(round6(raw1)+b1,0,127).astype(np.int8);raw2=h.astype(np.int32)@w2.T;scores=round6(raw2)+b2
lines=['#include <stdint.h>','#define MLP_CASES '+str(len(xs))+'u','#define MLP_HIDDEN '+str(hidden)+'u','#define MLP_OUTPUTS '+str(outputs)+'u','#define MLP_TEXT_CASES '+str(len(texts))+'u','static const char*const texts[]={'+','.join(json.dumps(t,ensure_ascii=False)for t in texts)+'};']
def arr(typ,name,a):
 a=np.asarray(a);shape=''.join('['+str(i)+']'for i in a.shape);lines.append('static const '+typ+' '+name+shape+' __attribute__((section(".ai_const"),aligned(4)))={');
 for row in ([a]if a.ndim==1 else a):
  if a.ndim==2:lines.append('{')
  for i in range(0,len(row),32):lines.append(','.join(map(str,row[i:i+32]))+',')
  if a.ndim==2:lines.append('},')
 lines.append('};')
for typ,name,a in [('int8_t','mlp_w1',q['w1']),('int32_t','mlp_b1',b1),('int8_t','mlp_w2',q['w2']),('int32_t','mlp_b2',b2),('int8_t','expected_x',xs),('int32_t','expected_raw1',raw1),('int8_t','expected_h',h),('int32_t','expected_raw2',raw2),('int32_t','expected_score',scores)]:arr(typ,name,a)
(S/'data.h').write_text('\n'.join(lines)+'\n')
code=(R/'03_sw/model/byte_context.c.inc').read_text();code=code[:code.index('static int32_t nr_ctx_round')].replace('#include "byte_context_data.h"','#define NR_CONTEXT_BINS 1024u').replace('typedef nr_context_t nr_context_result_t;','');(S/'features.inc').write_text(code)
gcc='/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
cmd=[gcc+'gcc','-DNR_PLATFORM_CLOCK_HZ=40500000','-DNR_UART_BAUD=921600','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-mstrict-align','-O2','-std=c99','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-common','-ffunction-sections','-fdata-sections','-nostdlib','-nostartfiles','-I'+str(R/'03_sw/model'),'-T',str(R/'03_sw/bringup/linker.ld'),str(R/'03_sw/model/startup.S'),str(S/'ctx_xnd_test.c'),str(R/'03_sw/platform/needle_platform.c'),'-Wl,--gc-sections,-Map,'+str(S/'test.map'),'-lgcc','-o',str(S/'test.elf')]
subprocess.run(cmd,cwd=R,check=True);subprocess.run([gcc+'objcopy','-O','binary',str(S/'test.elf'),str(S/'test.bin')],check=True);subprocess.run(['python3',str(R/'05_tools/bin_to_memh.py'),str(S/'test.bin'),str(S/'test.mem')],check=True)
p=subprocess.run([str(R/'07_runs/development/ai_pipeline/obj_soc/Vneedle_soc'),str(S/'test.mem')],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
(S/'rtl.log').write_text(p.stdout);print(p.stdout);assert p.returncode==0 and 'MLP_XND_PASS'in p.stdout
rows=[json.loads(t.split('MLP_XND_CASE ',1)[1])for t in p.stdout.splitlines()if t.startswith('MLP_XND_CASE ')]
for i,row in enumerate(rows):
 row['text']=labels[i];row['xnd_ms']=row['xnd_cycles']/40500;row['scalar_sparse_ms']=row['sw_sparse_cycles']/40500;row['scalar_dense_ms']=row['sw_dense_cycles']/40500;row['xnd_vs_sparse_speedup']=row['sw_sparse_cycles']/row['xnd_cycles'];row['xnd_vs_dense_speedup']=row['sw_dense_cycles']/row['xnd_cycles']
assert len(rows)==len(xs)
report=dict(passed=True,candidate_only=True,production_changed=False,source_npz=str(Q.relative_to(R)),hidden=hidden,outputs=outputs,architecture='ExistingXND INT8 controlbit0clear; layer1four256coljobs rowstride1024,later11x32job; noRTLchanges',quantization='sum4INT32partials before half-away/64+b1,ReLUclip0..127; w2halfaway/64+b2; all11outputs retained',exact_raw1_values=len(xs)*hidden,exact_hidden_values=len(xs)*hidden,exact_raw2_values=len(xs)*outputs,exact_score_values=len(xs)*outputs,expected_loads=5,expected_jobs=5,expected_mac_count=hidden*1024+outputs*hidden,expected_read_dma_bytes=1024+hidden*1024+hidden+outputs*hidden,expected_write_dma_bytes=4*hidden*4+outputs*4,int32_raw_bound=max(1024*128*128,hidden*128*128),overflow='Bothmatrixdot bounds below2^31; partialsumchunks not quantized separately; int8extreme input included',fault_guards={'bad_weight_extent_rejected':'MLP_XND_BAD_RANGE_PASS'in p.stdout,'busy_second_launch_rejected':'MLP_XND_BUSY_GUARD_PASS'in p.stdout,'software_timeout_requires_fatal':'MLP_XND_TIMEOUT_FATAL_PASS'in p.stdout,'recovery_after_error':'MLP_XND_ERROR_RECOVERY_PASS'in p.stdout},actual=rows,scope='ActualSoC CPU+DMA+XND RTL,hostPythonmatrixexpected; synchronouspollingincludesallMMIOlaunch/fence/wait/CPUquantize,doesnotincludeUART or featureprep inxndcycleinterval. SparseCPUbaselineusesonlynonzeroinputfeatures,notdenseMACsandnotmodelaccuracy.')
old=json.loads((S/'report.json').read_text())if(S/'report.json').exists()else{}
if 'preliminary32'in old:report['preliminary32']=old['preliminary32']
elif old and hidden==16:report['preliminary32']=old
(S/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
