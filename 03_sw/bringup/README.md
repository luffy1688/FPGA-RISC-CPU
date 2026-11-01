# 裸机验收工程

- startup.s：复位入口、栈、BSS 清零和机器态异常返回。
- cpu_acceptance.S：真正编译出的 RV32IM 指令验收程序，包含整数、字节/半字内存、分支跳转、M 扩展、custom dot4、CSR 和故障陷阱。
- main.c：调用验收程序，经 UART 输出 PASS/FAIL，并写入 0x100000fc 测试标记。
- linker.ld：把 CPU 固件放在 0x00000000..0x1ffff，AI scratchpad 放在 0x20000..0x3ffff。

服务器上的系统 TB 使用相同 256 KiB 地址模型；非法数据访问返回总线错误，UART 和 0x100000fc 只由 TB 观察。当前验收仿真已通过，结果写入 07_runs/sim/cpu_acceptance.log。cpu_acceptance.hex 是仿真生成物，不作为源码维护。
