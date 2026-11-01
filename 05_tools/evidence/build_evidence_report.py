#!/usr/bin/env python3
"""Summarize existing frozen evidence without filling unmeasured board fields.

The report preserves each measurement scope. Historical synthetic fixtures,
observed development examples, candidate training and physical FPGA results are
kept separate so a presentation cannot accidentally turn them into a blind test.
"""
from __future__ import annotations
import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '07_runs/release/current_evidence_report.md'
SOURCES = {
    '模型冻结对照': '07_runs/model/current_report.json',
    'UART RTL': '07_runs/model/current_uart_report.json',
    'IRQ RTL': '07_runs/model/current_irq_report.json',
    'CoreMark': '07_runs/coremark/current_report.json',
    '旧合成拒识基线': '07_runs/model/confidence_gate_report.json',
    '118条开发评价': '07_runs/eval/current_independent_report.json',
    'RV32I/M自检': '07_runs/riscv_tests/current_report.json',
    '控制台行为': '05_tools/console/behavior_report.json',
    '运行PMU': '07_runs/model/runtime_pmu_report.json',
    '权重泛化记录': '07_runs/eval/current_generalization_report.json',
    '可选DDR集成': '07_runs/ddr/integration_report.json',
    '软件算子优化': '07_runs/model/optimization/current_report.json',
    # Optional: missing PDS evidence must not prevent an RTL-only report.
    'PDS实现': '07_runs/pds/current_report.json',
}

def load(rel):
    path = ROOT / rel
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        return {'_load_error': str(error)}

def val(value, digits=None):
    if value is None:
        return '待补'
    if isinstance(value, bool):
        return 'True' if value else 'False'
    if isinstance(value, (int, float)):
        return f'{value:,.{digits}f}' if digits is not None else f'{value:,}'
    return str(value).replace('|', '\\|').replace('\n', ' ')

def ratio(numerator, denominator, scale=100):
    if isinstance(numerator, (int, float)) and isinstance(denominator, (int, float)) and denominator:
        return f'{numerator / denominator * scale:.2f}%' if scale == 100 else f'{numerator / denominator:.3f}'
    return '待补'

def fraction(obj, correct, total):
    return f'{val(obj.get(correct))}/{val(obj.get(total))}'

def json_lines(text, prefix):
    rows = []
    for line in text.splitlines():
        if line.startswith(prefix):
            try:
                rows.append(json.loads(line[len(prefix):]))
            except ValueError:
                continue
    return rows

def pmu_rows(obj, path='', scope='', depth=0):
    """Accept nested runtime-parser schemas; display only real counter objects."""
    if depth > 5:
        return []
    rows = []
    if isinstance(obj, dict):
        scope = obj.get('scope', scope)
        if 'cycles' in obj and 'instret' in obj:
            rows.append((path or 'metrics', scope, obj))
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                rows.extend(pmu_rows(value, path + '.' + key, scope, depth + 1))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            rows.extend(pmu_rows(value, f'{path}[{index}]', scope, depth + 1))
    return rows

