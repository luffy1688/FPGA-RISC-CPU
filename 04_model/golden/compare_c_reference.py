#!/usr/bin/env python3
"""一次必要数值对齐：验证导出后 C 与 Python INT4/INT8 算法逐项相等。"""
import argparse
import json
import pathlib
import subprocess
from fixed_reference import FixedModel

ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--executable",default=str(ROOT/"04_model/golden/model_demo"))
    args=p.parse_args()
    data=[json.loads(x) for x in (ROOT/"04_model/datasets/template_holdout.jsonl").read_text(encoding="utf-8").splitlines()]
    model=FixedModel()
    mismatches=[]
    for item in data:
        reference=model.infer(item["text"])
        actual=json.loads(subprocess.check_output([args.executable,item["text"]],text=True))
        if actual["logits"]!=reference["logits"] or actual["index"]!=reference["index"]:
            mismatches.append({"text":item["text"],"reference":reference,"actual":actual})
    report={"examples":len(data),"logit_exact_matches":len(data)-len(mismatches),
            "mismatches":mismatches,"meaning":"numeric equivalence only, not an accuracy claim"}
    (ROOT/"04_model/golden/current_c_alignment.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(1 if mismatches else 0)
if __name__=="__main__":main()
