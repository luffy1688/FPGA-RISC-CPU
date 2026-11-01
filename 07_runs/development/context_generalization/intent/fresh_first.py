from train_intent import *
import subprocess
sys.path.insert(0,str(P/'context_v2'));from train_mlp import infer
out=D/'fresh_first_evaluation.json'
if out.exists():raise RuntimeError('First evaluation immutable; refusing overwrite')
q=np.load(D/'combined_candidate.npz');assert int(q['hidden'])==16
rows=read(P/'context_v2/data/fresh.jsonl');cache=np.load(P/'features.npz');text='\n'.join(x['text']for x in rows)+'\n'
p=subprocess.run([str(P/'baseline')],input=text,text=True,stdout=subprocess.PIPE,check=True);base=np.array([json.loads(l)['logits']for l in p.stdout.splitlines()],np.int32);assert len(base)==len(rows)
x=np.stack([features(r['text'],1024)for r in rows]);np.savez_compressed(D/'fresh_features.npz',x=x,base=base)
oldq=np.load(P/'context_int8.npz');old=fixed(x,oldq['weight'],oldq['bias']);baseline=fusion(base,old)
ct=infer(x,q);delta=fixed(x,q['repair_weight'],q['repair_bias'])*(base.argmax(1)==5)[:,None];bucket=base.argmax(1);threshold=q['thresholds'][bucket];diff=ct[:,1]-ct[:,0];deny=diff>=threshold;z=base.copy();z[:,:5]+=delta;z[deny,5]=np.maximum(z[deny,5],z[deny,:5].max(1)+diff[deny]-threshold[deny]+1)
truth=np.array([TOOLS.index(r['intent'])for r in rows]);met={}
for key,zz in [('baseline',baseline),('candidate',z)]:
 v=metrics(zz,rows);v.update(legal_correct=legal(v),legal_total=int((truth!=5).sum()),legal_wrong_tool=int(((zz.argmax(1)!=truth)&(zz.argmax(1)!=5)&(truth!=5)).sum()));met[key]=v
contexts={str(k):dict(n=int(sum(r.get('context',8)==k for r in rows)),baseline_correct=int(((baseline.argmax(1)==truth)&np.array([r.get('context',8)==k for r in rows])).sum()),candidate_correct=int(((z.argmax(1)==truth)&np.array([r.get('context',8)==k for r in rows])).sum()))for k in sorted({r.get('context',8)for r in rows})}
r=dict(scope='One first evaluation after whole joint weights,repair checkpoint,class thresholds frozen; synthetic heldout wrapper/grammar families plus official public OOD source;not independent-human blind data; no post-evaluation checkpoint or threshold selection',class_thresholds=q['thresholds'].tolist(),hidden=int(q['hidden']),metrics=met,by_context=contexts,raw_scores=[dict(text=row['text'],truth=row['intent'],encoder=base[i].tolist(),context=ct[i].tolist(),repair=delta[i].tolist(),bucket=int(bucket[i]),threshold=int(threshold[i]),contextdeny=bool(deny[i]),baseline_joint=baseline[i].tolist(),candidate_joint=z[i].tolist())for i,row in enumerate(rows)],system_tool_argument_evaluated=False,checkpoint_changed_after_first_evaluation=False)
out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['scope','class_thresholds','metrics','by_context']},ensure_ascii=True))
