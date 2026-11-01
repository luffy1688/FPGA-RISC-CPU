#!/usr/bin/env python3
from pathlib import Path
import subprocess,ctypes,random,json
R=Path(__file__).resolve().parents[2];D=R/'07_runs/review_followup_20261028'
s=D/'fixed_ratio_wrapper.c';s.write_text('#include "'+str(R/'03_sw/coremark/fixed_ratio.h')+'"\nuint32_t check_ratio(uint64_t a,uint32_t b){return nr_report_div_u64_u32(a,b); }\n')
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(s),'-o',str(D/'fixed_ratio.so')],check=True)
f=ctypes.CDLL(str(D/'fixed_ratio.so')).check_ratio;f.argtypes=[ctypes.c_uint64,ctypes.c_uint32];f.restype=ctypes.c_uint32
rows=[(300*10**12,376644901),(376644901%27000000*10**6,27000000),(600*10**12,500000000),(0,1),(2**64-1,1),(2**64-1,2**32-1),(123,0)];rng=random.Random(28)
rows += [(rng.randrange(2**64),rng.randrange(1,2**32))for _ in range(256)]
for a,b in rows:assert f(a,b)==(min(a//b,2**32-1)if b else 0),(a,b,f(a,b))
(D/'report_arithmetic.json').write_text(json.dumps({'checks':len(rows),'failures':0,'scope':'Host C helper vs Python integer arithmetic; target ELF/RTL verified separately'},indent=2)+'\n');print('REPORT_ARITHMETIC_PASS',len(rows))
