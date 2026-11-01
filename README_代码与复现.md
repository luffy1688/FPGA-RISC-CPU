# 构建与运行

## 环境

开发板PG2L200H-6 / FBB676，PDS2022.2-SP6.4，RV32IM GCC，Python3与Node.js。训练使用PyTorch，控制台使用Edge的Web Serial。

## 固件

在工程根目录运行：

```bash
make -C 03_sw/model ROOT="$PWD" TOOLCHAIN=/path/to/riscv32-unknown-elf- OUT="$PWD/07_runs/model" board-image
```

默认主频40.5MHz、UART921600、CoreMark1200迭代。模型参数已编入C头文件，可直接构建。重新训练的输入与脚本在07_runs/development中。

## PDS与下载

在06_pango_active/run_impl.tcl中设置taskRoot和taskDir，运行综合与布局布线。PG2L200H启动时隙使用DONE T3、GWEN/GRSN T2、GOUTEN T1。仓库内包含production.sbit，可通过PDS Programmer下载RAM；断电后重新下载。

## 控制台

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory 05_tools/console
```

Edge打开http://127.0.0.1:8765/?present=1&baud=921600&arch=1。选择CP210x串口并连接，短按KEY0，等待就绪。串口由一个程序使用。FTDI连接用于JTAG。

一键AI识别发送中文PWM20%请求；快速控制准备完成后发送led 37；CPU自检运行CoreMark。04_model与07_runs/development保存模型处理、训练和选择脚本，02_tb保存RTL测试。
