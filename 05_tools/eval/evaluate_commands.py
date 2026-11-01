#!/usr/bin/env python3
"""Run a frozen independent command set through the unchanged integer C model.
The boundary mode separates decoder correctness from model semantic quality.
Outputs overwrite stable current_* files; no training or weight export occurs.
"""
import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LABELS = ['read_temp', 'set_pwm', 'run_coremark', 'read_counter', 'set_led', 'reject']
STATUS = ['OK', 'REJECTED', 'MISSING_ARGUMENT', 'OUT_OF_RANGE', 'EMPTY', 'TOO_LONG',
          'BAD_ARGUMENT', 'BACKEND_ERROR', 'POLICY_REJECTED']
ROOT = Path(__file__).resolve().parents[2]

def ratio(n, d):
    return n / d if d else None

def matrix(rows, key):
    result = [[0] * 6 for _ in LABELS]
    for row in rows:
        predicted = row[key]
        if predicted >= 0:
            result[LABELS.index(row['intent'])][predicted] += 1
    return result

def execute(binary, row, forced=False):
    command = [str(binary), 'forced', str(LABELS.index(row['intent'])), row['text']] if forced else [str(binary), 'model', row['text']]
    parsed = json.loads(subprocess.check_output(command, text=True))
    parsed['raw_tool'] = LABELS[parsed['raw_index']] if parsed['raw_index'] >= 0 else None
    parsed['final_tool'] = LABELS[parsed['final_index']]
    parsed['status_name'] = STATUS[parsed['status']]
    parsed['actionable'] = parsed['status'] == 0 and parsed['final_index'] != 5
    parsed['actuator_write_candidate'] = parsed['actionable'] and parsed['final_tool'] in ('set_led', 'set_pwm')
    # Empty/oversized inputs fail before the forced semantic tool is consumed.
    expected_final = 'reject' if row['expected_status'] in ('EMPTY', 'TOO_LONG') else row['intent']
    # Explicit policy rejection is semantically equivalent to rejection for
    # unsupported semantic commands. Parameter-boundary contract stays exact.
    status_correct = parsed['status_name'] == row['expected_status']
    if row['section'] == 'semantic' and row['intent'] == 'reject':
        status_correct = parsed['status_name'] in ('REJECTED', 'POLICY_REJECTED')
    parsed['structured_correct'] = parsed['final_tool'] == expected_final and status_correct and (row['expected_argument'] is None or parsed['argument'] == row['expected_argument'])
    return parsed

