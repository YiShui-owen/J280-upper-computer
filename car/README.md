# 小车 BLE 配套依赖

当前网页使用用户交付 `SmartCar_Steering_V8_3_Trajectory_20261017.zip` 的 **RC83 / CAR8** 协议。原 ZIP SHA256 为 `5980839129e0fb9e4243bc5110619658120c716dd36a956b815f1544cae1473c`。`v83/` 原字节保存三个 `speed_*.py` 模块、配套 bin/hex、构建报告及原合同；来源见 [SOURCE.md](v83/SOURCE.md)，逐文件 SHA256 见 [MANIFEST_SHA256.json](v83/MANIFEST_SHA256.json)。原控制算法、参数默认值、协议、限幅和保护没有修改。

`backend/car_v83_service.py` 在单一所有者线程中创建原 `Session`、`Engine`、`BleTransport`，复用完整握手、CAR8 校验、档位读回、D/B/BRAKE、T/U/K、停车确认和恢复规则。运行入口只创建真实 BLE 传输；模拟器只用于离线测试。现有 Python 3.13 环境使用 `backend/requirements.txt` 中的 `bleak==3.0.2`，不加载交付包 CPython 3.14 扩展。

搜索、选择、连接和启用全部显式操作，没有自动连接或重连。身份校验只接受配套 RC83。配套固件归档在 `v83/firmware`，不会自动烧录；板上版本需要用户现场确认。构造服务和查询状态不启动 BLE。

网页输入采用随机会话、递增安全整数序号和200ms租约，只有 HTTP 输入接收路径续租。断档锁存直到所有者停车，再等待全中性输入；迟来的中性和运动输入不能掩盖断档。STOP/BRAKE/断开立即撤销最新意图，中断在途 ARM；出队再次检查会话，确认新静止反馈后轮换 token，旧请求不能恢复动作。故障锁定输入；同一 GATT 仅尝试一次原停车流程，之后须显式 STOP 重新握手；真实断链关闭且不重连。

急加速为一次性操作，不自动重试；原 Engine 检查快速档、持续手动前进、回正、新鲜活动反馈及峰值条件。BRAKE 与普通 STOP 使用不同原指令。八条轨迹沿用原时限、转向和停止规则，完成后按住不重复启动；必须释放再按。手动转向幅度按原确认的左右限位620/980分别缩放，中心750，不把非对称限位改成对称角度。

状态中的 `telemetry` 保留原 CAR8 字段，`profile` 仅取真实反馈。主帧没有配套辅助帧时，外层增加 `encoder_valid=false` 并将四个编码器字段置空，网页显示 `--`；配套辅助帧晚到可补齐同一快照。`received_at` 是本机秒时间戳，只由实际新主反馈推进；辅助包、重复包和状态轮询不能续新鲜度。后端沿用原 `FEEDBACK_SECONDS=1.2`，网页在1秒内展示，过期收起。编码器计数和目标速度不换算成未经标定的物理速度或位移。

普通STOP等待期间可用同一停车事务的token追加一次BRAKE，所有者取消普通停车等待，再调用原急刹流程。两请求统一在新静止反馈后得到新会话；轮换之后旧token仍拒绝。该机制不表示无线指令或物理制动即时完成，底层阻塞写仍受原传输超时约束。

|接口|用途|
|---|---|
|`GET /car/status`|连接、身份、反馈、阶段、故障和中性要求|
|`POST /car/scan`、`/car/connect`|显式搜索、按选择连接|
|`POST /car/intent`|会话/序号、方向/转向、速度、轨迹、慢段比例、手动转向幅度|
|`POST /car/profile`|停车后切换普通/快速档并等待读回|
|`POST /car/boost`|带会话/序号的一次性急加速|
|`POST /car/stop`、`/car/brake`、`/car/disconnect`|独立停车、急刹、断开及输入撤销|

HTTP 参数范围和互斥检查见 `backend/car_api.py`，接入设计见 [设计记录](../docs/superpowers/specs/2026-10-27-car-v83-design.md)，测试及实机边界见 [验证记录](../docs/car-v83-validation-20261027.md)。后端关停会撤销输入，在所有者线程停车并断开。BLE 固件租约仍是进程或网络突然中断时的最后保护。

旧 `vendor/`、根 `MANIFEST_SHA256.json` 和 `backend/car_service.py` 保留 2026-10-11 的 `BLUETOOTH_HOLD_V2 / CAR2` 历史依赖与回归测试，不再注册为网页入口。旧 ZIP SHA256 为 `382b59bb7a1edbba690d712798f514a9bab60c4053ca77ad8a9d2606c07ce282`。不混用两个版本的身份或停车规则。
