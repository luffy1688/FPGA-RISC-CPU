# XND 第一版接口与阅读顺序

XND 是我们为 CPU 添加的低比特向量执行单元。CPU 负责“发任务”，XND 负责“读数据、做乘加、写结果”。这里实现的是我们自己的硬件内核，不是把 Needle 官方运行库原样搬入 FPGA。

## 先认识这几个文件

| 文件 | 名字是什么意思 | 你应该看什么 |
|---|---|---|
| `01_rtl/xnd/xnd_engine.sv` | engine 是执行引擎，sv 是 SystemVerilog 硬件描述代码 | DMA 请求、四路乘加、两槽驻留、状态机 |
| `01_rtl/xnd/xnd_dot4.sv` | dot 是点积，4 表示四个数一起运算 | 最小点积模块，仍供 CPU 自定义指令使用 |
| `01_rtl/xnd/xnd_mmio.sv` | MMIO 是通过地址读写硬件寄存器 | 早期 dot4 演示壳，新的 SoC 应使用 engine |
| `02_tb/unit/tb_xnd_engine.sv` | tb 是测试台，unit 是单模块测试 | 怎样给硬件输入，怎样与正确答案比较 |
| `03_sw/xnd_runtime/xnd_mmio.h` | runtime 是 CPU 的调用接口，h 是 C 头文件 | CPU 怎样加载向量和启动 GEMV |
| `03_sw/xnd_runtime/gemv_reference.c` | reference 是软件参考答案 | 权重打包格式和精确整数数学定义 |

GEMV 就是“矩阵乘一个向量”。例如输入 `[1,2,3]` 与一行权重 `[4,-1,2]` 得到 `1×4+2×(-1)+3×2=8`。每一行得到一个输出。硬件没有文字理解能力；文字模型的大量计算会被转换成这类运算。

## 硬件端口：与 SoC 的固定约定

模块端口为：

- MMIO 从端：`req_valid, req_write, req_addr[15:0], req_wdata[31:0], req_wstrb[3:0], req_ready, req_rdata[31:0], req_error`。
- DMA 主端：`mem_valid, mem_write, mem_addr[31:0], mem_wdata[31:0], mem_wstrb[3:0], mem_ready, mem_rdata[31:0], mem_error`。
- 时钟 `clk`、高电平同步复位 `reset`、完成中断 `irq`。

MMIO `req_addr` 是相对 XND 基址的**字节偏移**，不是全局地址。DMA `mem_addr` 是 RAM 全局字节地址。DMA 最多有一个未完成请求；XND 保持 `mem_valid`、地址、写数据，直到 `mem_ready=1` 的时钟边沿，`mem_error` 与该响应同时有效。等待连续超出 `DMA_TIMEOUT` 会终止任务，默认 4096 周期。

MMIO 即时响应，但未对齐、未知地址、只读寄存器写入、忙时启动或忙时改配置都会返回 `req_error=1`，不会改正在执行的任务。命令必须用完整 32 位 store。

## 寄存器表

默认基址 `0x40000000`。所有寄存器都按 4 字节对齐。

| 偏移 | 名称 | 含义 |
|---|---|---|
| 0x00 | STATUS | bit0 busy；bit1 done；bit2 error；bits8/9 为 slot0/1 有效 |
| 0x04 | RESULT | 最近的点积或最后一行 GEMV 的 INT32 结果 |
| 0x08 / 0x0c | OPERAND_A / B | dot4 的四个有符号 INT8 输入 |
| 0x10 | CMD | bits7:0 操作码，bit8 选择 slot |
| 0x20 / 0x24 / 0x28 | A_ADDR / W_ADDR / Y_ADDR | 输入向量、权重矩阵、输出向量地址 |
| 0x2c / 0x30 | COLS / ROWS | 矩阵列数、行数 |
| 0x34 | W_STRIDE_BYTES | 相邻权重行的字节距离 |
| 0x38 | CTRL | bit0 INT4（0 为 INT8）；bit1 允许完成中断 |
| 0x3c | ERROR_CODE | 错误码 |
| 0x40 | CYCLES | 当前/最近任务的忙周期数 |
| 0x44 / 0x48 | DMA_READ_BYTES / WRITE_BYTES | 实际读/写字节数，包含最后一个字的填充 |
| 0x4c | MACS | 有效乘加次数，不含填充 |
| 0x50 / 0x54 | SLOT0_COLS / SLOT1_COLS | 两个驻留槽最近成功 LOAD 的列数 |

CMD 操作码：1=dot4，2=LOAD，3=GEMV，4=INVALIDATE。例：`0x102` 是向 slot1 加载向量，`0x003` 是使用 slot0 执行 GEMV。

STATUS 的 done/error 是“粘住”的：读状态不会清除。在 STATUS 写 bit1=1 清 done，写 bit2=1 清 error/error_code；写 0 不清。这叫 W1C。新任务自动清前一任务完成状态。IRQ 为 `CTRL.bit1 && (done || error)`，确认完成后写 STATUS=6 撤销 IRQ。

