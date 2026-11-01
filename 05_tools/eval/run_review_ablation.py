#!/usr/bin/env python3
"""Run once after implementation freeze; all data are observed regressions."""
from pathlib import Path
import json,subprocess,hashlib,statistics
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];D=R/'07_runs/review_followup_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 freeze=json.loads((D/'server_implementation_freeze.json').read_text())
 for rel,h in freeze['inputs'].items():assert sha(R/rel)==h,rel
 target=D/'ablation_report.json';assert not target.exists(),'Preserve first frozen-version run; do not overwrite'
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(R/'05_tools/eval/ablation_review.c'),'-o',str(D/'ablation_review')],check=True)
 labels=['read_temp','set_pwm','run_coremark','read_counter','set_led','reject'];sets={}
 for name,rel in [('A','07_runs/eval/tool_contract_20261027/first_user_development_report.json'),('B','07_runs/eval/user25_second_20261027/development_report.json'),('C','07_runs/eval/user25_third_20261027/first_report.json'),('D','07_runs/eval/user25_fourth_20261027/first_report.json')]:
  sets[name]=[]
  for row in json.loads((R/rel).read_text())['results']:
   arg=row.get('expected_bit',row.get('expected_argument'))
   op=row.get('expected_operation',1 if row.get('expected_bit_value')==1 else 2 if row.get('expected_bit_value')==0 else 0)
   sets[name].append({'id':row['id'],'text':row['text'],'tool':labels.index(row['intent']),'argument':arg,'operation':op,'observed':True})
 sets['original12']=[{'id':x['id'],'text':x['text'],'tool':5,'argument':None,'operation':0,'observed':True}for x in json.loads((R/'08_review/20261027/adversarial_questions_report.json').read_text())['results']]
 sets['review_contrasts']=[{'id':x['id'],'text':x['text'],'tool':x['expected_tool'],'argument':x['argument'],'operation':x['operation'],'observed':True}for x in[json.loads(t)for t in(D/'modality_development_frozen.jsonl').read_text().splitlines()]]
 report={'generated_at':datetime.now(timezone.utc).isoformat(),'scope':'Server offline integer model and decoder; no dispatch/physical commands; user chose fourth set for regression, no blind holdout claim','implementation_freeze_sha256':sha(D/'server_implementation_freeze.json'),'modes':{'rules':'Transparent unique-domain + same context/capability and numeric parser, includes legal shorthand; no neural invocation','neural':'Raw class + margin, shared numeric parser only, no semantic capability/context rescue; unsafe offline ablation only','hybrid':'Frozen production candidate model+context+capability+schema','neutral_route':'Existing hybrid decoder with neutral reject/zero-margin prediction; diagnostic route ablation, not the sole competitive rule baseline'},'sets':{}}
 for name,rows in sets.items():
  group={'count':len(rows),'in_limit':sum(len(x['text'].encode())<=64 for x in rows),'results':[],'metrics':{}}
  for mode in report['modes']:
   results=[]
   for row in rows:
    a=json.loads(subprocess.check_output([str(D/'ablation_review'),mode,row['text']],text=True));active=a['status']==0 and a['final_index']!=5;over=len(row['text'].encode())>64
    strict=(not active)if row['tool']==5 else(active and a['final_index']==row['tool'] and a['operation']==row['operation']and(row['argument']is None or a['argument']==row['argument']))
    protocol=over and a['status']==5
    results.append({**row,'mode':mode,'actual':a,'strict':strict,'overlength':over,'protocol_refusal':protocol,'unauthorized_action':row['tool']==5 and active,'unauthorized_actuator_write':row['tool']==5 and active and a['final_index']in[1,4],'over_reject':row['tool']!=5 and not over and not active})
   eligible=[x for x in results if not x['overlength']]
   m={'total_in_limit':len(eligible),'strict_correct':sum(x['strict']for x in eligible),'unauthorized_actions':sum(x['unauthorized_action']for x in eligible),'unauthorized_writes':sum(x['unauthorized_actuator_write']for x in eligible),'over_rejections':sum(x['over_reject']for x in eligible),'protocol_overlength_refusals':sum(x['protocol_refusal']for x in results),'host_cpu_time_ns_mean':statistics.mean(x['actual']['host_model_cpu_ns']+x['actual']['host_decode_cpu_ns']for x in eligible),'failed_ids':[x['id']for x in eligible if not x['strict']]}
   slot_rows=[x for x in eligible if x['tool'] in [1,4]]
   m.update({'raw_intent_correct':sum(x['actual']['raw_index']==x['tool'] for x in eligible) if mode in ['neural','hybrid'] else None,
    'effective_intent_correct':sum((x['actual']['final_index'] if x['actual']['status']==0 else 5)==x['tool'] for x in eligible),
    'slot_commands':len(slot_rows),'slot_strict_correct':sum(x['strict'] for x in slot_rows)})
   group['metrics'][mode]=m;group['results']+=results;print(name,mode,json.dumps(m,ensure_ascii=False),flush=True)
  report['sets'][name]=group
 target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 lines=['# 固定版本的规则/神经/混合消融','',report['scope'],'','所有集合均已观察；原首评永久保留。本表不是独立保留集准确率。参数解析为所有路径共享的确定性逻辑，不由神经生成。','', '|集合|模式|严格目标|不应执行却接受|其中写入|过度拒绝|','|---|---|---:|---:|---:|---:|']
 for name,g in report['sets'].items():
  for mode,m in g['metrics'].items():lines.append('|%s|%s|%d/%d|%d|%d|%d|'%(name,mode,m['strict_correct'],m['total_in_limit'],m['unauthorized_actions'],m['unauthorized_writes'],m['over_rejections']))
 lines+=['','rules为包含合法简写的透明规则基线；neutral_route只是关闭模型后的现有救援路径，不得故意只选弱基线来证明神经价值。host CPU纳秒不是FPGA周期，也不含进程启动或串口。','如规则达到或超过混合，本作品应定位为低比特软硬协同推理演示与受限工具控制，不声称已证明NLU优越性。']
 target.with_suffix('.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
