# 五版本匹配上位机

从根目录 `Start_V1.cmd` 至 `Start_V5.cmd` 或每版 `Run_Host.cmd` 进入。共享源码按 `--variant` 选择界面和严格协议身份，不是同一个窗口自动猜固件。无需临时安装Python或BLE依赖。

详细功能与操作见 [总说明](../docs/README_CN.md)、[键盘](../docs/KEYBOARD_CN.md)、[接线](../docs/WIRING_CN.md)。日志为原始物理收发块加独立事件，无损压缩。不要把历史FD1W窗口用于FD2。

V4/V5最终资源例外：蓝牙键盘命令和ACK保留；USB 2Mbaud提供200Hz波形，选择USB+BLE。BT10为230400，不是USB波特率。成品键盘与Windows配对，由指定RawInput设备转发，BT10不作通用HID主机。
