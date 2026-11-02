#!/usr/bin/env python3
"""构建d64模型QKV依赖图，输出同图三种真实activation槽计划。
此报告是静态LOAD/字节预算；实际周期必须由RTL或实板测量，不含DDR或DMA重叠。
"""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SLOT_BYTES=256
SLOTS=2

def qkv_graph(length,dimension=64,layers=2):
    if not 1<=length<=64 or dimension>256 or dimension%8:
        raise ValueError('当前模型length=1..64、dimension为8倍数且<=256')
    graph=[]
    for layer in range(layers):
        for first in range(0,length,2):
            for projection in ('q','k','v'):
                for token in range(first,min(first+2,length)):
                    graph.append({'tensor':f'x:{layer}:{token}', 'layer':layer,
                        'token':token,'projection':projection,'columns':dimension,
                        'rows':dimension,'last_use':projection=='v'})
    return graph

def schedule(graph,mode):
    slots=[None]*(SLOTS if mode=='lifetime' else 1)
    plan=[]
    loads=0
    live_peak=0
    for index,node in enumerate(graph):
        tensor=node['tensor']
        reuse=mode!='reload' and tensor in slots
        if reuse: slot=slots.index(tensor)
        elif mode=='lifetime':
            if None not in slots: raise ValueError('live tensors exceed 2 activation banks')
            slot=slots.index(None)
        else: slot=0
        if not reuse:
            slots[slot]=tensor
            plan.append({'op':'LOAD','slot':slot,'tensor':tensor,'bytes':node['columns']})
            loads+=1
        live_peak=max(live_peak,sum(node['columns'] for item in slots if item is not None))
        plan.append({'op':'GEMV','slot':slot,'dependency':tensor,'graph_index':index,
            'matrix':f"blocks.{node['layer']}.{node['projection']}",
            'rows':node['rows'],'columns':node['columns'],
            'packed_int4_stride':node['columns']//2,'last_use':node['last_use']})
        if node['last_use']: slots[slot]=None
    return {'load_commands':loads,'gemv_commands':len(graph),
        'activation_dma_bytes':sum(x['bytes'] for x in plan if x['op']=='LOAD'),
        'weight_dma_bytes':sum(x['rows']*x['columns']//2 for x in graph),
        'output_dma_bytes':sum(x['rows']*4 for x in graph),
        'peak_resident_payload_bytes':live_peak,'plan':plan}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--length',type=int,default=2)
    parser.add_argument('--out',default=str(ROOT/'07_runs/schedule/qkv_plan.json'))
    args=parser.parse_args()
    graph=qkv_graph(args.length)
    report={'schema':1,'scope':'real d64 model QKV graph; on-chip RAM DMA only',
        'hardware':{'activation_slots':SLOTS,'bytes_per_slot':SLOT_BYTES,
          'concurrent_operations':1,'source':'01_rtl/xnd/xnd_engine.sv'},
        'limitations':['No DDR byte claim','No DMA/compute overlap',
          'Natural token-major QKV already reaches minimum loads; lifetime cannot improve its load count'],
        'graph':graph,'strategies':{m:schedule(graph,m) for m in ('reload','single','lifetime')}}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({m:{k:v for k,v in r.items() if k!='plan'}
           for m,r in report['strategies'].items()},indent=2))
if __name__=='__main__': main()
