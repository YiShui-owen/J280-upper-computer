J280 Showcase V2.1 比赛展示补丁

目标：
- 1920×1080 单屏展示，无滚动
- 顶部中央高可见状态信标
- 左/中/右：被控量 / 3D 数字孪生 / 控制侧
- 底部：α 响应曲线 / 扰动恢复面板 / PWM 曲线
- 扰动事件自动标线、峰值偏角、恢复时间、恢复后 RMS
- 不修改 FastAPI、WebSocket、V5.12 tuner、通信协议或 FPGA 控制逻辑

覆盖方法：
1. 关闭当前 J280 Showcase Frontend 窗口（后端和 V5.12 tuner 可保持运行）。
2. 将本补丁 frontend\src 下三个文件覆盖到现有工程：
   D:\FPGA\上位机2\j280-showcase-upper-computer\frontend\src\
   - App.vue
   - DigitalTwin3D.vue
   - style.css
3. 不需要重新 npm install（前提是你当前 Three.js 版本已经正常运行）。
4. 在 frontend 目录执行：npm run dev
5. 浏览器刷新 http://localhost:5173
6. 比赛展示建议按 F11 全屏。

扰动恢复展示逻辑（仅前端统计，不改控制）：
- 点击 +12/-12 q2 后记录事件时刻
- 峰值偏角：事件后 |α| 的最大值
- 恢复判定：BALANCE 且 |α|<0.5°、|αdot|<5°/s 持续 0.35s
- 恢复时间：从扰动命令成功写入到满足恢复判据
- 恢复后 RMS：恢复之后最近 3s 的 α RMS

如果现场发现阈值过严/过松，可以只调整 App.vue 中 updateDisturbance() 的前端判据，不影响 FPGA。
