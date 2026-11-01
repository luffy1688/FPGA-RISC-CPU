# 独立工具命令开发评价

`host_command_eval.c` 是服务器主机评价入口，名字表示“在主机上评价一条命令”。它只调用现有整数 C 模型和解码器，不链接到 FPGA 固件，不控制外设。

`evaluate_commands.py` 逐条读取冻结 JSONL，编译主机入口，并生成当前报告和逐句明细。运行：

```sh
cd /work/LUO/NeedleRV-X
python3 05_tools/eval/evaluate_commands.py
```

输入为 `04_model/datasets/independent_commands.jsonl`，共 90 条语义句子（六类各 15 条）和 28 条参数边界。2026-10-02 首次推理前已逐句定义。作者为 Codex；尚未经过参赛者审定；不是从真实用户收集的独立测试集。语义句子的完全相同文本不在 train、template_development、template_holdout 中，但相似措辞和模板仍可能存在。

输出只覆盖 `07_runs/eval/current_independent_report.json`、同名 Markdown 和 `current_independent_results.jsonl`，便于查看和清理。`command_eval` 是可再生成的主机可执行文件。

报告区分三种含义：

- 原始分类：神经网络最高 logit 的工具类。
- 拒识后分类：分差门与十进制参数检查后的工具类。
- 严格结构化成功：工具、状态和预期参数都对。

参数边界还会显式指定预期工具来隔离语义分类，检查 0/255、0/100、负数、越界、缺失、多参数、小数、空输入、65 字节、全角/中文数字等合同。它不是分类准确率。空输入和超长输入在分类前直接成为 reject；不应因为 forced 工具不同而误判失败。

“可执行候选”只表示状态 OK 且工具不是 reject。若最终工具是 LED/PWM，则标为“外设写入候选”；这段程序不真实调用 dispatcher。低分差门不能阻止分差很高的错误，也不能代替否定语义理解。

本集不能在看完结果后删除失败样例、换成成功句子或反复调参后仍称独立。若未来用于训练，必须另建未参与训练的新评价集。本次不改变模型权重、PDS 工程或实板结论。

## 策略开发对照

首轮原始分类 49/90，旧解码严格成功 48/90，完整118条预测已保存在 `07_runs/eval/frozen_semantic_baseline.json`。以后重评会检查文本/ID不变、逐句原始logit是否不变，并比较最终工具、状态和参数。该集已经被观察，任何策略收益都只是同集开发对照；不能再称未经观察的独立测试成绩。报告保留首轮失败例句，尤其两条中英文否定LED命令。
