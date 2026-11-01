# 物理板卡串口采集

`uart_capture.ps1` 兼容 Windows PowerShell 5.1，不安装依赖，不操作 JTAG。固定使用 115200 / 8N1 / 无流控，DTR、RTS 均关闭。运行前先关闭占用同一 COM 口的 Xshell、HiBurn 或浏览器串口页面；串口号以当前设备管理器识别的 CP210x 为准。

```powershell
# 在工程根目录运行；按当前识别结果修改 COM10。
.\05_tools\board\uart_capture.ps1 -Port COM10 `
    -OutputDirectory .\07_runs\board\uart_session `
    -CommandFile .\07_runs\board\uart_session\command.json `
    -StopFile .\07_runs\board\uart_session\capture.stop
```

默认连续采集一小时，可用 `-DurationSeconds` 调整。每次生成独立文件：

- `uart_*.bin`：精确保留接收字节，只有 RX；不会写入假启动信息。
- `uart_*.txt`：UTF-8 流式解码，跨读取块的中文不会拆坏；无效/末尾不完整编码用替代字符，原始字节仍在 BIN 中。
- `uart_*.jsonl`：带时间的 RX/TX、错误和关闭事件；收发字节同时保留 Base64。TX 只记录串口写操作，不能当板上执行成功。
- `capture_status.json`：当前状态、字节数、READY、最近一行及路径；同目录临时文件后原子替换，避免并发读取看到写到一半的 JSON。

`CommandFile` 是单个 UTF-8 JSON 对象，例如 `{"id":"led-001","text":"led 37"}`。每个 ID 在同一次采集中至多发送一次；仅收到完整 `NR_READY` 行才发送普通命令，发送后等待下一条 READY。命令最多 64 个 UTF-8 字节，不允许内含换行；工具自动追加 LF。修改文件中的 ID 才表示新的命令，不要连续排队。默认整行写入；可用 `-CharacterIntervalMilliseconds 2` 逐字节发送。

启动文本可能已经错过时，可**显式进行一次**不会写外设的连通性诊断：

```json
{"id":"probe-001","text":":probe","probe":true}
```

只有 `probe:true` 且文本严格为 `:probe`，才能越过 READY 门控；同一次采集中最多一次，默认字节间隔 2 ms，可用 `-ProbeCharacterIntervalMilliseconds` 调整。当前完整固件应回复 `NR_CONTROL_ERROR invalid_config` 和 `NR_READY`：前者是无效控制命令的预期响应，不是模型出错。先被动接收数秒再探测；启动/忙碌期间可能丢 RX 字节，工具不会自动重复诊断。smoke 镜像不解析命令，不会回复 READY。

需要回到 Xshell 时，创建指定 StopFile，例如：

```powershell
New-Item -ItemType File -Path .\07_runs\board\uart_session\capture.stop -Force
```

工具刷新日志、关闭串口后写入 `state=stopped`、`serial_open=false`。再打开 Xshell。已有 StopFile 会让下次采集直接停止，不会自动删除它；确认旧采集已经退出后再手动移除。也可在运行窗口按 Ctrl+C，工具的 finally 块会释放串口。

串口证据与配置 DONE 分开：工具不读取 DONE，也不烧录 FPGA。DONE=1 只证明配置状态；`NR_BUILD`/`NR_READY` 和真实 `NR_RESULT` 才能作为固件启动及功能证据。探针响应仅证明命令循环和双向串口，不能代替 LED/PWM、ADC、CoreMark 或模型验收。脚本通过 PowerShell 7 和 Windows PowerShell 5.1 语法解析；status 的原子替换在两种宿主中分别完成两次真实文件替换核对。硬件收发验收应以独立的现场记录为准。

## 汇总真实日志

`summarize_bringup.py` 只读取采集 JSONL 与 PDS 日志，重建原始 RX，保存输入哈希和逐命令响应，不连接硬件。支持 PDS 的 UTF-16 或 UTF-8 文本日志。

```powershell
python .\05_tools\board\summarize_bringup.py `
    --uart-events .\07_runs\board\uart_session\uart_实际时间.jsonl `
    --program-log .\07_runs\board\uart_session\program.log `
    --output .\07_runs\board\uart_session\bringup_report.json
```

报告分别记录 Program 成功、DONE 状态、启动 READY、探针往返和模型命令往返；不会据此自动宣布全部实板验收完成。采集中生成的哈希是该时刻快照，结束后应再汇总一次。当前已用真实零 RX 的现场日志确认这些功能字段保持 false。

最小测试顺序为探针、`读取计数器`、`led 37`、`read temp`、`set pwm 50`、`run coremark`，每条等待下一次 READY；对相同输入分别运行 `:config 0` 与 `:config 6`，比对真实 logits 与 cycles。LED/PWM 还要现场观察或测量；ADC 的 `execute=2` 表示不可用，不能填入温度；CoreMark 要核对 CRC、完成状态及计时区间，少于 10 秒不能宣布有效基准成绩。
