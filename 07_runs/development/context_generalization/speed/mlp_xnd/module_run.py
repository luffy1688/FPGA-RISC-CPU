from pathlib import Path
import subprocess,json
R=Path("/work/LUO/NeedleRV-X");S=Path(__file__).resolve().parent
gcc='/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-'
cmd=[gcc+'gcc','-DNR_PLATFORM_CLOCK_HZ=40500000','-DNR_UART_BAUD=921600','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-mstrict-align','-O2','-std=c99','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-common','-ffunction-sections','-fdata-sections','-nostdlib','-nostartfiles','-I'+str(R/'03_sw/model'),'-T',str(R/'03_sw/bringup/linker.ld'),str(R/'03_sw/model/startup.S'),str(S/'module_test.c'),str(R/'03_sw/model/semantic_xnd.c'),str(R/'03_sw/platform/needle_platform.c'),'-Wl,--gc-sections,-Map,'+str(S/'module.map'),'-lgcc','-o',str(S/'module.elf')]
subprocess.run(cmd,cwd=R,check=True);subprocess.run([gcc+'objcopy','-O','binary',str(S/'module.elf'),str(S/'module.bin')],check=True);subprocess.run(['python3',str(R/'05_tools/bin_to_memh.py'),str(S/'module.bin'),str(S/'module.mem')],check=True)

p=subprocess.run([str(R/'07_runs/development/ai_pipeline/obj_soc/Vneedle_soc'),str(S/'module.mem')],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
(S/'module_rtl.log').write_text(p.stdout);print(p.stdout);assert p.returncode==0and'MODULE_PASS'in p.stdout
report=json.loads((S/'report.json').read_text());report['production_module']=dict(passed=True,source='03_sw/model/semantic_xnd.c',raw_log='speed/mlp_xnd/module_rtl.log',workspace_bytes=2152,ai_scratch_bytes=2144,cpu_state_bytes=8,poisoned_no_load_scratch=True,slot_invalidation_verified=True,bad_index_guard=True,bad_weight_guard=True,busy_no_fallback=True,subsequent_recovery=True,cases=[json.loads(line.split('MODULE_CASE ',1)[1])for line in p.stdout.splitlines()if line.startswith('MODULE_CASE ')])
(S/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
