# NeedleRV-X 完整交互镜像上板说明模板

> 发布者说明：本文件按 2026-10-11 当前代码编写。仅在正式 `pangu_200pro_board.sbit` 生成成功、与本说明所列固件一致后，将它作为烧录包 README 使用。先填写下面的实测/构建信息；不要把 smoke 文件更名冒充完整镜像。本模板不是实板通过记录。

| 交付项 | 发布时填写 |
|---|---|
| 完整位流 | `pangu_200pro_board.sbit`；实际文件路径：**待填写** |
| 生成时间 | **待填写** |
| PDS 精简结果 | `07_runs/pds/current_report.json`；资源、WNS/TNS：**待最终报告** |
| 板卡 | 盘古 200Pro+，Logos2 `PG2L200H-6-FBB676` |
| 实板证据 | UART 原始 TXT/JSON 与板卡照片；**待上板取得** |

## 1. 先认识四类文件

- `.sbit` 是 FPGA 的配置文件，JTAG 烧录时选择它。完整交互镜像文件名是 `pangu_200pro_board.sbit`。
- `.smsk` 是与位流配套的掩码文件，随同名 `.sbit` 保留即可，不把它当启动程序。
- `model_interactive.mem` 是 CPU 程序和模型的片上 RAM 初始化内容，已经包含在生成的位流中，**不单独交给 JTAG**。
- `console/index.html` 是电脑上的串口页面，显示真正从板子收到的结果。页面不在电脑或云端运行模型。默认完整工程没有 HDMI 视频输出；演示画面显示在电脑浏览器中。

代码和实验的主目录是服务器 `/work/LUO/NeedleRV-X`。本地仅保留稳定交付、烧录文件、控制台和比赛材料。PDS 工程输入为 `06_pango/pangu_200pro_board.pds`，顶层为 `01_rtl/board/pangu_200pro_board.sv`，其默认初始化文件为 `firmware/model_interactive.mem`。

## 2. 连接与下载

1. 使用板卡配套的 12 V 适配器供电；将板上的 USB-UART Type-C 数据口与 JTAG 下载器 USB 口接到同一台本地 Windows 电脑。
2. JTAG 线接板上丝印 JTAG 的接口，按照已确认的厂家针脚图连接。单针线按 TCK/TMS/TDI/TDO/GND 等信号对应；若使用十针排线，按 Pin 1 标记对齐。不把 JTAG 线插到 FMC。
3. 板卡上电后，在 PDS 的 `Tools → Configuration` 扫描器件，确认识别到 `PG2L200H`，选择本包的完整 `.sbit`，对器件执行 `Program`。
4. 首轮下载到配置 RAM，先完成下面的串口和外设体验，再考虑 Flash 固化。配置 RAM 内容在断电后消失；本说明不包含 Flash 固化流程。
5. 烧录成功的提示只证明下载步骤完成。收到启动协议和真实工具结果，才证明该交互固件已经运行。

## 3. 打开电脑上的串口页面

1. 使用桌面 Chrome 或 Edge，关闭占用同一个 COM 口的串口终端。
2. 在控制台所在目录打开 PowerShell，执行下面命令，并在浏览器访问 `http://localhost:8765/`：

```powershell
# 进入当前烧录包里的 console 文件夹；这里的路径由实际交付位置决定。
Set-Location '<当前烧录包路径>\console'
# 此服务只提供静态网页，不做后台推理，也不接管串口。
python -m http.server 8765 --bind 127.0.0.1
```

3. 点击“选择串口并连接”，手动选择板卡 USB-UART 对应的 COM 口。参数固定为 **115200、8 数据位、无校验、1 停止位、无流控（8N1）**。
4. 连接后按板上 `KEY0` 逻辑复位按钮，使启动信息重新输出。当前约束的逻辑复位是 C22，KEY1/C23 仅作为 GPIO 输入；不要用配置复位按钮替代它。
5. 依次观察以下内容，再开始发送指令：

