# 标准CoreMark的裸机移植

CoreMark检查CPU能否运行真实C程序，以及列表、矩阵和状态机算法的执行效率。测试CRC是基准程序要求的计算校验，用来发现CPU计算错误。

## 文件名

- core_portme.h：port me意为需要平台适配的头文件，选择数据类型、静态2000字节数据集、整数报告。
- core_portme.c：用CPU cycle CSR计时，提供标准volatile种子，结束时输出性能事件。
- core_portme_print.c：裸机串口printf，仅处理基准使用的整数格式。
- startup.S：复位后建栈、清BSS、进入main；意外异常点亮0xEE并停住。
- Makefile：使用同一GCC选项编译所有基准算法和移植层；performance/validation只更换规定种子。
- 05_tools/sim/soc_run.cpp：逐时钟驱动Verilator生成的RTL，不替CPU执行指令。
- 05_tools/sim/check_coremark.py：检查两个标准种子CRC、完成标记和至少10秒计时，输出current_report.json。

上游算法保持在09_refs/coremark，未改core_main/list/matrix/state/util。首版静态数据2000字节，单上下文；I/D Cache各4 KiB两路，预测器开启，主存为256 KiB同步片上RAM。

## 已确认结果（2026-10-01）

| 参数 | performance | validation |
|---|---:|---:|
| 标准种子 | 0,0,0x66 | 0x3415,0x3415,0x66 |
| 迭代 | 200 | 200 |
| 计时周期 | 366786230 | 366848170 |
| 按27 MHz换算秒数 | 13.584675 | 13.586969 |
| 列表/矩阵/状态机CRC | 全部通过 | 全部通过 |
| CoreMark/MHz（按周期计算） | 0.545277 | 0.545185 |

这些是RTL仿真数据。正式性能通常采用performance种子结果；validation用于正确性确认。板上频率和成绩仍待PDS/实板。HAS_FLOAT=0的原始输出把秒和每秒迭代截为整数，所以精确换算取NR_CYCLES和NR_HZ，以current_report.json为准。BOOT_INSTRET及分支/cache计数从复位累积，包含初始化和报告，不是计时区间差分。

仿真将串口报告发送加速到9 Mbaud，CPU计时算法区间不执行串口输出；上板UART仍用27 MHz、115200。当前32位周期差计时要求单次区间短于2^32周期（27 MHz约159秒）。200次当前在这个范围内。

## 运行

在服务器根目录运行 `make -C 03_sw/coremark simulate`。默认200次、两组种子，生成物只更新07_runs/coremark。单轮bring-up可用 `make -C 03_sw/coremark ITERATIONS=1`，但单轮不满足10秒，不作为正式成绩。计时统计不需要哈希或无关扫描。

下一步优化取指/Cache命中响应及访存等待，然后在同频、同算法、同编译选项下比较；不使用XND指令改变CoreMark算法。
