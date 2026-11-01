from pathlib import Path
import subprocess,re,json
D=Path(__file__).resolve().parent;P=D.parent;R=P.parents[2]
import subprocess,re
T='/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
cases=['请读取FPGA当前温度。','请将PWM占空比设置为20%。','只关闭LED0，其他LED不要改变','假设把LED0点亮会发生什么？']
src='#include "'+str(R/'03_sw/platform/needle_platform.h')+'"\n#define NR_CONTEXT_SCRATCH_ATTR __attribute__((section(".ai_scratch"),aligned(4)))\n#include "capacity_boundary.c"\nstatic const char *const cases[]={'+','.join(json.dumps(x,ensure_ascii=False)for x in cases)+'};\nint main(void){for(uint32_t i=0;i<4;i++){uint32_t n=0;while(cases[i][n])n++;int32_t encoder[6]={-300,-200,-100,100,20,500},out[36];uint32_t start=nr_cycle();for(uint32_t rep=0;rep<16;rep++)if(run_capacity((const uint8_t*)cases[i],n,encoder,out)){NR_LED=0xee;return 2;}uint32_t end=nr_cycle();nr_puts("COMBINED_COST {\"case\":");nr_put_u32(i);nr_puts(",\"cycles16\":");nr_put_u32(end-start);nr_puts(",\"bytes\":");nr_put_u32(n);nr_puts(",\"bucket\":");nr_put_i32(out[32]);nr_puts("}\n");}NR_LED=0xc0;return 0;}\n'
for key in ['case','cycles16','bytes','bucket']:src=src.replace(chr(34)+key+chr(34),chr(92)+chr(34)+key+chr(92)+chr(34))
src=src.replace('nr_puts('+chr(34)+'}'+chr(10)+chr(34)+');','nr_puts('+chr(34)+'}'+chr(92)+'n'+chr(34)+');')
(D/'capacity_benchmark.c').write_text(src)
subprocess.run([T+'gcc','-DNR_PLATFORM_CLOCK_HZ=40500000','-DNR_UART_BAUD=921600','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-mstrict-align','-O2','-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-function','-ffreestanding','-fno-builtin','-fno-common','-ffunction-sections','-fdata-sections','-nostdlib','-nostartfiles','-I'+str(R/'03_sw/model'),'-T',str(R/'03_sw/bringup/linker.ld'),str(R/'03_sw/model/startup.S'),str(D/'capacity_benchmark.c'),str(R/'03_sw/platform/needle_platform.c'),'-Wl,--gc-sections,-Map,'+str(D/'capacity_benchmark.map'),'-lgcc','-o',str(D/'capacity_benchmark.elf')],cwd=R,check=True)
subprocess.run([T+'objcopy','-O','binary',str(D/'capacity_benchmark.elf'),str(D/'capacity_benchmark.bin')],check=True)
subprocess.run(['python3',str(R/'05_tools/bin_to_memh.py'),str(D/'capacity_benchmark.bin'),str(D/'capacity_benchmark.mem')],check=True)
p=subprocess.run([str(R/'07_runs/development/ai_pipeline/obj_soc/Vneedle_soc'),str(D/'capacity_benchmark.mem')],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True,timeout=120)
(D/'capacity_cost.log').write_text(p.stdout);a=[json.loads(x.split('COMBINED_COST ',1)[1])for x in p.stdout.splitlines()if x.startswith('COMBINED_COST ')];assert len(a)==len(cases)
for text,x in zip(cases,a):x.update(text=text,cycles_per_call=x['cycles16']/16,ms=x['cycles16']/16/40500)
r=dict(scope='Candidate context64x16+oldrepair5+only-stillreject-tool5 and Unicode features only,allweights.ai_const shared SRAM; encoder not included; fake originalencoderreject used to exercise maximum repair branch,not classification accuracy',clock_hz=40500000,calls_per_case=16,constant_bytes=72044,cases=a)
(D/'capacity_cost.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=True))
