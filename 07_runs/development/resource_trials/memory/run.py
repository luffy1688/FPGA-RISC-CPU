
from pathlib import Path
import subprocess,re,json,shlex
R=Path('/work/LUO/NeedleRV-X');S=Path(__file__).resolve().parent
GCC='/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
results=[]
for kib in [512,768]:
 end=kib*1024;sub=S/str(kib);sub.mkdir(exist_ok=True)
 header=(R/'03_sw/xnd_runtime/xnd_mmio.h').read_text().replace('0x00040000u',hex(end)+'u')
 (S/'03_sw/xnd_runtime/xnd_mmio.h').write_text(header)
 link=(R/'03_sw/bringup/linker.ld').read_text().replace('ORIGIN = 0x00020000, LENGTH = 128K','ORIGIN = '+hex(end-131072)+', LENGTH = 128K')
 (sub/'linker.ld').write_text(link)
 cmd=[GCC+'gcc','-DNR_PLATFORM_CLOCK_HZ=40500000','-DNR_UART_BAUD=921600','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-mstrict-align','-O2','-std=c99','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-common','-ffunction-sections','-fdata-sections','-nostdlib','-nostartfiles','-I'+str(S/'03_sw/model'),'-T',str(sub/'linker.ld'),str(R/'03_sw/model/startup.S'),str(S/'test.c'),str(S/'03_sw/model/semantic_xnd.c'),str(R/'03_sw/platform/needle_platform.c'),'-Wl,--gc-sections,-Map,'+str(sub/'test.map'),'-lgcc','-o',str(sub/'test.elf')]
 subprocess.run(cmd,cwd=R,check=True)
 subprocess.run([GCC+'objcopy','-O','binary',str(sub/'test.elf'),str(sub/'test.bin')],check=True)
 subprocess.run(['python3',str(R/'05_tools/bin_to_memh.py'),str(sub/'test.bin'),str(sub/'test.mem')],check=True)
 old=(R/'07_runs/development/ai_pipeline/obj_soc/Vneedle_soc__verFiles.dat').read_text().splitlines()[1][3:-1]
 args=shlex.split(old);args[args.index('-j')+1]='2';idx=args.index('--Mdir');args[idx+1]=str(sub/'obj')
 args=[str(S/'needle_soc.sv')if x==str(R/'01_rtl/soc/needle_soc.sv')else str(S/'runner.cpp')if x.endswith('/ai_pipeline/selftest_runner.cpp')else x for x in args]
 args.extend(['-GSRAM_BYTES='+str(end),'-Wno-fatal'])
 with (sub/'build.log').open('w')as log:subprocess.run(['verilator',*args],cwd=R,check=True,stdout=log,stderr=subprocess.STDOUT)
 p=subprocess.run([str(sub/'obj/Vneedle_soc'),str(sub/'test.mem')],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
 (sub/'rtl.log').write_text(p.stdout)
 assert p.returncode==0 and 'EXPANDED_MEMORY_BOUNDARY_PASS'in p.stdout and 'MLP64_PASS'in p.stdout,p.stdout[-1500:]
 cases=[json.loads(t.split('MLP64_CASE ',1)[1])for t in p.stdout.splitlines()if t.startswith('MLP64_CASE ')]
 assert len(cases)==18
 results.append(dict(kib=kib,passed=True,score_exact_count=18*8*16,ai_const_start=end-131072,ai_const_high_address_exercised=True,cpu_high_address_alias_and_byte_strobe=True,hardware_oob_activation_rejected=True,hardware_below_AI_activation_rejected=True,production_source_changed=False,actual_vendor_synthesis=False,estimated_drm36_equiv=2+kib//2,estimate_basis='Existing256KiB PDS mainRAM128DRM36equiv pluscache2; linear extrapolation only; new map not synthesized'))
 print('MEMORY_TRIAL_PASS',kib,flush=True)
(S/'report.json').write_text(json.dumps(dict(passed=True,scope='Actual CPU+cache+real synchronoussoc_ram+XND RTLsimulation. AIconstants/workspace relocatedto top128KiB ofexpandedmemory. No physical,STAorvendorresource claim.',results=results),indent=2)+'\n')
