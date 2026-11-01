# Needle-inspired 小模型：当前板卡验证版

本目录是神经模型的软件部分，CPU / XND 的 RTL 在 `01_rtl`。源码和实验均放在服务器，继续更新 current 文件，避免给每次训练另建 v1/v2/v3 文件。

## 先用小白的话理解它

你输入“设置 PWM 为 63”，CPU 先把文字拆成 UTF-8 字节。小神经网络判断这句话要调用 `set_pwm`，然后显式的十进制解析器读取 63，CPU 检查范围为 0～100。最后才允许写外设。神经网络负责**判断意图**，数字解析和合法性检查属于软件，不能把两者混称大模型能力。

当前模型是原创的 **2 层、4 个 attention head 的 byte-attention encoder**，有 5 个工具和 1 个 reject 类。输出是固定工具 schema，不生成自由文本。它参考了 Needle 的低比特计算、窄域工具调用、按层组织参数三个思路；**不是上游 Needle3 的权重，也不是完整 Needle3 架构或通用轻量 LLM**。最终路线的更强语言模型仍需要后续真实数据、架构升级和评估。

## 200Pro+ 配置和完成边界

| 项目 | 当前 BRAM64 bring-up | 后续性能配置 |
|---|---|---|
| 维度 / 层数 / 长度 | d=64 / 2层 / 最多64 UTF-8字节 | d=128 / 2层起步 / 64字节 |
| 输入 | 0～255 固定字节词表，ASCII忽略大小写 | 同一接口，可扩模型 |
| 权重 / 激活 / 累加 | INT4 / INT8 / INT32 | 同一精度 |
| 模型常量 | 47,066字节：权重43,200、偏置3,608、exp LUT 258 | 约156KiB，需重新导出实算 |
| 软件 workspace | 21,696字节，无malloc（FF单token复用后） | 42,880字节（同样采用FF单token缓冲） |
| XND兼容 staging | 1,280字节 | 1,280字节 |
| 神经任务 | 工具意图分类 | 后续评估更强的窄域语言/工具模型 |

当前 d64 由我们暂定的256KiB SoC RAM与128KiB固件分区决定。用户提供的 PG2L200H-6IFBB676 参数是415块36Kbit BRAM，共14,940Kbit，约1.82MiB；板卡本身并非只能运行d64。PDS可用后可尝试扩大片上RAM到512KiB并保留缓存/AI地址边界，再决定是否接入DDR3。DDR3资料为8Gbit、32位、1066Mbps，这是接口规格，不等于已测有效带宽。第一张接口清单写的是100Pro+，引脚以200Pro+真实原理图/约束为准。

模型参数排成[输出,输入]，每行INT4低nibble对应较小列号，4字节对齐。CPU只读常量在低半区；运行workspace在 `.ai_scratch`，由主链接脚本放到 `0x20000..0x3ffff`。engine的activation/output必须高半，weight允许读取整片RAM。缓存与DMA不会争用同一份可写缓存数据。

## 文件名怎么读

- `train/byte_model.py`：byte表示按字节输入，model是训练结构。
- `train/train_export.py`：train训练，export导出。默认d64，支持`--d-model 128`。
- `datasets/train.jsonl`：每行一个训练语句/意图/数值。
- `datasets/template_development.jsonl`：已观察过的开发集，仅帮助发现问题。
- `datasets/template_holdout.jsonl`：新的保留模板集；不用于挑epoch。
- `train/current.pt`：当前可继续训练的浮点/QAT参数。
- `export/current_int4.npz`：定点golden读取的INT4和整数偏置。
- `export/current_manifest.json`：维度、矩阵、缩放和内存预算。
- `golden/fixed_reference.py`：纯整数参考算法；golden意为可信参考值。
- `golden/compare_c_reference.py`：导出后必需的C/Python数值对齐。
- `../03_sw/model/byte_tool_model.c`：不用Python/浮点的裸机推理。
- `../03_sw/model/byte_model_data.h`：导出的常量；不用手改。
- `../03_sw/model/byte_tool_xnd.c`：将GEMV接到自研低比特硬件。
- `../05_tools/plan/descriptor_plan.py`：生成LOAD一次、GEMV多次的驻留计划。

## 运行当前结果

已有Python3.8、torch1.13、numpy1.22，无须安装全局库。

