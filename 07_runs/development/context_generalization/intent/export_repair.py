from train_intent import *
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',default='profile_reject_repair5_256.pt');a=parser.parse_args()
c=torch.load(D/a.checkpoint,map_location='cpu');cfg=c['config'];w=c['weight'].astype(np.int8);b=c['bias'].astype(np.int32);assert cfg['kind']=='reject_repair5'
lines=['/* Learned repair of encoder rejects only; context veto remains dominant. */','#ifndef NR_BYTE_INTENT_REPAIR_DATA_H','#define NR_BYTE_INTENT_REPAIR_DATA_H','#include <stdint.h>',f'#define NR_INTENT_BINS {cfg["bins"]}u',f'#define NR_INTENT_WEIGHT_BYTES {w.size+b.nbytes}u','static const int8_t nr_intent_weights[5][NR_INTENT_BINS] __attribute__((section(".ai_const"),aligned(4)))={']
for row in w:
 lines.append('{')
 for i in range(0,len(row),32):lines.append(','.join(map(str,row[i:i+32]))+',')
 lines.append('},')
lines+=['};','static const int32_t nr_intent_bias[5] __attribute__((section(".ai_const"),aligned(4)))={'+','.join(map(str,b))+'};','#endif']
(D/'byte_intent_repair_data.h').write_text('\n'.join(lines)+'\n');np.savez_compressed(D/'selected_repair_int8.npz',weight=w,bias=b,bins=cfg['bins'],kind=cfg['kind'])
print(json.dumps(dict(config=cfg,constant_bytes=int(w.size+b.nbytes),heldout_read=False)))
