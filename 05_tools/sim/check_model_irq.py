#!/usr/bin/env python3
"""检查真实整模型 timer IRQ 恢复；只检查中断恢复。"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "07_runs/model"

def main():
    log = (OUT / "irq.log").read_text(encoding="utf-8")
    assert "NR_MODEL_IRQ_PASS" in log and "MODEL_IRQ_DONE" in log
    assert not any(marker in log for marker in ["NR_IRQ_ERROR", "RTL_TRAP", "RTL_TIMEOUT"])
    rows = [json.loads(line.partition("NR_IRQ_RESULT ")[2])
            for line in log.splitlines() if line.startswith("NR_IRQ_RESULT ")]
    assert len(rows) == 2
    baseline, interrupted = rows
    assert baseline["enabled"] == 0 and interrupted["enabled"] == 1
    for row in rows:
        assert (row["mode"], row["graph"], row["dot4"]) == (3, 1, 1)
        assert (row["tool"], row["decode"], row["execute"], row["led"]) == (3, 0, 0, 37)
        assert row["value"] > row["end"] > row["begin"]
        assert row["cycles"] == row["end"] - row["begin"]
        assert row["timer_enabled_after"] == 0 and row["failures"] == 0
    assert baseline["irq_count"] == baseline["irq_in_model"] == baseline["mcause"] == 0
    assert interrupted["irq_count"] == interrupted["irq_in_model"] == 1
    assert interrupted["mcause"] == 0x80000007
    assert interrupted["begin"] < interrupted["irq_cycle"] < interrupted["end"]
    assert 0 < interrupted["mepc"] < 0x20000 and interrupted["mepc"] % 4 == 0
    assert interrupted["logits"] == baseline["logits"]
    # 使用既有整网参考数值，仅读取既有报告，不重新运行模型。
    frozen = json.loads((OUT / "current_report.json").read_text(encoding="utf-8"))
    reference = next(c["results"][6] for c in frozen["comparisons"]
                     if c["text"] == "读取计数器")
    assert baseline["logits"] == reference["logits"]
    counters = ["loads", "jobs", "reuses", "activation_bytes", "weight_bytes", "output_bytes"]
    assert all(baseline[k] == interrupted[k] == reference[k] for k in counters)
    report = {
        "passed": True, "model_stage":"stage3_generalization", "target": "RV32/XND cycle-by-cycle RTL; not physical board",
        "clock_hz": 27000000, "text": "读取计数器", "runs": rows,
        "exact_logits_equal": True, "frozen_reference_equal": True,
        "timer_cause": "0x80000007", "irq_during_inference": True,
        "xnd_busy_observed_at_irq": bool(interrupted["xnd_status_at_irq"] & 1),
        "scope": "one timer IRQ, full register context restored, polling XND continues",
        "limitations": ["not a concurrency or model reentrancy guarantee",
                        "not a nested/multi-source interrupt proof",
                        "no physical PDS/board validation", "cycle difference is not isolated ISR cost"],
    }
    (OUT / "current_irq_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS MODEL IRQ: one timer trap/MRET inside real inference; exact logits and DMA accounting")
    print("XND busy at ISR observation:", report["xnd_busy_observed_at_irq"])

if __name__ == "__main__":
    main()
