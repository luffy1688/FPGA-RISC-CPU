#!/usr/bin/env python3
"""Evaluate the frozen user set without training or peripheral execution."""
from pathlib import Path
import hashlib,json,subprocess
from collections import Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'07_runs/eval/user25_20261027'
LABELS=['read_temp','set_pwm','run_coremark','read_counter','set_led','reject']
STATUS=['OK','REJECTED','MISSING_ARGUMENT','OUT_OF_RANGE','EMPTY','TOO_LONG','BAD_ARGUMENT','BACKEND_ERROR','POLICY_REJECTED']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 dataset=OUT/'frozen_commands.jsonl'
 manifest=json.loads((OUT/'frozen_manifest.json').read_text())
 assert sha(dataset)==manifest['dataset_sha256']
 rows=[json.loads(s) for s in dataset.read_text().splitlines() if s]
 binary=OUT/'command_eval'
 inputs=[ROOT/'03_sw/model/byte_tool_model.c',ROOT/'03_sw/model/byte_tool_model.h',ROOT/'03_sw/model/byte_model_data.h',ROOT/'05_tools/eval/host_command_eval.c',ROOT/'03_sw/model/main.c']
 before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'03_sw/model'),str(inputs[0]),str(inputs[3]),'-o',str(binary)],check=True)
 canary=json.loads(subprocess.check_output([str(binary),'model','led 37'],text=True))
 assert canary['logits']==[-524,-154,-376,-286,526,327] and canary['final_index']==4 and canary['argument']==37
 results=[]
 for row in rows:
  actual=json.loads(subprocess.check_output([str(binary),'model',row['text']],text=True))
  actual.update(raw_tool=LABELS[actual['raw_index']] if actual['raw_index']>=0 else None,final_tool=LABELS[actual['final_index']],status_name=STATUS[actual['status']])
  actionable=actual['status']==0 and actual['final_index']!=5
  strict=actionable and actual['final_tool']==row['intent'] and (row['expected_argument'] is None or actual['argument']==row['expected_argument'])
  note=''
  if row['desired_action']=='set_led_bit':
   strict=False;note='Current schema sets an entire LED mask, not an individual bit while preserving the others.'
  elif row['intent']=='reject':
   strict=actual['final_tool']=='reject' and actual['status'] in (1,5,8)
   if actual['status']==5:note='81 UTF-8 bytes exceeds 64-byte interface; rejected before model. Not evidence of semantic refusal.'
   elif actionable:note='Unsupported requested action was accepted as a supported substitute.'
  if len(row['text'].encode())>64:assert actual['raw_index']==-1 and actual['status']==5
  results.append({**row,'utf8_bytes':len(row['text'].encode()),'actual':actual,'raw_intent_correct':actual['raw_tool']==row['intent'],'final_class_matches':actual['final_tool']==row['intent'],'strict_decoded_target_matches':strict,'actionable':actionable,'actuator_write_candidate':actionable and actual['final_tool'] in ('set_led','set_pwm'),'note':note})
 assert before=={str(p.relative_to(ROOT)):sha(p) for p in inputs},'Production sources changed during evaluation'
 eligible=[r for r in results if r['utf8_bytes']<=64]
 def matrix(key,items):
  m=[[0]*6 for _ in range(6)]
  for r in items:
   label=r['actual'][key]
   if label is not None:m[LABELS.index(r['intent'])][LABELS.index(label)]+=1
  return m
 metrics={
  'total':len(rows),'in_interface_limit':len(eligible),'oversize_ids':[r['id'] for r in results if r['utf8_bytes']>64],
  'raw_correct_all':sum(r['raw_intent_correct'] for r in results),'raw_denominator_all':len(rows),
  'raw_correct_in_limit':sum(r['raw_intent_correct'] for r in eligible),'raw_denominator_in_limit':len(eligible),
  'pipeline_class_match_all':sum(r['final_class_matches'] for r in results),
  'strict_decoded_target_match_all':sum(r['strict_decoded_target_matches'] for r in results),
  'strict_decoded_target_match_in_limit':sum(r['strict_decoded_target_matches'] for r in eligible),
  'out_of_schema_led_ids':[r['id'] for r in results if r['desired_action']=='set_led_bit'],
  'unsupported_in_limit':sum(r['intent']=='reject' for r in eligible),
  'unsupported_semantically_refused_in_limit':sum(r['intent']=='reject' and r['actual']['final_tool']=='reject' and r['actual']['status'] in (1,8) for r in eligible),
  'unsupported_accepted_ids':[r['id'] for r in results if r['intent']=='reject' and r['actionable']],
  'unsupported_actuator_write_candidate_ids':[r['id'] for r in results if r['intent']=='reject' and r['actuator_write_candidate']],
  'backend_failures':sum(r['actual']['model_rc']!=0 or r['actual']['status']==7 for r in results)}
 report={'schema':'needlervx.user25.frozen_evaluation.v1','generated_at':datetime.now(timezone.utc).isoformat(),'scope':'Offline integer C model plus same decode_prediction entry used in interactive firmware. No peripheral dispatcher or FPGA execution. Original user text, weights, threshold and production sources unchanged.',
  'dataset_manifest':manifest,'source_sha256':before,'evaluator_sha256':sha(Path(__file__)),'binary_sha256':sha(binary),'gcc':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],
  'known_board_led37_logits_match':True,'labels':LABELS,'metrics':metrics,'raw_confusion_in_limit':matrix('raw_tool',eligible),'pipeline_confusion_all':matrix('final_tool',results),'results':results,
  'limits':['User supplied set; external human authorship and broader representativeness not verified.','Exact text overlap absent in four checked datasets; this does not prove absence of semantic/template overlap.','Set now observed; any changes based on it require a fresh held-out set for independent accuracy claims.','Classification, guarded decoding and actual physical execution are different facts.','LED bit-update commands are outside the deployed full-mask tool contract.','ID25 is too long and never reaches neural inference. Protocol refusal is not semantic understanding.']}
 (OUT/'current_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 cn={'read_temp':'温度','set_pwm':'PWM','run_coremark':'CoreMark','read_counter':'计数器','set_led':'LED','reject':'拒绝',None:'未推理'}
 md=['# 用户25条原文冻结评价','',f'生成：{report["generated_at"]}。服务器离线整数C模型与交互固件的decode_prediction入口；没有执行外设，未训练或修改生产源码。','',
 f'- 输入冻结SHA256：{manifest["dataset_sha256"]}。',
 f'- 原始神经分类：{metrics["raw_correct_all"]}/25；64字节范围内{metrics["raw_correct_in_limit"]}/24。第25条81字节，超限，未推理。',
 f'- 策略后工具类别匹配：{metrics["pipeline_class_match_all"]}/25；严格解码目标匹配：{metrics["strict_decoded_target_match_all"]}/25。',
 f'- 第5～8条是单LED开关，而现工具为整体掩码，严格目标不算通过。',
 f'- 范围内不支持请求的语义拒绝：{metrics["unsupported_semantically_refused_in_limit"]}/4；超限第25条另计。',
 f'- 不支持请求被接受的编号：{metrics["unsupported_accepted_ids"]}；其中LED/PWM写入候选：{metrics["unsupported_actuator_write_candidate_ids"]}。',
 '- 仅是用户提供25句的当前快照，不代表通用中文准确率。此集已观察，后续按它修改后不能继续称盲测。','',
 '| 编号 | 原文 | 字节 | 期望 | 原始分类 | 策略后/状态/参数 | 严格目标 |','|---|---|---:|---|---|---|---|']
 for r in results:
  a=r['actual'];md.append(f'| {r["id"]} | {r["text"]} | {r["utf8_bytes"]} | {cn[r["intent"]]} | {cn[a["raw_tool"]]} | {cn[a["final_tool"]]}/{a["status_name"]}/{a["argument"]} | {"通过" if r["strict_decoded_target_matches"] else "未通过"} |')
 md+=['','## 原始神经分类混淆矩阵（24条范围内原文）','','行是真实类别，列为预测类别；顺序温度/PWM/CoreMark/计数器/LED/拒绝。','',
 '| 实际/预测 | 温度 | PWM | CoreMark | 计数器 | LED | 拒绝 |','|---|---:|---:|---:|---:|---:|---:|']
 for label,values in zip(LABELS,report['raw_confusion_in_limit']):md.append('| '+cn[label]+' | '+' | '.join(map(str,values))+' |')
 md+=['','逐条logits、分差、来源哈希和策略后混淆矩阵见同目录current_report.json。保持原文，不截断第25条，不将LED编号当整体掩码来提高分数。','']
 (OUT/'current_report.md').write_text('\n'.join(md))
 print(json.dumps(metrics,ensure_ascii=True))
 for r in results:print(r['id'],r['actual']['raw_tool'],r['actual']['final_tool'],r['actual']['status_name'],r['actual']['argument'],r['strict_decoded_target_matches'])
if __name__=='__main__':main()
