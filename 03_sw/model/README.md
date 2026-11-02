# 主核固件与整数模型运行时

本目录接收单条UTF-8请求，完成语境和工具判断、参数检查、外设操作及结果返回。主核以54MHz运行，UART921600/8N1，单条输入最多64字节。

## 组成

|文件|作用|
|---|---|
|main.c|启动、串口命令、运行模式、工具调用与双核结果汇总|
|byte_tool_model.c|字节编码器、attention、语境分支、工具判断和整数运算|
|byte_tool_xnd.c|4MAC描述符、两槽激活计划与数据搬运|
|semantic_xnd.c / semantic_cached.c|8MAC位置语义计算及常驻权重缓存|
|byte_model_data.h / byte_engram_data.h|编码器与学习型短语参数|
|byte_context_data.h / byte_semantic_data.h|语境、位置分支及工具残差参数|
|tool_dispatch.c|温度、计数器、LED、PWM与CoreMark执行和读回|
|link_protocol.c|串口结果帧与校验|
|tensor_plan.c|激活存活范围和缓冲复用|

学习权重合计197816B。字节编码器为两层d64、四头，含学习型2/3-gram记忆。位置分支为2048→64→16，CPU执行70→5受约束工具残差。4MAC/8MAC使用INT4或INT8权重和INT32累加，语义头第一层权重驻留128KiB缓存。

## 构建双核固件

在工程根目录配置GCC14工具前缀和GCC15 CoreMark编译器：

```sh
export TOOLCHAIN=/path/to/gcc14/bin/riscv32-unknown-elf-
export CORE_CC=/path/to/gcc15/bin/riscv32-unknown-elf-gcc
python3 05_tools/build_dual_firmware.py 3000 54000000
```

主核镜像为`07_runs/model/dual/primary/interactive.mem`，副核镜像为`07_runs/model/dual/worker/interactive.mem`。PDS入口位于`06_pango_active/run_impl.tcl`。

## 处理路径

明确机器指令直接解析。中文请求先判语境，再由明确语法提取参数；未命中语法时运行完整编码器。“一键AI识别”使用完整模型路径，供展示与软件/硬件计算对照。各路径共用能力、参数和写后读回检查。

控制项包括`:config 0..6`、`:fast 0/1`及输出格式；确认后再发送下一句。配置0为软件，配置6为两槽生命周期、交错QKV与dot4。快路径、语境路径和完整模型参与情况独立记录。

`NR_RESULT`和紧凑帧返回工具、参数、执行状态及读回。`cycles`计模型计算，`tool_cycles`计工具执行；浏览器往返另行计算。温度采用摄氏度×100整数；LED返回掩码，PWM返回百分比，CoreMark返回算法周期。

## 工具

LED支持整体掩码和单位置位/清位，其他位保持。PWM固定1kHz、占空比0～100%；PWM启用时GPIO7由PWM占用。清零计数器、修改温度、变更PWM频率、多动作与越界参数均拒绝。32位周期计数器会回绕。

副核只运行计算自检，通过邮箱返回状态、周期与CRC，不访问外设和AI引擎。副核忙碌时主核仍可执行完整模型和IO操作；重复启动被拒绝。

## 测量

指定中文PWM完整模型软件658.079ms、加速路径54.640ms，五组输出数组一致。两核各3000次CoreMark，均超过10秒且CRC通过。逐句指令、时序及资源数据见`07_runs/board/current`和`06_pango_active/report_timing`。
