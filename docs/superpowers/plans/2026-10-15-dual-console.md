# 两场景上位机实施计划

> 按 writing-plans 组织，在当前工作区执行。依照 AGENTS.md 保留已有未提交修改，不要求新分支、设计审批或提交。独立 BLE 任务使用 subagent-driven-development，完成后依照 requesting-code-review 审查。

目标：实现两场景布局、主页面手势与交付协议的实车 BLE 遥控接入。

架构：SG21/SA21 链路不变；新增独立 CarService 与 `/car` API；前端以共享模型和状态驱动两套布局。技术栈保持 FastAPI、Vue、Three.js、ECharts，BLE 复用交付 Python 驱动。

约束：不自动连接、不恢复参数、不自动启动动作；输入不得替代反馈；空载／有负载仅改变模型；不改交付控制逻辑、限幅、固件或配置；全部验证离线。

- [x] 1. 独立实车后端：新增 `backend/car_service.py`、`backend/car_api.py`、`backend/test_car_service.py`、`car/` 来源说明与原样依赖，在 `backend/main.py` 注册。先用假传输验证未连接初态、搜索选择、HOLD_V2 身份／停车证据、输入序号与过期停止，再实现后台线程。接口：GET `/car/status`；POST `/car/scan`、`/car/connect`（device_id）、`/car/intent`（session、sequence、direction、steering）、`/car/stop`（session）、`/car/disconnect`（session）。状态含 connected、identified、feedback_fresh、telemetry、received_at、session、phase、error。`python -m unittest discover -s backend` 应全部通过；不调用真实扫描。
- [x] 2. 前端输入：新增 `carInput.js` 与 `useCarControl.js`，先以 `createCarInput() 的冲突输入与 intent()` 验证冲突归零，以及 STOP 后按键未释放不恢复。实现每 70 ms 输入刷新、150 ms 状态观察、显式启用遥控；`CarControlPanel.vue` 接收 control，`CarControlPad.vue` 接收 enabled/held 并发出 press/release/stop。服务失败与浏览器生命周期释放输入。`node --test tests/carInput.test.js` 通过。
- [x] 3. 台架与主画面：`DigitalTwin3D.vue` 增加 `sceneMode`，仅切换历史固定支撑和现有 chassis 可见性，不重挂载 STEP。不根据转向指令或未标定计数动画。`App.vue` 两布局共用一份状态；无车手势主区、车载遥控主区；`style.css` 使用网格清楚分区，在三种指定分辨率中均不溢出。
- [x] 4. 手势与新鲜度：新增 `gesturePresentation.js`／`GesturePanel.vue`，先用 `accepted=true` 但 `mode=IDLE` 验证“请求接受”与“实际动作”分离；无读回不猜开关。通过 HostControlPanel expose `setGesture(value)`、`busy` 复用原请求机制。摆控指标按 angle_received_at／arm_received_at 分页判断，不呈现旧值。`node --test tests/*.test.js` 通过。
- [x] 5. 离线联调和说明：更新 README 与 AGENTS 已实现状态；构建并用浏览器 fixture 验证两场景、挂载不发命令、空态／断流、手势请求状态、按住／松开／失焦停止和三种分辨率，留下截图。最终独立审查实车接口与输入取消路径，修复重要发现并复核。记录测试通过数量与实车未验证边界。
验证记录：2026-10-15，后端 48 项、前端 40 项通过，Vite 构建通过（保留 Three.js/ECharts 现有大 bundle 提示）。两固件离线浏览器 fixture 覆盖 1600×900、1920×1080、2560×1440 与 390px 窄屏，两布局、负载、手势一次提交/实际读回、断流收起、独立车辆反馈、按住/松开/捕获外释放/失焦、刷新后显式接管、编辑框内 Space/Esc、停车后立即再次动作的新会话中性握手。浏览器无 pageerror。测试脚本与截图位于工作区外层 `.workbench/dual-console-browser/`。

独立审查发现并修复编辑框停车键优先级与新 token 中性握手窗口，复核后需求符合性与代码质量均通过，无待处理分级发现。两份 BLE 原始依赖与附件逐字节一致且 SHA-256 清单吻合。无 BLE 搜索、连接、COM/JTAG、运动或烧录操作；实物方向、停止距离、无线时延及带摆负载仍待人工验收。已有未提交改动保留，本次未提交或推送。