def main():
    source_paths = dict(SOURCES)
    if not (ROOT / source_paths['权重泛化记录']).exists():
        source_paths['权重泛化记录'] = '04_model/candidate_generalization/export/candidate_evaluation_report.json'
    records = {name: load(rel) for name, rel in source_paths.items()}
    generalization = records['权重泛化记录']
    protocol = load('04_model/candidate_generalization/protocol.json')
    training = load('04_model/export/current_training_report.json') or load('04_model/candidate_generalization/export/candidate_training_report.json')
    model, uart, irq, core = (records[k] for k in ('模型冻结对照', 'UART RTL', 'IRQ RTL', 'CoreMark'))
    confidence, evaluation, isa, console, runtime = (records[k] for k in ('旧合成拒识基线', '118条开发评价', 'RV32I/M自检', '控制台行为', '运行PMU'))
    ddr = records['可选DDR集成']
    pds = records['PDS实现']
    pds_ok = bool(pds) and not pds.get('_load_error')
    bitstream = pds.get('bitstream', {})
    pnr = pds.get('pnr', {})
    timing = pds.get('timing', {})
    capacity = pds.get('capacity', {})
    log_path = ROOT / '07_runs/model/interactive.log'
    log = log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else ''
    host_path = ROOT / '07_runs/model/host_acceptance.log'
    host = host_path.read_text(encoding='utf-8', errors='replace') if host_path.exists() else ''
    host_match = re.search(r'PASS HOST_MODEL:\s*(\d+) checks', host)
    rows = uart.get('results', [])
    lines = ['# NeedleRV-X 冻结证据报告', '',
             '> 此文件只汇总已有记录。PDS实现、RTL仿真与实体测量各自保留范围，位流生成不等于实板功能通过；ILA与实体外设按实际记录填报。', '',
             f"生成时间（UTC）：{datetime.datetime.now(datetime.timezone.utc).isoformat()}", '',
             '## 1. 配置与证据来源', '', '| 项目 | 当前记录 |', '|---|---|',
             '| CPU | RV32IM，五级顺序流水、I/D Cache、BTB/BHT、机器态 CSR/异常/中断 |',
             f"| 目标板 | 盘古200Pro+，PG2L200H-6IFBB676；完整位流生成：{val(bitstream.get('exists'))}，实体板验证：{val(pds.get('physical_board_verified'))} |",
             f"| 模型参考时钟 | {val(model.get('clock_hz'))} Hz，RTL 周期换算 |",
             f"| 模型工作区 | {val(model.get('workspace_bytes'))} bytes |",
             f"| 冻结模型计时范围 | {val(model.get('timing_scope'))} |", '',
             '| 来源 | 文件 | 记录状态 |', '|---|---|---|']
    for name, rel in source_paths.items():
        data = records[name]
        state = ('读取失败：' + val(data.get('_load_error'))) if data.get('_load_error') else ('已有记录' if data else '待补')
        lines.append(f'| {name} | `{rel}` | {state} |')
    lines += ['', '## 2. 冻结模型加速对照', '', '| 输入 | UTF-8 bytes | SW cycles | 最优配置 | 最优 cycles | 加速比 |', '|---|---:|---:|---:|---:|---:|']
    comparisons = model.get('comparisons', [])
    all_runs = []
    numeric_equal = True
    for item in comparisons:
        result = item.get('results', [])
        all_runs.extend(result)
        software = next((r for r in result if r.get('config') == 0), None)
        measured = [r for r in result if isinstance(r.get('cycles'), (int, float)) and r['cycles'] > 0]
        best = min(measured, key=lambda r: r['cycles']) if measured else None
        if software and best:
            lines.append(f"| {val(item.get('text'))} | {val(item.get('utf8_bytes'))} | {val(software.get('cycles'))} | config {val(best.get('config'))} | {val(best.get('cycles'))} | {software['cycles']/best['cycles']:.3f}x |")
            numeric_equal &= all(r.get('logits') == software.get('logits') for r in result)
        else:
            numeric_equal = False
    if not comparisons:
        lines.append('| 待补 | 待补 | 待补 | 待补 | 待补 | 待补 |')
    logit_diffs = [abs(a-b) for item in comparisons
                   for r in item.get('results', [])
                   for a, b in zip(r.get('logits', []), item.get('results', [{}])[0].get('logits', []))
                   if isinstance(a, (int, float)) and isinstance(b, (int, float))]
    lines += ['',
              f"- 已记录 {len(comparisons)} 个输入、{len(all_runs)} 条配置路径；logits 对软件基线相等：{val(numeric_equal if all_runs else None)}；全部后端 failures=0：{val(all(r.get('failures') == 0 for r in all_runs) if all_runs else None)}。",
              f"- 配置间最大logits差：{val(max(logit_diffs) if logit_diffs else None)}；工具执行失败（execute=3）：{val(sum(r.get('execute') == 3 for r in all_runs) if all_runs else None)}；策略/非法参数预期拒绝（execute=1）：{val(sum(r.get('execute') == 1 for r in all_runs) if all_runs else None)}。",
              f"- 模型阶段：{val(model.get('model_stage', model.get('stage')))}。",
              '- 此表是冻结性能对照，来源版本与计时范围保留；不是模型准确率，也不能自动替代当前固件的实板延迟。DMA 字节为片上通路计数，不是已验证 DDR 流量；引擎周期不是完整请求周期。', '',
              '## 3. RV32I/M 与主机软件验收', '',
              f"- 上游主体：{fraction(isa, 'passed', 'total')} 通过，失败 {val(isa.get('failed'))}；确定性总线等待：{val(isa.get('wait_states'))}。",
              f"- 分组：RV32UI {fraction(isa.get('groups', {}).get('rv32ui', {}), 'passed', 'total')}；RV32UM {fraction(isa.get('groups', {}).get('rv32um', {}), 'passed', 'total')}。",
              f"- 报告器负例诊断：{val(isa.get('harness_diagnostics_passed'))}；来源提交：`{val(isa.get('upstream', {}).get('commit'))}`。",
              '- 使用未改动的官方 riscv-tests 指令主体与本项目裸机适配；ma_data 因未对齐陷阱策略排除。裸核+RAM结果不包含 Cache、正式架构认证、PDS 或物理 FPGA。失败摘要包含编号、分支 PC 和陷阱 PC。',
              f"- 主机模型/解码验收：{host_match.group(1) if host_match else '待补'} checks，状态 {'PASS' if host_match else '待补'}；原始日志 `07_runs/model/host_acceptance.log`。",
              '- `decode=8` 为工具语义策略拒绝，将实际工具置为 reject；不是神经模型识别正确，也不是新训练成果。主机验收含后端失败传播、参数边界和策略拒绝。', '',
              '## 4. 语义评价、拒识与权重边界', '',
              f"- 旧 80 条合成模板基线（model_stage={val(confidence.get('model_stage', confidence.get('stage', '历史旧权重fixture，JSON未标stage')))}）：{val(confidence.get('baseline_correct'))}/{val(confidence.get('examples'))} → 单独 margin 门限后 {val(confidence.get('gated_correct'))}/{val(confidence.get('examples'))}，门限 {val(confidence.get('threshold_margin'))}。该结果只对应旧合成 fixture，不能沿用为当前策略准确率或开放中文识别率。"]
    semantic = evaluation.get('semantic', {})
    boundary = evaluation.get('parameter_boundary', {})
    development = evaluation.get('policy_development_comparison', {})
    comparison_label = ('同权重策略开发对照' if development.get('raw_predictions_equal_to_baseline') is True
                        else '历史开发参考（原始分类已改变或基线待补，不能归因仅策略）')
    total = semantic.get('examples', 0) + boundary.get('examples', 0) if evaluation else None
    lines += [f"- 当前开发评价集：{val(total)} 条（语义 {val(semantic.get('examples'))} + 参数 {val(boundary.get('examples'))}）；该集合已经看过并用于策略开发，**不是未观察盲测**。助手编写/冻结的样本也不是独立真实用户采样。",
              f"- 118集报告阶段：{val(evaluation.get('model_stage', evaluation.get('stage', '报告未标stage，需结合本轮部署版本')))}。原始预测对该报告内基线相等：{val(development.get('raw_predictions_equal_to_baseline'))}。该结果只作已观察开发集评价；不同model_stage不得自动混合，当前权重状态另见下表。", '',
              '| 118开发集评价范围（见model_stage） | 结果 | 解释 |', '|---|---:|---|',
              f"| 原始模型语义分类 | {fraction(semantic, 'raw_correct', 'examples')}（{ratio(semantic.get('raw_correct'), semantic.get('examples'))}） | 使用原始 tool 分类 |",
              f"| 策略后结构化结果 | {fraction(semantic, 'structured_correct', 'examples')}（{ratio(semantic.get('structured_correct'), semantic.get('examples'))}） | 含 margin、参数与领域策略，不是模型准确率 |",
              f"| 支持命令可执行覆盖 | {fraction(semantic, 'supported_structured_correct', 'supported_examples')}（{ratio(semantic.get('supported_structured_correct'), semantic.get('supported_examples'))}） | 拒绝支持命令会降低可用性 |",
              f"| 非支持命令不可执行 | {fraction(semantic, 'reject_nonactionable', 'reject_examples')} | 仅此开发集；不构成安全保证 |",
              f"| 隔离参数解码 | {fraction(boundary, 'forced_decoder_correct', 'examples')} | 强制正确工具，仅测十进制语法 |",
              f"| 参数集端到端结构化 | {fraction(boundary, 'end_to_end_structured_correct', 'examples')} | 模型和解码组合 |",
              f"| 非法参数可执行候选 | {val(len(boundary['invalid_actionable_candidates']) if 'invalid_actionable_candidates' in boundary else None)}/{val(boundary.get('invalid_examples'))} | 主机离线候选，不是硬件写操作 |",
              f"| 非支持外设写候选 | {val(len(semantic['unsupported_actuator_write_candidates']) if 'unsupported_actuator_write_candidates' in semantic else None)} | 主机离线候选，不声称实板零误写 |", '',
              f"{comparison_label}：结构化 {val(development.get('baseline_structured_correct'))} → {val(development.get('current_structured_correct'))}；原始分类 {val(development.get('baseline_raw_correct'))} → {val(development.get('current_raw_correct'))}。来源 `07_runs/eval/current_independent_report.json`。"]
    labels = evaluation.get('labels', [])
    confusion = semantic.get('confusion_guarded_rows_actual_columns_predicted', [])
    if labels and confusion:
        lines += ['', '策略后混淆矩阵（行=真实工具，列=实际工具；reject 含策略拒绝）：', '',
                  '| 真实工具 | ' + ' | '.join(labels) + ' |', '|---|' + '---:|' * len(labels)]
        for label, counts in zip(labels, confusion):
            lines.append('| ' + label + ' | ' + ' | '.join(val(x) for x in counts) + ' |')
    lines += ['', '### 预先冻结合成表达集与权重阶段', '',
              f"- 泛化记录 adopted：{val(generalization.get('adopted'))}；candidate_only：{val(generalization.get('candidate_only'))}；model_stage：{val(generalization.get('model_stage', generalization.get('stage')))}。未明确 adopted=True 的记录只当候选实验，不称当前部署成绩。",
              f"- 训练样本：{val(protocol.get('train_examples', training.get('train_examples')))}；预先冻结表达集：{val(protocol.get('fresh_test_examples'))} 条、{val(protocol.get('fresh_test_template_families'))} 个模板族。",
              f"- checkpoint规则：{val(training.get('checkpoint_selection'))}；计划epochs：{val(protocol.get('training_plan', {}).get('epochs'))}。固定最终epoch，不以fresh结果挑checkpoint。",
              '- 所有语言数据是助手编写的合成数据，模板ID/原文分离仍不能排除共享词汇、语法和作者偏差；不表述为真实用户准确率。已观察的90语义/118开发集不升级为盲测。', '',
              '| fresh135评价 | 冻结旧权重 | 新权重（采用状态见上） |', '|---|---:|---:|']
    before = generalization.get('fresh_test_baseline_current_weights', {})
    after = generalization.get('fresh_test_candidate_weights', {})
    for title, correct, total in [('原始神经分类', 'raw_correct', 'examples'),
                                  ('策略后结构化', 'structured_correct', 'examples'),
                                  ('支持命令可执行覆盖', 'supported_actionable', 'supported_examples'),
                                  ('非支持命令不可执行', 'reject_nonactionable', 'reject_examples')]:
        lines.append(f"| {title} | {fraction(before, correct, total)}（{ratio(before.get(correct), before.get(total))}） | {fraction(after, correct, total)}（{ratio(after.get(correct), after.get(total))}） |")
    lines += ['', f"- 新权重宏平均类别正确率：{val(after.get('macro_raw_accuracy') * 100 if isinstance(after.get('macro_raw_accuracy'), (int, float)) else None, 2)}%；该指标不是F1。"]
    alignment = generalization.get('numeric_alignment', {})
    lines += [f"- Python/C整数量化logits对齐：{fraction(alignment, 'exact_logit_matches', 'examples')}；仅证明数值等价，不证明语义正确、RTL或实板。"]
    demonstration = generalization.get('default_counter_demonstration', {})
    if demonstration:
        lines += [f"- 计数器默认演示：{val(demonstration.get('text'))}，来源 `{val(demonstration.get('origin'))}`；不是保留集准确率证据。原21字节输入与新15字节输入分别保留，不能换标签对比延迟。"]
    fresh_confusion = after.get('confusion_guarded', [])
    if fresh_confusion and labels:
        lines += ['', '新权重fresh合成集策略后混淆矩阵（行真实、列实际）：', '',
                  '| 真实工具 | ' + ' | '.join(labels) + ' |', '|---|' + '---:|' * len(labels)]
        for label, counts in zip(labels, fresh_confusion):
            lines.append('| ' + label + ' | ' + ' | '.join(val(x) for x in counts) + ' |')
    lines += ['', '低 margin 不是校准概率；策略可以降低误执行，但会扩大拒绝范围。中文数词/全角数字不在当前 ASCII 十进制参数协议内。', '',
              '## 5. UART、配置切换与控制台', '',
              f"- UART RTL 总状态：{val(uart.get('passed'))}；结果 {len(rows) if uart else '待补'} 条；溢出排空：{val(uart.get('input_overflow_drained'))}。",
              '- 实际 RX 字节流 → UART → 自研 CPU → 神经推理/解码/工具派发；LED/PWM 波形、CoreMark 返回等仍是 RTL 板级环境，实体板待验证。',
              f"- UART 结果中策略拒绝 decode=8：{sum(r.get('decode') == 8 for r in rows) if uart else '待补'} 条；使用 raw tool 与 selected_tool 分开记录，不把策略改写成原始分类。",
              f"- 控制台假 DOM/串口行为检查：{val(console.get('checks'))} checks，失败 {val(console.get('failures'))}；物理板验证：{val(console.get('physical_board_verified'))}。"]
    configs = uart.get('configuration_acknowledgements') or uart.get('configurations') or uart.get('configs') or json_lines(log, 'NR_CONFIG ')
    lines += [f"- 运行配置确认记录：{val([r.get('config') for r in configs if isinstance(r, dict)]) if configs else '待补'}；控制错误次数：{log.count('NR_CONTROL_ERROR invalid_config') if log else '待补'}。",
              '- `:config 0..6` 是固件控制协议，不经过模型；仅在 NR_READY 后发送、收到 NR_CONFIG 后确认。配置 ACK 只证明控制协议响应，配置后实际推理对照仍以 NR_RESULT/验收报告为准。']
    lines += [f"- RTL配置切换验收：{val(uart.get('runtime_config_switch_pass'))}；非法配置保留状态：{val(uart.get('invalid_config_preserves_state'))}；策略拒绝验收：{val(uart.get('policy_denials_pass'))}。",
              f"- 当前UART内运行SW→XND对照加速比：{val(uart.get('runtime_sw_to_xnd_speedup'), 3)}x；它与第2节冻结配置表分别保留，不能混用版本。"]
    if rows:
        lines += ['', '| case | config | 原始/实际工具 | decode/execute | inference cycles | tool cycles | request cycles |', '|---:|---:|---|---|---:|---:|---:|']
        for r in rows:
            lines.append(f"| {val(r.get('case'))} | {val(r.get('config'))} | {val(r.get('tool'))}/{val(r.get('selected_tool'))} | {val(r.get('decode'))}/{val(r.get('execute'))} | {val(r.get('cycles'))} | {val(r.get('tool_cycles'))} | {val(r.get('request_cycles'))} |")
    lines += ['', '## 6. 可选DDR路径行为验证', '']
    if ddr:
        dtests=ddr.get('tests', [])
        lines += [f"- 状态：{val(all(x.get('passed') for x in dtests) if dtests else None)}；范围：{val(ddr.get('scope'))}。",
                   f"- bringup/fault：{', '.join(x.get('name','')+':'+('PASS' if x.get('passed') else 'FAIL') for x in dtests)}。",
                   '- 已覆盖CPU/XND owner锁定仲裁、27MHz与异步UI时钟的一字邮箱CDC、256-bit/32-bit lane与byte strobe、初始化门控、背压、地址边界、超时、晚回复隔离和共同复位。',
                   '- HMIC部分是简化行为模型；没有DDR PHY训练、PDS时序、实板带宽或真实DDR数据。默认ENABLE_DDR=0的盘古顶层仍走片上RAM。']
    else:
        lines += ['- 可选DDR集成记录待补。']
    lines += ['', '## 7. CoreMark 与 PMU', '', '| 项目 | performance | validation |', '|---|---:|---:|']
    p = core.get('runs', {}).get('performance', {})
    v = core.get('runs', {}).get('validation', {})
    for field, title, digits in [('iterations', 'iterations', None), ('cycles', 'cycles', None),
                                 ('seconds_from_cycles', 'seconds @ reference clock', 6),
                                 ('coremark_per_mhz_from_cycles', 'CoreMark/MHz @ reference clock', 6),
                                 ('crc_pass', 'CRC pass', None), ('duration_pass', 'duration >=10s', None)]:
        lines.append(f'| {title} | {val(p.get(field), digits)} | {val(v.get(field), digits)} |')
    lines += ['', f"- CoreMark 范围：{val(core.get('environment'))}；计数器范围：{val(core.get('counter_scope'))}。",
              '- CoreMark 使用自身 timed cycles 和标准 CRC/时长；PMU 额外采样的 cycles 含采样开销，不能替代 CoreMark 成绩。',
              f"- 运行 PMU 解析状态：{val(runtime.get('passed'))}；数据来源：`{val(runtime.get('source'))}`；物理板：{val(runtime.get('physical_board_verified', runtime.get('physical_board')))}。", '',
              '| PMU 记录/范围 | cycles | instret | 条件分支 | 重定向失配 | memory/load stall | I/D misses | 区间 CPI |', '|---|---:|---:|---:|---:|---:|---|---:|']
    counters = pmu_rows(runtime, scope=runtime.get('sampling', ''))
    for name, run in core.get('runs', {}).items():
        if isinstance(run.get('pmu'), dict):
            counters.extend(pmu_rows(run['pmu'], path=f'CoreMark {name} PMU'))
    request_counters = [] if runtime.get('requests') else [(f'UART case {r.get("case")}', 'inference snapshot delta including sampling overhead', r['pmu'])
                        for r in rows if isinstance(r.get('pmu'), dict)]
    if not counters and not request_counters:
        lines.append('| 待补 | 待补 | 待补 | 待补 | 待补 | 待补 | 待补 | 待补 |')
    for path, scope, data in counters + request_counters:
        is_delta = any(token in (path + ' ' + scope).lower() for token in ('bracket', 'delta', 'inference')) and 'cumulative' not in scope.lower()
        cpi = ratio(data.get('cycles'), data.get('instret'), scale=1) if is_delta else '不可按混合/累计范围计算'
        redirects = data.get('redirect_misses', data.get('mispredicts'))
        stalls = data.get('mem_load_stall_cycles', data.get('stalls'))
        lines.append(f"| {val(path)} / {val(scope)} | {val(data.get('cycles'))} | {val(data.get('instret'))} | {val(data.get('branches'))} | {val(redirects)} | {val(stalls)} | {val(data.get('ic_misses'))}/{val(data.get('dc_misses'))} | {cpi} |")
    lines += ['', f"- PMU采样范围：{val(runtime.get('sampling'))}；计时/CPI范围：{val(runtime.get('cpi_scope'))}。",
              '- 重定向失配包含跳转/BTB 情况，不能除以条件分支数宣称错预测率。memory/load stall 包含 memory hold 与 load hazard，不等于单独 load-use 次数。旧累计 metrics 的 timed cycles 与 boot counters 范围可能不同，因此不推导 CPI。', '',
              '## 8. IRQ、PDS实现与待上板字段', '']
    if irq:
        enabled = [r for r in irq.get('runs', []) if r.get('enabled')]
        run = enabled[-1] if enabled else {}
        lines += [f"- timer IRQ：{val(irq.get('irq_during_inference'))}；mcause：`{val(irq.get('timer_cause'))}`；logits 与无 IRQ 对照相等：{val(irq.get('exact_logits_equal'))}。",
                  f"- IRQ count：{val(run.get('irq_count'))}；mepc：{val(run.get('mepc'))}；IRQ时观察到 XND busy：{val(irq.get('xnd_busy_observed_at_irq'))}。",
                  '- 单个 timer IRQ 的完整上下文恢复证明不代表嵌套、多源、重入或 IRQ 命中正在传输 DMA 的证明。']
    else:
        lines.append('- IRQ 记录待补。')
    if pds_ok:
        lines += ['', '### PDS完整工程实现', '',
                  f"- 日期：{val(pds.get('date'))}；工具：{val(pds.get('tool'))}；top：`{val(pds.get('top'))}`；目标：`{val(pds.get('target'))}`。",
                  f"- 布局布线成功：{val(pnr.get('passed'))}；位流存在：{val(bitstream.get('exists'))}；生成时间：{val(bitstream.get('generated_local'))}；SCBV：{val(bitstream.get('scbv'))}。",
                  f"- 位流：`{val(bitstream.get('path'))}`，{val(bitstream.get('bytes'))} bytes；实体板验证：{val(pds.get('physical_board_verified'))}。", '',
                  '| PNR资源 | 使用量 | 器件容量 | 占比 |', '|---|---:|---:|---:|']
        for key, label in [('lut', 'LUT'), ('ff', 'FF'),
                           ('drm36_equivalent', 'DRM（36 Kbit等效）'), ('apm', 'APM')]:
            lines.append(f"| {label} | {val(pnr.get(key))} | {val(capacity.get(key))} | {ratio(pnr.get(key), capacity.get(key))} |")
        lines += [f"| ADC | {val(pnr.get('adc'))} | — | — |", '',
                  f"- 综合LUT：{val(pds.get('synthesis', {}).get('lut'))}；资源表采用PNR最终LUT，不把两个阶段混为同一数值。",
                  f"- 内部时钟：{val(timing.get('clock_hz'))} Hz；setup WNS：{val(timing.get('setup_wns_ns'), 3)} ns；TNS：{val(timing.get('setup_tns_ns'), 3)} ns；slow/fast hold WHS：{val(timing.get('hold_slow_whs_ns'), 3)}/{val(timing.get('hold_fast_whs_ns'), 3)} ns。",
                  f"- PDS估算频率：{val(timing.get('estimated_frequency_mhz'), 4)} MHz；属于实板频率测量：{val(timing.get('estimated_frequency_is_board_measurement'))}。",
                  f"- IO延时约束完整：{val(timing.get('io_delays_complete'))}；UART、按键和复位为异步接口，未完整设置外部input/output delay。内部时钟时序通过不等于完整板级IO时序闭合。",
                  '- ADC原语已经过PDS实现，raw code、温度换算和valid/fault仍需实板测量；UART/LED/PWM/CoreMark与模型延迟也不能由位流生成替代。']
    else:
        lines += ['', '- PDS实现记录尚未提供；这是可选输入，不影响已有RTL/主机证据的生成。']
    lines += ['', '| 字段 | 当前状态 | 下一步 |', '|---|---|---|',
              f"| PDS版本、WNS/TNS、资源 | {'完整工程已有实现记录' if pds_ok else '待补'} | 最高频率实板测量与完整IO延时约束仍待补 |",
              f"| .sbit与实体UART/LED/PWM/复位 | 位流：{val(bitstream.get('exists'))}；实体板：{val(pds.get('physical_board_verified'))} | 固定同一位流，记录串口、外设和复位证据 |",
              '| CoreMark/LUT | 待补 | 用同一版资源和完整时长成绩计算 |',
              f"| 片内温度ADC | {'ADC原语已实现，实板待测' if pds_ok and pnr.get('adc') else '候选RTL'} | raw code、valid/fault、换算公式与实板读数；不可用时保留 unavailable |",
              '| ILA | 待补 | branch redirect、load-use stall、XND busy、UART RX |',
              '| 未观察真实中文集合 | 待补 | 由用户/第三方独立采集，冻结后评价；不再复用118开发集 |', '',
              '## 9. 来源与声明边界', '',
              '- riscv-tests 保留上游 LICENSE；这里只称适配后的指令回归，不称官方认证。CoreMark算法与参赛来源说明保留原始出处。',
              '- Needle 只用于低比特、工具调用和拒识思路；没有移植官方 Needle3，也不是 `.cact` 运行时。',
              '- 公开 GitHub/Huawei 资料为方法对照，不代替本板 PDS 测量；X 未找到可核验硬件数据，未采信。',
              '- 已有PDS资源/时序按第8节实现记录列出；实板最高频率、同版CoreMark/LUT、AI延迟/识别及ILA仍需各自证据，本报告不自动补入尚未取得的数据。']
    optimization_note = ROOT / '07_runs/model/optimization/current_report.md'
    if optimization_note.exists():
        lines += ['', '## 10. 2026-10-07软件算子优化', '',
                  '- 只在权重、RTL与数值协议不变的条件下比较；正式周期关闭profile插桩，范围以原始报告为准。',
                  '- CoreMark、IRQ及DDR章节保留各自既有固件/日期记录，不能自动视为本轮优化固件的新验收。', '',
                  '- 下文为10月7日原始优化记录，保留其周期与当时PDS状态；当前整网周期和PDS状态分别以第2、第8节为准。', '',
                  re.sub(r'(?m)^(#{1,4}) ', lambda match: '##' + match.group(1) + ' ', optimization_note.read_text(encoding='utf-8').strip())]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(OUT)

if __name__ == '__main__':
    main()
