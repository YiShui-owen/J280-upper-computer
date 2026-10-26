# SRAM 一键切换实施计划

> For agentic workers: 使用 subagent-driven-development；任务A、B、C按 dispatching-parallel-agents 在互不重叠文件并行，根任务负责后端编排及整合，完成后独立审查。不得提交/推送或访问真实硬件。

**Goal:** 在原展示界面提供V1～V5 SRAM下载、校验、Host切换与身份确认，支持本机路径配置。

**Architecture:** 官方CLI仅执行固定SRAM Program and Verify；原样Host通过外层排他交接控制串口；FastAPI后台任务管理状态和重连；Vue只在用户选择时提交一次。完整契约见同日设计文档。

**Tech Stack:** Python标准库/FastAPI、原Host/CPython3.12、Gowin Programmer CLI、Vue；不升级依赖。

## Global Constraints

仅SRAM操作4；不改上游字节；不调用硬件scan/download进行开发验证；不自动ZERO/RUN/调参；不因网络超时重发；完整状态身份核验前不成功；本机设置和日志不入库；已批准UI布局保持；基线标签不动。

### Task A：位流、工具适配与命令守卫

Files: firmware/**, backend/gowin_programmer.py, backend/test_gowin_programmer.py, .gitattributes。

- [x] 从指定归档导入五个最终bitstream，保存来源清单并核对原哈希；设置原字节属性。
- [x] 写失败测试覆盖路径发现/配置、未知版本、被篡改位流、明确缆线选择、多设备/错型号和命令只有操作4。
- [x] 实现设计接口，使用注入runner离线验证工具输出与超时，所有实际process无shell、隐藏控制台、有界日志、不重试。
- [x] 聚焦测试通过并自审边界。

### Task B：Host排他准备与自动重连入口

Files: host/fd2_automation.py, host/fd2_bridge.py, launch_host.py, backend/test_fd2_automation.py, backend/test_fd2_launcher.py。

- [x] 写失败测试：回放/缺USB拒绝、STOP只发一次、ACK与新鲜实际零输出均必需、准备时所有来源普通命令拒绝、STOP放行、重复ID、会话切换、所有者正确关闭。
- [x] 实现prepare/release/close及短锁顺序；请求线程不跨原接收/command持锁；关闭GUI通过主线程回调。
- [x] 实现仅显式 `--automation-connect` 的目标Host连接，保留USB+BLE及原日志，正常离线/headless行为不变。
- [x] 聚焦测试与便携运行时断连入口通过。

### Task C：固件切换界面

Files: frontend/src/FirmwarePanel.vue, frontend/src/firmwarePresentation.js, frontend/tests/firmware.test.js。

- [x] 写失败测试：默认空选择、只有用户选择触发、忙/回放禁用、未知结果查询不重发、一次隔离确认。
- [x] 实现设计的API契约和配置/任务状态，有限轮询、保留ID与日志、卸载清理。
- [x] node测试及build通过，报告App所需最小整合点，不改其他文件。

### Task D：后端编排与整合

Files: backend/firmware_service.py, backend/firmware_api.py, backend/test_firmware_service.py, backend/test_firmware_api.py, backend/main.py, backend/host_bridge.py, backend/car_api.py, frontend/src/App.vue, frontend/src/fd2Presentation.js, .gitignore。

- [x] 失败测试覆盖单任务/重复ID、重启未知、prepare之前不启动写、原Host释放、CLI失败不重试、重新连接真实身份、缺Host仅明确隔离允许、回放禁用、来源校验。
- [x] 实现本地配置、journal、有界日志及后台任务；下载中拦截普通摆控/小车命令与设置改动，排空旧轮询。
- [x] App集成面板和任务状态，下载即时禁控；不调整已批准主画面。
- [x] 独立审查实现与契约，解决发现后执行全套测试/构建、三尺寸离线UI/版本/失败/超时场景、原件哈希。
- [x] 更新README/AGENTS/验证记录和计划，报告真实完成项及实机未验收项。

## 完成记录

2026-10-25：软件任务已完成，后端193项、前端86项测试及构建通过；三尺寸离线UI和任务恢复检查通过。工具独立审查发现的两项解析问题已修复并增加回归，最终复核发现的旧状态重复帧问题也已修复并通过独立定点复审。真实CLI仅调用--help，未进行实机扫描/下载。完整结果与接板待验项见 `docs/sram-validation-20261025.md`。