def table(matrix_values):
    lines = ['| Actual / Predicted | ' + ' | '.join(LABELS) + ' |', '|---|' + '|'.join(['---:']*6) + '|']
    for label, counts in zip(LABELS, matrix_values):
        lines.append('| ' + label + ' | ' + ' | '.join(map(str, counts)) + ' |')
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT/'04_model/datasets/independent_commands.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT/'07_runs/eval')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    binary = args.binary or args.output/'command_eval'
    rows = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    semantic = [r for r in rows if r['section'] == 'semantic']
    boundary = [r for r in rows if r['section'] == 'parameter_boundary']
    assert len({r['id'] for r in rows}) == len(rows), 'duplicate IDs'
    assert len({r['text'] for r in semantic}) == len(semantic), 'duplicate semantic text'
    assert all(len(r['text'].encode()) <= 64 for r in semantic), 'semantic exceeds firmware input bound'
    overlap = {}
    for name in ('train.jsonl', 'template_development.jsonl', 'template_holdout.jsonl'):
        known = {json.loads(line)['text'] for line in (ROOT/'04_model/datasets'/name).read_text().splitlines() if line.strip()}
        overlap[name] = [r['id'] for r in semantic if r['text'] in known]
    assert not any(overlap.values()), 'independent semantic text overlaps an existing dataset'
    if not args.skip_build:
        subprocess.run(['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I'+str(ROOT/'03_sw/model'), str(ROOT/'03_sw/model/byte_tool_model.c'),
                        str(ROOT/'05_tools/eval/host_command_eval.c'), '-o', str(binary)], check=True)
    results = []
    sem_result = []
    boundary_result = []
    for row in rows:
        actual = execute(binary, row)
        result = dict(row, model=actual)
        if row['section'] == 'semantic':
            sem_result.append(dict(row, **actual))
        else:
            result['forced_decode'] = execute(binary, row, forced=True)
            boundary_result.append(result)
        results.append(result)
    raw_correct = sum(r['raw_tool'] == r['intent'] for r in sem_result)
    guarded_correct = sum(r['final_tool'] == r['intent'] for r in sem_result)
    structured_correct = sum(r['structured_correct'] for r in sem_result)
    supported = [r for r in sem_result if r['intent'] != 'reject']
    rejects = [r for r in sem_result if r['intent'] == 'reject']
    reject_safe = sum(not r['actionable'] for r in rejects)
    rejected_supported = sum(not r['actionable'] for r in supported)
    writes_unsupported = [r['id'] for r in rejects if r['actuator_write_candidate']]
    misroute_supported = [r['id'] for r in supported if r['actuator_write_candidate'] and r['final_tool'] != r['intent']]
    forced_correct = sum(r['forced_decode']['structured_correct'] for r in boundary_result)
    invalid = [r for r in boundary_result if r['expected_status'] != 'OK']
    unsafe_invalid = [r['id'] for r in invalid if r['model']['actionable']]
    invalid_writes = [r['id'] for r in invalid if r['model']['actuator_write_candidate']]
    per_label = {}
    for label in LABELS:
        selected = [r for r in sem_result if r['intent'] == label]
        per_label[label] = {'count':len(selected), 'raw_correct':sum(r['raw_tool']==label for r in selected),
                            'guarded_correct':sum(r['final_tool']==label for r in selected),
                            'structured_correct':sum(r['structured_correct'] for r in selected)}
    per_language = {}
    for language in sorted({r['language'] for r in sem_result}):
        selected = [r for r in sem_result if r['language']==language]
        per_language[language] = {'count':len(selected),'raw_correct':sum(r['raw_tool']==r['intent'] for r in selected),
                                 'structured_correct':sum(r['structured_correct'] for r in selected)}
    report = {
        'format':'nr-independent-command-eval-v1', 'generated_utc':datetime.now(timezone.utc).isoformat(),
        'dataset':str(args.dataset.relative_to(ROOT)), 'dataset_frozen_before_first_prediction':True,
        'author':'Codex, independently composed before predictions; user review pending',
        'model_source':'03_sw/model/byte_tool_model.c with adopted byte_model_data.h; manifest records training stage',
        'model_stage':json.loads((ROOT/'04_model/export/current_manifest.json').read_text(encoding='utf-8')).get('stage','unmarked'),
        'scope':'offline C integer software backend; no FPGA/PDS/real user/temperature/side-effect validation',
        'semantic_exact_text_overlap':overlap, 'labels':LABELS,
        'semantic':{'examples':len(sem_result),'raw_correct':raw_correct,'raw_accuracy':ratio(raw_correct,len(sem_result)),
                    'guarded_correct':guarded_correct,'guarded_accuracy':ratio(guarded_correct,len(sem_result)),
                    'structured_correct':structured_correct,'structured_accuracy':ratio(structured_correct,len(sem_result)),
                    'confusion_raw_rows_actual_columns_predicted':matrix(sem_result,'raw_index'),
                    'confusion_guarded_rows_actual_columns_predicted':matrix(sem_result,'final_index'),
                    'per_label':per_label,'per_language':per_language,
                    'supported_examples':len(supported),'supported_nonactionable':rejected_supported,
                    'supported_structured_correct':sum(r['structured_correct'] for r in supported),
                    'supported_actionable_coverage':ratio(sum(r['actionable'] for r in supported),len(supported)),
                    'all_actionable_candidates':sum(r['actionable'] for r in sem_result),
                    'correct_actionable_candidates':sum(r['actionable'] and r['structured_correct'] for r in sem_result),
                    'reject_examples':len(rejects),'reject_nonactionable':reject_safe,'reject_nonactionable_rate':ratio(reject_safe,len(rejects)),
                    'unsupported_actuator_write_candidates':writes_unsupported,'supported_actuator_misroutes':misroute_supported},
        'parameter_boundary':{'examples':len(boundary_result),'forced_decoder_correct':forced_correct,
                              'forced_decoder_accuracy':ratio(forced_correct,len(boundary_result)),
                              'end_to_end_structured_correct':sum(r['model']['structured_correct'] for r in boundary_result),
                              'invalid_examples':len(invalid),'invalid_actionable_candidates':unsafe_invalid,
                              'invalid_actuator_write_candidates':invalid_writes},
        'minimum_margin':16,
        'status_equivalence':'unsupported semantic reject accepts REJECTED or POLICY_REJECTED; parameter-boundary expected status stays exact',
        'status_histogram':dict(Counter(r['status_name'] for r in sem_result)),
        'limitations':[
            'Assistant-authored development set, not independent human collection and not an open-domain accuracy claim.',
            'Exact text disjointness does not establish semantic/template/source independence.',
            'Ground truth is declared before inference; no post-result sample edits or weight training in this run.',
            'Forced-tool decoder results isolate decimal syntax only and cannot prove model semantic correctness.',
            'A status OK means the dispatcher could execute the request; this offline program writes no hardware.',
            'Low-margin gating is not calibrated probability and cannot guarantee safety against confidently wrong predictions.',
            'Chinese numerals and full-width digits are outside the current ASCII decimal argument contract.'
        ]}
    baseline_path = args.output/'frozen_semantic_baseline.json'
    comparison = None
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text())
        baseline_by_id = {r['id']: r for r in baseline['results']}
        assert {r['id'] for r in baseline['results']} == {r['id'] for r in results}, 'baseline IDs changed'
        assert all(r['text'] == baseline_by_id[r['id']]['text'] for r in results), 'frozen baseline text changed'
        failures_before = [r for r in baseline['results'] if r['section']=='semantic' and not r['model']['structured_correct']]
        comparison = {
            'dataset_already_observed_for_policy_development': True,
            'interpretation':'same frozen observed development set before/after decoder policy; not an unobserved test score',
            'baseline_file':str(baseline_path.relative_to(ROOT)),
            'raw_predictions_equal_to_baseline':all(r['model']['raw_index']==baseline_by_id[r['id']]['model']['raw_index'] and r['model']['logits']==baseline_by_id[r['id']]['model']['logits'] for r in results),
            'baseline_raw_correct':baseline['report']['semantic']['raw_correct'],
            'baseline_structured_correct':baseline['report']['semantic']['structured_correct'],
            'current_raw_correct':raw_correct, 'current_structured_correct':structured_correct,
            'baseline_unsupported_write_candidates':baseline['report']['semantic']['unsupported_actuator_write_candidates'],
            'current_unsupported_write_candidates':writes_unsupported,
            'baseline_failures':failures_before,
            'changed_policy_cases':[{'id':r['id'],'text':r['text'],'before':baseline_by_id[r['id']]['model'],'after':r['model']} for r in results if (r['model']['final_index'],r['model']['status'],r['model']['argument']) != (baseline_by_id[r['id']]['model']['final_index'],baseline_by_id[r['id']]['model']['status'],baseline_by_id[r['id']]['model']['argument'])]
        }
        comparison['weights_changed_from_initial_baseline'] = not comparison['raw_predictions_equal_to_baseline']
        if comparison['weights_changed_from_initial_baseline']:
            comparison['interpretation'] = 'same frozen observed development set comparing model weights and decoder policy; not an unobserved test score'
        report['policy_development_comparison'] = comparison

    (args.output/'current_independent_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (args.output/'current_independent_results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in results))
    md = [
        '# 独立命令开发评价（冻结集）', '',
        '这组句子由 Codex 在查看新结果之前逐句编写，尚未由参赛者审定。它与现有训练、开发、留出集不存在完全相同的语义句子；这不等于来自独立真实用户，也不能证明没有相似模板。固定权重未重新训练。', '',
        f'- 语义样例：{len(sem_result)} 条，每类 15 条；中文和英文混合。',
        f'- 原始分类：{raw_correct}/{len(sem_result)} = {raw_correct/len(sem_result):.2%}。',
        f'- 分差拒识后的分类：{guarded_correct}/{len(sem_result)} = {guarded_correct/len(sem_result):.2%}。',
        f'- 工具、状态与参数全部正确：{structured_correct}/{len(sem_result)} = {structured_correct/len(sem_result):.2%}。',
        f'- 不支持/否定指令未形成可执行请求：{reject_safe}/{len(rejects)}；支持的指令未形成可执行请求：{rejected_supported}/{len(supported)}。',
        f'- 不支持指令中的 LED/PWM 写入候选：{len(writes_unsupported)}；支持指令错误路由到 LED/PWM 的候选：{len(misroute_supported)}。', '',
        '“候选”表示状态 OK 且工具为 LED/PWM；本离线程序不执行实际外设操作。',
        f'本集允许执行 {sum(r["actionable"] for r in sem_result)} 条，其中结构化请求正确 {sum(r["actionable"] and r["structured_correct"] for r in sem_result)} 条。这个小型已观察开发集不能给出普适安全保证。', '',
        '## 原始分类混淆矩阵', '',table(report['semantic']['confusion_raw_rows_actual_columns_predicted']), '',
        '## 分差拒识后混淆矩阵', '',table(report['semantic']['confusion_guarded_rows_actual_columns_predicted']), '',
        '## 参数边界', '',
        f'- 显式指定预期工具、仅评价十进制解码器：{forced_correct}/{len(boundary_result)}。',
        f'- 同样边界走完整模型加解码：{report["parameter_boundary"]["end_to_end_structured_correct"]}/{len(boundary_result)}。',
        f'- 无效参数仍产生可执行工具候选：{len(unsafe_invalid)}/{len(invalid)}，其中 LED/PWM 写入候选 {len(invalid_writes)}。',
        '- ASCII 十进制整数是当前明确支持的参数格式；中文数字、全角数字不在协议中。', '',
        '## 解释与后续使用', '',
        '- 参数解码器通过不代表语义模型能理解否定词或所有表达；分差门也不能阻止高分差的错误。',
        '- 应将本报告作为发现薄弱项的开发评价，不能挑出成功句子后宣称泛化准确率提高。',
        '- 若以后用这些失败句子训练，需另立一份未用于训练的新评价集，保留当前报告的历史含义。',
        '- 本次没有 PDS、实板、实际温度或外设安全结论；标准基准与 RTL 性能数字不因这次主机评价改变。', '',
        '复现：`python3 05_tools/eval/evaluate_commands.py`。逐条结果见 `current_independent_results.jsonl`。', '']
    if comparison:
        md.insert(2, '**当前性质：这份冻结集已经被观察，后续结果只用于同集调度策略开发对照，不能再称未经观察的独立测试成绩。原始分类与旧策略结果已保留。**\n')
        md.extend([
            '## 已观察开发集的模型与调度对照', '',
            f'- 原始分类基线：{comparison["baseline_raw_correct"]}/90；当前原始分类：{raw_correct}/90。',
            f'- 全部原始 logit 与分类逐句保持一致：{comparison["raw_predictions_equal_to_baseline"]}。',
            f'- 严格工具、状态和参数正确：旧解码 {comparison["baseline_structured_correct"]}/90 → 当前 {structured_correct}/90。',
            f'- 不支持命令的 LED/PWM 写入候选：旧解码 {len(comparison["baseline_unsupported_write_candidates"])} → 当前 {len(writes_unsupported)}。',
            ('- 本轮包含模型权重更新；raw变化与调度后的变化分别报告，不能将两者混称。' if comparison['weights_changed_from_initial_baseline'] else '- 本轮变化属于确定性调度策略，不能写成神经网络分类准确率提高。'),
            '- 不支持语义的正确拒绝包括 REJECTED 和新增 POLICY_REJECTED；参数边界状态仍逐项精确比较。', '',
            '### 首轮失败例句（保留原始结果）', '',
            '| ID | 句子 | 预期 | 首轮最终工具/状态 | 分差 |',
            '|---|---|---|---|---:|'])
        old_failures = comparison['baseline_failures']
        priority = [r for r in old_failures if r['id'] in ('sem-reject-10','sem-reject-11')]
        priority += [r for r in old_failures if r not in priority][:14]
        for row in priority:
            m=row['model']
            md.append(f'| {row["id"]} | {row["text"]} | {row["intent"]} | {m["final_tool"]}/{m["status_name"]} | {m["margin"]} |')
        md.extend(['', '全部首轮118条结果保存于 `frozen_semantic_baseline.json`；当前逐句变化见 JSON 报告 `policy_development_comparison`。', ''])

    (args.output/'current_independent_report.md').write_text('\n'.join(md))
    print(json.dumps({'semantic_raw':f'{raw_correct}/{len(sem_result)}','semantic_guarded':f'{guarded_correct}/{len(sem_result)}',
                      'structured':f'{structured_correct}/{len(sem_result)}','reject_nonactionable':f'{reject_safe}/{len(rejects)}',
                      'forced_decoder':f'{forced_correct}/{len(boundary_result)}','unsupported_actuator_write_candidates':writes_unsupported,
                      'invalid_actionable_candidates':unsafe_invalid},ensure_ascii=False))
    # This is an evaluation, not a fabricated pass threshold. Structural/runtime
    # errors abort above; a low semantic score is reported honestly, not hidden.

if __name__ == '__main__':
    main()
