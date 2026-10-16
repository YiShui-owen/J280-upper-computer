# 小车 BLE 配套依赖

`vendor/` 原样保存用户附件 `SmartCarBluetooth_Current_20261011(1).zip` 中运行必要的两个源码，逐字节 SHA-256 见 `MANIFEST_SHA256.json`。附件内来源路径为 `SmartCarBluetooth_Current_20261011/Smart_Car_CLI/scripts/bluetooth_client.py` 与同目录 `wireless_client.py`。原 ZIP SHA-256 为 `382b59bb7a1edbba690d712798f514a9bab60c4053ca77ad8a9d2606c07ce282`。

后端只使用当前 BLE100 GATT 驱动和 `BLUETOOTH_HOLD_V2` 身份，复用原始流同步、ASCII/CAR2 校验、`control_step`、`new_control`、`keepalive`、`start_drive`、`stop_and_confirm`。原控制算法、参数、限幅与停车规则未改。文件中随交付存在的 SPP、TCP、模拟器入口未由网页注册或调用。未打包附件扩展、固件、烧录工具、GUI 或项目级指令。

`backend/car_service.py` 为网页连接增加一个 BLE 独占线程、显式搜索选择、随机控制会话、递增输入序号与单调时间 0.2 秒输入租约。输入只由 HTTP 接收路径更新；后台不会替网页续租。输入过期后确认停车，并要求新的全中性输入。即使中性输入和下一次方向输入在同一线程周期内到达，也会保留已经发生的租约中断。显式 STOP 成功后保留连接并换控制会话，旧输入、旧 STOP 与旧断开请求均不能操作新会话。网页仍须由用户手动启用遥控。

`connected` 与 `identified` 仅在原始 GATT/同步/身份校验及本次 STOP 后新静止读回均通过时成立。`feedback_fresh` 独立按实际 CAR2 接收时间判断，阈值为 0.5 秒；缓存读数不更新时间。`received_at` 为本机秒时间戳，`telemetry` 原样保留固件 CAR2 字段，不把控制目标换算成车速或位移。反馈过期的缓存仍可供诊断，界面须根据新鲜度收起实时读数。

连续 CAR2 的新鲜度仅控制读数呈现。初次验证后，即使暂时没有 CAR2，只要原始命令 ACK 正常且网页输入租约有效，仍可显式遥控；每次停止仍要求原驱动收到本次 STOP 的 ACK 和其后的新静止 CAR2，缺失时关闭连接并报告停车未确认。

明确的当前动作电机故障仅在原驱动证据和新停车读回确认后保持连接，松开输入才能继续操作；未知异常或停车无法确认则关闭连接并报告错误。关闭后端会撤销输入，在线程内调用原始确认停车与断开，并等待该线程结束。BLE 固件租约是进程或网络突然中断时的最后保护；离线测试不能证明物理停止距离、无线时延或实车状态。

运行依赖见 `backend/requirements.txt`，现有 Python 3.13 环境使用 `bleak==3.0.2`，不加载交付包的 CPython 3.14 扩展。后端构造与状态查询不搜索、不连接、不自动重连。接口为 `/car/status`、`/car/scan`、`/car/connect`、`/car/intent`、`/car/stop`、`/car/disconnect`。

验证仅使用 `backend/test_car_service.py` 中明示的假物理传输与原始解析器，以及 ASGI 接口 fixture：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s backend
```

本次未执行 BLE 搜索、连接、运动、COM/JTAG 操作或固件维护，实车方向、停车、故障和无线断流仍需人工验收。
