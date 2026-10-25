# FD2 五版本实现计划

> For agentic workers: 使用 subagent-driven-development；独立 Host 与前端任务按 dispatching-parallel-agents 并行，主任务负责后端与整合，分别审查后统一验证。用户已授权实施，不增加中途审批。

**Goal:** 将 V1～V5 新交付接入现有双场景展示上位机，提供真实完整波形、版本专属信息及明确的离线回放。

**Architecture:** 原样 Host 负责硬件与日志，外层桥向 FastAPI 提供状态、游标帧及一次性命令；Vue 复用现有布局/模型。具体字段以同日设计文档“共同契约”为准。

**Tech Stack:** Python/Tk、stdlib HTTP、FastAPI、Vue、ECharts、Three.js；不升级依赖。

## Global Constraints

遵守设计中的全部硬件/数据语义；不连接 COM/BLE/JTAG、不运行电机、不改上游控制代码；本地原工作区实施，保留历史依赖，不提交推送。代码任务先写失败测试，再实现；文件导入与文档仅核对内容/哈希。

### Task 1：Host 原样依赖、桥接与回放

Files: host/fd2/**, host/fd2_bridge.py, host/fd2_replay.py, launch_host.py, START_HOST.bat, backend/test_fd2_bridge.py, backend/test_fd2_launcher.py。

- [x] 从 V5 ZIP 导入 host/runtime 原字节，记录来源、大小和 SHA256；附五版身份能力表。
- [x] 写失败测试：五版启动参数；独立帧游标连续批次；旧会话不能恢复控制；重复 request_id 不重发；V5 拒绝起摆；回放不连接硬件。
- [x] 实现设计 HTTP 契约及上游外层接收捕获。使用原 command(source='WEB/'+id)，跟踪上游真实 write_requested/ACK 事件，保留请求结果未知。
- [x] 实现原日志 ZIP 的 RX-only 回放，读取 session.json 检查格式和版本，验证原 chunk CRC，不解释 TX 为命令。
- [x] 用 unittest 和五版 --help、断连启动核验；报告接口和实际测试结果。

### Task 2：后端 FD2 遥测转换和公共接入

Files: backend/fd2_telemetry.py, backend/host_bridge.py, backend/main.py, backend/test_fd2_telemetry.py, backend/test_main.py。

接口：FD2TelemetryAdapter.observe(snapshot, now, waveform) -> (data, rows, reset)，现有 HostClient 协议不变。

- [x] 写失败测试断言：
```python
self.assertEqual(identify(status_v5), 'V5')
self.assertEqual(len(rows_from_200_frames), 200)
self.assertEqual(rows[-1]['raw']['wide_encoder'], str(2**60))
self.assertFalse(data_after_stale['display_fresh'])
self.assertIsNone(data_after_stale['angle_deg'])
```
- [x] 按 wire_version/firmware/schema 验证身份；按新协议单位转换；板时映射独立于 HTTP 轮询，重复游标不产生新样本，重置和缺口明确处理。
- [x] 保留独立 D 诊断时序和失效时间；自适应采用上游实际均值；处理 session 变化、状态与控制分别过期。
- [x] 对新的动作严格检查版本/新鲜度/回放状态，原 Host 执行一次；保留旧适配用于历史测试。
- [x] Hub 接入五版分页，缓存 120 秒以上、每次数据捕获不丢点，测试后端全套。

### Task 3：版本展示与轨迹波形

Files: frontend/src/Fd2ControlPanel.vue, Fd2FeaturePanel.vue, fd2Presentation.js, fd2Waveform.js, App.vue, WaveformPanel.vue, hostPresentation.js, gesturePresentation.js, frontend/tests/fd2*.test.js。

- [x] 以固定契约写失败测试：V5 无起摆、V3均值覆盖、手势识别不冒充接受、诊断目标独立时间、120秒缓存、断流不连线。
- [x] 更新日常 V1～V5 设置和显式动作；保持主画面布局与独立小车遥控，回放显式标记且禁用命令。
- [x] 按真实三通道画摆角/参考、累计旋臂/参考/最终目标、PWM；提供至少120秒历史查看及导出，V3显示实际增益变化。
- [x] 模型采用新摆角与可用旋臂计数；按固件隔离显示标定，所有无效数据为空。
- [x] node --test tests/*.test.js 与 npm run build，通过后报告。

### Task 4：整合与审查

- [x] 逐项审查两个任务与后端契约，补充端到端离线 HTTP/回放测试。
- [x] 使用明确离线样本检查1600×900、1920×1080、2560×1440；检查空态、断流、回放和五版操作可见性。
- [x] 更新 README、AGENTS、来源清单与联调清单。
- [x] 统一运行后台和前端检查，审查差异后报告实际完成内容及尚未实机验证项。

## 完成记录

2026-10-25：四项任务完成。后端114项、前端72项测试通过，构建成功；五版便携运行时断连启动及2250项源文件哈希通过。离线UI三尺寸15张主图与空态/断流/回放/STOP交互已检查。详情见 `docs/fd2-validation-20261025.md`。未进行实机连接、运动、烧录或Git提交。
