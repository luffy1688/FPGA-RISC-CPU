# 工具命令离线评价

`host_command_eval.c`调用整数C模型和解码器，在主机评价工具、状态与参数，不操作外设。

```sh
python3 05_tools/eval/evaluate_commands.py
```

这个入口使用早期118条开发检查：90条语义句子与28条参数边界，输入为`04_model/datasets/independent_commands.jsonl`。语义文本为合成模板，已用于开发；原始来源、首轮分数和失败样本保留在数据及结果文件。当前1138条、900条及实板四批结果按各自入口与记录统计，不与118条检查混合。

结果分别报告原始分类、分差门控后分类及工具/状态/参数均正确的严格成功。参数边界覆盖LED/PWM上下限、缺失、多参数、负数、小数、空输入与超长输入。`current_independent_report.json`及逐句JSONL写入`07_runs/eval`。
