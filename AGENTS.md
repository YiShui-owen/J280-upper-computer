# 项目协作规则

## 2026-11-04 ADB1 07 日常更新

日常四版改为 `ADB1_07`、`V4_USB_BLE`、`G3_C1`、`DS13`；旧 `ADB1_FASTP` 和 `ADB1` 仅保留追溯。07原Host在 `host/adb1_07`，外层桥/断开启动窗口在 `host/adb1_07_bridge.py` / `host/adb1_07_window.py`。完整身份16/41444231/41444203/wire3/caps15；角P/D5ms、位置P/D25ms，T每5ms epoch增1，快P增5且schema41445001。两解析器必须隔离。07共享较早DownStop的wire身份，`delivery_profile=ADB1_07`仅为软件入口声明，不证明板上精确位流；无声明的旧ADB1仍为历史入口。

本版S1仍为人工写入值，复位默认49/0/260、25/0/620；预填草稿不得视为读回或实际采用。保留用户要求的网页和窗口自适应手动启闭；07为受约束的V3响应阻尼记忆，不沿用旧快P绝对搜索解释。下滑STOP始终优先，不受运动间隔屏蔽。原Host保留用户动作拒绝，心跳不覆盖。窗口启动无串口所有者，只有明确连接才取交付共享硬件互斥并打开端口；不自动连接、烧录或写参。固件 `firmware/releases/20261104/ADB1_07_CommandFlow_S1.fs` SHA为41b9192fed5b4e887e458e1a69689ad7a660964ca8cf1ccacd6c4e31f7b4bf45。详见 `docs/adb1-07-sync-20261104.md`，以下11/03说明为历史记录。

## 2026-11-03 V4 双连接更新

同日电脑端连续六键覆盖包已应用：蓝牙副路位置/保持命令确认异常时隔离副路，旧命令结果未知且不重发，未发送的旧蓝牙位置队列丢弃，后续新请求走 USB；须手动断开重连蓝牙才解除隔离。该补丁不改位流，CRC 丢包根因尚未确认。来源及覆盖前备份见 `host/v4_usb_ble/patches/20261103_six_key/`。

最新 V4 日常入口为 `V4_USB_BLE`，固件 `5634523A` / schema `56345208` / wire4 / variant4 / layout5。旧 `V4_R28` 的 `56345239` 是另一身份，保留供追溯，不可冒认。原双连接 Host 在 `host/v4_usb_ble/PC_Bluetooth`，通过 `host/v4_usb_ble_bridge.py` 接入；新位流位于 `firmware/releases/20261103/V4_USB_BLE_5634523A.fs`。启动不自动连接、烧录、校零或运动。

USB 主路和蓝牙副路由同一原 Host、同一逻辑会话和统一请求 ID 管理；蓝牙就绪时位置及保持命令优先走蓝牙，USB 仍负责普通命令与数据，蓝牙未就绪时新提交的位置可走 USB。已发送但结果未知的命令不得换路重发。STOP/ESTOP 由原 Host 同事件镜像到可用双路。网页的同步条件额外要求本会话匹配的 `3A` 主路 ACK 和 schema/layout 正确的主路 D；长 D 尚未到达时原 Host 仍可按其自身规则使用，但网页等待身份核验。独立硬件验证边界见 `docs/v4-usb-ble-20261103.md`。

## 2026-11-03 日常版本更新

日常启动与网页版本选项为 ADB1_FASTP、V4_USB_BLE、G3_C1、DS13；旧 V4_R28 和 V1～V5 仅供追溯。各版依 firmware/schema/wire/variant 完整身份区分，严禁把不同身份合并为同一固件。原 Host 与位流按分支保存并核验来源，不能自动下载、连接、校零、写参或运行。

ADB1 的 S1 是人工写入值，不是原 FS 上电默认；用户于 2026-11-04 明确要求恢复 ADB1_FASTP 自适应手动开关，网页右侧和参数窗口均提供启用/关闭；使用原 Host 命令和设备读回，不自动启用。历史交付说明保留为来源记录，当前以本条用户指示为准。V4 R28 为纯 BLE compact 和独立诊断，不提供起摆。G3 C1 为基于真实 ENC 的 GOWIN 映射展示而非二维实物轨迹。DS13 R2 的网页和 Host 窗口手绘共享互斥控制；网页按住时以输入时间戳续租，Host 窗口按住时检测实际鼠标，原 Host 按约 20ms 独立发送最新点并处理 ACK，松开、失焦、隐藏或会话变化结束；点流 200ms 超时与原通信保护独立，迟到输入不得复活已结束笔画。手绘目标和编码器实测以板端同一笔画原点对照，不能把目标当作实际。新增原始日志回放必须只读且禁用全部硬件命令。新版软件离线测试不等于板端机械效果验收。

