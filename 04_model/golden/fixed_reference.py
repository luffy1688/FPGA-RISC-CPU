#!/usr/bin/env python3
"""与裸机 C 相同的整数算法。只在 Python 使用 numpy 加速矩阵乘法，不用浮点推理。"""
import argparse
import json
import pathlib
import numpy as np

ROOT=pathlib.Path(__file__).resolve().parents[2]
TOOLS=("read_temp","set_pwm","run_coremark","read_counter","set_led","reject")

def shift_round(value, shift):
    v=np.asarray(value,dtype=np.int64)
    if shift<=0:
        return v << (-shift)
    sign=np.where(v<0,-1,1)
    return sign*((np.abs(v)+(1<<(shift-1)))>>shift)

def divide_round(value, divisor):
    v=np.asarray(value,dtype=np.int64)
    return np.where(v<0,-1,1)*((np.abs(v)+divisor//2)//divisor)

def clip8(x):
    return np.clip(x,-128,127).astype(np.int8)

class FixedModel:
    def __init__(self, path=None):
        self.p=np.load(path or ROOT/"04_model/export/current_int4.npz")
        self.d=int(self.p["embedding.weight"].shape[1])

    def linear(self,x,name,clamp=True):
        # 权重[输出,输入]，每输出一路INT32累加。对应XND的GEMV接口。
        w=self.p[name+".weight"].astype(np.int64)
        raw=x.astype(np.int64) @ w.T
        y=shift_round(raw,int(self.p[name+".weight.shift"]))+self.p[name+".bias"]
        return clip8(y) if clamp else y.astype(np.int32)

    def infer(self,text):
        values=list(text.lower().encode("utf-8"))
        if not values:
            raise ValueError("empty input")
        if len(values)>64:
            raise ValueError("input longer than 64 UTF-8 bytes")
        n=len(values)
        emb=shift_round(self.p["embedding.weight"][values],int(self.p["embedding.weight.shift"])-5)
        pos=shift_round(self.p["position.weight"][:n],int(self.p["position.weight.shift"])-5)
        x=clip8(divide_round(emb+pos,2))
        hdim=self.d//4
        for layer in range(2):
            stem="blocks."+str(layer)+"."
            q=self.linear(x,stem+"q").reshape(n,4,hdim).transpose(1,0,2)
            k=self.linear(x,stem+"k").reshape(n,4,hdim).transpose(1,0,2)
            v=self.linear(x,stem+"v").reshape(n,4,hdim).transpose(1,0,2)
            scores=shift_round(q.astype(np.int64) @ k.astype(np.int64).transpose(0,2,1),9)
            delta=scores.max(-1,keepdims=True)-scores
            probability=np.where(delta<=128,self.p["exp_lut"][np.minimum(delta,128)],0).astype(np.int64)
            context=divide_round(probability @ v.astype(np.int64),probability.sum(-1,keepdims=True))
            context=clip8(context.transpose(1,0,2).reshape(n,self.d))
            x=clip8(divide_round(x.astype(np.int64)+self.linear(context,stem+"o").astype(np.int64),2))
            ff=clip8(np.maximum(0,self.linear(x,stem+"ff1").astype(np.int32)))
            x=clip8(divide_round(x.astype(np.int64)+self.linear(ff,stem+"ff2").astype(np.int64),2))
        pooled=clip8(divide_round(x.astype(np.int64).sum(0),n))
        logits=self.linear(pooled,"head",clamp=False)
        intent=int(logits.argmax())
        order=np.sort(logits)
        return {"intent":TOOLS[intent],"index":intent,"logits":[int(v) for v in logits],
                "margin":int(order[-1]-order[-2])}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--text")
    args=p.parse_args()
    model=FixedModel()
    if args.text:
        print(json.dumps(model.infer(args.text),ensure_ascii=False));return
    data=[json.loads(x) for x in (ROOT/"04_model/datasets/template_holdout.jsonl").read_text(encoding="utf-8").splitlines()]
    correct=0;confusion=[[0]*6 for _ in range(6)];fixtures=[]
    for item in data:
        result=model.infer(item["text"])
        correct+=result["intent"]==item["intent"]
        confusion[TOOLS.index(item["intent"])][result["index"]]+=1
        fixtures.append({"text":item["text"],"expected_intent":item["intent"],**result})
    report={"format":"nr-fixed-evaluation-v1","data":"template_holdout.jsonl","examples":len(data),
            "correct":correct,"accuracy":correct/len(data),"confusion_rows_actual_columns_prediction":confusion,
            "labels":list(TOOLS),"scope":"synthetic disjoint-template closed-intent evaluation only"}
    (ROOT/"04_model/golden/current_fixed_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"04_model/golden/current_fixtures.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in fixtures),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
