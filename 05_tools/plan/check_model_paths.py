#!/usr/bin/env python3
"""主机必要数值验收：80条现有输入，调度次序/分组dot4 fallback都不改logits。"""
import ctypes as C
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Prediction(C.Structure):
    _fields_=[('tool',C.c_int),('logits',C.c_int32*6),('margin',C.c_int32)]
lib=C.CDLL(str(ROOT/'07_runs/schedule/model_paths.so'))
lib.nr_model_predict.argtypes=[C.c_void_p,C.c_uint32,C.POINTER(Prediction)]
lib.nr_model_dot_i8.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32]
lib.nr_model_dot_i8.restype=C.c_int32
inputs=[json.loads(line)['text'] for line in (ROOT/'04_model/datasets/template_holdout.jsonl').read_text().splitlines()]
for text in inputs:
    data=text.encode('utf-8')
    lib.nr_model_set_qkv_interleaved(0);lib.nr_model_set_attention_dot4(0)
    reference=Prediction();assert lib.nr_model_predict(data,len(data),C.byref(reference))==0
    for graph,dot4 in ((1,0),(0,1),(1,1)):
        lib.nr_model_set_qkv_interleaved(graph);lib.nr_model_set_attention_dot4(dot4)
        actual=Prediction();assert lib.nr_model_predict(data,len(data),C.byref(actual))==0
        assert bytes(actual)==bytes(reference),(text,graph,dot4,list(actual.logits),list(reference.logits))
# 四种字节对齐、短尾和-128边界；C接口支持非4B对齐而非违反strict aliasing。
a=(C.c_int8*24)(*([-128,127,-1,0,1,63,-64,12]*3))
b=(C.c_int8*24)(*([127,-128,0,-1,2,-63,64,-12]*3))
checks=0
for off_a in range(4):
    for off_b in range(4):
        for count in range(0,18):
            pa=C.byref(a,off_a);pb=C.byref(b,off_b)
            lib.nr_model_set_attention_dot4(0);reference=lib.nr_model_dot_i8(pa,pb,count)
            lib.nr_model_set_attention_dot4(1);actual=lib.nr_model_dot_i8(pa,pb,count)
            assert reference==actual,(off_a,off_b,count)
            checks+=1
report={'examples':len(inputs),'model_path_exact_matches':len(inputs)*3,
        'unaligned_tail_dot_checks':checks,'execution':'host grouped-dot fallback; not custom instruction RTL proof'}
(ROOT/'07_runs/schedule/host_paths.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
