from pathlib import Path
import json,numpy as np,ctypes as C,subprocess,sys,time
R=Path('/work/LUO/NeedleRV-X');P=R/'07_runs/development/context_generalization';F=Path(__file__).resolve().parent;M=F/'03_sw/model';D=R/'07_runs/development/resource_trials/capacity';E=R/'07_runs/development/resource_trials/experts'
sys.path.insert(0,str(P));sys.path.insert(0,str(D));from feature_extract import position_features
from veto_train import features,fixed
q=dict(np.load(D/'h64_f2048_position.npz'));fu=dict(np.load(E/'fusion_position_selected.npz'))
read=lambda p:[json.loads(z)for z in p.read_text().splitlines()if z.strip()]
paths={'original80':R/'04_model/datasets/template_development.jsonl','aug192':R/'07_runs/development/nlu_candidate/augmentation_dev.jsonl','observed288':R/'07_runs/development/semantic_train/semantic_diagnostic.jsonl','old_validation':P/'data/validation.jsonl','validation':P/'context_v2/data/validation.jsonl','observed1138':P/'context_v2/data/fresh.jsonl','observed900':P/'capacity/internal_audit.jsonl'}
cache=np.load(P/'context_v2/features.npz');base={n:cache[n+'_base'].astype(np.int32)for n in list(paths)[:5]};base['observed1138']=np.load(P/'intent/fresh_features.npz')['base'].astype(np.int32);base['observed900']=np.load(P/'capacity/audit_features.npz')['base'].astype(np.int32)
subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC','-I'+str(M),str(M/'byte_tool_model.c'),str(F/'host_boundary.c'),'-o',str(F/'host_boundary.so')],check=True)
lib=C.CDLL(str(F/'host_boundary.so'));lib.integrated_cpu.argtypes=[C.c_char_p,C.c_uint32,C.POINTER(C.c_int32)]
ra=lambda x,d:np.sign(x)*((np.abs(x)+d//2)//d)
report=dict(scope='Actualisolatedfull_model CPUencoder+position2048head+oldrepair+contexttoolcascade+frozen70featurefusion. IndependentNumPyint32goldenandfrozenencoderbase. All7setsobserved. No hardware/physicalclaim.',passed=False,sets={});began=time.monotonic()
for n,path in paths.items():
 rows=read(path);x=np.stack([position_features(r['text'])for r in rows]);old=np.stack([features(r['text'],1024)for r in rows]);h=np.empty((len(rows),64),np.int32)
 for i,v in enumerate(x):
  nz=np.flatnonzero(v);h[i]=np.clip(ra(q['w1'][:,nz].astype(np.int32)@v[nz].astype(np.int32),64)+q['b1'],0,127)
 head=ra(h@q['w2'].astype(np.int32).T,64)+q['b2'];bucket=base[n].argmax(1);rep=fixed(old,q['oldrepair_weight'],q['oldrepair_bias'])*(bucket==5)[:,None];pre=base[n].copy();pre[:,:5]+=rep;cascade=pre.argmax(1)==5;delta=head[:,11:16]*cascade[:,None];pre[:,:5]+=delta
 feature=np.concatenate([h,np.clip(ra(base[n],8),-127,127)],axis=1);fdelta=ra(feature.astype(np.int32)@fu['fusion_w'].astype(np.int32).T,64)+fu['fusion_b'];gap=np.sort(pre,axis=1)[:,-1]-np.sort(pre,axis=1)[:,-2];use=(pre.argmax(1)!=5)&(gap<=256);joint=pre.copy();joint[:,:5]+=fdelta*use[:,None];joint[use,5]=np.minimum(joint[use,5],joint[use,:5].max(1)-1)
 th=q['thresholds'][bucket];diff=head[:,1]-head[:,0];deny=diff>=th;joint[deny,5]=np.maximum(joint[deny,5],joint[deny,:5].max(1)+diff[deny]-th[deny]+1)
 expected=np.column_stack([base[n],head,rep,delta,joint,fdelta,use,gap,bucket,th,deny]).astype(np.int32);assert expected.shape[1]==48
 for i,r in enumerate(rows):
  wire=r['text'].encode();out=np.zeros(48,np.int32);rc=lib.integrated_cpu(wire,len(wire),out.ctypes.data_as(C.POINTER(C.c_int32)));assert rc==48 and np.array_equal(out,expected[i]),(n,i,r['text'],rc,out.tolist(),expected[i].tolist())
 report['sets'][n]=dict(cases=len(rows),exact_fields=len(rows)*48);print('ACTUAL_FULLCPU_PASS',n,len(rows),flush=True)
report.update(passed=True,total_cases=sum(x['cases']for x in report['sets'].values()),seconds=time.monotonic()-began);(F/'host_numeric.json').write_text(json.dumps(report,indent=2)+'\n');print('ALL_ACTUAL_FULLCPU_PASS',report['seconds'],flush=True)
