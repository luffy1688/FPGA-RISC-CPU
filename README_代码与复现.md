# 代码与复现

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

当前控制台通过真实UART完成15个事务。四批用户原文24/25、25/25、25/25、25/25；完整模型另有一条LED0置位误拒绝，默认混合路径通过20项位保持检查。逐句结果与失败输入见对应JSON；模型分类和混合路径分别统计。

仿真在服务器完成，本机PDS用于布局布线与RAM下载。PDS使用主核和副核各自对应的ROM。只下载RAM，断电后重新下载。
