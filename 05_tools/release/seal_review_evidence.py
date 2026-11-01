"""Verify closed physical capture and current native WDF lineage; read only except seal."""
from pathlib import Path
import argparse,json,hashlib,base64,statistics
from datetime import datetime,timezone
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main(root,write=True):
 d=root/'07_runs/board/20261028_review_acceptance';task=root/'07_runs/review_followup_20261028';status=load(d/'capture_status.json');accept=load(d/'acceptance_report.json');ila=load(d/'ila_capture_report.json');analysis=load(d/'ila/analysis.json');bound=load(d/'production_uart_boundary.json')
 capture_path=lambda value:Path(value)if Path(value).is_file()else d/str(value).replace(chr(92),'/').rsplit('/',1)[-1]
 assert status['state']=='stopped'and not status['serial_open']and status['ready']and status['error']is None
 assert accept['passed']and len(accept['results'])==51 and not accept['failures']and ila['complete']
 fourth=[x for x in accept['results']if x.get('group')=='fourth'];q=[x for x in accept['results']if x.get('group')=='original12'];assert len(fourth)==25 and len(q)==12 and all(x['actual']['execute']==1 for x in q)
 logs=[load(root/folder/'delivery_report.json')for folder in ['06_pango_review_20261028','06_pango_review_ila_20261028']]
 assert logs[0]['production_synthesis_adf_sha256']==logs[1]['production_synthesis_adf_sha256']and logs[0]['rom_sha256']==logs[1]['rom_sha256']
 assert sha(root/'06_pango_review_20261028/generate_bitstream/pangu_200pro_board.sbit')==logs[0]['sbit_sha256']==load(d/'program_report.json')['sbit_sha256']==ila['production_sbit_sha256']
 assert sha(root/'06_pango_review_ila_20261028/generate_bitstream/pangu_200pro_board.sbit')==logs[1]['sbit_sha256']==ila['ila_sbit_sha256']
 assert analysis['elf_lineage']['elf_sha256']==sha(root/'07_runs/model/review_followup_20261028/interactive.elf')
 assert analysis['elf_lineage']['elf_binary_matches_board_mem']and analysis['elf_lineage']['built_mem_matches_board']
 assert analysis['elf_lineage']['firmware_mem_sha256']==logs[0]['rom_sha256']
 cap=analysis['captures'];assert set(cap)=={'xnd','coremark','adc_a','adc_b','pwm25'}
 assert analysis['signal_map_sha256']==sha(root/'06_pango_review_ila_20261028/signal_map_bound.json')
 assert analysis['analyzer_sha256']==sha(root/'05_tools/board/analyze_ila.py')
 assert sha(root/'06_pango_review_20261028/synthesize/pangu_200pro_board_syn.adf')==logs[0]['production_synthesis_adf_sha256']
 for tag,item in cap.items():
  assert item['wdf_sha256']==sha(d/'ila'/(tag+'.wdf')) and item['project_sha256']==sha(d/'ila'/(tag+'.dprj'))
  assert next(x['wdf_sha256']for x in ila['captures']if x['tag']==tag)==item['wdf_sha256']
 for tag in ['adc_a','adc_b']:
  a=cap[tag]['adc'];assert a['valid_samples_in_window']>0 and a['status_values_reconstructed']==[5]
 assert analysis['adc_sample_counter_delta_mod32']>0
 pwm=cap['pwm25']['pwm'];assert len(pwm['period_samples'])>=1 and all(x==27000 for x in pwm['period_samples'])and all(x==6750 for x in pwm['high_samples'])and pwm['enable']['min']==pwm['enable']['max']==1
 assert cap['coremark']['coremark_named_pc_samples']>0 and cap['coremark']['activity']['ex_valid']>0
 assert 0<cap['xnd']['activity']['xnd_busy_samples']<4096
 cm=[x['coremark']for x in accept['results']if'coremark'in x];assert len(cm)==4 and len(set(x['cycles']for x in cm))==1 and cm[0]['seconds_nominal']>=10
 assert next(x['uart_result']for x in ila['captures']if x['tag']=='coremark')['value']==cm[0]['cycles']
 events=[json.loads(x)for x in capture_path(status['events_path']).read_text(encoding='utf-8-sig').splitlines()];assert not[x for x in events if x['direction']=='ERROR']
 raw=capture_path(status['raw_path']).read_bytes();rebuilt=b''.join(base64.b64decode(x['data']['bytes_base64'])for x in events if x['direction']=='RX');assert raw==rebuilt
 text=capture_path(status['text_path']).read_text(encoding='utf-8');assert text==raw.decode('utf-8',errors='replace')
 assert hashlib.sha256(raw[:bound['rx_prefix_bytes']]).hexdigest()==bound['rx_prefix_sha256']
 tx=[x['data']for x in events if x['direction']=='TX'];assert len(tx)==len(set(x['id']for x in tx))==54 and all(x['completed']for x in tx)
 expected={x['id']for x in load(d/'acceptance_cases.json')['cases']}|{'ila-init-pwm25','ila-xnd','ila-coremark'};assert set(x['id']for x in tx)==expected
 builds=[json.loads(x[9:])for x in text.splitlines()if x.startswith('NR_BUILD ')];assert len(builds)==2 and all(x['firmware']=='software_modality_guard_oct28'for x in builds)
 freeze=load(task/'server_implementation_freeze.json')
 for rel,h in freeze['inputs'].items():assert sha(root/rel)==h,rel
 result={'schema':'needlervx.current_physical_evidence_seal.v1','passed':True,'sealed_at':datetime.now(timezone.utc).isoformat(),'implementation_freeze_sha256':sha(task/'server_implementation_freeze.json'),'production_sbit_sha256':logs[0]['sbit_sha256'],'ila_sbit_sha256':logs[1]['sbit_sha256'],'same_functional_synthesis_and_rom':True,'production_requests':51,'production_model_results':49,'fourth_strict':25,'fourth_raw':sum(x['raw_class_correct']for x in fourth),'original12_refused':12,'coremark_production_runs':4,'coremark':cm[0],'same_image_inference':accept['same_image_comparison'],'ila_coremark_crc':True,'ila_analysis_sha256':sha(d/'ila/analysis.json'),'raw_rx_bytes':len(raw),'tx_bytes':sum(x['bytes_written']for x in tx),'unique_tx_ids':54,'raw_text_base64_match':True,'capture_closed':True,'final_ram_state':ila['final_state'],'pwm_ila':pwm,'temperature_production_centidegrees':sorted(set(x['actual']['value']for x in fourth if x['actual']['selected_tool']==0 and x['actual']['execute']==0)),'limits':['Observed regression sets, not blind generalization','No neural NLU superiority over fair rules demonstrated','Internal pre-pad waveform, no external waveform/power/frequency measurement','27MHz nominal, not measured FMAX','No official Needle/YOLO/LLM transplant, burst protocol, DDR PHY or direct HDMI']}
 result['artifact_sha256']={p.relative_to(root).as_posix():sha(p)for p in sorted(d.rglob('*'))if p.is_file()and p.name!='evidence_seal.json'and p.suffix in ['.json','.jsonl','.bin','.txt','.wdf','.dprj','.png','.csv']}
 if write:(d/'evidence_seal.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items()if k not in ['artifact_sha256','pwm_ila']},ensure_ascii=False,indent=2))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--verify-only',action='store_true');x=a.parse_args();main(x.root,not x.verify_only)
