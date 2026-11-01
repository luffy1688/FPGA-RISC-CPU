from veto_train import R,D,read,features,fixed,evaluate,metrics,infer_base
import json,subprocess,numpy as np,time
path=D/'heldout_first_evaluation.json';assert not path.exists(),'First evaluation is immutable: do not reuse after tuning'
config=json.loads((D/'c_validation.json').read_text())['config'];arrays=np.load(D/'context_int8.npz');print('NPZ_KEYS',arrays.files,flush=True)
rows=read(D/'data/heldout.jsonl');base=infer_base(rows);x=np.stack([features(r['text'],config['bins'])for r in rows])
print('rows',len(rows),flush=True)
pred=subprocess.run([str(D/'eval_context')],input='\n'.join(x['text']for x in rows)+'\n',text=True,stdout=subprocess.PIPE,check=True)
out=[json.loads(l)for l in pred.stdout.splitlines()];assert len(rows)==len(out)
new=np.array([o['logits']for o in out],np.int32);assert np.array_equal(base,np.array([o['encoder_logits']for o in out]))
source={};context={}
for name,ix in [('public_MASSIVE_test',[i for i,r in enumerate(rows)if r['source']=='MASSIVE1.1/zh-CN']),('synthetic_unseen_families',[i for i,r in enumerate(rows)if r['source']!='MASSIVE1.1/zh-CN'])]:
 source[name]={'baseline':metrics(base[ix],[rows[i]for i in ix]),'candidate':metrics(new[ix],[rows[i]for i in ix])}
for kind in sorted(set(r['context']for r in rows)):
 ix=[i for i,r in enumerate(rows)if r['context']==kind];context[str(kind)]={'baseline':metrics(base[ix],[rows[i]for i in ix]),'candidate':metrics(new[ix],[rows[i]for i in ix])}
j={'scope':'First evaluation after checkpoint and threshold locked; synthetic family-separated and official public test-source OOD, not independent-human blind FPGA commands','checkpoint_config':config,'baseline':metrics(base,rows),'candidate':metrics(new,rows),'by_source':source,'by_context':context,'system_reject_false_accepts':sum(r['intent']=='reject'and o['status']==0 for r,o in zip(rows,out)),'predictions':[dict(text=r['text'],expected=r['intent'],source=r['source'],family=r['family'],baseline_logits=base[i].tolist(),candidate=o)for i,(r,o)in enumerate(zip(rows,out))],'evaluated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'used_to_tune_checkpoint':False}
path.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:j[k]for k in ['baseline','candidate','by_source','system_reject_false_accepts']}),flush=True)
