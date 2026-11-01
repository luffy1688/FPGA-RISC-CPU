"""Lossless context constants export; uses existing quantized arrays only,never trains."""
from pathlib import Path
import argparse,json,re,numpy as np

def export_arrays(w,b,threshold,dest,model_header=None,force_full=False):
 w=np.asarray(w,dtype=np.int32);b=np.asarray(b,dtype=np.int32)
 assert w.ndim==2 and w.shape[0]==2 and b.shape==(2,) and np.all((w>=-128)&(w<=127))
 bins=w.shape[1];assert bins>0and bins<=65536and bins&(bins-1)==0
 delta=w[0]+w[1];indices=np.nonzero(delta)[0];dt=np.int8 if np.all((delta[indices]>=-128)&(delta[indices]<=127))else np.int16
 corr=delta[indices].astype(dt);fullbytes=2*bins+8;packedbytes=bins+indices.size*(2+np.dtype(dt).itemsize)+8
 packed=not force_full and packedbytes<fullbytes;payload=int(packedbytes if packed else fullbytes)
 lines=['/* Lossless export of the frozen quantized head; sparse antisymmetry corrections. */','#ifndef NR_BYTE_CONTEXT_DATA_H','#define NR_BYTE_CONTEXT_DATA_H','#include <stdint.h>','#ifndef NR_CONTEXT_ENABLED','#define NR_CONTEXT_ENABLED 1','#endif','#ifndef NR_CONTEXT_CONST_ATTR','#define NR_CONTEXT_CONST_ATTR','#endif',f'#define NR_CONTEXT_BINS {bins}u',f'#define NR_CONTEXT_THRESHOLD {int(threshold)}',f'#define NR_CONTEXT_WEIGHT_BYTES {payload}u',f'#define NR_CONTEXT_UNPACKED_WEIGHT_BYTES {fullbytes}u',f'#define NR_CONTEXT_PACKED {int(packed)}',f'#define NR_CONTEXT_CORRECTIONS {len(indices)if packed else 0}u','#define NR_CONTEXT_SCRATCH_BYTES (2u*NR_CONTEXT_BINS+NR_CONTEXT_BINS/8u+512u)']
 def array(typ,name,a,align=4):
  aa=np.asarray(a);shape=''.join(f'[{v}]'for v in aa.shape)
  lines.append(f'static const {typ} {name}{shape} NR_CONTEXT_CONST_ATTR __attribute__((aligned({align})))={{')
  for row in ([aa]if aa.ndim==1 else aa):
   if aa.ndim==2:lines.append('{')
   for start in range(0,len(row),32):lines.append(','.join(map(str,row[start:start+32]))+',')
   if aa.ndim==2:lines.append('},')
  lines.append('};')
 if packed:
  array('int8_t','nr_ctx_weight0',w[0].astype(np.int8))
  if len(indices):
   array('uint16_t','nr_ctx_correction_index',indices.astype(np.uint16),2)
   array('int8_t'if dt==np.int8 else'int16_t','nr_ctx_correction_delta',corr,1 if dt==np.int8 else 2)
 else:array('int8_t','nr_ctx_weights',w.astype(np.int8))
 array('int32_t','nr_ctx_bias',b);lines.append('#endif')
 Path(dest).write_text('\n'.join(lines)+'\n')
 if model_header:
  p=Path(model_header);s=p.read_text();s,n=re.subn(r'#define NR_MODEL_CONTEXT_BYTES \(NR_MODEL_CONTEXT_ENABLED\?\d+u:0u\)',f'#define NR_MODEL_CONTEXT_BYTES (NR_MODEL_CONTEXT_ENABLED?{payload}u:0u)',s);assert n==1
  scratch=2*bins+bins//8+512
  s,n=re.subn(r'#define NR_MODEL_CONTEXT_SCRATCH_BYTES \(NR_MODEL_CONTEXT_ENABLED\?\d+u:0u\)',f'#define NR_MODEL_CONTEXT_SCRATCH_BYTES (NR_MODEL_CONTEXT_ENABLED?{scratch}u:0u)',s);assert n==1;p.write_text(s)
 return dict(bins=bins,threshold=int(threshold),packed=packed,correction_bins=int(len(indices)),correction_delta_bits=np.dtype(dt).itemsize*8,logical_quantized_bytes=fullbytes,constant_payload_bytes=payload,payload_bytes_saved=fullbytes-payload,scratch_bytes=2*bins+bins//8+512,weights_unchanged=True)

def main():
 a=argparse.ArgumentParser();a.add_argument('npz',type=Path);a.add_argument('--output',required=True,type=Path);a.add_argument('--model-header',type=Path);a.add_argument('--force-full',action='store_true');z=a.parse_args();s=np.load(z.npz);key='weight'if'weight'in s else'weights';print(json.dumps(export_arrays(s[key],s['bias'],int(s['threshold']),z.output,z.model_header,z.force_full)))
if __name__=='__main__':main()
