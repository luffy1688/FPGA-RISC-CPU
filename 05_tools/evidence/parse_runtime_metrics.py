#!/usr/bin/env python3
"""Parse actual UART PMU snapshots; never substitute simulated board values.
Counters are bracket deltas modulo 2^32. CSR reads are sequential, so PMU CPI
includes a small sampling overhead and is not an atomic hardware snapshot.
"""
import argparse
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--log",type=Path,default=ROOT/"07_runs/model/interactive.log")
    p.add_argument("--output",type=Path,default=ROOT/"07_runs/model/runtime_pmu_report.json")
    p.add_argument("--source-kind",choices=["rtl_simulation","physical_board"],default="rtl_simulation")
    args=p.parse_args()
    text=args.log.read_text(encoding="utf-8",errors="replace")
    requests=[];core=[]
    for line in text.splitlines():
        if line.startswith("NR_RESULT "):
            row=json.loads(line.split(" ",1)[1]);m=row.get("pmu")
            if m:
                requests.append({"case":row["case"],"config":row["config"],"model_cycles":row["cycles"],
                    "tool_cycles":row["tool_cycles"],"request_cycles":row["request_cycles"],"pmu":m,
                    "approx_cpi_with_sampling":m["cycles"]/m["instret"] if m["instret"] else None})
        if line.startswith("NR_PMU "):
            m=json.loads(line.split(" ",1)[1]);m["approx_cpi_with_sampling"]=m["cycles"]/m["instret"] if m["instret"] else None;core.append(m)
    timing=[dict(zip(["cycles","hz","iterations"],map(int,m))) for m in re.findall(r"NR_CYCLES=(\d+) NR_HZ=(\d+) NR_ITERATIONS=(\d+)",text)]
    for t,m in zip(timing,core):
        m["timed_region"]=t;m["seconds_from_cycles"]=t["cycles"]/t["hz"]
    result={"passed":bool(requests and core),"source":str(args.log),"source_kind":args.source_kind,
        "physical_board_verified":args.source_kind=="physical_board","requests":requests,"coremark_brackets":core,
        "counter_semantics":{"branches":"conditional branch executions",
            "redirect_misses":"all instruction next-PC prediction redirects, includes jumps; not a branch-only miss count",
            "mem_load_stall_cycles":"memory hold OR load hazard cycles, not load-use alone",
            "ic_misses":"instruction cache miss transactions","dc_misses":"data cache miss transactions"},
        "sampling":"sequential CSR reads; per-region deltas modulo 2^32; require each region below one full wrap",
        "cpi_scope":"PMU bracket includes sampling overhead; model cycles exclude tool/UART; request excludes RX and UART reporting"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"PMU parsed: requests={len(requests)}, CoreMark={len(core)}, source={args.source_kind}")
    if not result["passed"]:raise SystemExit("missing request or CoreMark PMU records")
if __name__=="__main__":main()
