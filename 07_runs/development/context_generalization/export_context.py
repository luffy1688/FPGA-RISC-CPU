"""Export the one already-selected INT8 context head. Does not train or open heldout."""
from pathlib import Path
import json, torch,numpy as np
D=Path(__file__).resolve().parent
r=json.loads((D/'veto_report.json').read_text());assert r['complete'] and r['selection_gate']
j=torch.load(D/'best.pt',map_location='cpu');c=j['config'];w=j['state_dict']['linear.weight'].numpy();b=j['state_dict']['linear.bias'].numpy()
w=np.clip(np.sign(w)*np.floor(np.abs(w*64)+.5),-128,127).astype(np.int8);b=(np.sign(b)*np.floor(np.abs(b*32)+.5)).astype(np.int32)
assert w.shape==(2,c['bins']) and b.shape==(2,)
lines=['/* Independently implemented learned Unicode context head; no external engine. */','#ifndef NR_BYTE_CONTEXT_DATA_H','#define NR_BYTE_CONTEXT_DATA_H','#include <stdint.h>','#ifndef NR_CONTEXT_ENABLED','#define NR_CONTEXT_ENABLED 1','#endif',f'#define NR_CONTEXT_BINS {c["bins"]}u',f'#define NR_CONTEXT_THRESHOLD {c["threshold"]}',f'#define NR_CONTEXT_WEIGHT_BYTES {w.size+b.nbytes}u','#define NR_CONTEXT_SCRATCH_BYTES (2u*NR_CONTEXT_BINS)','static const int8_t nr_ctx_weights[2][NR_CONTEXT_BINS] __attribute__((aligned(4)))={']
for row in w:
 lines.append('{')
 for i in range(0,len(row),32):lines.append(','.join(map(str,row[i:i+32]))+',')
 lines.append('},')
lines +=['};','static const int32_t nr_ctx_bias[2] __attribute__((aligned(4)))={'+','.join(map(str,b))+'};','#endif']
(D/'byte_context_data.h').write_text('\n'.join(lines)+'\n')
np.savez_compressed(D/'context_int8.npz',weight=w,bias=b,bins=c['bins'],threshold=c['threshold'])
print(json.dumps({'selected_config':c,'constant_bytes':int(w.size+b.nbytes),'scratch_bytes':2*c['bins'],'heldout_opened':False}))
