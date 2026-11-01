# Stage 3 泛化训练复现资料

该固定最终epoch模型已正式采用，manifest为stage3_generalization。正式权重/NPZ/C常量分别在04_model/train/current.pt、04_model/export/current_int4.npz、03_sw/model/byte_model_data.h。完整首轮比较与135/135数值对齐报告保留在07_runs/eval/current_generalization_report.json和.md，fresh逐句预测在generalization_fresh_predictions.jsonl。PDS与RTL/固件证据由root刷新。

本目录仅保留datasets三份JSONL、protocol.json、train_candidate.py、evaluate_candidate.py、initialization.pt。初始化checkpoint是原模型的warm-start输入（约357KB），覆盖current后必须保留它才能复现；不是重复的候选或中间epoch。当前candidate.pt、C运行时副本、候选export和主机二进制已清理，可由脚本重新生成。

训练使用现有CUDA Python，固定seed29/100epoch/batch64，d64/两层/四头/64byte不变。3000训练句子六类各500；数字随机0..999并部分#掩码；参数仍由显式解码器验证。135句/70表达模板test在训练前冻结且未用于挑checkpoint，但完成首轮评价后已被观察。今后重跑只能叫复现或开发对照，不能叫新的独立盲测。

入口：使用现有CUDA解释器执行04_model/train/train_export.py --stage3-candidate，再运行本目录evaluate_candidate.py。两者只生成隔离候选，不自动采用正式权重；不要运行legacy默认模板训练来复现stage3。原始比较基线记录已经保存，重跑时baseline current可能已是新模型，应以07_runs/eval完整首轮报告为历史依据。

默认中文计数器演示“读取计数器”是训练样例（raw read_counter、margin208、status0），不作泛化证据。旧句“我想查看计数器”raw正确但margin4，保留为拒绝回归，门槛16不降低。


## 2026-10-10 Needle schema chain reproducibility

The Needle-inspired candidate chain now runs from the server default `python3` command. When the EDA shell exposes Python 3.8, the script re-executes with the bundled `/usr/bin/python3.12` so the vendored schema helper's PEP 604 annotations remain usable. The run generated 50 schema-shaped candidates, accepted 48 and rejected 2; the production model, firmware and flashed memory were unchanged. Existing candidate-only matching remains 41/48 raw and 40/48 after the board guard. No official Needle runtime or weights are installed, so this is schema-reference and candidate review evidence, not an official Needle inference score.
