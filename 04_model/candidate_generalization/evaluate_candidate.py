#!/usr/bin/env python3
"""Candidate final-epoch offline check; never overwrites production reports."""
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CANDIDATE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'04_model/golden'))
sys.path.insert(0,str(ROOT/'05_tools/eval'))
from fixed_reference import FixedModel
from evaluate_commands import execute, LABELS, matrix, table

def summarize(rows):
    raw=sum(r['raw_tool']==r['intent'] for r in rows)
    structured=sum(r['structured_correct'] for r in rows)
    per_label={}
    for label in LABELS:
        chosen=[r for r in rows if r['intent']==label]
        per_label[label]={'examples':len(chosen),'raw_correct':sum(r['raw_tool']==label for r in chosen),'structured_correct':sum(r['structured_correct'] for r in chosen)}
    supported=[r for r in rows if r['intent']!='reject']
    rejects=[r for r in rows if r['intent']=='reject']
    return {'examples':len(rows),'raw_correct':raw,'raw_accuracy':raw/len(rows),
            'macro_raw_accuracy':sum(v['raw_correct']/v['examples'] for v in per_label.values())/6,
            'structured_correct':structured,'structured_accuracy':structured/len(rows),
            'per_label':per_label,'confusion_raw':matrix(rows,'raw_index'),'confusion_guarded':matrix(rows,'final_index'),
            'supported_examples':len(supported),'supported_actionable':sum(r['actionable'] for r in supported),
            'reject_examples':len(rejects),'reject_nonactionable':sum(not r['actionable'] for r in rejects),
            'unsupported_actuator_write_candidates':[r['id'] for r in rejects if r['actuator_write_candidate']],
            'supported_actuator_misroutes':[r['id'] for r in supported if r['actuator_write_candidate'] and r['final_tool']!=r['intent']]}

def evaluate(binary, data):
    return [dict(row,**execute(binary,row)) for row in data]

