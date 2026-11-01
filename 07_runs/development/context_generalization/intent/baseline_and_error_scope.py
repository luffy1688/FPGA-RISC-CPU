from train_intent import *
import subprocess,collections,re
fresh=read(P/'context_v2/data/fresh.jsonl');dev=read(P/'context_v2/data/validation.jsonl');report=json.loads((D/'system_combined_report.json').read_text())
p=subprocess.run([str(P/'integrated')],input='\n'.join(x['text']for x in fresh)+'\n',stdout=subprocess.PIPE,text=True,check=True);out=[json.loads(l)for l in p.stdout.splitlines()];assert len(out)==len(fresh)
baseline={}
for mode,key,st in [('full','selected','status'),('fast','fast_selected','fast_status')]:
 pred=np.array([x[key]if mode=='full'or x['fast_handled']else x['selected']for x in out]);truth=np.array([TOOLS.index(x['intent'])for x in fresh]);legal=truth!=5
 baseline[mode]=dict(n=len(fresh),correct=int((pred==truth).sum()),legal_total=int(legal.sum()),legal_correct=int(((pred==truth)&legal).sum()),false_accept=int(((pred!=5)&~legal).sum()),false_reject=int(((pred==5)&legal).sum()),wrong_legal_tool=int(((pred!=truth)&(pred!=5)&legal).sum()))
(D/'same_fresh_system_baseline.json').write_text(json.dumps(dict(scope='Actual previous accepted protocol5 integrated executable on same1138 fresh,after finalcandidateweights frozen;observational comparison,not reselection',executable='context_generalization/integrated',baseline=baseline,current={m:{k:v for k,v in report['results']['fresh'][m].items()if k!='errors'}for m in ['full','fast']}),indent=2)+'\n');print('BASELINE',json.dumps(baseline))
for name,rows in [('validation',dev),('fresh',fresh)]:
 bytext={x['text']:x for x in rows};errors=[dict(x,source=bytext[x['text']].get('source'),context=bytext[x['text']].get('context'))for x in report['results'][name]['fast']['errors']if x['expected']=='reject'];groups=collections.Counter((x['source'],x['context'])for x in errors);print('NEGATIVE_ERRORS',name,json.dumps({str(k):v for k,v in groups.items()},ensure_ascii=True));public=[x for x in errors if'MASSIVE'in(x['source']or'')];print('PUBLIC_ERRORS',json.dumps(public,ensure_ascii=True));
 byctx={k:next((x for x in errors if x['context']==k),None)for k in range(1,9)};print('REPRESENTATIVE',name,json.dumps(byctx,ensure_ascii=True))