错误码：1 非法命令，2 参数/对齐错误，3 超出 RAM，4 驻留槽无效或长度不符，5 DMA 错误，6 DMA 超时。对忙时启动等 MMIO 拒绝，CPU 会获得总线错误；硬件不抢占旧任务。

## 数值与内存格式

- 激活：有符号 INT8，范围 -128..127，一字四个数，低字节对应更小列。
- INT4 权重：二进制补码 -8..7，一字八个数，低 nibble 对应更小列。例如 `[-8,7,-1,0]` 打包为字节 `0x78,0x0f`。
- INT8 权重：与激活相同的字节顺序。
- 输出：每行一个有符号 INT32，**未**做缩放、偏置、激活函数或重新量化。这些由后续模型运行代码显式处理。
- 每行权重从 4 字节对齐地址开始；stride 必须是 4 的倍数并足以容纳一行。INT4 的 19 列需要 10 个有效字节，stride 至少 12；INT8 的 19 列 stride 至少 20。
- A/W/Y 地址均须 4 字节对齐。A 的末尾、权重行末尾补到 4 字节；最后一个 DMA 字中多出的元素不参加计算。
- 默认列数/行数上限均为 256。两槽共储存 512 字节 INT8 激活。4 个乘法器每个计算拍最多完成 4 次乘加；INT4 每个权重字计算两拍，INT8 每个权重字一拍。

只读权重 W 可以在 `0x00000000..0x0003ffff`；输入 A 和输出 Y 必须在 `0x00020000..0x0003ffff`，硬件检查该边界。只读模型权重可以放在低半 RAM 的 `.rodata`，无需镜像。高半该区域绕过 CPU 数据 Cache，CPU 和 XND 看到同一份数据。不要直接把缓存区域的新数据交给 DMA；除非后续专门实现 Cache flush。DMA 范围检查包含填充字节，防止尾部读越界。

## 两槽驻留与软件顺序

把两个槽理解为两个小抽屉：

1. 在 uncached AI RAM 准备 activation，填写 A_ADDR/COLS/CTRL。
2. 发 LOAD 命令，等待 done；成功后相应 slot valid 变为 1。
3. 填写 W_ADDR/Y_ADDR/COLS/ROWS/STRIDE/CTRL。
4. 发 GEMV 命令，等待 done、检查 error，再读取输出。
5. 对同一向量再次发其他矩阵的 GEMV，不需要重复 LOAD。Q/K/V 三个线性投影可以共用同一槽。
6. 下一个向量可加载到另一槽。第一版执行引擎同一时刻只处理一个任务；双槽表示数据驻留，**不表示**后台 LOAD 与 GEMV 同时计算。
7. 需要丢弃向量时发 INVALIDATE。失败的 LOAD 不会留下有效的半个向量。

C 的 `xnd_job_t` 是轻量软件任务描述符；先调用 `xnd_load_activation`，用 `xnd_wait` 等待，再调用 `xnd_launch_gemv`。后续同槽 GEMV 可以复用。内存屏障在操作前后执行，但屏障不能替代 Cache flush，因此仍使用 uncached 区域。

## 当前验证边界

2026-10-01 的真实 Icarus 单元仿真覆盖：正负极值 dot4、INT4/INT8 GEMV、19 列非整字尾部、DMA 等待、两槽保留、源 RAM 改写后驻留仍有效、乘加/字节计数、done 保持、W1C/IRQ、参数/范围/槽/DMA/超时错误。四路版本通过；Verilator `-Wall` 对 engine 无警告。

这是单元验证，不能称为板上结果。SoC 并发总线、CPU 启动、模型精度以及 PDS 综合/时序/烧录由后续对应阶段证明。模型 bridge 当前只把 8 的倍数列宽交给硬件（当前 d64 模型的 64/128 列满足），其它列宽会回退软件；这里的单元测试对非 8 尾部验证的是 XND 引擎和描述符协议，不代表模型已经使用该通用路径。

描述符规划器也已在服务器执行：`--rows 64 --cols 64 --weight-bits 4 --reuse 3`
生成 1 个 LOAD、3 个 GEMV，`weight_stride_bytes=32`，`required_bytes=6976`，所有
activation/output 地址落在 `0x20000..0x3ffff`。`19x19` 的规划结果为 INT4 stride=12、
INT8 stride=20；这是引擎协议的尾部能力，模型 bridge 对该列宽仍按上文回退软件。

必要的单元运行命令（所有产物仍在 07_runs）：

```bash
cd /work/LUO/NeedleRV-X
iverilog -g2012 -s tb_xnd_engine -o 07_runs/xnd/xnd_unit.vvp \
  01_rtl/xnd/xnd_engine.sv 02_tb/unit/tb_xnd_engine.sv
vvp 07_runs/xnd/xnd_unit.vvp
```
