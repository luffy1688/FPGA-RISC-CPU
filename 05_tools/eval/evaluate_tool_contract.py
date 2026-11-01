#!/usr/bin/env python3
"""Score raw neural, typed contract, and rejection separately; preserve first runs."""
from pathlib import Path
import argparse,json,subprocess,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'07_runs/eval/tool_contract_20261027'
LABELS=['read_temp','set_pwm','run_coremark','read_counter','set_led','reject']
STATUS=['OK','REJECTED','MISSING_ARGUMENT','OUT_OF_RANGE','EMPTY','TOO_LONG','BAD_ARGUMENT','BACKEND_ERROR','POLICY_REJECTED']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--second-acceptance',action='store_true');parser.add_argument('--second-development',action='store_true');args=parser.parse_args()
 assert not(args.second_acceptance and args.second_development)
 is_acceptance=args.second_acceptance
 second=is_acceptance or args.second_development
 folder=ROOT/'07_runs/eval/user25_second_20261027' if second else ROOT/'07_runs/eval/user25_20261027'
 dest=(folder/('first_report.json' if is_acceptance else 'development_report.json')) if second else DEV/'first_user_development_report.json'
 if is_acceptance:
  assert not dest.exists(),'First acceptance already exists; never overwrite it'
  assert (DEV/'rtl_report.json').exists() and json.loads((DEV/'rtl_report.json').read_text())['passed']
  assert (DEV/'release_freeze.json').exists(),'Freeze implementation before acceptance'
  frozen=json.loads((DEV/'release_freeze.json').read_text())
  for path,h in frozen['inputs'].items():assert sha(ROOT/path)==h,path
 rows=[json.loads(x)for x in (folder/'frozen_commands.jsonl').read_text().splitlines()if x]
 manifest=json.loads((folder/'frozen_manifest.json').read_text())
 assert sha(folder/'frozen_commands.jsonl')==manifest['dataset_sha256']
 binary=DEV/'command_eval'
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'03_sw/model'),str(ROOT/'03_sw/model/byte_tool_model.c'),str(ROOT/'05_tools/eval/host_command_eval.c'),'-o',str(binary)],check=True)
 results=[];raw_matrix=[[0]*6 for _ in range(6)];selected_matrix=[[0]*6 for _ in range(6)]
 for row in rows:
  a=json.loads(subprocess.check_output([str(binary),'model',row['text']],text=True))
  n=len(row['text'].encode());expected=LABELS.index(row['intent'])
  if n<=64:raw_matrix[expected][a['raw_index']]+=1
  selected_matrix[expected][a['final_index']]+=1
  actionable=a['status']==0 and a['final_index']!=5
  strict=actionable and a['final_index']==expected
  if row.get('desired_action')=='set_led_bit':
   strict=strict and a['operation']==(1 if row['expected_bit_value'] else 2) and a['argument']==row['expected_bit']
  elif row['intent']=='set_led':
   strict=strict and a['operation']==0 and a['argument']==row['expected_argument']
  elif row['expected_argument']is not None:strict=strict and a['argument']==row['expected_argument']
  if row['intent']=='reject':strict=a['final_index']==5 and a['status']in (1,8)
  protocol_refusal=n>64 and a['status']==5 and a['final_index']==5
  results.append({**row,'utf8_bytes':n,'actual':a,'raw_intent_correct':n<=64 and a['raw_index']==expected,'strict_semantic_target_match':strict,'protocol_overlength_refusal':protocol_refusal,'actionable':actionable})
 in_limit=[x for x in results if x['utf8_bytes']<=64]
 metrics={'total':len(rows),'in_limit':len(in_limit),'raw_correct':sum(x['raw_intent_correct']for x in in_limit),'strict_correct':sum(x['strict_semantic_target_match']for x in in_limit),'protocol_overlength_refusals':[x['id']for x in results if x['protocol_overlength_refusal']],'selected_class_match':sum(x['actual']['final_index']==LABELS.index(x['intent']) for x in results),'unsupported_accepted':[x['id']for x in results if x['intent']=='reject'and x['actionable']],'backend_errors':sum(x['actual']['model_rc']!=0 or x['actual']['status']==7 for x in results),'selection_sources':{str(k):sum(x['actual']['selection_source']==k for x in results)for k in range(5)},'supplied_byte_count_mismatches':[x['id']for x in results if 'supplied_utf8_bytes'in x and x['utf8_bytes']!=x['supplied_utf8_bytes']]}
 report={'schema':'needlervx.typed_contract.evaluation.v1','generated_at':datetime.now(timezone.utc).isoformat(),'phase':'first second-user acceptance after release freeze' if is_acceptance else 'observed second-user developmental regression' if second else 'already observed first-user developmental regression','model_stage':'tool_contract_20261027','physical_board_verified':False,'scope':'Server offline integer model + same decoder as firmware; dispatcher behavior independently verified in host/RTL. Rule-selected tools do not count as neural correctness.','dataset_sha256':manifest['dataset_sha256'],'release_freeze_sha256':sha(DEV/'release_freeze.json')if is_acceptance else sha(DEV/'refinement_freeze.json')if second and (DEV/'refinement_freeze.json').exists() else None,'binary_sha256':sha(binary),'metrics':metrics,'labels':LABELS,'raw_confusion_in_limit':raw_matrix,'selected_confusion':selected_matrix,'results':results,'limits':['User text visible during development; second set excluded from training and all prior prediction loops, not developer-blind.','No measured FPGA latency/accuracy claim from this host run.','If used to change code after first run, treat it as observed development; preserve this first report.']}
 dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 title='第二批用户25句首次固定版本评价'if is_acceptance else'第二批已观察用户25句的开发回归'if second else'第一批25句的开发回归（首轮原报告保留）'
 md=['# '+title,'',report['scope'],'',f'- 模型：tool_contract_20261027；原始神经分类 {metrics["raw_correct"]}/{metrics["in_limit"]}；严格语义目标 {metrics["strict_correct"]}/{metrics["in_limit"]}。',
 f'- 超长协议拒绝：{metrics["protocol_overlength_refusals"]}；不支持请求被接受：{metrics["unsupported_accepted"]}；后端错误：{metrics["backend_errors"]}。',
 f'- 选择来源0神经/1只读schema/2明确LED schema/3拒绝/4明确PWM schema：{metrics["selection_sources"]}。',
 f'- 用户填写字节数与实际不一致的编号：{metrics["supplied_byte_count_mismatches"]}；以原文重新编码的实际数为准。',
 '- 服务器离线评价，不是实板测试；schema规则的收益不计入原始模型准确率。','',
 '| 编号 | 原文 | 实际字节 | 期望 | 原始分类 | 最终工具/状态 | 参数/操作/来源 | 严格目标 |','|---|---|---:|---|---|---|---|---|']
 for x in results:
  a=x['actual'];raw=LABELS[a['raw_index']]if a['raw_index']>=0 else'未推理';verdict='通过'if x['strict_semantic_target_match']else'超长协议拒绝'if x['protocol_overlength_refusal']else'未通过'
  md.append(f'| {x["id"]} | {x["text"]} | {x["utf8_bytes"]} | {x["intent"]} | {raw} | {LABELS[a["final_index"]]}/{STATUS[a["status"]]} | {a["argument"]}/{a["operation"]}/{a["selection_source"]} | {verdict} |')
 md+=['','## 原始神经混淆矩阵','', '| 实际/预测 | '+' | '.join(LABELS)+' |','|---|'+'---:|'*6]
 for name,counts in zip(LABELS,raw_matrix):md.append('| '+name+' | '+' | '.join(map(str,counts))+' |')
 md+=['','operation：0整体掩码/普通工具，1单灯开，2单灯关。selection_source：0模型，1只读schema，2明确LED schema，3拒绝，4明确PWM schema。','所有logits、状态和哈希保存在同名JSON；原始输入未改写。','']
 mdpath=dest.with_suffix('.md');mdpath.write_text('\n'.join(md))
 if is_acceptance:
  manifest.update(inference_runs=1,first_evaluated_at=report['generated_at'],first_report_sha256=sha(dest),implementation_freeze_sha256=report['release_freeze_sha256'],now_observed=True)
  (folder/'frozen_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'report':str(dest.relative_to(ROOT)),'metrics':metrics},ensure_ascii=True))
if __name__=='__main__':main()
