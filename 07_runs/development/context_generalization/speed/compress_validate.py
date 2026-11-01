from pathlib import Path
import numpy as np,ctypes,subprocess,json,random
from compress_export import export_arrays
R=Path('/work/LUO/NeedleRV-X');S=Path(__file__).resolve().parent;M=R/'03_sw/model';rng=np.random.RandomState(20261030);random.seed(20261030)
weights=[];w=rng.randint(-127,128,(2,1024),dtype=np.int32);w[1]=-w[0];weights.append(('exact_antisymmetric_zero_corrections',w.copy()));w[1,0]=127;w[0,0]=127;w[1,1]=-128;w[0,1]=-128;weights.append(('int16_corrections',w.copy()));weights.append(('full_fallback',rng.randint(-128,128,(2,1024),dtype=np.int32)))
meta=[]
for name,w in weights:
 b=np.array([-29,31],np.int32);m=export_arrays(w,b,64,S/'fixture_data.h');m['case']=name;meta.append(m)
 inc=(M/'byte_context.c.inc').read_text().replace('#include "byte_context_data.h"','#include "'+str(S/'fixture_data.h')+'"')
 (S/'fixture.inc').write_text(inc)
 (S/'fixture.c').write_text('#include "byte_tool_model.h"\n#include "'+str(S/'fixture.inc')+'"\nint run(const uint8_t*b,uint32_t n,int32_t*out){nr_context_t c;int32_t z[6]={0,1,2,3,4,5};int s=nr_context_apply(b,n,z,&c);out[0]=c.logits[0];out[1]=c.logits[1];out[2]=c.scalar_macs;return s;}\n')
 subprocess.run(['gcc','-O2','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(M),str(S/'fixture.c'),'-o',str(S/('fixture_'+name+'.so'))],check=True)
 lib=ctypes.CDLL(str(S/('fixture_'+name+'.so')));lib.run.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_int32)]
 for _ in range(100):
  raw=bytes(random.randrange(65,91)for _ in range(random.randrange(1,65)));f=np.zeros(1024,np.int32);cp=[x+32 for x in raw]
  for i in range(len(cp)):
   h=2166136261
   for width in range(1,min(4,len(cp)-i)+1):
    h=((h^cp[i+width-1])*16777619)&0xffffffff;v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff;f[v&1023]+= -1 if v&1024 else 1
  f=np.clip(f,-3,3)*8;dots=f@w.T;want=np.sign(dots)*((np.abs(dots)+32)//64)+b
  out=(ctypes.c_int32*3)();assert lib.run(raw,len(raw),out)==0and list(out)[:2]==want.tolist(),(name,raw)
  expected_macs=int(np.count_nonzero(f))+(int(np.count_nonzero(f[np.nonzero(w.sum(0))[0]]))if m['packed']else int(np.count_nonzero(f)))
  assert out[2]==expected_macs,(name,out[2],expected_macs)
report=json.loads((S/'report.json').read_text());report['general_export_runtime_fixtures']=dict(passed=True,cases=meta,random_valid_inputs_per_fixture=100,scope='Necessary zero-correction/int16correction/fullfallback branches,nottrainingaccuracy')
(S/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(meta))
