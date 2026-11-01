#!/usr/bin/env python3
"""真实RV32/XND对照：执行图与dot4分别切换，数值与DMA由独立参考检查。"""
import json,pathlib,subprocess,argparse,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
CASES=["led 37","pwm -1","hello","读取计数器"]
CONFIGS=[(0,0,0),(1,0,0),(2,0,0),(1,1,0),(2,1,0),(3,1,0),(3,1,1)]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--log',type=pathlib.Path,default=ROOT/'07_runs/model/selftest.log');parser.add_argument('--output',type=pathlib.Path,default=ROOT/'07_runs/model/current_report.json');parser.add_argument('--oracle',type=pathlib.Path,default=ROOT/'04_model/golden/model_demo');args=parser.parse_args()
    log=args.log.read_text()
    assert "NR_MODEL_PASS" in log and "MODEL_DONE" in log and "MODEL_ERROR" not in log
    rows=[json.loads(line.split("NR_RESULT ",1)[1]) for line in log.splitlines() if line.startswith("NR_RESULT ")]
    assert len(rows)==len(CASES)*len(CONFIGS)
    build=json.loads(next(line.split("NR_BUILD ",1)[1] for line in log.splitlines() if line.startswith("NR_BUILD ")))
    indexed={(r["case"],r["config"]):r for r in rows}
    memory=int(build.get('semantic_memory',0));postprocess=int(build.get('xnd_postprocess',0))
    assert memory in (0,1) and postprocess in (0,1)
    comparisons=[]
    for case,text in enumerate(CASES):
        oracle=json.loads(subprocess.check_output([str(args.oracle),text],universal_newlines=True))
        result=[]
        for config,(mode,graph,dot4) in enumerate(CONFIGS):
            r=indexed[(case,config)]
            assert (r["mode"],r["graph"],r["dot4"])==(mode,graph,dot4)
            assert (r["logits"],r["tool"],r["decode"],r["argument"])==(oracle["logits"],oracle["index"],oracle["status"],oracle["argument"])
            assert not r["failures"]
            length=len(text.encode("utf-8"))
            if mode:
                # 12 per-token projections, 1 head; memory adds K/V64x64.
                jobs=12*length+1+2*memory
                saved_loads=4*length if mode==3 or (mode==2 and not graph) else (4*(length%2) if mode==2 else 0)
                saved_loads+=memory if mode>=2 else 0  # K/V share one memory vector
                loads=jobs-saved_loads
                assert (r["jobs"],r["loads"],r["reuses"])==(jobs,loads,jobs-loads),(case,config,r['jobs'],r['loads'],r['reuses'],jobs,loads)
                assert r["weight_bytes"]==32768*length+192+4096*memory
                assert r["activation_bytes"]==896*length+64+128*memory-saved_loads*64
                if postprocess:
                    assert r['bias_bytes']==3584*length+512*memory
                    assert r['residual_bytes']==1024*length*int(build.get('post_fuse',0))
                    assert r['output_bytes']==896*length+128*memory+24
                else:
                    assert r.get('bias_bytes',0)==0 and r.get('residual_bytes',0)==0
                    assert r.get('output_bytes',3584*length+512*memory+24)==3584*length+512*memory+24
            else: assert not any(r.get(k,0) for k in ["loads","jobs","weight_bytes","activation_bytes","bias_bytes","residual_bytes","output_bytes"])
            assert r["execute"]==[0,1,1,0][case]
            if case==0: assert r["value"]==37
            if case==3: assert r["value"]>0
            result.append(r)
        comparisons.append({"text":text,"utf8_bytes":length,"results":result,
            "xnd_vs_software":result[0]["cycles"]/result[2]["cycles"],
            "lifetime_vs_single_same_graph":result[4]["cycles"]/result[5]["cycles"],
            "dot4_vs_scalar_same_graph":result[5]["cycles"]/result[6]["cycles"],
            "combined_vs_software":result[0]["cycles"]/result[6]["cycles"]})
    report={"version":4,"model_stage":build.get('model_stage','stage3_generalization'),"target":"RV32IM/cache/BTB/XND actual RTL integration",'build':build,'semantic_memory':memory,'xnd_postprocess':postprocess,
        "kernel_stage":build.get("kernel_stage","pre_oct7"),
        "kernel_options":{key:build.get(key,0) for key in ["q_reuse","av4","post_fuse","profile"]},
        "clock_hz":build.get('clock_hz'),"timing_scope":"inference only; no UART/dispatch",
        "configurations":[{"config":i,"mode":m,"graph":g,"dot4":d} for i,(m,g,d) in enumerate(CONFIGS)],
        "meaning":"integration/performance samples, not model accuracy or physical board timing",
        "dot4_comparison_scope":"config5 to config6 includes CPU dot4 and packed-Q reuse" if build.get("q_reuse",0) else "config5 to config6 includes CPU dot4 only",
        "workspace_bytes":int(re.search(r'workspace=(\d+)',log).group(1)) if re.search(r'workspace=(\d+)',log) else None,"comparisons":comparisons}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("PASS MODEL: 28 real RV32 paths, 3 same-graph hardware schedules, dot4 exact logits")
    for c in comparisons:
        print("%s cycles=%s; combined=%.3fx; lifetime/single=%.3fx; dot4=%.3fx"%(c["text"],[r["cycles"] for r in c["results"]],c["combined_vs_software"],c["lifetime_vs_single_same_graph"],c["dot4_vs_scalar_same_graph"]))
if __name__=="__main__":main()
