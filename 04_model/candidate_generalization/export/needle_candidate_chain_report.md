# Needle候选工具表达链路

本报告把官方Needle仓库的工具schema构造用于候选表达的结构化生成，然后以板端工具范围、单调用约束和参数范围进行人工规则校正。服务器没有安装cactus-needle运行时，也没有needle3权重，因此这次不是官方模型推理准确率实验。

- 源码提交：`6bd836d521a2991510bf303cd0d87e025e8ce9dc`
- schema构造：`09_refs/needle/needle/agent/tools.py`
- 原始候选：50 条；通过：48 条；拒绝：2 条
- 通过类别：`{'read_temp': 4, 'read_counter': 4, 'run_coremark': 4, 'set_led': 16, 'set_pwm': 16, 'reject': 4}`
- 拒绝原因：`{'PWM percent outside 0..100': 1, 'FPGA demo accepts one deterministic action per request': 1}`
- 生产模型、固件和板级工程均未修改。

## 可审计文件

- `needle_schema.json`：由官方源码build_schema生成的工具schema。
- `needle_candidates_raw.jsonl`：候选生成阶段（含边界和故意非法样本）。
- `needle_candidates_filtered.jsonl`：规则人工复核后可执行的单调用候选。
- `needle_candidate_append.jsonl`：可选训练追加集，当前不自动合并。

## 采用边界

这条链路可以作为“Needle结构化工具设计思想 → 人工过滤 → FPGA小模型执行”的证据；不能把它写成“Needle3已经在FPGA上运行”或“官方模型生成了这些文本”。若后续取得官方运行时和权重，应另存官方推理原始输出、模型版本、置信度和人工修改记录，再决定是否纳入训练。
