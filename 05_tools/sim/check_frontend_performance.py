#!/usr/bin/env python3
"""Same-binary CPU front-end A/B; real SoC RTL, no user-language acceptance."""
from pathlib import Path
import subprocess,json,re,hashlib
R=Path(__file__).resolve().parents[2];D=R/'07_runs/review_followup_20261028'
def command(args,log):
 with log.open('w')as f:subprocess.run(args,cwd=R,stdout=f,stderr=subprocess.STDOUT,check=True)
def main():
 (D/'coremark_run').mkdir(exist_ok=True)
 command(['make','-C','03_sw/coremark','OUT=../../07_runs/review_followup_20261028/coremark_run/performance','RUN=performance','all'],D/'coremark_firmware_build.log')
 elf=D/'coremark_run/performance.elf';prefix='/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
 dis=subprocess.check_output([prefix+'objdump','-d',str(elf)],text=True);(D/'coremark_disassembly.txt').write_text(dis)
 assert '__udivdi3'not in dis,'Unsupported compressed-library divide must not be linked'
 sources=[]
 for f in ['01_rtl/cpu','01_rtl/mem','01_rtl/periph','01_rtl/xnd']:sources+=sorted(str(p)for p in(R/f).glob('*.sv'))
 results=[]
 for mode in [0,1]:
  obj=D/('coremark_obj_%d'%mode)
  args=['verilator','--cc','--exe','--build','-j','2','--top-module','needle_soc','-GCLK_HZ=27000000','-GBAUD=1000000',"-GCPU_FETCH_OVERLAP=1'b"+str(mode),'-GINIT_FILE="'+str(D/'coremark_run/performance.mem')+'"','-Wno-UNUSEDSIGNAL','-Wno-UNUSEDPARAM','-Wno-PINCONNECTEMPTY','--Mdir',str(obj)]+sources+[str(R/'01_rtl/soc/needle_soc.sv'),str(R/'05_tools/sim/soc_run.cpp')]
  log=D/('coremark_mode_%d.log'%mode)
  prior=log.read_text()if log.exists()else''
  if mode==0 and 'COREMARK_DONE'in prior and 'NR_COREMARK_PRECISE'in prior and 'RTL_TRAP'not in prior:
   text=prior;print('REUSE_SAME_BINARY_BASELINE',flush=True)
  else:
   command(args,D/('coremark_build_%d.log'%mode));print('BUILT',mode,flush=True)
   command([str(obj/'Vneedle_soc'),'COREMARK_DONE','700000000'],log);text=log.read_text()
  assert 'Correct operation validated.'in text and 'COREMARK_DONE'in text and 'RTL_TRAP'not in text
  m=re.search(r'NR_CYCLES=(\d+) NR_HZ=(\d+) NR_ITERATIONS=(\d+)',text);assert m
  c,hz,it=map(int,m.groups());pmu=json.loads(next(x[7:]for x in text.splitlines()if x.startswith('NR_PMU ')))
  precise=re.search(r'NR_COREMARK_PRECISE seconds=([\d.]+) coremark_per_mhz=([\d.]+)',text);assert precise
  assert abs(float(precise[1])-c/hz)<.0000011 and abs(float(precise[2])-it*1000000/c)<.0000011
  a={'overlap':mode,'cycles':c,'hz':hz,'iterations':it,'seconds_reference':c/hz,'coremark_per_mhz':it*1000000/c,'pmu':pmu,'cpi':pmu['cycles']/pmu['instret'],'crc_passed':True,'precise_print_checked':True,'physical':False};results.append(a);print(json.dumps(a),flush=True)
 (D/'coremark_frontend_ab.json').write_text(json.dumps({'scope':'Same binary and SoC, only CPU_FETCH_OVERLAP differs; actual clock RTL, not physical board','binary_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'results':results,'algorithm_cycles_speedup':results[0]['cycles']/results[1]['cycles']},indent=2)+'\n')
if __name__=='__main__':main()
