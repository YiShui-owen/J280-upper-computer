# J280 展示型上位机 V1.0

这是一版面向 FPGA 创新设计大赛现场展示的上位机，不替代原 V5.12 tuner，而是叠加在已经验证稳定的 tuner 之上。

## 为什么这样接

原 tuner 已经负责：
- COM 串口独占
- V5.12 遥测接收
- HOME-M29 自动起摆
- 安全停止
- mailbox 远程命令

展示上位机因此不直接抢 COM 口，而是：

`FPGA -> UART -> V5.12 tuner -> log/mailbox -> FastAPI -> WebSocket -> Vue/ECharts`

这样既保留稳定的工程链路，又能把比赛现场 UI 做得更漂亮。

## 第一次使用

1. 先按原流程运行 `START_HERE.bat`，完成烧录、抓零，并让 V5.12 tuner 保持运行。
2. 双击 `INSTALL_ONCE.bat`，只需要运行一次。
3. 检查 `backend/config.json` 中的路径：

```json
"tuner_project_dir": "D:\\FPGA\\实验\\J280_V512_1MS10MS_PID_HANDOFF_20260924\\project"
```

如果你的交接包位置不同，只改这一项。
4. 双击 `START_SHOWCASE.bat`。
5. 浏览器自动打开 `http://localhost:5173`。

## 比赛展示界面

建议在 1920×1080 分辨率下按 F11 全屏，也支持 1600×900 和 2560×1440。

- 左侧约 64% 为机械舞台，保留旋转、缩放、平移、重置视角，以及自动启动 / 停止。
- 右侧集中显示摆杆偏角、摆杆角速度、旋臂角度、PWM 和近 3 秒角度 RMS。
- 三通道波形默认共用最近 10 秒窗口；鼠标停在波形区时扩展为最近 30 秒并继续实时滚动，移开恢复 10 秒。底部秒数表示距当前的时间，悬停提示显示本机时刻及毫秒。
- 前端缓存最近 30 秒收到的遥测；尚未实现历史回放。无数据时不生成演示曲线。
- PID 参数在「工程设置」中下发；姿态标定也从这里打开。原有 ±12 q2 扰动按钮收在「调试工具」折叠项中，执行成功后在波形中标记一次事件。

场景组件 `frontend/src/DigitalTwin3D.vue` 与页面布局独立；替换机械模型不需要重写测控区域。波形组件为 `WaveformPanel.vue`，纯数据与图表配置位于 `waveform.js`。后端接口、端口和命令流程保持原样。

前端验证（在 `frontend` 目录）：

```sh
node --test tests/waveform.test.js
npm run build
```

## 安全

网页里的 START 会写入原 tuner mailbox，由原 tuner 执行 HOME-M29，而不是绕过原安全流程。
现场演示仍必须保持旋臂运动范围内无人、无线材和杂物。
