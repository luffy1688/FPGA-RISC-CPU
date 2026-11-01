"""Read standard UART transcripts; fail on a CRC, duration or completion problem."""
import json,re
from pathlib import Path
expected={'performance':('e9f5','e714','1fd7','8e3a'), 'validation':('18f2','e3c1','0747','8d84')}
report={'environment':'RTL simulation of needle_soc; both caches and predictor enabled', 'memory':'256 KiB on-chip RAM; 4 KiB 2-way I-cache and 4 KiB 2-way D-cache', 'counter_scope':'NR_PMU is a timed bracket delta with sequential sampling overhead; BOOT_* lines remain cumulative', 'physical_board_verified':False, 'runs':{}}
for run,crcs in expected.items():
 text=Path('07_runs/coremark/'+run+'.log').read_text()
 if 'ERROR!' in text or 'Correct operation validated.' not in text or 'COREMARK_DONE' not in text: raise SystemExit('CoreMark run failed: '+run)
 for name,exp in zip(['seedcrc','crclist','crcmatrix','crcstate'],crcs):
  got=re.search(name+r'\s*: 0x([0-9a-f]+)',text)
  if not got or got.group(1)!=exp: raise SystemExit(run+' CRC mismatch: '+name)
 cycles,hz,iters=map(int,re.search(r'NR_CYCLES=(\d+) NR_HZ=(\d+) NR_ITERATIONS=(\d+)',text).groups())
 if cycles<hz*10: raise SystemExit(run+' below 10 seconds')
 report['runs'][run]={'iterations':iters,'cycles':cycles,'reference_clock_hz':hz,'seconds_from_cycles':cycles/hz,'iterations_per_second_at_reference_clock':iters*hz/cycles,'coremark_per_mhz_from_cycles':iters*1000000/cycles,'crc_pass':True,'duration_pass':True}
 pmu_lines=[x.split('NR_PMU ',1)[1] for x in text.splitlines() if x.startswith('NR_PMU ')]
 if len(pmu_lines)!=1:raise SystemExit(run+' missing PMU bracket')
 pmu=json.loads(pmu_lines[0])
 if not pmu['instret'] or pmu['cycles']<cycles:raise SystemExit(run+' invalid PMU bracket')
 pmu['approx_cpi_with_sampling']=pmu['cycles']/pmu['instret']
 report['runs'][run]['pmu']=pmu
Path('07_runs/coremark/current_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['runs'],indent=2))
