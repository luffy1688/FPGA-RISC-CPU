#!/usr/bin/env python3
"""首代XND驻留计划：明确地址、packed INT4行距和容量，避免虚构的外部内存。
先LOAD一次activation，再用同一slot做一个或多个GEMV；对应tensor residence。
"""
import argparse
import json
from dataclasses import asdict, dataclass

AI_START=0x20000
AI_END=0x40000

def align4(value):
    return (value+3)&~3

@dataclass
class Descriptor:
    op: str
    activation_addr: int
    weight_addr: int
    output_addr: int
    columns: int
    rows: int
    weight_stride_bytes: int
    control: int
    slot: int

def make_plan(rows,cols,scratch_bytes,weight_bits=4,reuse=1):
    if not (1<=rows<=256 and 1<=cols<=256):
        raise ValueError("current engine supports 1..256 rows/columns")
    if weight_bits not in (4,8) or reuse<1:
        raise ValueError("weight_bits must be 4/8 and reuse positive")
    stride=align4((cols*weight_bits+7)//8)
    activation_bytes=align4(cols)
    weight_bytes=rows*stride
    output_bytes=rows*4
    required=activation_bytes+reuse*(weight_bytes+output_bytes)
    if required>min(scratch_bytes,AI_END-AI_START):
        raise ValueError("plan needs %d bytes but shared-memory budget is %d"%(required,scratch_bytes))
    activation=AI_START
    weights=activation+activation_bytes
    outputs=weights+reuse*weight_bytes
    control=1 if weight_bits==4 else 0
    # LOAD与GEMV对应MMIO command=2和3，不会触发不存在的DDR地址。
    plan=[Descriptor("LOAD",activation,0,0,cols,0,0,control,0)]
    for matrix in range(reuse):
        plan.append(Descriptor("GEMV",activation,weights+matrix*weight_bytes,
                               outputs+matrix*output_bytes,cols,rows,stride,control,0))
    return {"version":2,"layout":{"AI_START":AI_START,"AI_END":AI_END,"required_bytes":required,
                                 "activation_bytes":activation_bytes,"weight_stride_bytes":stride,
                                 "weight_bits":weight_bits},
            "residence":{"load_commands":1,"gemv_commands":reuse,
                         "activation_dma_bytes_saved_vs_reload":activation_bytes*(reuse-1)},
            "plan":[asdict(x) for x in plan]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rows",type=int,default=64)
    p.add_argument("--cols",type=int,default=64)
    p.add_argument("--scratch-bytes",type=int,default=128*1024)
    p.add_argument("--weight-bits",type=int,choices=(4,8),default=4)
    p.add_argument("--reuse",type=int,default=3)
    p.add_argument("--out",default="-")
    args=p.parse_args()
    text=json.dumps(make_plan(args.rows,args.cols,args.scratch_bytes,args.weight_bits,args.reuse),indent=2)+"\n"
    if args.out=="-": print(text,end="")
    else:
        with open(args.out,"w",encoding="utf-8") as output:
            output.write(text)
if __name__=="__main__":main()
