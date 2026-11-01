"""Refresh existing entry points; keep raw failures and historical trial data."""
from pathlib import Path
import json
from PIL import Image
R=Path('D:/Desktop/FPGA');E=R/'上板交付/工程';M=R/'参赛材料';O=M/'展示素材'
def put(p,s):p.write_text(s.strip()+'\n',encoding='utf-8')
readme=(E/'README.md').read_text(encoding='utf-8')
readme=readme.replace('必要时运行CPU基础计算检查。','副核可在后台执行计算自检，主核继续接收中文请求和操作外设。')
start=readme.index('| CPU |');end=readme.index('\n| 模型分类',start)
readme=readme[:start]+'''| CPU | 两颗五级RV32IM软核，54MHz，独立程序与数据存储 |
| 主核 CoreMark/MHz | **4.038437**中位数，19次均通过CRC，各3000次迭代 |
| 副核 / 双核累计 | **3.890411 / 7.780660**每MHz；各3000次，共同14.280421秒 |
| 中文PWM完整模型 | **54.640ms**；同镜像软件658.079ms，加速**12.04倍** |
| 原生串口控制往返 | 四句各10次，中位数**1.32～3.66ms**，含USB与主机调度 |
| 整机资源 | **55,277 LUT / 39,035 FF / 342.5 DRM36等效 / 40 APM** |
| 时序 | 慢角setup **+0.569ns**，hold **+0.141ns** |'''+readme[end:]
readme=readme.replace('控制往返与完整模型计时对应不同路径；版本对照包含多项改动。','双核累计按两个独立实例的共同时间计算。控制往返与完整模型计时对应不同路径。')
a=readme.index('```bash',readme.index('### 1. 生成固件'));b=readme.index('\n### 2.',a)
readme=readme[:a]+'''```bash
# GCC 14交叉工具链提供应用编译、objcopy与libgcc
export TOOLCHAIN=/path/to/gcc14/bin/riscv32-unknown-elf-
# GCC 15用于统一编译两个实例的全部CoreMark算法
export CORE_CC=/path/to/gcc15/bin/riscv32-unknown-elf-gcc
python3 05_tools/build_dual_firmware.py 3000 54000000
cp 07_runs/model/dual/primary/interactive.mem 06_pango_active/firmware/model_interactive.mem
cp 07_runs/model/dual/worker/interactive.mem 06_pango_active/firmware/worker.mem
```

CPU支持Zba/Zbb/Zbc/Zbs/Zicond扩展。应用和AI采用GCC14 O2，CoreMark全部算法统一采用GCC15 O3与循环展开，算法源码保留原样。
'''+readme[b:]
readme=readme.replace('在PDS中打开`06_pango_active/run_impl.tcl`，按本机目录修改`taskRoot`和`taskDir`后运行。','在PDS中运行`06_pango_active/run_impl.tcl`，脚本按自身位置定位工程。')
readme=readme.replace('- **CPU自检**：运行CoreMark，约14.6秒后显示CRC与成绩。','- **后台计算自检**：副核开始计算，主核可继续运行中文AI和控制外设。\n- **CPU自检**：同时启动两个独立CoreMark实例，约14.28秒后显示各核CRC与累计吞吐。')
put(E/'README.md',readme)
put(E/'代码与复现.md','''# 代码与复现

构建、RAM下载与网页入口见[README](README.md)。默认双核54MHz，各3000次CoreMark。两核固件的完整重建输入在03_sw与09_refs，构建脚本为05_tools/build_dual_firmware.py。

|目录|用途|
|---|---|
|01_rtl|双核、Cache、片上存储、AI和外设|
|03_sw/model|主核应用、整数模型运行时及链接脚本|
|03_sw/dual|副核程序、CoreMark移植层及私有RAM布局|
|06_pango_active|当前ROM、54MHz约束、PDS入口与production.sbit|
|07_runs/board/current|四批实板、网页UART、控制延迟与最终指标|
|07_runs/frequency_current/dual54|当前双核物理验收、时序和资源|

副核经0x40020000邮箱接收启动请求，使用64KiB私有RAM、32KiB指令Cache和4KiB数据Cache，不访问AI引擎和板卡执行器。两核是独立实例，累计吞吐按共同时间计算。

当前控制台通过真实UART完成15个事务。四批用户原文24/25、25/25、25/25、25/25；完整模型另有一条LED0置位误拒绝，默认混合路径通过20项位保持检查。原始失败保留在对应JSON，不能将系统通过率作为神经准确率。

仿真在服务器完成，本机PDS用于布局布线与RAM下载。不得用旧实验目录的ROM替换当前两份固件。只下载RAM，断电后重新下载。
''')
put(R/'上板交付/README_当前上板入口.md','''# 当前上板入口

已验收版本为54MHz双核澄灯LumaRV。工程目录为`工程`，`D:/FPGA_PDS`指向该目录。

- RAM位流：`工程/06_pango_active/generate_bitstream/production.sbit`
- PDS入口：`工程/06_pango_active/run_impl.tcl`
- 主核ROM：`工程/06_pango_active/firmware/model_interactive.mem`
- 副核ROM：`工程/06_pango_active/firmware/worker.mem`
- 当前实板指标：`工程/07_runs/board/current/final_metrics.json`

主核4.038437 CoreMark/MHz，副核3.890411，双独立实例累计7.780660/MHz。两核各3000次，CRC通过且运行超过10秒。54MHz快慢角时序均通过。63MHz未通过时序，不作为交付镜像。

浏览器选择CP210x串口、921600波特率，连接成功后短按KEY0，等54MHz和就绪。当前串口为COM10，FTDI COM13/14是JTAG。只允许一个程序占用串口。RAM掉电失效，需重新下载，不写Flash/eFuse。

网页：http://127.0.0.1:8765/?present=1&baud=921600&arch=1
''')
put(R/'00_项目交接/开发与上板详细交接_20261027.md','''# 开发与上板交接

当前交付已更新至2026-11-01双核54MHz。以[当前上板入口](../上板交付/README_当前上板入口.md)和[项目进度](../FPGA_当前开发进度.md)为准。

服务器工程为/work/LUO/NeedleRV-X；本机工程为D:/FPGA_PDS。开发、训练与仿真在服务器，PDS生成和RAM下载在本机。当前源码已重新构建，主核和副核ROM与已验收输入逐字节一致。

主核处理UART、中文语义、执行许可和IO，副核用独立RAM后台运行计算自检。后台运行期间，主核完整模型输出与前台独立运行一致，PWM写后读回通过。重复启动被拒绝，副核无外设写权限。

实板完成四批原文、20项LED位保持、软件/硬件数组对齐、双核CRC与计时、原生串口40次延迟测量及网页程序15事务。详细记录在工程/07_runs/board/current和frequency_current/dual54，不重复运行已通过项目。

强制完整模型的一条LED0置位请求仍会误拒绝，默认混合路径可正确处理。四批原文仍有一条成绩询问被保守拒绝；失败记录保留。接下来只修真实故障，主要准备照片、正式视频和签署授权书。
''')
put(R/'00_项目交接/证据与资料索引_20261027.md','''# 当前资料索引

|材料|位置|
|---|---|
|当前指标|上板交付/工程/07_runs/board/current/final_metrics.json|
|四批原文|上板交付/工程/07_runs/board/current/dual_final_four_batches.json|
|网页程序与真实UART|上板交付/工程/07_runs/board/current/dual_final_console.json|
|原生延迟40次|上板交付/工程/07_runs/board/current/dual_final_latency.json|
|物理验收及已知模型失败|上板交付/工程/07_runs/frequency_current/dual54/physical_acceptance_final.json|
|并行应用及位保持|上板交付/工程/07_runs/frequency_current/dual54/physical_acceptance_complete.json|
|54MHz时序资源|上板交付/工程/06_pango_active/report_timing/pangu_200pro_clocked_board.rtr|
|可编辑技术报告|参赛材料/LumaRV_技术报告.docx|
|提交PDF和代码|参赛材料/提交文件|
|PPT及3D/GIF|参赛材料/LumaRV_答辩演示.pptx、展示素材|
|拍摄及配音|参赛材料/答辩与演示脚本.md|

所有路径相对于项目总目录。网页程序原生桥验收不等同于已完成第二屏Edge拍摄；照片和最终实拍视频仍由本人补入。
''')

