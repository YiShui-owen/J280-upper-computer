# V4 蓝牙启动辅助

`bt10_windows_select.py` 原字节来自用户交付的 `V4_BLE_Connection_For_Existing_Host_20261030.zip`，SHA-256 为 `6d896a8ed4656ed330dcfe119e649175ca2c504fd0116fb9fd9dce1caaa114ed`。它只为默认地址使用 Windows 未缓存 GATT 检查，其他地址沿用原扫描器。

`configure.py` 是本项目外层适配，`launch_host.py V4 --v4-ble` 在原 Host 外层桥安装后使用。默认纯 BLE，设备连接仍由用户点击；可选择 USB+BLE 获取 USB 遥测。原 Host、身份校验和串口所有者不变。该路径尚未实机验证。
