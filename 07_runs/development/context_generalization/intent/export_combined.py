from train_intent import *
r=json.loads((D/'classwise_joint_final_report.json').read_text());s=r['selected'];assert s['context_profile']=='grammar_shared16';q=np.load(P/'context_v2'/('profile_'+s['context_profile']+'.npz'));c=torch.load(D/s['repair'],map_location='cpu')
a={k:q[k]for k in q.files};a.update(repair_weight=c['weight'].astype(np.int8),repair_bias=c['bias'].astype(np.int32),repair_bins=np.array(c['config']['bins']),thresholds=np.array(s['thresholds'],np.int32));np.savez(D/'combined_candidate.npz',**a)
lines=['/* Candidate only; selected by observed development gates. Full encoder bucket, not schema hint. */','#ifndef NR_COMBINED_CANDIDATE_H','#define NR_COMBINED_CANDIDATE_H','#include <stdint.h>','#define NR_COMBINED_HIDDEN 16u','#define NR_COMBINED_OUTPUTS 11u']
for key in ['w1','b1','w2','b2','repair_weight','repair_bias','thresholds']:
 v=a[key];ctype='int8_t'if v.dtype==np.int8 else'int32_t';shape=''.join('['+str(i)+']'for i in v.shape);lines.append('static const '+ctype+' nr_combined_'+key+shape+' __attribute__((section(".ai_const"),aligned(4)))=')
 def emit(v):
  if v.ndim==1:return'{'+','.join(map(str,v.tolist()))+'}'
  return'{'+',\n'.join(emit(row)for row in v)+'}'
 lines.append(emit(v)+';')
lines+=['#endif'];(D/'combined_candidate_data.h').write_text('\n'.join(lines)+'\n')
print('COMBINED_BYTES',sum(a[k].nbytes for k in ['w1','b1','w2','b2','repair_weight','repair_bias','thresholds']))
