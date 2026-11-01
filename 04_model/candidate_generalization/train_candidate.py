#!/usr/bin/env python3
"""One frozen final-epoch QAT run. Candidate only; never writes current weights."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import json
import math
import sys
import time
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[2]
CANDIDATE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'04_model/train'))
from byte_model import ByteToolModel, TOOLS, SEQ, tokenize
from train_export import quant_weight, pack

def tensors(path, device):
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    token,length=zip(*(tokenize(row['text']) for row in rows))
    return rows,torch.tensor(token,device=device),torch.tensor(length,device=device),torch.tensor([TOOLS.index(row['intent']) for row in rows],device=device)

def export_candidate(model):
    arrays={}
    spec={'format':'nr-byte-tool-int4-v1','candidate_only':True,'d_model':64,'seq_len':64,'heads':4,'layers':2,'activation_scale':32,'tools':list(TOOLS),'tensors':[]}
    lines=['/* Candidate-only QAT export; adoption requires root approval. */','#ifndef NR_BYTE_MODEL_DATA_H','#define NR_BYTE_MODEL_DATA_H','#include <stdint.h>','#define NR_D 64','#define NR_SEQ 64','#define NR_HEADS 4','#define NR_LAYERS 2','#define NR_CLASSES 6']
    for name,param in model.named_parameters():
        ident='nr_'+name.replace('.','_')
        if name.endswith('.weight'):
            q,shift=quant_weight(param)
            data=pack(q)
            arrays[name]=q; arrays[name+'.shift']=np.array(shift,dtype=np.int32)
            spec['tensors'].append({'name':name,'shape':list(q.shape),'shift':shift,'packed_bytes':int(data.size)})
            lines.extend(['#define '+ident.upper()+'_SHIFT '+str(shift),'static const uint8_t '+ident+'[] __attribute__((aligned(4))) = {'])
            lines.extend('  '+','.join(str(int(v)) for v in data[i:i+24])+',' for i in range(0,len(data),24))
        else:
            data=np.rint(param.detach().cpu().numpy()*32).astype(np.int32)
            arrays[name]=data
            lines.append('static const int32_t '+ident+'[] __attribute__((aligned(4))) = {')
            lines.extend('  '+','.join(str(int(v)) for v in data[i:i+16])+',' for i in range(0,len(data),16))
        lines.append('};')
    exp_lut=np.maximum(1,np.rint(np.exp(-np.arange(129)/16.0)*4096)).astype(np.int32)
    arrays['exp_lut']=exp_lut
    lines.extend(['static const uint16_t nr_exp_lut[129] = {'+','.join(str(x) for x in exp_lut)+'};','#endif'])
    spec['packed_weight_bytes']=sum(t['packed_bytes'] for t in spec['tensors'])
    spec['bias_bytes']=sum(x.nbytes for n,x in arrays.items() if n.endswith('.bias'))
    spec['total_model_bytes']=spec['packed_weight_bytes']+spec['bias_bytes']+2*exp_lut.size
    spec['runtime_workspace_bytes']=21696
    spec['xnd_staging_bytes']=1280
    destination=CANDIDATE/'export'
    np.savez_compressed(destination/'candidate_int4.npz',**arrays)
    (destination/'candidate_manifest.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    (CANDIDATE/'c_model/byte_model_data.h').write_text('\n'.join(lines)+'\n')
    return spec

def main():
    protocol=json.loads((CANDIDATE/'protocol.json').read_text())
    (CANDIDATE/'export').mkdir(parents=True,exist_ok=True)
    (CANDIDATE/'c_model').mkdir(parents=True,exist_ok=True)
    plan=protocol['training_plan']
    torch.set_num_threads(4)
    torch.manual_seed(plan['seed']); np.random.seed(plan['seed'])
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.use_deterministic_algorithms(True)
    assert torch.cuda.is_available(), 'Existing CUDA interpreter is required; no install fallback'
    torch.cuda.set_per_process_memory_fraction(0.15,0)
    device=torch.device('cuda:0')
    train_rows,tx,tl,ty=tensors(CANDIDATE/'datasets/augmented_train.jsonl',device)
    dev_rows,dx,dl,dy=tensors(CANDIDATE/'datasets/observed_development.jsonl',device)
    model=ByteToolModel(64).to(device)
    prior=torch.load(CANDIDATE/'initialization.pt',map_location='cpu',weights_only=False)
    assert prior['d_model']==64
    model.load_state_dict(prior['state_dict'])
    optimizer=torch.optim.Adam(model.parameters(),lr=plan['learning_rate'])
    schedule=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=plan['epochs'],eta_min=0.00007)
    history=[]; started=time.monotonic()
    for epoch in range(plan['epochs']):
        model.train(); order=torch.randperm(len(ty),device=device); running=0.0
        for start in range(0,len(ty),plan['batch_size']):
            idx=order[start:start+plan['batch_size']]
            loss=torch.nn.functional.cross_entropy(model(tx[idx],tl[idx]),ty[idx])
            optimizer.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.0); optimizer.step()
            running+=float(loss.detach())
        schedule.step()
        if epoch%10==0 or epoch+1==plan['epochs']:
            model.eval()
            with torch.no_grad():
                dev_correct=int((model(dx,dl).argmax(-1)==dy).sum())
            entry={'epoch':epoch+1,'training_loss_sum':running,'observed_development_correct':dev_correct,'observed_development_examples':len(dev_rows),'elapsed_seconds':time.monotonic()-started}
            history.append(entry); print(json.dumps(entry),flush=True)
    model.eval()
    torch.save({'d_model':64,'state_dict':model.cpu().state_dict(),'seed':plan['seed'],'epochs':plan['epochs'],'initialization':'candidate_generalization/initialization.pt','candidate_only':True},CANDIDATE/'candidate.pt')
    spec=export_candidate(model)
    # Fresh holdout first accessed for inference after final epoch and export.
    _,hx,hl,hy=tensors(CANDIDATE/'datasets/fresh_semantic_holdout.jsonl',torch.device('cpu'))
    with torch.no_grad():
        pred=model(hx,hl).argmax(-1).tolist()
    report={'candidate_only':True,'training_plan':plan,'architecture':protocol['architecture'],'train_examples':len(train_rows),'train_balanced':True,'history':history,'fresh_holdout_examples':len(hy),'qat_float_fresh_holdout_correct':sum(p==int(y) for p,y in zip(pred,hy)),'qat_float_fresh_holdout_accuracy':sum(p==int(y) for p,y in zip(pred,hy))/len(hy),'checkpoint_selection':'final epoch 100, fixed before training; no holdout selection','elapsed_seconds':time.monotonic()-started,'torch_version':torch.__version__,'gpu_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'deployment':spec,'scope':'synthetic assistant-authored expression family holdout, not real user accuracy'}
    (CANDIDATE/'export/candidate_training_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('candidate_only','fresh_holdout_examples','qat_float_fresh_holdout_correct','elapsed_seconds','gpu_peak_allocated_bytes')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
