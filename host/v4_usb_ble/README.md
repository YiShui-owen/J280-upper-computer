# V4 USB＋蓝牙双连接交付来源

`PC_Bluetooth/` 以 `J280_V4_串口蓝牙双连接_上位机完整包_20261103.zip` 为基线，含 Python、Tk、BLE 和串口依赖。原 ZIP SHA-256：`650468afac7c6df482a7e184d7149ccb7ff5f8cc6d4e646e6b06a597b9c38722`。随后原样覆盖 `V4_电脑端连续六键修复_覆盖包_20261103.zip` 中的电脑端文件；覆盖包 SHA-256：`cf142944e0fbdd7c87ab3367ead6ecee4a6e766777183269297e7d44f921cedb`。覆盖前文件及覆盖包清单保存在 `patches/20261103_six_key/`；根目录 `FILES_SHA256.json` 记录覆盖前基线，不能单独用于核验覆盖后的文件。网页适配位于外部的 `host/v4_usb_ble_bridge.py`。

覆盖包修复蓝牙副路位置/保持命令确认异常误锁 USB：失败命令结果未知且不重发，失败前已排队的蓝牙位置命令丢弃，之后新按键走 USB；蓝牙须手动断开重连才恢复。该修复不改变位流、PID 或板端保护，蓝牙 CRC 丢包的根因仍未确认。

固件 `5634523A`、schema `56345208`、wire4 / variant4 / layout5；原 Host 也支持旧 `56345239`，但网页新版身份仅在匹配 `3A` ACK 及当前会话 D 帧后同步。注意包内 `PC_Bluetooth/VERSION.json` 的旧 `firmware` 字段仍是 `56345239`，其 `usb_bluetooth_firmware` 字段和位流、实际帧标识为 `5634523A`。

使用项目根目录的 `START_HOST.bat` 选择 2；配套窗口手动连接 USB，需要时再手动连接蓝牙。也可使用：

```powershell
.\host\v4_usb_ble\PC_Bluetooth\runtime\python.exe -B -X utf8 launch_host.py V4_USB_BLE
```

配套位流及完整分析见 [固件说明](../../firmware/README.md) 和 [双连接分析](../../docs/v4-usb-ble-20261103.md)。
