from pathlib import Path
D=Path(__file__).resolve().parent
exec((D/'train_experts.py').read_text().split('profiles=[')[0])
q=np.load(D/'candidate_route_selected.npz');report=dict(scope='Observed post-training selectivecontext-only ablation; expertcorrector only learnedtoolcandidateCoreMark/counter; tool5 and allotherclasses unchanged. All7setsobserved used to protect existingcorrectlegalitems,not heldout or guaranteedgeneralization.',baseline64=baseline64,candidates=[])
for branches in [[],[2],[3],[2,3]]:
 data={};thresholds=np.zeros(6,np.int32)
 for n in names:
  hidden=np.clip(rounding(ar[n].astype(np.int32)@q['w1'].astype(np.int32).T)+q['b1'],0,127);out=rounding(hidden@q['w2'].astype(np.int32).T)+q['b2'];z=unvetoed[n].copy();z[:,:5]+=out[:,11:16]*(z.argmax(1)==5)[:,None];learnedroute=z.argmax(1);originalout=out.copy()
  for k in branches:
   ix=np.flatnonzero(learnedroute==k)
   if len(ix):out[ix,:2]+=rounding(hidden[ix].astype(np.int32)@q['residual_w2'][k,:2].astype(np.int32).T)+q['residual_b2'][k,:2]
  diff=out[:,1]-out[:,0];bucket=route[n];oldth=q64['thresholds'][bucket];oldiff=originalout[:,1]-originalout[:,0];old=z.copy();den=oldiff>=oldth;old[den,5]=np.maximum(old[den,5],old[den,:5].max(1)+oldiff[den]-oldth[den]+1);correct_legal=(old.argmax(1)==truth[n])&(truth[n]!=5)
  for k in range(6):
   ix=np.flatnonzero(correct_legal&(bucket==k))
   if len(ix):thresholds[k]=max(thresholds[k],int(diff[ix].max())+1)
  data[n]=(z,diff,bucket)
 ev={}
 for n,(z,diff,bucket)in data.items():
  z=z.copy();th=thresholds[bucket];deny=diff>=th;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-th[deny]+1);ev[n]=detailed(z,rows[n])
 gate=all(ev[n]['correct']>=baseline64[n]['correct']and ev[n]['false_accept']<=baseline64[n]['false_accept']and all(ev[n]['by_class'][t][0]>=baseline64[n]['by_class'][t][0]for t in TOOLS[:5])for n in names);rec=dict(branches=branches,thresholds=thresholds.tolist(),baseline64_allset_gate=gate,constant_bytes=72044+len(branches)*136,extra_active_macs=128,metrics=ev);report['candidates'].append(rec);print('SELECTIVE',branches,gate,thresholds.tolist(),{n:(v['correct'],v['legal_correct'],v['false_accept'])for n,v in ev.items()},flush=True)
(D/'selective_context_report.json').write_text(json.dumps(report,indent=2)+'\n')