```text
NeedleRV-X BRAM64; workspace=...; clock_hz=27000000
NR_BUILD {"protocol":2,...,"clock_hz":27000000,"max_utf8_bytes":64,...}
NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}
NR_READY
```

`BRAM64` 是当前启动文案，不表示主 RAM 只有 64 KiB。默认主 RAM 为 256 KiB，输入上限为 64 个 UTF-8 字节。版本字符串目前为 `software_stage3_oct7`，它是固件内部标签，不应当作今天的生成日期；实际位流日期见发布表。

只出现一次 ASCII `A`、LED 为 `0x5A` 且没有 `NR_READY`，说明正在运行 smoke 诊断镜像；它不解析中文，不使用本页的发送功能。

## 4. 从一句话到 LED/PWM

一条输入的路径是：电脑发送 UTF-8 文本和换行 → 板上 UART 接收 → RV32IM CPU 运行整数语义模型 → CPU 检查工具和参数 → 写 LED/PWM 寄存器 → 串口输出 `NR_RESULT` 和下一条 `NR_READY`。没有电脑代替 FPGA 推理的步骤。

完整镜像启动即进入交互等待，不自动跑 CoreMark，也不自动修改 LED/PWM。默认配置 6 启用 XND 的 INT4 权重 × INT8 激活 GEMV、两槽生命周期驻留、交错 QKV 图和 CPU dot4。两路 Cache 与分支预测器保留。默认没有 DDR 控制器/PHY 数据路径。

每次只发送一条，等下一条 `NR_READY` 后继续。输入最多 64 个 UTF-8 字节，中文汉字通常占 3 字节；数字使用阿拉伯数字和十进制整数，不使用十六进制、小数或中文数词。

| 建议顺序与输入 | 可以观察什么 |
|---|---|
| `led 37` | 最先验证完整推理与执行。成功时 `selected_tool=4`、`decode=0`、`execute=0`、`value=37`，LED 掩码为 `0x25`。 |
| `设置LED为37` | 中文 LED 表达的现场样例。模型可能误判或拒绝，按真实 `NR_RESULT` 判断，不保证任意中文句式都通过。 |
| `pwm 25` | 成功时设置 1 kHz PWM，占空比 25%，`selected_tool=1`、`value=25`。 |
| `设置PWM占空比为25` | 中文 PWM 表达的现场样例，仍需查看真实分类、分差和执行状态。 |
| `读取计数器` | 读取 CPU 的 `mcycle` 低 32 位。回值是周期计数，不是温度或模型耗时。 |
| `read temp` / `读取温度` | 请求 FPGA 片内温度；有效 ADC 样本到达前可以返回暂不可用。 |
| `run coremark` | 请求 CPU 基准，期间等待完整校验和计时输出以及下一个 `NR_READY`，不连续发送。 |
| `pwm -1` | 参数越界，`decode=3`、`execute=1`；不会修改 PWM。 |

LED 数值是 8 位掩码，范围 0～255，bit 0 对应逻辑 LED0。PWM 数值是百分比，范围 0～100；PWM 启用后使用 LED7，其他七个 LED 仍由 GPIO 掩码驱动。**执行 PWM 后再写 LED 不会关闭 PWM**，因此 LED7 继续显示 PWM；想重新观察纯 8 位 LED 掩码，按 KEY0 复位，再先做 LED 测试。不要从亮度推断精确占空比，需要波形测量时再使用示波器/ILA。

LED/PWM 动作要求神经模型选中相应类别、分差不低于 16、明确的单一工具领域词以及合法的唯一整数参数。参数是 CPU 按语法解析的，不是神经模型预测。否定、多工具或不匹配的领域词可以使请求被拒绝。当前只读类（温度、CoreMark、计数器）存在唯一领域词消歧通道，可放行弱分差；不要把这部分结果算成神经模型原始分类准确率。

