# model 模型运行与真实工具入口

> 2026-10-27 tool_contract_20261027：当前服务器权重已完成24epoch固定warm-start并通过167条Python/C整数对齐；旧上板5A7/59EE镜像不随源码改变。新固件支持LED整体掩码/单灯开关，独立记录operation与selection_source；能力检查阻止清零计数器、调温及修改跑分。第二批集合按冻结后首次验收流程执行，所有首轮数据保留。


本目录在自研RV32软核执行完整d64定点attention模型。默认交互程序采用两槽生命周期和CPU dot4；PC仅输入文本并展示真实串口结果。

| 文件 | 名字含义与作用 |
|---|---|
| main.c | 主入口；接收一行、推理、解码、执行、打印，或运行7配置对照 |
| byte_tool_model.c | byte为UTF8字节；模型线性/attention/非线性/分类输出 |
| byte_tool_xnd.c | XND后端；描述符、激活staging、驻留和搬运统计 |
| tensor_plan.c | tensor张量；plan为生命周期分配，防止覆盖仍存活的向量 |
| byte_model_data.h | 固定低比特模型常量，47300B量级，实际常量47066B |
| tool_dispatch.c | dispatch派发；检查参数后操作GPIO/PWM/计数器/温度或CoreMark |
| coremark_tool.c | CoreMark工具包装；官方算法CRC成功后才报告OK |
| startup.S | startup启动；设置栈/trap并清零BSS |
| Makefile | 编译配方，固定输出至07_runs/model |

## 七种配置

0软件自然图；1reload自然图；2单槽自然图；3reload交错图；4单槽交错图；5两槽生命周期交错图；6配置5加CPU dot4。公平存储策略比较使用3/4/5；dot4比较5/6；软件与完整最佳路径比较0/6。自然token-major图的单槽已经能复用QKV，不把重排产生的冲突隐藏。

workspace由29760降到21696B，另有1280B XND staging；同一输入4×7路径logits一致。最新完整周期/字节/loads/jobs见07_runs/model/current_report.json；当前stage3预冻结135模板原始87/135、严格工具100/135；与135/135或80/80数值一致分开表述。详见07_runs/eval/current_generalization_report.json。

## 编译与输出

make -C 03_sw/model all：selftest/interactive ELF、BIN、MEM；make -C 03_sw/model simulate：28真实RV32路径；uart-simulate：实际UART RX刺激；board-image：复制交互MEM到06_pango/firmware。

模型代码-O2/Wall/Wextra/Werror，RV32IM ABI，无Linux依赖。CPU byte loads用于未对齐pack，避免工具链将4字节memcpy合并成会trap的unaligned LW；对齐情况使用快路径。

## 电脑串口演示

物理串口115200/8N1，UTF8，连接后按KEY0重启，等待NR_READY再发一行（最多64字节）。推荐运行05_tools/console/index.html，README给出localhost静态服务方式。初始用led 37、pwm 25、读取计数器、帮我执行CoreMark。任意新中文句子的分类不保证正确；页面显示实际工具，而不是按按钮预设成功。

NR_RESULT字段：cycles只计模型推理，value是实际工具结果；execute 0成功、1拒绝、2不可用、3执行失败。read_temp value为有符号摄氏度×100，其余工具为LED掩码、PWM百分比、mcycle或CoreMark计时周期。

LED7由PWM启用后占用；其余LED显示GPIO，GPIO寄存器读回仍为原掩码。PWM1kHz，0到100百分比合法。run_coremark实际占用约14秒，等待返回NR_READY再发下一条。

片内温度使用PG2L200H ADC。HARD_ADC=0通用仿真没有传感器，不返回模拟温度；物理顶层HARD_ADC=1实例化GTP_ADC_E2。转换公式、寄存器和有效/超时边界见06_pango/TEMPERATURE.md。ADC控制器通过仿真，硬原语仍需PDS与实板验证。

fatal DMA错误直接终止，不能继续复用状态不明的DMA缓冲；软件fallback只用于不支持的矩阵尺寸。运行时单实例不可重入，ISR禁止调用模型或抢占XND。

## 置信度拒识门

