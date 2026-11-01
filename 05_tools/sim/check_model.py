#!/usr/bin/env python3
"""真实RV32/XND对照：执行图与dot4分别切换，数值与DMA由独立参考检查。"""
import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
CASES=["led 37","pwm -1","hello","读取计数器"]
CONFIGS=[(0,0,0),(1,0,0),(2,0,0),(1,1,0),(2,1,0),(3,1,0),(3,1,1)]
def main():
    log=(ROOT/"07_runs/model/selftest.log").read_text()
    assert "NR_MODEL_PASS" in log and "MODEL_DONE" in log and "MODEL_ERROR" not in log
    rows=[json.loads(line.split("NR_RESULT ",1)[1]) for line in log.splitlines() if line.startswith("NR_RESULT ")]
    assert len(rows)==len(CASES)*len(CONFIGS)
    build=json.loads(next(line.split("NR_BUILD ",1)[1] for line in log.splitlines() if line.startswith("NR_BUILD ")))
    indexed={(r["case"],r["config"]):r for r in rows}
    comparisons=[]
    for case,text in enumerate(CASES):
        oracle=json.loads(subprocess.check_output([str(ROOT/"04_model/golden/model_demo"),text],universal_newlines=True))
        result=[]
        for config,(mode,graph,dot4) in enumerate(CONFIGS):
            r=indexed[(case,config)]
            assert (r["mode"],r["graph"],r["dot4"])==(mode,graph,dot4)
            assert (r["logits"],r["tool"],r["decode"],r["argument"])==(oracle["logits"],oracle["index"],oracle["status"],oracle["argument"])
            assert not r["failures"]
            length=len(text.encode("utf-8"))
            if mode:
                jobs=12*length+1
                saved_loads=4*length if mode==3 or (mode==2 and not graph) else (4*(length%2) if mode==2 else 0)
                loads=jobs-saved_loads
                assert (r["jobs"],r["loads"],r["reuses"])==(jobs,loads,jobs-loads)
                assert r["weight_bytes"]==32768*length+192
                assert r["activation_bytes"]==896*length+64-saved_loads*64
            else: assert not any(r[k] for k in ["loads","jobs","weight_bytes","activation_bytes"])
            assert r["execute"]==[0,1,1,0][case]
            if case==0: assert r["value"]==37
            if case==3: assert r["value"]>0
            result.append(r)
        comparisons.append({"text":text,"utf8_bytes":length,"results":result,
            "xnd_vs_software":result[0]["cycles"]/result[2]["cycles"],
            "lifetime_vs_single_same_graph":result[4]["cycles"]/result[5]["cycles"],
            "dot4_vs_scalar_same_graph":result[5]["cycles"]/result[6]["cycles"],
            "combined_vs_software":result[0]["cycles"]/result[6]["cycles"]})
    report={"version":3,"model_stage":"stage3_generalization","target":"RV32IM/caches/BTB/XND RTL, Cache 2-edge hits",
        "kernel_stage":build.get("kernel_stage","pre_oct7"),
        "kernel_options":{key:build.get(key,0) for key in ["q_reuse","av4","post_fuse","profile"]},
        "clock_hz":27000000,"timing_scope":"inference only; no UART/dispatch",
        "configurations":[{"config":i,"mode":m,"graph":g,"dot4":d} for i,(m,g,d) in enumerate(CONFIGS)],
        "meaning":"integration/performance samples, not model accuracy or physical board timing",
        "dot4_comparison_scope":"config5 to config6 includes CPU dot4 and packed-Q reuse" if build.get("q_reuse",0) else "config5 to config6 includes CPU dot4 only",
        "workspace_bytes":21696,"comparisons":comparisons}
    (ROOT/"07_runs/model/current_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("PASS MODEL: 28 real RV32 paths, 3 same-graph hardware schedules, dot4 exact logits")
    for c in comparisons:
        print("%s cycles=%s; combined=%.3fx; lifetime/single=%.3fx; dot4=%.3fx"%(c["text"],[r["cycles"] for r in c["results"]],c["combined_vs_software"],c["lifetime_vs_single_same_graph"],c["dot4_vs_scalar_same_graph"]))
if __name__=="__main__":main()
