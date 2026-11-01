# RV32IM 上游指令自检

这一目录可以理解成“把别人写好的 CPU 考题，放到我们的 CPU 上执行”。考题主体来自 RISC-V 官方社区 `riscv-tests` 仓库，保持原样。我们的代码只负责给考题安排复位入口、内存位置、报错出口，不代替考题计算正确答案。

## 文件名字和职责

- `riscv_test.h`：本工程裸机适配头。设置 `_start`/`mtvec`，把通过或失败的编号写到 TB 可观察的地址 `0x100000fc`；陷阱先把 `mepc` 写到 `0x100000f8`。
- `linker.ld`：把每个考题放在从地址 0 开始的 256 KiB RAM，让 CPU 复位后就能执行。
- `diagnostic_fail.S` / `diagnostic_trap.S`：故意制造一次失败和一次非法指令，确认报告器真的能够记录失败编号、分支 PC、`mcause` 和 `mepc`；它们不是上游 ISA 测试，不计入 49 个结果。
- `../../02_tb/system/tb_riscv_tests.sv`：CPU 周围的仿真小环境。默认取指和数据口加入确定性等待周期，并直接观察报错写操作。
- `../../05_tools/sim/run_riscv_tests.py`：批量编译、执行、汇总脚本。每次更新同一组结果路径，不创建日期版本目录。

## 使用方法

在服务器 `/work/LUO/NeedleRV-X` 下执行：

```sh
make -C 03_sw/riscv_tests
# CPU 某条指令改动时，只选对应考题（仍同时检查 2 个报告器负例）：
make -C 03_sw/riscv_tests selected TESTS='rv32ui-add rv32um-div'
```

输出集中在 `07_runs/riscv_tests/`：

- `current_report.json`：机器可读取的完整摘要，记录来源提交、工具链、通过数、排除原因、每个测试周期和最后 PC。
- `current_report.md`：便于阅读和比赛引用的摘要。
- `current_run.log` / `rtl_compile.log`：一次运行汇总和 RTL 编译日志。
- 每个测试目录的 `build.log`、`run.log`、`test.elf/bin/hex`：编译诊断和当次可重现输入。

局部选题运行写入 `07_runs/riscv_tests/selected/`，保留完整运行摘要不被覆盖。

完整运行默认选取 `rv32ui` 中 41 个、`rv32um` 中 8 个程序。`rv32ui-ma_data` 故意排除：该测试要求未对齐访问成功；我们的 CPU 采用陷阱策略，已有 `03_sw/bringup/cpu_acceptance.S` 测试未对齐异常。脚本不会悄悄把这类测试判定为通过。

## 当前结果和可声称范围

2026-10-02 服务器仿真：**49/49 通过，0 失败；报告器 2 个负例诊断通过**。静态 `test_N` 标签共 1102 个，数字只表示源程序断言标签数量，不是运行时覆盖率或 1102 项独立认证。

默认仿真有总线等待，覆盖整数运算、立即数、分支/跳转、字节/半字/字内存、旁路间距、M 扩展（包括除零、符号及溢出边界）和裸核 `fence.i` 自修改代码。

准确说法是“采用官方 riscv-tests 指令主体，经过本项目裸机环境适配的 RV32I/M 回归”。这**不是** `riscv-arch-test` 正式架构合规认证；没有覆盖完整特权态、A/F/D/V 等扩展，也没有覆盖 Cache、PDS、布局布线时序或实体 FPGA。`fence.i` 结果不能单独证明带 Cache 的一致性。

## 第三方来源

- 来源：https://github.com/riscv-software-src/riscv-tests
- 冻结提交：见 `07_runs/riscv_tests/current_report.json` 的 `upstream.commit`。
- 本地源码：`09_refs/riscv-tests/isa/rv32ui`、`rv32um`、它们引用的 `rv64ui`/`rv64um` 和 `isa/macros/scalar/test_macros.h`。
- 许可证：保留 `09_refs/riscv-tests/LICENSE` 中的 UC Regents BSD 风格声明。测试主体、标量断言宏没有修改；本目录裸机头/TB/脚本是本项目代码。
- 下载不足或首次恢复时，在工程根目录执行 `git clone --depth 1 https://github.com/riscv-software-src/riscv-tests.git 09_refs/riscv-tests`。本适配没有使用上游 `env` 子模块。
