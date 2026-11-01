#!/usr/bin/env python3
"""Needle-inspired candidate generation and review chain for the FPGA tool model.

This script deliberately keeps the production model untouched. It imports the
vendored Needle schema builder to generate the same JSON tool-schema shape, then
creates a small, inspectable candidate set, applies explicit review rules, and
writes an optional training append file. The server currently has no official
Needle engine/weights installed, so this is schema-reference generation rather
than an official Needle model inference run; the report records that boundary.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import sys
from collections import Counter

# The vendored Needle schema helper uses PEP 604 annotations. Re-run with
# the bundled Python 3.12 when the server EDA shell exposes Python 3.8.
if sys.version_info < (3, 10) and os.environ.get("NR_NEEDLE_REEXEC") != "1":
    _py312 = "/usr/bin/python3.12"
    if os.path.exists(_py312):
        os.environ["NR_NEEDLE_REEXEC"] = "1"
        os.execv(_py312, [_py312, *sys.argv])
from pathlib import Path
try:
    from typing import Annotated, Optional
except ImportError:  # Python 3.8 on the server
    from typing import Optional
    from typing_extensions import Annotated

ROOT = Path(__file__).resolve().parents[2]
CHAIN = Path(__file__).resolve().parent
OUT = CHAIN / "export"
NEEDLE_TOOLS = ROOT / "09_refs" / "needle" / "needle" / "agent" / "tools.py"
COMMIT = "6bd836d521a2991510bf303cd0d87e025e8ce9dc"

# The definitions mirror the fixed FPGA command surface. They are not runtime
# implementations: the board-side decoder remains the authority at execution.
def set_led(value: Annotated[int, "LED code 0..255"]):
    "Set the board LED display code."

def set_pwm(percent: Annotated[int, "PWM duty 0..100 percent"]):
    "Set the board PWM duty cycle in percent."

def read_counter():
    "Read the CPU cycle/event counter."

def read_temp():
    "Read the FPGA die temperature sample."

def run_coremark():
    "Run the CoreMark performance test and report its score."

TOOLS = {
    "set_led": set_led,
    "set_pwm": set_pwm,
    "read_counter": read_counter,
    "read_temp": read_temp,
    "run_coremark": run_coremark,
}

# These are deliberately short, human-readable seed expressions. The values
# exercise normal actions, range boundaries, and rejection/multi-action cases.
SEEDS = [
    ("read_temp", ["读取芯片温度", "帮我采集 FPGA 内部温度", "查询一下当前结温", "请报告片内温度"]),
    ("read_counter", ["读取计数器", "查看 CPU 周期计数", "报告当前事件计数", "帮我读一下计数器"]),
    ("run_coremark", ["运行 CoreMark", "开始 CoreMark 性能测试", "测一下处理器 CoreMark", "执行一次性能基准"]),
    ("set_led", ["把 LED 设为 {v}", "设置板上灯光代码 {v}", "LED 显示值改成 {v}", "请将指示灯编码设为 {v}"]),
    ("set_pwm", ["把 PWM 调到 {v}%", "设置 PWM 占空比 {v}", "将板上 PWM 设为 {v}％", "输出 {v} 的 PWM"]),
    ("reject", ["播放一段音乐", "帮我打开浏览器", "同时点亮 LED 并设置 PWM 为 50", "撤销刚才的操作"]),
]

# Values include ordinary values and legal boundary values. Review rules reject
# out-of-range values and multi-call candidates before any training append.
VALUES = {"set_led": [0, 37, 128, 255], "set_pwm": [0, 25, 50, 100]}
INVALID = [
    {"id": "invalid-pwm-range", "text": "把 PWM 调到 120%", "intent": "set_pwm", "function_calls": [{"name": "set_pwm", "arguments": {"percent": 120}}], "arg": 120},
    {"id": "invalid-multi-call", "text": "同时点亮 LED 并设置 PWM 为 50", "intent": "set_led", "function_calls": [{"name": "set_led", "arguments": {"value": 1}}, {"name": "set_pwm", "arguments": {"percent": 50}}], "arg": 1},
]

def load_official_schema_builder():
    spec = importlib.util.spec_from_file_location("needle_reference_tools", NEEDLE_TOOLS)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

def build_schema():
    module = load_official_schema_builder()
    schemas = [module.build_schema(fn) for fn in TOOLS.values()]
    # The vendored source has no schema for reject: Needle represents an
    # off-topic request as an empty function_calls list.
    return schemas

def candidate_rows():
    rows = []
    i = 0
    for intent, texts in SEEDS:
        if intent in VALUES:
            for text_template in texts:
                for value in VALUES[intent]:
                    param = "value" if intent == "set_led" else "percent"
                    text = text_template.format(v=value)
                    rows.append({"candidate_id": f"seed-{i:03d}", "text": text, "intent": intent,
                                 "function_calls": [{"name": intent, "arguments": {param: value}}], "arg": value,
                                 "generator": "needle-schema-reference", "review_status": "pending"})
                    i += 1
        elif intent == "reject":
            for text in texts:
                rows.append({"candidate_id": f"seed-{i:03d}", "text": text, "intent": "reject",
                             "function_calls": [], "arg": None,
                             "generator": "needle-schema-reference", "review_status": "pending"})
                i += 1
        else:
            for text in texts:
                rows.append({"candidate_id": f"seed-{i:03d}", "text": text, "intent": intent,
                             "function_calls": [{"name": intent, "arguments": {}}], "arg": None,
                             "generator": "needle-schema-reference", "review_status": "pending"})
                i += 1
    for item in INVALID:
        row = dict(item)
        row["generator"] = "needle-schema-reference"
        row["review_status"] = "pending"
        rows.append(row)
    return rows

def review(row):
    calls = row["function_calls"]
    if row["intent"] == "reject":
        if calls:
            return False, "reject intent must have empty function_calls"
        return True, "off-topic or unsupported action; empty call is required"
    if len(calls) != 1:
        return False, "FPGA demo accepts one deterministic action per request"
    call = calls[0]
    if call["name"] not in TOOLS:
        return False, "tool is outside the board command surface"
    args = call.get("arguments", {})
    if call["name"] == "set_led" and not (0 <= int(args.get("value", -1)) <= 255):
        return False, "LED value outside 0..255"
    if call["name"] == "set_pwm" and not (0 <= int(args.get("percent", -1)) <= 100):
        return False, "PWM percent outside 0..100"
    if call["name"] in ("read_temp", "read_counter", "run_coremark") and args:
        return False, "read/test tool does not accept arguments"
    return True, "schema, cardinality, and board range reviewed"

def append_rows(rows):
    out = []
    for r in rows:
        if r["intent"] == "reject":
            continue
        arg = r.get("arg")
        out.append({
            "text": r["text"], "intent": r["intent"], "arg": arg,
            "template_id": "needle_ref/" + r["candidate_id"],
            "digits_masked": False,
            "author": "Needle schema-reference candidate + manual review",
            "origin": "needle_candidate_chain; no official runtime inference on this server",
            "needle_trace": {"candidate_id": r["candidate_id"], "function_calls": r["function_calls"], "review": r["review_reason"]},
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    schemas = build_schema()
    rows = candidate_rows()
    accepted, rejected = [], []
    for row in rows:
        ok, reason = review(row)
        row["review_status"] = "manual-rule-reviewed:accepted" if ok else "manual-rule-reviewed:rejected"
        row["review_reason"] = reason
        (accepted if ok else rejected).append(row)
    # A runtime marker prevents this report from being confused with a Needle
    # model accuracy run. The source schema API was executed; model inference was not.
    runtime_probe = {"package_available": importlib.util.find_spec("needle") is not None,
                     "weights_present": False, "official_model_inference": False,
                     "reason": "server has vendored Needle source but no installed runtime/weights"}
    all_rows = rows
    raw_path = out / "needle_candidates_raw.jsonl"
    filt_path = out / "needle_candidates_filtered.jsonl"
    app_path = out / "needle_candidate_append.jsonl"
    raw_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8")
    filt_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in accepted), encoding="utf-8")
    append = append_rows(accepted)
    app_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in append), encoding="utf-8")
    (out / "needle_schema.json").write_text(json.dumps({"source": str(NEEDLE_TOOLS.relative_to(ROOT)), "source_commit": COMMIT, "tools": schemas}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "chain": "Needle candidate generation -> manual review -> FPGA small model candidate append",
        "source_commit": COMMIT, "source_path": str(NEEDLE_TOOLS.relative_to(ROOT)),
        "runtime_probe": runtime_probe,
        "schema_builder_executed": True,
        "production_model_changed": False,
        "production_firmware_changed": False,
        "raw_candidates": len(all_rows), "accepted_candidates": len(accepted), "rejected_candidates": len(rejected),
        "accepted_by_intent": dict(Counter(r["intent"] for r in accepted)),
        "rejection_reasons": dict(Counter(r["review_reason"] for r in rejected)),
        "append_file": str(app_path.relative_to(ROOT)),
        "adoption": "optional; retraining/export/RTL evidence is a separate decision",
        "limits": ["Candidate text is synthetic and manually authored, not a user corpus.", "No official Needle model/weights inference was executed on this server.", "The append file is not merged into train.jsonl and is not flashed to the board.", "Any adopted model must rerun Python/C bit-exact, UART, cycle, and board evidence."],
    }
    (out / "needle_candidate_chain_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# Needle候选工具表达链路", "", "本报告把官方Needle仓库的工具schema构造用于候选表达的结构化生成，然后以板端工具范围、单调用约束和参数范围进行人工规则校正。服务器没有安装cactus-needle运行时，也没有needle3权重，因此这次不是官方模型推理准确率实验。", "", f"- 源码提交：`{COMMIT}`", f"- schema构造：`{NEEDLE_TOOLS.relative_to(ROOT)}`", f"- 原始候选：{len(all_rows)} 条；通过：{len(accepted)} 条；拒绝：{len(rejected)} 条", f"- 通过类别：`{dict(Counter(r['intent'] for r in accepted))}`", f"- 拒绝原因：`{dict(Counter(r['review_reason'] for r in rejected))}`", "- 生产模型、固件和板级工程均未修改。", "", "## 可审计文件", "", "- `needle_schema.json`：由官方源码build_schema生成的工具schema。", "- `needle_candidates_raw.jsonl`：候选生成阶段（含边界和故意非法样本）。", "- `needle_candidates_filtered.jsonl`：规则人工复核后可执行的单调用候选。", "- `needle_candidate_append.jsonl`：可选训练追加集，当前不自动合并。", "", "## 采用边界", "", "这条链路可以作为“Needle结构化工具设计思想 → 人工过滤 → FPGA小模型执行”的证据；不能把它写成“Needle3已经在FPGA上运行”或“官方模型生成了这些文本”。若后续取得官方运行时和权重，应另存官方推理原始输出、模型版本、置信度和人工修改记录，再决定是否纳入训练。", ""]
    (out / "needle_candidate_chain_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"raw": len(all_rows), "accepted": len(accepted), "rejected": len(rejected), "append": len(append), "runtime": runtime_probe}, ensure_ascii=False))

if __name__ == "__main__":
    main()
