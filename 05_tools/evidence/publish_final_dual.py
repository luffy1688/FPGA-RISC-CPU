"""Synchronize the current delivery to the two existing private worktrees.

This prepares files only. Git commit/push remains a separate explicit command.
"""
from pathlib import Path
import subprocess,shutil,json,tarfile
R=Path('D:/Desktop/FPGA');E=R/'上板交付/工程';M=R/'参赛材料'
T=Path('C:/Users/luo/AppData/Local/Temp')
repos=[T/'lumarv_github_publish',T/'needlervx_gitlink_publish']
git='C:/Users/luo/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
files={}
def add(source,dest=None):
 if source.is_file():files[dest or source.relative_to(E).as_posix()]=source
tracked=subprocess.check_output([git,'-C',str(repos[1]),'ls-files','-z']).decode().split('\0')
for name in tracked:
 if name and not name.startswith('docs/') and not name.endswith('.bak')and name not in ['LICENSE','.gitignore','README_代码与复现.md']:
  add(E/name if(E/name).is_file()else repos[1]/name,name)
add(repos[1]/'.gitignore','.gitignore')
for dirname in ['01_rtl','02_tb','03_sw','05_tools']:
 for f in(E/dirname).rglob('*'):
  if f.is_file()and not any(x in ['__pycache__','node_modules','.arch-build','build']for x in f.parts)and f.suffix.lower()not in ['.pyc','.o','.vvp','.elf','.bin','.vcd','.fst','.db','.bak']:
   add(f)
for name in ['README.md','LICENSE','第三方来源.md','05_tools/build_dual_firmware.py']:
 add(E/name)
add(E/'代码与复现.md','README_代码与复现.md')
for name in ['run_impl.tcl','pangu_200pro_board.fdc','firmware/model_interactive.mem','firmware/worker.mem','generate_bitstream/production.sbit','report_timing/pangu_200pro_clocked_board.rtr','report_timing/pangu_200pro_clocked_board.prr']:
 add(E/'06_pango_active'/name)
for f in(E/'07_runs/board/current').glob('dual_final_*'):add(f)
add(E/'07_runs/board/current/final_metrics.json')
for name in ['physical_acceptance_final.json','physical_acceptance_complete.json','program_ram_final.log','program_ram.tcl']:
 add(E/'07_runs/frequency_current/dual54'/name)
for name in ['core_formal_result.json','core_formal_sim.log']:
 add(E/'07_runs/frequency_current/dual_compare'/name)
for name in ['core_validation_result.json','core_validation_sim.log']:
 add(E/'07_runs/frequency_current/dual_validation'/name)
add(E/'07_runs/model/dual/rebuild_result.json')
for name in ['LumaRV_技术报告.docx','LumaRV_答辩演示.pptx','技术报告.md','答辩与演示脚本.md']:
 add(M/name,'docs/'+name)
add(M/'提交文件/LumaRV_技术报告.pdf','docs/LumaRV_技术报告.pdf')
for folder in ['图表','展示素材']:
 for f in(M/folder).glob('*'):
  if f.is_file()and not f.name.startswith(('拍摄剪辑模板','控制台_')):add(f,'docs/'+folder+'/'+f.name)
# Keep the public standalone page in its existing path as well as beside media.
add(M/'展示素材/成果展示.html','docs/成果展示.html')
for repo in repos:
 for name,src in files.items():
  dest=repo/name;dest.parent.mkdir(parents=True,exist_ok=True)
  if src.resolve()!=dest.resolve():shutil.copy2(src,dest)
transport=T/'lumarv_final_sync.tar'
with tarfile.open(transport,'w')as tar:
 for name,src in sorted(files.items()):tar.add(src,arcname=name,recursive=False)
# Materials outside the public source tree, synchronized to the server only.
extra=[R/'00_交接总览.md',R/'FPGA_当前开发进度.md',R/'上板交付/README_当前上板入口.md']
extra+=list((R/'00_项目交接').glob('*20261027.md'))
extra+=list(M.glob('*.md'))+[M/'项目理解与导师讲解.docx']+list((M/'提交文件').glob('*.md'))
extra+=list((M/'展示素材').glob('拍摄剪辑模板*'))
with tarfile.open(transport,'a')as tar:
 for src in extra:
  if src.is_file():tar.add(src,arcname='_workspace/'+src.relative_to(R).as_posix(),recursive=False)
(T/'lumarv_final_public_files.json').write_text(json.dumps(sorted(files),ensure_ascii=False),encoding='utf-8')
print(json.dumps({'files':len(files),'source_bytes':sum(x.stat().st_size for x in files.values()),'transport_bytes':transport.stat().st_size,'worktrees':[str(x)for x in repos]},ensure_ascii=False))
