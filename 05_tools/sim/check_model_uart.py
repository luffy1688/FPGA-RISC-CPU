#!/usr/bin/env python3
"""真实 UART 位流到 CPU、模型及工具的窄验收，不代替实板。"""
import json
import pathlib
import subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    log=(ROOT/"07_runs/model/interactive.log").read_text(encoding="utf-8")
    assert "MODEL_UART_DONE" in log and "NR_BACKEND_ERROR" not in log
    assert log.count("NR_INPUT_ERROR too_long")==1
    assert log.count("NR_CONTROL_ERROR invalid_config")==1
    configs=[json.loads(x.split("NR_CONFIG ",1)[1]) for x in log.splitlines() if x.startswith("NR_CONFIG ")]
    assert [r["config"] for r in configs]==[6,0,6]
    build=[json.loads(x.split("NR_BUILD ",1)[1]) for x in log.splitlines() if x.startswith("NR_BUILD ")]
    assert len(build)==1 and build[0]["protocol"]==2
    rows=[json.loads(x.split("NR_RESULT ",1)[1]) for x in log.splitlines() if x.startswith("NR_RESULT ")]
    texts=["led 37","pwm 25","pwm -1","hello","读取计数器","请告诉我温度","帮我执行CoreMark",
           "不要设置LED为7","do not change LED to 10","led 7 pwm 25","led 37","led 37","我想查看计数器"]
    assert len(rows)==len(texts)
    for case,(r,text) in enumerate(zip(rows,texts)):
        oracle=json.loads(subprocess.check_output([str(ROOT/"04_model/golden/model_demo"),text],universal_newlines=True))
        cfg=0 if case==10 else 6
        assert r["case"]==case and r["config"]==cfg and r["failures"]==0
        assert (r["mode"],r["graph"],r["dot4"])==((0,0,0) if cfg==0 else (3,1,1))
        assert r["logits"]==oracle["logits"] and r["decode"]==oracle["status"]
        assert r["selected_tool"]==oracle["selected_index"]
        expected=[0,0,1,1,0,2,0,1,1,1,0,0,0][case]
        assert r["execute"]==expected, (case,r)
        top=sorted(r["logits"],reverse=True)
        assert r["margin"]==top[0]-top[1] and r["confidence_threshold"]==16
        pmu=r["pmu"]
        assert pmu["instret"]>0 and pmu["cycles"]>=r["cycles"]
        assert r["request_cycles"]>=r["cycles"]+r["tool_cycles"]
    assert rows[0]["value"]==37 and rows[1]["value"]==25
    assert rows[4]["selected_tool"]==3 and rows[4]["value"]>0
    assert rows[5]["selected_tool"]==0 and rows[5]["value"]==0
    assert "PWM_LINE_PASS clocks=27000 high=6750" in log
    assert "Correct operation validated." in log and "ERROR!" not in log
    assert "NR_COREMARK_RETURN" in log and rows[6]["selected_tool"]==2 and rows[6]["value"]>=270000000
    for r in rows[7:10]:
        assert r["selected_tool"]==5 and r["decode"] in (1,8) and r["execute"]==1
    # A unique read-only schema hint may safely recover this low-margin counter read.
    assert rows[12]["decode"]==0 and rows[12]["selected_tool"]==3 and rows[12]["execute"]==0
    assert rows[10]["loads"]==rows[10]["jobs"]==rows[10]["reuses"]==0
    assert rows[0]["logits"]==rows[10]["logits"]==rows[11]["logits"]
    speedup=rows[10]["cycles"]/rows[11]["cycles"]
    assert speedup>1
    report={"target":"27MHz needle_soc RTL, UART 1MHz 8N1 RX stimulus",
        "passed":True,"model_stage":build[0]["model_stage"],"physical_board_verified":False,"input_overflow_drained":True,
        "runtime_config_switch_pass":True,"invalid_config_preserves_state":True,
        "policy_denials_pass":True,"runtime_sw_to_xnd_speedup":speedup,"build":build[0],"configs":configs,"results":rows,
        "meaning":"RX/firmware/tool integration only; physical board test pending"}
    (ROOT/"07_runs/model/current_uart_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS MODEL UART: 13 requests, policy denials, config0/6, PWM pin, CoreMark CRC+10s")
if __name__=="__main__":main()
