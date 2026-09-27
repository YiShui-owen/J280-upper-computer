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

## 展示版主要内容

- 姿态数字孪生动画
- 摆杆实时偏角 / 角速度
- 旋臂角度 / 角速度
- PWM 输出
- 近 3 s 角度 RMS
- 1 ms / 10 ms 双环控制架构
- 实时响应曲线
- 标准 ±12 q2 扰动按钮
- 自动启动 / 停止按钮
- 工程 PID 设置默认折叠，不干扰比赛展示

## 安全

网页里的 START 会写入原 tuner mailbox，由原 tuner 执行 HOME-M29，而不是绕过原安全流程。
现场演示仍必须保持旋臂运动范围内无人、无线材和杂物。