p=O/'拍摄剪辑模板_字幕.srt';s=p.read_text(encoding='utf-8').replace('周期40500，高电平8100','周期54000，高电平10800').replace('在板上执行1200次CoreMark','两核各执行3000次CoreMark').replace('基准运行约14.6秒','双核共同时间约14.28秒');put(p,s)
p=O/'拍摄剪辑模板_编辑源.py';s=p.read_text(encoding='utf-8').replace('保留约14.585秒运行及最终CRC、计时、READY','保留约14.28秒双核运行及各核CRC、共同计时、READY');put(p,s)
put(O/'展示解说稿.md','''# 二十秒结构展示解说

先展开十个模块。主核接收中文，副核独立运行后台自检。位置语义、短语记忆和低比特编码器处理请求，CPU检查工具与参数，PWM写入后读取寄存器。越界请求被拒绝，输出保持。

|时间|画面|
|---|---|
|0—5秒|主副核分工、模块分层与机器语法|
|5—10秒|位置特征、8MAC语义侧核与短语记忆|
|10—15秒|4MAC编码器、许可与PWM20%回读|
|15—20秒|能力越界拒绝、双核CRC及返回|

20秒为三倍速讲解动画，不用于测量执行延迟。完整中文PWM模型54.640ms，原生控制往返中位数1.32～3.66ms，双核共同基准时间14.280421秒。动画无音轨，可按上文后期配音。
''')
d=json.loads((O/'media_info.json').read_text(encoding='utf-8'));data=json.loads((E/'05_tools/console/showcase_data.json').read_text(encoding='utf-8'))
d.update(clock_hz=54000000,core_count=2,record_case_ids={k:v.get('wire_result',{}).get('case')for k,v in data['records'].items()})
d['labeled_model_animation'].update(modules=10,evidence='07_runs/board/current/dual_final_console.json',record_case=173,receipt={'requested':20,'readback':20,'period':54000,'high':10800,'enabled':1,'match':1})
for media in d['media_outputs']:
 for typ in ['mp4','gif']:
  f=O/media['video'if typ=='mp4'else'gif'];media[typ+'_bytes']=f.stat().st_size
 im=Image.open(O/media['gif']);media.update(gif_frames=im.n_frames,gif_dimensions=list(im.size),gif_duration_ms=sum((im.seek(i)or im.info.get('duration',0))for i in range(im.n_frames)))
put(O/'media_info.json',json.dumps(d,ensure_ascii=False,indent=2))
print('CURRENT_ENTRIES_UPDATED')
