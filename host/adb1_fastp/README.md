# ADB1 快 P / S1 配套 Host

`host/` 和 `vendor/` 直接提取自 `ADB1_S1_队友交付封存_20261103.zip` 的 `原版完整包`，原字节未修改；`MANIFEST_SHA256.json` 记录 ZIP SHA256 和逐文件 SHA256。运行时复用项目既有 CPython 3.12/Tk；随交付的 serial 位于本目录 vendor。代码通过 `host.adb1_fastp.host` 独立包名加载，避免混用旧 ADB1 协议。

网页桥见 `host/adb1_fastp_bridge.py`。窗口仅将 S1 数值设为输入草稿，手动触发写入后由原 Host 发出独立读回；实际读回取 Host 状态，不从草稿推断。2026-11-04 按用户明确要求恢复自适应手动开关，网页和原窗口均使用原 Host 的 ADAPT_ENABLE / ADAPT_DISABLE 命令及 ACK；启动不自动启用。原始交付代码没有改动。离线模拟不是硬件数据；连接、写入、运行均需明确操作。