这是 J280 旋转倒立摆展示上位机，日常支持 2026-11-03 的 ADB1_FASTP、V4_USB_BLE、G3_C1、DS13 四个分支；旧 V4_R28、FD2 V1～V5 与 SG21 / SA21 / SP24 保留历史资料，不再列为日常启动或网页版本选项。链路为 `FPGA → USB 或 BT10 → 配套 Host（唯一设备所有者）→ 本机 HTTP → FastAPI → WebSocket → Vue`。旧 V5.12 日志/mailbox 链路已替换，不按历史文档恢复旧协议。

技术栈为 Python/FastAPI/uvicorn、Vue/Vite、ECharts、Three.js。依赖以 `backend/requirements.txt`、前端 package/锁文件为准。

|文件|职责|
|---|---|
|`backend/host_bridge.py`|固定 loopback HTTP 客户端、身份/命令检查、分页遥测转换与去重|
|`backend/fd2_telemetry.py`、`host/fd2_bridge.py`、`host/fd2_replay.py`|FD2 五版身份、coherent T 和独立 D 游标、一次性命令及原生日志 RX-only 回放|
|`host/fd2/upstream`|V5 包中的原样通用 Host 与 CPython 3.12；来源及逐文件哈希在 `host/fd2`|
|`backend/sp24_telemetry.py`、`host/sp24_bridge.py`|SP24原Host外层只读游标历史、精确帧时间/原点/有效性适配；不改控制|
|`backend/main.py`|Host 分页排空、FD2 120 秒历史（历史版30秒）、WebSocket、`/snapshot`、`/health`、`/config`、`/command`、`/requests/{id}`|
|`backend/config.json`|本机桥端口与预期固件版本，默认 8371 / auto|
|`host/gesture/host`、`host/adaptive/host`|用户交付的原样 Host、测试、指南、模板；来源与清单见 `host/README.md` 和 `MANIFEST_SHA256.json`|
|`host/sp24/gesture/host`、`host/sp24/presets`|SP24原样运行依赖、参数预设及来源哈希；launcher precise安装只读桥|
|`frontend/src/HostControlPanel.vue`、`hostPresentation.js`|摆控设置、PID/起摆/手势/SA21 配置、操作状态、样本缓存与 RMS|
|`frontend/src/App.vue`、`Fd2ControlPanel.vue`、`Fd2FeaturePanel.vue`、`fd2Presentation.js`|双场景、V1～V5 显式操作、手势/自适应/运动状态、120秒缓存与回放禁控|
|`DigitalTwin3D.vue`、`pendulumModel.js`、`pendulumLoad.js`、`pendulumCalibration.js`|用户 STEP 模型、按固件保存的显示标定/下垂对齐、显示插值及可切换挂载；原件见 `frontend/model-sources`|
|`WaveformPanel.vue`、`waveform.js`|按页分通道的真实波形，10 秒窗口，悬停 30 秒|
|`preciseWaveform.js`|SP24摆角/ref、旋臂局部角/目标、PWM；板端轴、缺帧断线、保峰抽点|
|`fd2Waveform.js`|FD2摆角/参考、累计旋臂/参考/独立最终目标、实际PWM；板时、120秒窗口、保峰抽点|
|`CarControlPanel.vue`、`CarControlPad.vue`、`useCarControl.js`、`carInput.js`|显式 BLE 连接、按住遥控、键盘与输入取消；不调用旧模拟源码|
|`backend/car_v83_service.py`、`car_api.py`、`car/v83/`|当前 RC83 原样依赖、单所有者线程、输入租约、会话/序号及独立 `/car` 接口；旧 `car_service.py` / `car/vendor` 仅作 HOLD_V2 历史回归|

## 工作方式

版本约定（用户于2026-10-16明确）：日常使用始终以用户最新交付为准。最新交付作为唯一日常启动和页面入口；历史版本仅在仓库中备份供追溯。2026-10-25 已将日常入口切换为 FD2 V1～V5。记录约定本身不代表授权自动提交或推送仓库。

