# FD2 五版本展示适配

用户已确认统一上位机方案并于 2026-10-25 授权开始修改。当前无实物，以离线验证完成软件交付，现场联调另列。沿用已确认双场景 UI、三维模型和独立 WH-BLE102 小车服务。

## 范围与约束

- 日常启动和设置只展示 V1～V5；旧版依赖及适配保留供追溯，不删除用户数据、不自动提交或推送。
- 以 V5 独立包内最新共享 Host 为原样依赖；保持 UART/CRC、身份、参数、控制算法、保护、原日志及串口唯一所有者。
- V1 三起摆；V2 SWM4 与光学手势转圈；V3 手动平衡和角 P/D 自适应；V4 三起摆和六相对位置；V5 手动平衡、六位置及六有限轨迹，无起摆、自适应或光学手势。
- USB 2 Mbaud 提供 200Hz 控制事务；BT10 只提供键盘命令/ACK；小车 BLE 单独显示。只有显式操作可以发送命令，无自动连接、校零、起摆、参数恢复或重试。
- 保留独立板时、序号、control epoch；状态和诊断不能冒充 200Hz 控制样本。缺帧断线，重启换段；64位原始计数以十进制字符串跨 JSON。
- V5 默认轨迹 32 秒，连续历史至少 120 秒；配套 Host 原始日志覆盖完整会话，并支持离线原始日志回放，明确显示回放、禁用全部硬件操作。

## 模块和接口（并行任务共同契约）

`host/fd2/` 保存原样上游 host、依赖、运行时和来源清单。`host/fd2_bridge.py` 在原串口接收处理外层捕获已接受的帧，提供 loopback HTTP。`host/fd2_replay.py` 读取原 Host 的 ForestFive.Physical.v1 ZIP，只解释接收字节，不执行归档中的代码。

`GET /status` 返回：

```json
{"protocol":"FD2","variant":5,"user_code":"46443435","schema":"46443405","wire_version":5,"session":"unique-stream-id","connected":false,"synced":false,"status_age_s":null,"control_age_s":null,"diagnostic_age_s":null,"host":{},"requests":{},"transport":{},"replay":{"active":false,"finished":false,"label":""}}
```

`host` 包含原 HostState 的 latest、last_control、latest_diagnostic、actual_gain_averages、gesture_events、command_events、error、log_error、crc_errors、sequence_gaps 等可序列化字段；省略 history/compact_history/goal_history 和 tuple-key 配置表。`transport` 使用 usb_connected、ble_connected 布尔字段与 route_errors，不将 USB 成功视作 BLE 成功。`session` 随新 owner/回放源/板端重启而变。

`GET /waveform?after=&stream=&limit=512` 返回原游标结构 stream/cursor/head/tail/overrun/samples；每个 sample 是 `{cursor, received_at, frame, gap_before}`，frame 为原 protocol.decode 得到的完整 telemetry 或 diagnostic 字典。telemetry 仅收 coherent 控制事务，diagnostic 独立入队；保留至少 120 秒，批次最多 512。host 波形游标单调且不因读取推进。

`POST /command` 和 `GET /request/{id}` 兼容当前请求结果模型。接受 action：stop、estop、zero、balance、clear-fault、start-swing、adapt-enable、adapt-disable、position、trajectory、hold。position/trajectory 使用整数 value 1～6；其他不接收 value。同 request_id 同内容不重发，不同内容拒绝；ACK 只能标记 accepted/rejected，不推断机械到位。回放拒绝全部命令。

后端新增 `fd2_telemetry.py`，由现有 TelemetryAdapter 分派。对网页输出 firmware='V1'…'V5'，保留原有公共读数，并增加：

```python
capabilities = dict(swing_up=True, optical_gesture=True, adaptive=False, positions=False, trajectories=False, ble_commands=False)
fd2 = dict(control_fresh=False, diagnostic_fresh=False, control_age_s=None, diagnostic_age_s=None,
           crc_errors=0, sequence_gaps=0, bridge_overrun=False, log_error='', error='')
# 其余字段
motion = dict(origin_count=None, final_target_count=None, final_target_deg=None, actual_count=None,
              reference_count=None, request_id=None, action=None, planner_phase=None, trajectory_done=False,
              tracking_settled=False, settle_ms=None, measured_velocity=None, tracking_error=None)
adaptive = dict(manual_gains=None, active_gains=None, target_gains=None, enabled=False, used=False,
                freeze_reason=None, averages=None)
swing = dict(profile=None, stage=None)
# gesture_event 只表示识别事件；action_reason 为全局最近动作原因，不能强行归因到识别。
gesture_event = dict(code=0, sequence=0, received_at=0)
```

最新实际值必须在独立有效期内；replay.active 明确回放，connected=false、synced=false、status_fresh=false；额外 `display_fresh` 用于回放数据展示，绝不允许控制。正常模式 display_fresh=control_fresh（状态面板可用 status_fresh）。

网页 samples 公共字段：sample_id、session_epoch、received_at、plot_at、measurement_at（秒）、board_ms、gap_before、channels。telemetry 通道 angle_deg、alpha_ref_deg、arm_angle_deg、arm_reference_deg、duty_actual_percent、angle_kp、angle_kd；diagnostic 通道 final_target_deg，仅使用该诊断自己的板时，不冒充同步控制。每样本 raw 保存原宽整数。

新 FD2 前端组件管理必要操作和版本展示，旧参数面板只保留历史代码。摆角使用原 Host 的 `(mean_adc12-3085)*345/4096`，旋臂使用 Forest 1040单位/圈换算，PWM 为 Q15×100/32768。模型旋臂取累计角的周期内表示；展示标定按 V1～V5 分别存储。目标曲线有效性来自板端字段；实际到位只显示 tracking_settled。

## 验证与交付

测试覆盖包文件哈希、五版身份、原生 codec 帧、宽整数、200Hz 批次、游标缺口、断流/重启、参数均值与独立诊断、命令一次发送、回放拒绝硬件命令。执行后台全套 unittest、前端 node tests/build、离线浏览器三分辨率与新 Host 断连启动检查。报告明确哪些仅离线通过。