`byte_tool_model.h` 中的 `NR_MIN_CONFIDENCE_MARGIN=16` 是 Needle 风格的轻量拒识门：`margin=最高logit-次高logit`，它是整数分差，不是概率。低于门槛时 `nr_tool_decode_prediction()` 把工具改为 `reject`，因此不会写 LED/PWM 等外设。旧权重80条模板离线门控曾从61/80到62/80；这是历史基线，不能用于当前stage3权重准确率。当前模型已经进行3000句固定100epoch扩展训练，135模板原始87/135、严格工具100/135，全部合成且不是开放中文准确率。`07_runs/model/confidence_gate_report.json` 保存了范围和结果，`host-acceptance` 已增加低分差不触发外设的验收。

## 运行配置、策略与PMU

控制协议`:config 0..6`，等待NR_CONFIG确认实际配置。NR_BUILD记录固件协议/模型阶段/时钟；非法配置不改变状态。NR_RESULT中的tool是模型原分类，selected_tool是实际解码工具，margin为整数分差，decode8表示否定/多工具/文字类别不匹配，仅拒绝不纠正分类。tool_cycles计派发执行、request_cycles计推理/解码/执行/计数采样，不含RX/结果打印。pmu是区间差分；顺序CSR采样有开销，branches和redirect_misses含义不同，不计算误导性分支失败率。详见00_docs/stage3_software_handoff.md。

默认“读取计数器”支持；旧“我想查看计数器”margin4被16门槛拒绝并保留回归，不降低门槛制造演示成功。

## 10月7日默认优化与复现

默认编译开关Q_REUSE=1、AV4=1、POST_FUSE=0、PROFILE=0。Q复用只在config6的dot4路径启用；AV4作用于所有配置，不改变七配置的硬件策略。后处理融合保留为显式候选，实测退步而默认关闭。

Q复用把同一query/head的4个32bit打包值保留，再遍历K；AV4读一次指数权重并累加四个连续V通道。指数权重是0到4096，不截成INT8；累加后仍使用原精确除法。循环只形成有效key地址。原workspace与DMA计数不增加。

正式配置6对同源码control：led 1462381→1303072周期，中文4656058→3717459周期。5→6同时包含dot4与Q复用，不再解释成单独dot4指令收益。完整消融、边界与UART记录见07_runs/model/optimization/current_report.md/json。NR_BUILD增加kernel_stage与实际开关字段，协议2保持。

需要复现单项消融时使用MODEL_FLAGS并强制重编译模型（修改变量本身不会自动使已有ELF失效）：

```sh
make -C 03_sw/model -W byte_tool_model.c ../../07_runs/model/selftest.mem MODEL_FLAGS='-DNR_OPT_Q_REUSE=0 -DNR_OPT_AV4=1 -DNR_OPT_POST_FUSE=0 -DNR_MODEL_PROFILE=0'
```

profile目标生成独立optimization/profile ELF/MEM并使用已有obj_soc执行诊断，不覆盖正式interactive ELF。它只测config5/6的led/中文，Q/AV/fuse均关闭；PROFILE计数不用于正式提速。输出会切换current.mem且覆盖profile.log，不与正式仿真同时执行。重新回到默认固件：

```sh
make -C 03_sw/model -W byte_tool_model.c all host board-image
```

## Tool contract v2

- Contract: tool_schema.json; checks in byte_tool_model.c and tool_dispatch.c.
- LED mask keeps legacy led 37; explicit masks accept hexadecimal. LED0..LED7 / first..eighth ordinal with an on/off verb update only one bit. GPIO7 is unavailable as a single LED while PWM owns it.
- PWM accepts 0..100 ASCII percent, Chinese 百分之 integers and integral 成 units. Multiple/negative/fractional/unsupported frequency requests are rejected.
- operation: 0 normal/mask, 1 LED bit on, 2 LED bit off. selection_source: 0 accepted neural class, 1 read-only schema rescue, 2 explicit bounded LED schema rescue, 3 denied. Raw logits and class remain separate from routing.
- UART capacity remains 64 UTF-8 bytes. CRLF is coalesced; empty input returns NR_INPUT_ERROR empty; overflow drains before READY. No truncation.
- Historical board images/ELF remain intact. New firmware outputs are isolated under 07_runs/model/tool_contract_20261027.
