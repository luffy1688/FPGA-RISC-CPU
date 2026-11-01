"""Summarize saved native PDS evidence; does not implement or program hardware."""
from pathlib import Path
import argparse,json,re,hashlib
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def summarize(root,role):
 folder=root/('06_pango_review_20261028'if role=='production'else'06_pango_review_ila_20261028')
 bit=folder/'generate_bitstream/pangu_200pro_board.sbit'
 if not bit.exists():return None
 timing=folder/'report_timing/pangu_200pro_board.rtr';util=folder/'place_route/pangu_200pro_board.prr'
 t=timing.read_text(errors='replace');u=util.read_text(errors='replace')
 slacks={}
 for label in ['Setup Summary(Slow Corner):','Hold Summary(Slow Corner):','Setup Summary(Fast Corner):','Hold Summary(Fast Corner):']:
  s=t.split(label,1)[1];m=re.search(r'^\s*board_clk\s+board_clk\s+([-\d.]+)\s+([-\d.]+)',s,re.M);assert m,label
  slacks[label.rstrip(':')]={'worst_ns':float(m[1]),'total_ns':float(m[2])}
 resources={}
 for typ in ['CLMA','CLMS']:
  block=u.split('| Use of '+typ,1)[1].split('| Use of ',1)[0]
  for kind in ['FF','LUT']:
   value=int(re.search(r'^\|\s+'+kind+r'\s+\|\s+(\d+)',block,re.M)[1]);resources[kind]=resources.get(kind,0)+value
 for kind in ['DRM','APM','ADC','GPLL']:
  resources[kind]=int(re.search(r'^\| Use of '+kind+r'\s+\|\s+(\d+)',u,re.M)[1])
 prod=root/'06_pango_review_20261028';rom=prod/'firmware/model_interactive.mem';freeze=root/'07_runs/review_followup_20261028/server_implementation_freeze.json'
 result={'schema':'needlervx.pds.review.v1','role':role,'physical_acceptance_separate':True,'sbit_sha256':sha(bit),'sbit_bytes':bit.stat().st_size,'clock_hz_reference':27000000,'resources_whole_soc':resources,'timing':slacks,'declared_constraints_met':'All Constraints Met.'in t,'limits':['Not complete external synchronous IO closure','Not measured highest stable frequency','Resources include whole SoC, firmware RAM, peripherals and XND; ILA role additionally contains debug cores'],'rom_sha256':sha(rom),'implementation_freeze_sha256':sha(freeze),'production_synthesis_adf_sha256':sha(prod/'synthesize/pangu_200pro_board_syn.adf'),'evidence':{p.relative_to(root).as_posix():sha(p)for p in[bit,timing,util,rom]}}
 assert result['declared_constraints_met']and all(x['worst_ns']>=0 and x['total_ns']==0 for x in slacks.values())
 (folder/'delivery_report.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);args=a.parse_args()
 print(json.dumps([summarize(args.root,x)for x in ['production','ila']],indent=2))
