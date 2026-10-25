# FD2 V1～V5 原样 Host

来源：用户于 2026-10-25 交付的 `J280_V5_Standalone_20261025(1).zip`。`SOURCE.json` 记录归档 SHA256；`MANIFEST_SHA256.json` 逐文件记录大小及 SHA256。`upstream/host/` 与 `upstream/runtime/` 是归档对应前缀的原字节文件，没有修改控制、协议或参数。归档其他路径不执行、不导入。

原样依赖与外层适配分开：`../fd2_bridge.py` 观察原 Host 已接受的 coherent T 与独立 D，提供 loopback HTTP 及显式一次性命令；`../fd2_replay.py` 使用原 `trace_log.iter_chunks` 验证原生日志、按物理时间 RX-only 回放。回放绝不启动串口 owner 线程或解释 TX 为命令；ACK 不进入可能安排读回的原接收分支。

|版本|完整 firmware / schema|wire|能力|
|---|---|---|---|
|V1|46443231 / 46443203|2|三起摆，光学手势|
|V2|46443432 / 46443402|3|SWM4，光学旋转手势|
|V3|46443233 / 46443203|2|手动平衡，角P/D自适应|
|V4|46443434 / 46443404|4|三起摆，六位置|
|V5|46443435 / 46443405|5|手动平衡，六位置，六有限轨迹|

日常执行仓库根 `START_HOST.bat`，使用随交付的 CPython 3.12（BT10 winrt 扩展为 cp312）。GUI 中显式连接；不自动串口/蓝牙连接、校零或运行。原 Host 日志及其磁盘保护原样保留。USB、BT10 与小车 BLE 是不同通道。

离线示例（在仓库根执行）：

```powershell
.\host\fd2\upstream\runtime\python.exe -B -X utf8 launch_host.py V5 --offline-preview
.\.venv\Scripts\python.exe -B -X utf8 launch_host.py V3 --headless --offline-preview --once --port 0
.\host\fd2\upstream\runtime\python.exe -B -X utf8 launch_host.py V5 --replay 'D:\logs\ForestFive_V5_session.zip' --headless
```

HTTP 默认 `127.0.0.1:8371`。请求要求 `X-J280-Local: 1`、精确的 loopback Host 且不得包含 Origin。`/waveform` 固定保留最多 64000 条完整样本，覆盖约 200Hz T 加独立 D 的至少 120 秒；每批最多 512 条，head 是最旧可用游标、tail 是最新游标，读取不推进写游标。过载、会话变化与序号/时间缺口明确标识；JSON 超过 JS 安全整数范围的计数为十进制字符串。

原始日志是完整会话依据，环形窗口不替代日志。回放结束保持 `replay.active=true`，`finished=true`；所有硬件命令均拒绝。离线验证不能替代实机运动、方向和保护验收。


## 外层适配的可追溯修正

- 原 Host 文件和上述清单保持不变。所有 HTTP、安全输入检查、会话游标和命令映射均属于 `host/fd2_bridge.py` 外层适配。
- 外层接收包装不跨原 `_receive` 持有 HostState 锁。原 STATUS ACK 可安排独立读回；桥不得改变原 Host 内部分段锁的次序。定向双线程测试覆盖读回和队列 trace 并发。
- 生命周期派发门将会话变更与命令队列插入串行化，派发前再次核对 owner/session；更换会话后旧请求保持结果未知，不向旧 owner 补发。真实 ACK 除 request_id 外还要求 opcode 相符。
- V3 回放的统计通过原 `gain_average.summarize` 计算。播放时使用当前单调时间，播放结束后冻结到最后控制接收时刻；仅恢复历史均值展示，不改变 connected/synced、硬件许可或上游算法。
- 回归测试包含原 native codec 控制帧、原 `_send` 与 ACK、同 ID 错 opcode、V3 原日志统计、CRC 损坏和会话切换。格式化工具仅安装在系统临时目录，项目依赖未升级。