```bash
cd /work/LUO/NeedleRV-X
python3 04_model/golden/fixed_reference.py --text "set pwm 63"
gcc -std=c99 -O2 -Wall -Wextra -Werror -I03_sw/model \
  03_sw/model/byte_tool_model.c 03_sw/model/host_demo.c \
  -o 04_model/golden/model_demo
04_model/golden/model_demo "set pwm 63"
python3 04_model/golden/compare_c_reference.py
```

已在服务器实际执行：`byte_tool_model.c`、`byte_tool_xnd.c` 和 `gemv_reference.c`
均通过 `gcc -std=c99 -O2 -Wall -Wextra -Werror`；Python/C 对保留集 80 条语句的
logits 和类别索引逐项相等（80/80）。这只是数值实现对齐，不等于模型准确率。

只在真的要重训时运行，命令会更新同一套current参数：

```bash
python3 04_model/train/train_export.py --d-model 64 --epochs 140
python3 04_model/golden/fixed_reference.py
```

主工程链接 `byte_tool_model.c` 与可选的 `byte_tool_xnd.c`，不链接服务器 `host_demo.c`。调用 `nr_tool_decode(bytes,len,&request)`。只有 `status==NR_TOOL_OK` 才执行工具；PWM 0..100、LED 0..255；缺数字/多数字/小数/负数均拒绝。

`nr_model_enable_xnd(1)`是旧单槽兼容入口；当前交互程序选择NR_XND_LIFETIME、交错QKV和CPU dot4。生命周期flags声明输入存活/最后使用，不能只靠相同指针猜测。4输入×7真实RV32配置logits逐项相同，三种存储策略对照使用同一交错图；额外生命周期收益约0.38%～0.58%，未降低权重字节，也没有DMA/计算重叠。最新数据见07_runs/model/current_report.json。

串口位流验证LED、真实PWM25%引脚波形、中文计数器、按需CoreMark、非法输入/超长恢复。片内温度硬ADC候选代码已接入，通用仿真无物理传感器返回不可用；真实采样须PDS和实板确认。默认使用05_tools/console中文Web Serial页面，PC不承担推理。

## 现在的真实结果与限制

第二轮训练采用类别均衡、前后礼貌词和数字扰动。第一轮看过的模板集合已降为development，新的holdout基础模板与训练不同；不按holdout选择epoch。定点模型在这80条synthetic保留语句上 **61/80 = 76.25%**。这只能证明当前闭集模板能力，不能宣称真实语言泛化、竞赛完成、国一概率或正式Needle移植完成。

C与Python所有logits的逐项对齐结果保存在 `golden/current_c_alignment.json`；语义准确率和数值一致率是不同指标。整模型与XND已在主SoC RTL中执行；实板烧录、资源/时序报告尚未完成。后续优先加入你实际会说的中文指令、保留用户语句测试集、改进counter与coremark混淆，再提升到d128。不要因为训练准确率高就认为陌生语句也正确。

上游源码保留于 `09_refs/needle`，遵循其Apache-2.0许可。此目录的训练结构与C实现是项目自己的小模型，不调用官方JAX/Flax架构或.cact运行时。

## Stage 3 数据泛化模型（当前正式采用）

当前manifest标记 `stage3_generalization`。架构仍d64/两层/四头/64byte、模型常量47,066B。六类均衡3000句训练加入数字随机与#掩码、否定/不支持/多工具reject。训练前冻结的新135句/70表达模板集只在固定最后100epoch权重评价一次：原始INT4/INT8分类87/135（64.44%），策略后严格请求100/135（74.07%），Python/C定点精确135/135。它是Codex编写的合成模板评价，不是真实用户或开放中文识别率，此后已经被观察。

已观察90句开发集当前raw68/90、严格70/90；原始首轮raw49/90保存在frozen_semantic_baseline，不改原始记录。确定性拒识策略与神经网络分类分别报告。默认中文演示采用明确的训练语句“读取计数器”（margin208）；旧“我想查看计数器”（margin4）保留低置信拒绝回归，门槛仍16。

正式文件仍使用train/current.pt、export/current_int4.npz、export/current_manifest.json与03_sw/model/byte_model_data.h。完整采用报告在07_runs/eval/current_generalization_report。固件、RTL性能和PDS证据由root刷新，不沿用旧权重数字。

候选复现目录仅保留数据、脚本、protocol与原始初始化checkpoint。使用服务器现有CUDA Python运行 `04_model/train/train_export.py --stage3-candidate` 可复现隔离候选；该入口不会覆盖正式模型。不要把legacy默认模板训练当作stage3训练。复现后的同集评价只能作已观察开发对照。