def main():
    assert (CANDIDATE/'candidate.pt').exists(), 'training must finish first'
    cdir=CANDIDATE/'c_model'
    cdir.mkdir(parents=True,exist_ok=True)
    (CANDIDATE/'export').mkdir(parents=True,exist_ok=True)
    for name in ('byte_tool_model.c','byte_tool_model.h'):
        (cdir/name).write_text((ROOT/'03_sw/model'/name).read_text())
    binary=CANDIDATE/'candidate_command_eval'
    baseline_binary=CANDIDATE/'baseline_command_eval'
    subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(cdir),str(cdir/'byte_tool_model.c'),str(ROOT/'05_tools/eval/host_command_eval.c'),'-o',str(binary)],check=True)
    subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'03_sw/model'),str(ROOT/'03_sw/model/byte_tool_model.c'),str(ROOT/'05_tools/eval/host_command_eval.c'),'-o',str(baseline_binary)],check=True)
    fresh=[json.loads(l) for l in (CANDIDATE/'datasets/fresh_semantic_holdout.jsonl').read_text().splitlines()]
    observed=[json.loads(l) for l in (CANDIDATE/'datasets/observed_development.jsonl').read_text().splitlines()]
    train=[json.loads(l) for l in (CANDIDATE/'datasets/augmented_train.jsonl').read_text().splitlines()]
    assert not {r['text'].lower() for r in train}&{r['text'].lower() for r in fresh}
    assert not {r['template_id'] for r in train}&{r['template_id'] for r in fresh}
    candidate=evaluate(binary,fresh)
    baseline=evaluate(baseline_binary,fresh)
    development=evaluate(binary,observed)
    fixed=FixedModel(CANDIDATE/'export/candidate_int4.npz')
    mismatches=[]
    for row in candidate:
        ref=fixed.infer(row['text'])
        if ref['logits']!=row['logits'] or ref['index']!=row['raw_index']:
            mismatches.append({'id':row['id'],'python':ref,'C':row})
    required=[]
    for text,label,arg,status in [('led37','set_led',37,'OK'),('pwm -1','set_pwm',None,'OUT_OF_RANGE'),('hello','reject',None,'REJECTED'),('我想查看计数器','read_counter',None,'OK')]:
        row={'id':'bringup/'+text,'section':'semantic','text':text,'intent':label,'expected_argument':arg,'expected_status':status}
        required.append(dict(row,**execute(binary,row)))
    report={'candidate_only':True,'adopted':False,'evaluation_phase':'observed reproduction; original first-final-epoch report preserved in 07_runs/eval/current_generalization_report.json','architecture_unchanged':{'dim':64,'layers':2,'heads':4,'max_utf8_bytes':64},
            'fresh_test_protocol':'new assistant-authored expression templates frozen before training; evaluated at predetermined final epoch only; not used to train/select checkpoint',
            'fresh_test_baseline_current_weights':summarize(baseline),'fresh_test_candidate_weights':summarize(candidate),
            'observed_development_candidate':summarize(development),'numeric_alignment':{'examples':len(candidate),'exact_logit_matches':len(candidate)-len(mismatches),'mismatches':mismatches,'meaning':'numeric equivalence only, not recognition accuracy'},
            'required_bringup_inputs':required,
            'limitations':['All language data are synthetic and Codex-authored, not real user collection.','Template ID and exact-text separation do not eliminate shared vocabulary/grammar or author bias.','Observed independent_commands is development only; cannot call its improvement a blind-test result.','Current decoder policy may reject otherwise correct neural predictions and does not correct raw model decisions.','No RTL cycle/FMAX/resource/physical-board claim follows from this candidate check.','Candidate remains isolated until root adopts and regenerates firmware/golden/performance evidence.']}
    (CANDIDATE/'export/candidate_evaluation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (CANDIDATE/'export/fresh_test_predictions.jsonl').write_text(''.join(json.dumps({'id':c['id'],'text':c['text'],'intent':c['intent'],'baseline':b,'candidate':c},ensure_ascii=False)+'\n' for b,c in zip(baseline,candidate)))
    (CANDIDATE/'export/observed_development_predictions.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in development))
    base=report['fresh_test_baseline_current_weights']; cand=report['fresh_test_candidate_weights']; dev=report['observed_development_candidate']
    md=['# 数据泛化候选报告', '',
        '**候选尚未采用，当前权重、固件和RTL性能报告未覆盖。**', '',
        '- 架构保持 d64 / 两层 / 四头 / 最多64 UTF-8字节；47,066字节模型常量。',
        '- 3000条训练句子，六类各500；加入否定、不支持设备、多工具请求；数字随机0..999，部分逐位替换为#。数字合法性仍由显式十进制解码器判断。',
        '- 新135句、70表达模板的测试集先冻结；固定最后100epoch权重，不使用test选checkpoint。作者Codex，全部合成，非真实用户。', '',
        f'- 新模板定点原始分类：当前权重 {base["raw_correct"]}/135 ({base["raw_accuracy"]:.2%}) → 候选 {cand["raw_correct"]}/135 ({cand["raw_accuracy"]:.2%})。',
        f'- 新模板宏平均原始分类：{base["macro_raw_accuracy"]:.2%} → {cand["macro_raw_accuracy"]:.2%}。',
        f'- 新模板严格工具/状态/参数：{base["structured_correct"]}/135 → {cand["structured_correct"]}/135。',
        f'- 新模板不支持请求未执行：{cand["reject_nonactionable"]}/{cand["reject_examples"]}；支持请求允许执行：{cand["supported_actionable"]}/{cand["supported_examples"]}。',
        f'- 已观察90句开发集的候选原始分类 {dev["raw_correct"]}/90，严格结构化 {dev["structured_correct"]}/90；不能称盲测。',
        f'- Python/C定点logit精确一致：{len(candidate)-len(mismatches)}/{len(candidate)}。', '',
        '## 新模板原始分类混淆矩阵', '',table(cand['confusion_raw']), '',
        '## 新模板策略后混淆矩阵', '',table(cand['confusion_guarded']), '',
        '## 必要边界', '',
        '- 原始神经网络分类与确定性拒识策略分别报告；策略不会纠正分类。',
        '- 这次只评价服务器软件，不改PDS、不生成.sbit、不声称性能/实板验证。',
        '- 若采用候选，需要更新当前导出、C常量、golden与固件，再验证已有RTL工具路径。', '']
    (CANDIDATE/'export/candidate_evaluation_report.md').write_text('\n'.join(md))
    print(json.dumps({'fresh_baseline_raw':base['raw_correct'],'fresh_candidate_raw':cand['raw_correct'],'fresh_examples':len(candidate),'baseline_structured':base['structured_correct'],'candidate_structured':cand['structured_correct'],'development_raw':dev['raw_correct'],'development_structured':dev['structured_correct'],'numeric_matches':len(candidate)-len(mismatches),'bringup_correct':[r['structured_correct'] for r in required]},ensure_ascii=False))
    if mismatches: raise SystemExit(1)
if __name__=='__main__': main()
