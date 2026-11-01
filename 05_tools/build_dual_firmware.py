from pathlib import Path
import subprocess,sys,shlex,os
r=Path(__file__).resolve().parents[1];b=r/'07_runs/frequency_current';d=r/'07_runs/model/dual';d.mkdir(parents=True,exist_ok=True);f=r/'03_sw/dual';n=int(sys.argv[1]);hz=int(sys.argv[2])if len(sys.argv)>2 else 54000000
prefix=os.environ.get('TOOLCHAIN','/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-')
cc=shlex.split(os.environ.get('CORE_CC','/work/LUO/toolchains/gcc15-build/gcc/xgcc -B/work/LUO/toolchains/gcc15-build/gcc/'))
libgcc=subprocess.check_output([prefix+'gcc','-print-libgcc-file-name'],universal_newlines=True).strip()
w=d/'worker';w.mkdir(exist_ok=True)
flags=['-march=rv32im_zicsr_zifencei_zba_zbb_zbc_zbs_zicond','-mabi=ilp32','-mstrict-align','-O3','-funroll-all-loops','-mtune=rocket','-std=c99','-ffreestanding','-fno-builtin','-fno-common','-ffunction-sections','-fdata-sections','-nostdlib','-nostartfiles','-DNR_COREMARK_LIBRARY=1','-DPERFORMANCE_RUN=1','-DITERATIONS='+str(n),'-DCPU_HZ='+str(hz),'-DTOTAL_DATA_SIZE=2000','-I'+str(r/'03_sw/coremark'),'-I'+str(r/'09_refs/coremark')]
flags+=['-DFLAGS_STR='+repr(' '.join(flags)).replace("'",'"')]
with(d/'build.log').open('w')as log:
 objects=[]
 for name in ['core_main','core_list_join','core_matrix','core_state','core_util','core_portme','core_portme_print']:
  src=f/'worker_port.c'if name=='core_portme'else f/'worker_print.c'if name=='core_portme_print'else r/'09_refs/coremark'/(name+'.c')
  obj=w/(name+'.o');cmd=cc+flags+(['-Dmain=nr_coremark_entry']if name=='core_main'else[])+['-c',str(src),'-o',str(obj)]
  subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT);objects.append(str(obj))
 subprocess.run(cc+flags+['-T',str(f/'worker.ld'),str(r/'03_sw/model/startup.S'),str(f/'worker_main.c')]+objects+['-Wl,--gc-sections',libgcc,'-o',str(w/'interactive.elf')],check=True,stdout=log,stderr=subprocess.STDOUT)
 subprocess.run([prefix+'objcopy','-O','binary',str(w/'interactive.elf'),str(w/'interactive.bin')],check=True,stdout=log,stderr=subprocess.STDOUT)
 subprocess.run(['python3',str(r/'05_tools/bin_to_memh.py'),str(w/'interactive.bin'),str(w/'interactive.mem')],check=True,stdout=log,stderr=subprocess.STDOUT)
 subprocess.run(['make','-j4','-f',str(r/'03_sw/model/Makefile'),'all','OUT='+str(d/'primary'),'CPU_HZ='+str(hz),'CORE_ITERATIONS='+str(n),'ROOT='+str(r),'TOOLCHAIN='+prefix,'CORE_CC='+' '.join(shlex.quote(v)for v in cc)],cwd=str(r/'03_sw/model'),check=True,stdout=log,stderr=subprocess.STDOUT)
print('DUAL_FIRMWARE_READY',n,hz,'worker_bytes',(w/'interactive.bin').stat().st_size,flush=True)
