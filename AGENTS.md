# 项目协作规则

这是 J280 旋转倒立摆展示上位机，支持 2026-10-15 的 SG21 / SA21 / SP24 交付。链路为 `FPGA → UART → 配套 Host（唯一串口所有者）→ 本机 HTTP → FastAPI → WebSocket → Vue`。旧 V5.12 日志/mailbox 链路已替换，不按历史文档恢复旧协议。

技术栈为 Python/FastAPI/uvicorn、Vue/Vite、ECharts、Three.js。依赖以 `backend/requirements.txt`、前端 package/锁文件为准。

|文件|职责|
|---|---|
|`backend/host_bridge.py`|固定 loopback HTTP 客户端、身份/命令检查、分页遥测转换与去重|
|`backend/sp24_telemetry.py`、`host/sp24_bridge.py`|SP24原Host外层只读游标历史、精确帧时间/原点/有效性适配；不改控制|
|`backend/main.py`|Host 轮询、30 秒历史、WebSocket、`/snapshot`、`/health`、`/config`、`/command`、`/requests/{id}`、模板下载|
|`backend/config.json`|本机桥端口与预期固件版本，默认 8371 / auto|
|`host/gesture/host`、`host/adaptive/host`|用户交付的原样 Host、测试、指南、模板；来源与清单见 `host/README.md` 和 `MANIFEST_SHA256.json`|
|`host/sp24/gesture/host`、`host/sp24/presets`|SP24原样运行依赖、参数预设及来源哈希；launcher precise安装只读桥|
|`frontend/src/HostControlPanel.vue`、`hostPresentation.js`|摆控设置、PID/起摆/手势/SA21 配置、操作状态、样本缓存与 RMS|
|`frontend/src/App.vue`、`GesturePanel.vue`|无车实验台/车载遥控台、真实摆控数据、30 秒缓存、主页面手势|
|`DigitalTwin3D.vue`、`pendulumModel.js`、`pendulumLoad.js`、`pendulumCalibration.js`|用户 STEP 模型、按固件保存的显示标定/下垂对齐、显示插值及可切换挂载；原件见 `frontend/model-sources`|
|`WaveformPanel.vue`、`waveform.js`|按页分通道的真实波形，10 秒窗口，悬停 30 秒|
|`preciseWaveform.js`|SP24摆角/ref、旋臂局部角/目标、PWM；板端轴、缺帧断线、保峰抽点|
|`CarControlPanel.vue`、`CarControlPad.vue`、`useCarControl.js`、`carInput.js`|显式 BLE 连接、按住遥控、键盘与输入取消；不调用旧模拟源码|
|`backend/car_service.py`、`car_api.py`、`car/`|原样交付 BLE 依赖、独占线程、输入租约、会话/序号、独立 `/car` HTTP 接口|

## 工作方式

版本约定（用户于2026-10-16明确）：日常使用始终以用户最新交付为准。后续适配将最新交付作为唯一日常启动和页面入口；历史版本仅在仓库中备份供追溯，不再默认保留多版本并列选择。当前这次已完成的SG21／SA21／SP24并列实现按用户要求暂时保持，不因记录此约定立即清理或修改功能；下次版本适配时遵循本约定。记录约定本身不代表授权自动提交或推送仓库。

界面基准（用户于2026-10-16确认）：当前 UI 设计已通过，见 `DESIGN.md` 第10节及 `docs/design/2026-10-16/` 的离线参考图。后续沿用石墨灰、银色模型、少量琥珀色操作、桌面模型向上和左右跨列绘制、手势区等线字体及统一字阶；不默认恢复文字黑色衬底、模糊阴影或堆叠小字说明。除用户进一步要求，不主动重排已通过的布局。

所有沟通、总结与说明使用中文。修改前查看 git 状态、相关实现、调用方与测试；保留用户未提交改动。优先最小范围修改，不做无关依赖升级、重构或参数调整。跨模块联调任务先给简短计划，不强制为每次修改创建分支、设计审批或提交。