2026-10-27 更新：`J280_V1_V2_V5_Complete_20261027.zip` 中 V1/V2 为起摆接平衡锚点/新帧修复，V5 为现有源码重新编译；三份 Host/runtime 均与现有 2250 项原样依赖同字节。来源及校验记录在 `host/fd2/releases/20261027/`；现场固定入口为父目录 `现场烧录固件/V*/J280_V*.fs`，仅 V1/V2/V5 已替换，旧五版在 `历史版本备份/20261027-before-v1-v2-v5-update/`。未进行烧录。完整 firmware/schema/wire 未变，不能仅凭身份自动宣称板上已运行修复位流。

自动烧录评估（2026-10-25）：用户选择 SRAM 临时下载，断电不保留；提供的本机 Programmer 目录为 `C:\Gowin\Gowin_V1.9.12.03_x64\Programmer\bin`，已只读确认存在 `programmer_cli.exe`。后续实现需支持不同电脑的路径发现/本机配置，不能写死该绝对路径。目前仅评估，尚未授权实施自动烧录或进行硬件下载。用户已明确要求先将现有版本同步到 GitHub，固定恢复标签见 `VERSIONING.md`。

界面基准（用户于2026-10-16确认）：当前 UI 设计已通过，见 `DESIGN.md` 第10节及 `docs/design/2026-10-16/` 的离线参考图。后续沿用石墨灰、银色模型、少量琥珀色操作、桌面模型向上和左右跨列绘制、手势区等线字体及统一字阶；不默认恢复文字黑色衬底、模糊阴影或堆叠小字说明。除用户进一步要求，不主动重排已通过的布局。

所有沟通、总结与说明使用中文。修改前查看 git 状态、相关实现、调用方与测试；保留用户未提交改动。优先最小范围修改，不做无关依赖升级、重构或参数调整。跨模块联调任务先给简短计划，不强制为每次修改创建分支、设计审批或提交。

原始交付源码作为配套依赖保存；未经明确授权不改变其中控制算法、UART/CRC、身份、ID/ACK/读回规则、参数默认值、安全限幅、抓零、起摆/交接/故障保护。修改 Host 时同步维护来源说明和哈希，不能伪装为原版。

## 通信与数据保护