## 5. 看懂结果并保存现场证据

- `tool` 是原始神经分类，`selected_tool` 是解码后的实际工具，`margin` 是未校准的整数分差，不是概率。
- `execute=0` 表示工具执行成功；`execute=1` 表示拒绝执行；`execute=2` 表示当前工具不可用。`decode=8` 是语义策略拒绝，不表示原始模型已经正确识别。
- `cycles` 只计推理；`request_cycles` 包含推理、解码和工具派发，不含 UART 收取和打印。页面依据固件报告的 27 MHz 换算耗时。
- CoreMark 必须结合 `Correct operation validated`、无错误、完整 `NR_CYCLES/NR_HZ/NR_ITERATIONS` 与不短于 10 秒的计时判断；部分文字不是完整成绩。
- 下载页面上的原始 TXT 日志与证据 JSON，保留 TX/RX、NR_BUILD、NR_CONFIG 和 NR_RESULT。实板证据还应结合板卡照片、实际位流与 PDS 报告；服务器 RTL 仿真日志不替代它。

## 6. 片内温度能做到什么

完整物理顶层默认 `HARD_ADC=1`，实例化 `GTP_ADC_E2`；读取的是 FPGA 芯片内部温度，不是房间温度。采样器等待真实转换完成，并约每 100 ms 读一次温度寄存器；启动后至少等待约 200 ms，再尝试温度命令。

温度工具仅在状态位为“硬件可用且样本有效、无故障”时执行。原始 12 位 code 按 `T=code×0.1219−273.15` 换算；`value` 是有符号摄氏度乘以 100，网页除以 100 显示。显示两位小数不代表测量精度。

没有有效样本、ADC 未转换或访问超时会返回 `execute=2`，**不填假温度**。访问超时进入故障状态，需要板上逻辑复位恢复。若 ADC 仍不可用，先保留原始日志和现场现象，由后续开发定位；本模板不宣称 ADC 已在实板验证。

## 7. 同一位流比较软件与加速路径

收到 `NR_READY` 后，用页面配置下拉框选择 0 并点击“切换配置”，等 `NR_CONFIG` 确认后发送 `led 37`；再切换 6，发送同一句话。控制指令实际为 `:config 0` 与 `:config 6`，它们不经过模型，不直接修改外设。

比较两次真实 `cycles`、`logits` 和搬运统计，保持输入相同。配置 0 是软件 natural，配置 6 是 lifetime + dot4 interleaved；这属于组合收益比较。需要单独看 dot4 与 packed-Q reuse 的联合增益时比较配置 5→6，不能把它称作仅一条指令的收益。片上 DMA 字节不是外部 DDR 流量，引擎周期不是 CPU 端到端周期。

本项目是原创 Needle-inspired 窄域整数工具模型及 RISC-V/XND 硬件，不是在 FPGA 上直接运行官方 Needle 的整个运行时或大模型权重。自由中文表达仍可能误判，应公开保留失败结果。

## 8. 常见现象

- 页面“串口已连接”但没有 `NR_READY`：先按 KEY0；检查 COM 口、115200/8N1，以及是否下载了完整交互镜像。
- 文字乱码：检查串口参数，关闭另一个占用 COM 口的程序，再复位接收完整启动行。
- `NR_INPUT_ERROR too_long`：本行超过 64 字节，固件排空该行后会重新输出 `NR_READY`；缩短文本再发送。
- `NR_BACKEND_ERROR reset_required`：后端已经中止，按 KEY0 复位，保存错误原始行，不自动重复外设动作。
- 中文请求被拒绝：查看原始 `tool`、`selected_tool`、`margin` 与 `decode`；不要用更换日志或人工固定工具执行掩盖模型限制。

发布时只附必要的位流、配套掩码、控制台、本说明和精简报告。完整源码及实验留在服务器主工程，PDS 大型工作数据库不进入烧录包。
