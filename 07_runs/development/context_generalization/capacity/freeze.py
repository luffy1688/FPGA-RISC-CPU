from pathlib import Path
import numpy as np,json
D=Path(__file__).resolve().parent;P=D.parent
r=json.loads((D/'calibrated_report.json').read_text());selected=r['selected'];assert selected['profile']=='latest_shared64_tool5'and selected['mode']=='cascade';q=np.load(D/'calibrated_selected.npz');old=np.load(P/'intent/combined_candidate.npz');a={k:q[k]for k in q.files};a['thresholds']=a['thresholds'].astype(np.int32);a['oldrepair_weight']=old['repair_weight'];a['oldrepair_bias']=old['repair_bias'];np.savez(D/'frozen_candidate.npz',**a)
metadata=dict(scope='Frozen v3 capacity candidate,not deployed;1138 is observed regression used for error-family augmentation and selection,not blind;old16 first861/1138 immutable',architecture='Unicode1024 sparse -> shared64ReLU -> binary2+context9+legaltool5; oldEngram encoder immutable;oldrepair first if originalencoderreject;newtool5 only if stillreject;classconditionalveto last',hidden=64,outputs=16,thresholds=q['thresholds'].tolist(),constant_bytes=sum(a[k].nbytes for k in ['w1','b1','w2','b2','oldrepair_weight','oldrepair_bias','thresholds']),selection=selected,lineage=json.loads((D/'lineage.json').read_text()),frozen_before_new_internal_audit=True)
(D/'frozen_config.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
lines=['/* V3 capacity candidate only, not production. INT8 sums round only after complete dot. */','#ifndef NR_CAPACITY_DATA_H','#define NR_CAPACITY_DATA_H','#include <stdint.h>','#define NR_CAPACITY_HIDDEN 64u','#define NR_CAPACITY_OUTPUTS 16u']
for key in ['w1','b1','w2','b2','oldrepair_weight','oldrepair_bias','thresholds']:
 v=a[key];ctype='int8_t'if v.dtype==np.int8 else'int32_t';shape=''.join('['+str(i)+']'for i in v.shape);lines.append('static const '+ctype+' nr_capacity_'+key+shape+' __attribute__((section(".ai_const"),aligned(4)))=')
 def emit(v):return'{'+','.join(map(str,v.tolist()))+'}'if v.ndim==1 else'{'+',\n'.join(emit(row)for row in v)+'}'
 lines.append(emit(v)+';')
lines+=['#endif'];(D/'capacity_data.h').write_text('\n'.join(lines)+'\n');print('FROZEN',metadata['constant_bytes'],metadata['thresholds'])
