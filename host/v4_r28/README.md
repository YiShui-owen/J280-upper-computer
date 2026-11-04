# V4 R28 原版交付

`PC_Bluetooth/` 从 `J280_V4_R28_56345239_20261103_Complete.zip` 的同名目录原样提取，包含 runtime 和 vendor_ble。原 ZIP SHA256：`ba1f7f7117ffe7c48693a82c84d50dc81b32cac2054b776d0fdcba84130502ee`。逐文件 SHA256 见 `MANIFEST_SHA256.json`，共 2124 项。`host/v4_r28_bridge.py` 是独立外层适配，不修改原版。

从项目根目录运行：

```powershell
host/v4_r28/PC_Bluetooth/runtime/python.exe -B -X utf8 -m host.v4_r28_bridge --port 8371
```

窗口启动后须由用户手动连接蓝牙。会话日志仍由原 Host 保存。此桥暂未实现 `ForestD1.Raw.v2` 回放；不支持起摆和轨迹。没有通过实机验证。
