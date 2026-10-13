# 项目协作规则

## 架构与文件定位

这是 J280 FPGA 旋转倒立摆的展示型上位机。数据链路为 `FPGA → UART → 外部 V5.12 tuner → 日志 → FastAPI → WebSocket → Vue`；命令反向经 FastAPI 写入 tuner 的 mailbox。COM 口由 tuner 独占，本仓库不包含 FPGA 控制逻辑或 tuner 主程序。

技术栈：后端 Python、FastAPI、uvicorn；前端 Vue 3、Vite、JavaScript ES 模块、ECharts、Three.js。依赖以 `backend/requirements.txt`、`frontend/package.json` 和锁文件为准。

| 文件 | 职责 |
| --- | --- |
| `backend/main.py` | 解析十六进制遥测、跟读最新日志；提供 `/health`、`/snapshot`、`/ws`、`/command`、`/config` |
| `backend/config.json` | `tuner_project_dir`、`log_glob`、`mailbox_name` 定位外部工程、日志与命令文件 |
| `frontend/src/App.vue` | 比赛展示布局、小车待接入空态、真实摆控状态、30 秒缓存、近 3 秒 RMS、WebSocket 重连与原 START/STOP/PID 命令；工程操作在演示设置中 |
| `frontend/src/CarControlPanel.vue`、`CarControlPad.vue` | 设置中的小车连接 UI 与主画面方向按钮；等待实车，控件尚未启用 |
| `frontend/src/DigitalTwin3D.vue` | 一体化车载 Three.js 模型、轮转示意、相机交互、原姿态映射、显示插值及浏览器本地标定 |
| `frontend/src/pendulumModel.js`、`assets/models/`、`model-sources/` | 用户 STEP 摆杆及网页 GLB 资产、等比显示适配；转换方法见 `frontend/model-sources/README.md` |
| `frontend/src/WaveformPanel.vue`、`waveform.js` | ECharts 实例与横向/堆叠三通道波形；默认 10 秒，悬停 30 秒并继续滚动 |
| `frontend/src/carSimulation.js`、`useCarPresentation.js` | 旧版离线底盘模拟源码，当前页面不调用 |
| `frontend/src/style.css` | 页面布局与响应式样式；`main.js`、`index.html` 为入口 |
| `frontend/tests/waveform.test.js` | Node 内置测试，覆盖数据、时间轴、空值、事件与 ECharts 更新 |

使用说明见 `README_CN.md`，版本管理见 `VERSIONING.md`。`frontend/README_覆盖说明.txt` 和 `docs/superpowers/plans/` 含历史方案；与当前源码不一致时以源码为准，不按旧覆盖说明替换现有文件。当前先设计小车 UI，等拿到实物再继续功能接入；不启用模拟动作，不将实车控制、定位或联合闭环写成已实现功能。

## 启动与配置

- 实机运行前，先按外部 tuner 工程的 `START_HERE.bat` 流程完成烧录、抓零并保持 tuner 运行；该脚本不在本仓库。核对 `backend/config.json` 的路径、日志匹配规则及 mailbox 文件名。
- 首次安装使用根目录 `INSTALL_ONCE.bat`；日常启动使用 `START_SHOWCASE.bat`。后端为 `http://127.0.0.1:8000`，页面为 `http://localhost:5173`。
- 手动启动：在 `backend` 执行 `python -m uvicorn main:app --host 127.0.0.1 --port 8000`；另在 `frontend` 执行 `npm run dev`。页面 API/WS 地址、Vite 端口与后端 CORS 配置须保持对应。

## 修改方式

- 修改前阅读相关实现、调用方、配置与测试，查看 `git status` 和有关差异；保留用户已有未提交改动。
- 优先最小范围修改，不做无关重构、依赖升级或顺带调整硬件参数。
- 简单任务直接执行；跨模块或影响软硬件联调的复杂任务先给简短计划。按任务需要安排检查，不强制每次改动都经历设计文档、分支或多轮审批。

## 通信、控制与展示保护

- 未经用户明确确认，不修改 UART/遥测协议、字段含义、符号位与定点换算、命令格式和顺序、控制算法、安全限制或硬件相关参数；包括 PID 默认值、PWM/REF 限制、抓零、HOME-M29 起摆、STOP 与故障处理。已有明确授权无需重复确认。
- 保留 tuner 对 COM 口及启动/停止流程的管理，展示层不得擅自直接打开串口或绕过 tuner。`/command` 返回成功仅证明 mailbox 写入成功，参数生效与动作完成须通过遥测或实机确认。
- 保护现有 PID 下发链路：界面逐项发送 `AKP`、`AKD`、`PKP`、`PKD`；后端还接受 `PKI`、`PWM`、`REF` 等前缀。不得在界面调整中擅自增删命令、改变默认值或下发顺序。
- 遥测保持现有 Q20 弧度转角度、Q15 转百分比及有符号解析；`received_at` 为本机秒时间戳，图表的 `now`、事件时间为毫秒，`fpga_time_ms` 为设备时间，不得混用。
- 读数和波形使用真实遥测，无数据保持空态，无效值保留缺口；不得生成假曲线、假在线状态或把已写入命令标为实机完成。3D 标定与平滑仅用于显示，不能改写原始遥测、波形或控制参数。

## 检查与验证边界

修改后执行与影响范围相符且能实际运行的检查，并记录结果。前端数据、波形或组件变更使用已有命令（在 `frontend`）：

```powershell
node --test tests/waveform.test.js tests/carSimulation.test.js tests/pendulumModel.test.js
npm run build
```

当前未配置后端自动测试套件。后端修改至少检查 Python 语法、JSON 配置，并按影响范围验证遥测解析或接口；只做文档修改可使用不写缓存的语法检查（在项目根目录）：

```powershell
python -c "import ast; from pathlib import Path; ast.parse(Path('backend/main.py').read_text(encoding='utf-8'))"
```

涉及界面或 3D 的修改，检查空态、断流、时间窗口、姿态映射和受影响交互；布局按现有 1600×900、1920×1080、2560×1440 目标核对。检查不得擅自向实机发送运动、扰动或参数命令，也不得自动烧录、抓零。无法验证的串口、参数生效、起摆、平衡与停止功能，明确列为“未实机验证”，离线测试和构建通过不能代替联调验收。

## 沟通与交付

所有沟通、改动总结和操作说明使用中文，保留代码标识符与协议命令原文。完成时说明改了什么、检查结果及未验证项；检查受环境限制或发现范围外问题时如实说明，不擅自扩大修改范围。
