# ADB1 07 指令调度修复 / S1

来源为 `ADB1_07_指令调度修复_S1_队友封存_20261104.zip`。`host/`、`vendor/`、`protocol/`、离线测试及发布证据按原字节保存，逐文件来源哈希见 `MANIFEST_SHA256.json`；原始顶层启动包装也仅作来源记录。运行入口使用相邻的 `adb1_07_bridge.py` 和 `adb1_07_window.py`，不直接执行存档的顶层启动脚本。复用项目已保存的 CPython 3.12/Tk。

`START_HOST.bat` 选 **1**，或在项目根运行：

```powershell
.\host\fd2\upstream\runtime\python.exe -B -X utf8 launch_host.py ADB1_07
```

启动无串口所有者，S1 六参数只预填草稿，不自动连接、写参、校零、运行或启用自适应。操作者手动填写 USB 端口并连接；不自动枚举串口。明确连接时在原串口工作线程取得交付的 `Global\J280_HW_LOCK` 共享互斥，设置 DTR/RTS 为关闭并独占打开。断开后释放；不抢占其他进程。

S1 为角度 `53.78/0/210.14`、位置 `17.67/0/616.61`；原固件复位默认仍为角度 `49/0/260`、位置 `25/0/620`。写入与独立读回由原 Host 管理；网页分别展示草稿、独立读回、实际采用。网页与桌面窗口均保留手动自适应开关，所有控制计算继续在 FPGA。

完整身份为 firmware `41444231` / schema `41444203` / wire3 / family16 / caps15；角 P/D 5ms、位置 P/D 25ms，T 每 5ms 的 epoch 增 1。旧快P为 schema `41445001`、epoch增5，依赖保存在 `host/adb1_fastp`，不混用解析器。

07 与更早 DownStop 共享 wire 身份。桥的 `delivery_profile=ADB1_07` 声明仅区分使用的配套软件，不能证明板上精确位流。请按实际烧录记录与位流 SHA 核对。配套位流在 `firmware/releases/20261104/ADB1_07_CommandFlow_S1.fs`。

原 Host 保留最近用户动作 ACK，心跳/读回不覆盖拒绝；ACK 不表示运动完成。光学下滑 STOP 在07中始终优先；新动作间隔不屏蔽 STOP。新自适应为受约束的 V3 响应阻尼记忆，不能沿用快P绝对搜索的说明。

完整分析及验证边界见 `docs/adb1-07-sync-20261104.md`。封存部署记录属于交付方历史证据，本轮仅离线验证及复制文件，没有接入或烧录设备。
