# 串口采集与延迟测量

当前双核固件使用CP210x UART、921600/8N1。采集前关闭浏览器或其他串口程序，保持板卡供电；串口打开后短按KEY0，等待启动与就绪。

## 原生测量

在工程根目录运行：

```powershell
python .\05_tools\board\native_latency.py --port COM10 --baud 921600 --repeat 10 --output 07_runs/board/latency_capture.json
```

`native_latency.py`使用Win32 ReadFile/WriteFile及高精度主机时钟。默认等待本次启动NR_READY后逐条发送，记录TX到结果与READY的时间；`--commands-json`可提供工具、参数和预期返回。`--assume-ready`仅用于明确的串口状态移交。一次测量结束后程序释放端口。

`--selftest`只检查主机解析器。往返时间包含USB、串口和主机调度；模型计算周期、工具计时另从返回帧读取。

## 兼容工具

`uart_capture.ps1`面向早期115200固件，保留RX字节、解码文本与收发事件。它不适用于当前921600双核镜像。`summarize_bringup.py`可离线整理已有UART和PDS日志。

当前实板的四批指令、40次控制往返和网页UART事务位于`07_runs/board/current/dual_final_*`。烧录入口及主副核ROM见`06_pango_active`。