- FD2 V1～V5 完整 firmware/schema/wire 身份见 `host/fd2/README.md`，三者共同核验。V3 自适应是角 P/D；V5 已移除自动起摆，网页不得恢复该动作。V4/V5 定位是旋臂相对定位，不是车辆位移。
- FD2 T 为200Hz完整控制事务，D为独立诊断；不得用状态快照或网络轮询替代原始批量采样。板时用于绘图，接收时刻用于链路龄；宽计数以十进制字符串保留。摆角为 `(ADC12-3085)*345/4096`，旋臂为 `count*360/1040`，PWM 为实际 Q15。累计角不等于机械零点。
- 2026-10-27 3D 修正：控制域角度可裁到85.071°，模型使用同一coherent T的有效 `quiet_q4/zero_q4` 有符号14位周期差乘 `6921/(16*2^20)*180/pi` 得到 `pendulum_pose_deg`，不覆盖 `angle_deg` 或波形。显式无效姿态保持上一姿态，不能按STOP猜下垂。FD2标定使用v3，异步身份/版本/会话切换正确隔离；历史三版仍v2。fault=1为角度保护，V5停止后仍检查该角度窗口；上位机不得取消该保护。
- FD2 状态、控制和诊断各自500ms失效；V3均值采用上游1秒/5秒时间加权统计并显示覆盖率。手势识别、全局最近动作原因、ACK、规划完成、跟踪到位分别展示，不相互推断。
- FD2 上游源码及运行时原字节保存；外层锁不跨原接收/命令回调，ACK匹配真实wire ID及opcode，会话切换后旧请求不补发。回放只读 `ForestFive.Physical.v1` ZIP 的RX，绝不启动设备线程或执行历史TX；始终标记离线、禁止摆控及小车硬件操作，结束冻结历史。
- 网页120秒环形缓存及绘图抽点不能替代原Host完整会话日志。USB为高频遥测，BT10为摆控命令/ACK，小车WH-BLE102是独立链路。
- 以下 SG21 / SA21 / SP24 专用规则适用于历史适配，不得套用到 FD2：
- SG21 身份对为 `53473231 / 53475421`，SA21 为 `53413231 / 53415421`，SP24 为 `53503234 / 53505424`；验证完整身份，普通写操作匹配预期版本。STOP 可发送给已识别的另一受支持 Host。
- COM 始终由对应 Host 管理；网页不自动连接串口、恢复参数、导入配置、起摆或切换自适应。不得擅自运行烧录、抓零、运动或参数命令来测试。
- 网页命令仅显式转发一次，保留 request_id；HTTP 200、accepted、ACK 不等于动作完成。超时为结果未知，不重发，使用查询恢复结果。
- PID 整组恢复是六个增益、积分使能、角度 D 滤波、角度窗口九项。实际写入顺序和独立读回由原 Host 引擎管理；不把网页草稿、历史参考值标记为实际读回。
- 遥测的有符号 Q20 弧度转角度、Q15 PWM 转百分比和 SA21 Q24 增益保持原含义。分页保留独立设备时间，不拼接成同步快照；同一页相同设备时间不产生新波形点。
- `received_at` / `observed_at` 是本机秒时间戳；图表 `now`、事件为毫秒；设备 `fpga_time_ms` 不能混用。波形 channels 指定所属通道，不能为别的页插入假数据或缺口。
- SG21／SA21 compact页未提供旋臂绝对角与硬件零点、位置目标/误差、参考角等旧字段，保持空值；SP24的目标/参考仅按精确帧真实有效性显示。3D旋臂姿态为示意，SP24局部原点同样不代表机械零点。显示标定不改写原始遥测或控制参数。
- SA21 配置须由原 Host 进行来源/可表示性筛选，不虚构 Ku/Tu 或误差尺度。导入保持自适应关闭，实际采用只在合格 BALANCE 后生效。
- 小车日常入口已更新为 2026-10-17 V8.3 的 WH-BLE102 / RC83，使用 `car/v83` 原字节 Session/Engine/BleTransport；旧 HOLD_V2 仅供历史回归，不注册网页版本选项。实机尚未验证；不生成假曲线、假在线、模拟运动、未知标定车速/位移或联合闭环完成标记。BLE 搜索、选择、连接、启用均由用户显式操作，不自动重连。遥控连接、车辆 CAR8 反馈与倒立摆链路分别判断；新鲜度沿用原协议1.2秒，网页更早收起过期读数；档位来自真实反馈。
- 场景及空载/有负载只影响模型显示，不检测实际负载、切 PID 或启用自适应。小车 STOP 与摆控 STOP 分别发送；按住输入、松开停车，失焦/隐藏/设置/切场景/进入回放取消遥控。200ms输入租约只由HTTP续租，断档锁存，不得由后台或晚中性输入掩盖；STOP 后旧 token/旧序号不能恢复动作。Shift急加速单次无重试，空格急刹与Esc普通STOP分开；F8/指针按住轨迹，完成后必须释放再按。复用 `car/v83` 原始协议，不擅自调整力度、停车、回中或保护逻辑，不自动烧录配套固件。
- SP24原Host保持原样；外层桥只读内存历史，游标缺口明确报告。100Hz样本按板端sample/capture分别绘制，宽整数到JS前为十进制字符串，局部原点不代表机械零点；原始30秒缓存不随抽点删除。250ms精确流stale不能被低速页刷新掩盖，停机新测量与PID有效目标/参考分别判断。
- SP24上滑起摆、左右相对定位/反向取消；起摆到实际BALANCE/HOLD接管完成前包括挥手的所有手势均忽略，独立STOP不受影响。page8事件、page9当前runtime和其独立到达时间分开；重连首份保留事件不是新手势。
- SP24定位参数及六项预设均显式STOP写；E工程候选仅影子资格，导入后保持关闭，不自动组合候选、标零、RUN或启用实际采用。SG21旧提示与SA21原profile守卫仍按各自版本执行。

## 启动与验证

使用摆控时先运行 `START_HOST.bat` 选择与板上实际固件相符的四个最新分支之一，在对应 Host 中明确连接 USB 或 BLE；再运行 `START_SHOWCASE.bat`。仅查看界面或小车遥控可不启动摆控 Host。离线预览与原日志回放命令见 `README_CN.md`，不得以实物连接验证替代离线检查。网页设置可修改本机桥端口/预期版本。FastAPI 为 `127.0.0.1:8000`，Vue 为 `localhost:5173`，CORS/WS/端口须对应；小车 BLE 在车载页另行显式搜索、选择、连接和启用。

修改后执行相关检查：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s backend
```

前端目录：

```powershell
node --test tests/*.test.js
npm run build
```

涉及界面、波形或 3D 时检查空态、断流、分页时间、姿态映射、操作状态和受影响交互，主画面按 1600×900、1920×1080、2560×1440 检查。验证只使用明确的离线 fixture 或 `--offline-preview` Host；不自动连接 COM/JTAG。离线测试、构建及内部时序通过均不能替代真实起摆、停止、方向、负重与温度/电压验收。完成时说明实际检查结果与未实机验证项。