原始交付源码作为配套依赖保存；未经明确授权不改变其中控制算法、UART/CRC、身份、ID/ACK/读回规则、参数默认值、安全限幅、抓零、起摆/交接/故障保护。修改 Host 时同步维护来源说明和哈希，不能伪装为原版。

## 通信与数据保护

- SG21 身份对为 `53473231 / 53475421`，SA21 为 `53413231 / 53415421`，SP24 为 `53503234 / 53505424`；验证完整身份，普通写操作匹配预期版本。STOP 可发送给已识别的另一受支持 Host。
- COM 始终由对应 Host 管理；网页不自动连接串口、恢复参数、导入配置、起摆或切换自适应。不得擅自运行烧录、抓零、运动或参数命令来测试。
- 网页命令仅显式转发一次，保留 request_id；HTTP 200、accepted、ACK 不等于动作完成。超时为结果未知，不重发，使用查询恢复结果。
- PID 整组恢复是六个增益、积分使能、角度 D 滤波、角度窗口九项。实际写入顺序和独立读回由原 Host 引擎管理；不把网页草稿、历史参考值标记为实际读回。
- 遥测的有符号 Q20 弧度转角度、Q15 PWM 转百分比和 SA21 Q24 增益保持原含义。分页保留独立设备时间，不拼接成同步快照；同一页相同设备时间不产生新波形点。
- `received_at` / `observed_at` 是本机秒时间戳；图表 `now`、事件为毫秒；设备 `fpga_time_ms` 不能混用。波形 channels 指定所属通道，不能为别的页插入假数据或缺口。
- SG21／SA21 compact页未提供旋臂绝对角与硬件零点、位置目标/误差、参考角等旧字段，保持空值；SP24的目标/参考仅按精确帧真实有效性显示。3D旋臂姿态为示意，SP24局部原点同样不代表机械零点。显示标定不改写原始遥测或控制参数。
- SA21 配置须由原 Host 进行来源/可表示性筛选，不虚构 Ku/Tu 或误差尺度。导入保持自适应关闭，实际采用只在合格 BALANCE 后生效。
- 小车软件已接入用户交付 WH-BLE102 HOLD_V2 驱动，实机尚未验证；不生成假曲线、假在线、模拟运动、未知标定车速/位移或联合闭环完成标记。BLE 搜索、选择、连接、启用均由用户显式操作，不自动重连。遥控连接、车辆 CAR2 反馈与倒立摆链路分别判断，反馈过期收起读数。
- 场景及空载/有负载只影响模型显示，不检测实际负载、切 PID 或启用自适应。小车 STOP 与摆控 STOP 分别发送；按住输入、松开停车，失焦/隐藏/设置/切场景取消遥控。输入租约失效不得由后台续租；STOP 后旧 token/旧序号不能恢复动作。复用 `car/vendor` 原始协议，不擅自调整力度、停车、回中或保护逻辑。
- SP24原Host保持原样；外层桥只读内存历史，游标缺口明确报告。100Hz样本按板端sample/capture分别绘制，宽整数到JS前为十进制字符串，局部原点不代表机械零点；原始30秒缓存不随抽点删除。250ms精确流stale不能被低速页刷新掩盖，停机新测量与PID有效目标/参考分别判断。
- SP24上滑起摆、左右相对定位/反向取消；起摆到实际BALANCE/HOLD接管完成前包括挥手的所有手势均忽略，独立STOP不受影响。page8事件、page9当前runtime和其独立到达时间分开；重连首份保留事件不是新手势。
- SP24定位参数及六项预设均显式STOP写；E工程候选仅影子资格，导入后保持关闭，不自动组合候选、标零、RUN或启用实际采用。SG21旧提示与SA21原profile守卫仍按各自版本执行。

## 启动与验证

使用摆控时先运行 `START_HOST.bat` 选择已烧录版本，在 Host 中明确连接串口；再运行 `START_SHOWCASE.bat`。仅查看界面或小车遥控可不启动摆控 Host。网页设置可修改本机桥端口/预期版本。FastAPI 为 `127.0.0.1:8000`，Vue 为 `localhost:5173`，CORS/WS/端口须对应；小车 BLE 在车载页另行显式搜索、选择、连接和启用。

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
