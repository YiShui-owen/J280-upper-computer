# ENC 旋臂显示跟随优化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 减少 FD2/ADB1 水平旋臂在运动时的显示落后和停顿。

**Architecture:** FD2/ADB1 后端轮询按包含本轮处理耗时的目标30Hz调度，保持逐批完整读取T/D数据。前端旋臂直接接受有效的新编码器位置，不再用独立D诊断速度拒收该位置，继续使用短路径显示插值；摆杆与历史协议的异常筛选保持原逻辑。

**Tech Stack:** Python asyncio/FastAPI、Vue、Three.js、unittest、Node test、隔离浏览器离线fixture。

## 约束

- 只改上位机显示链路，不改原始Host、FPGA控制、抓零、保护、协议、传感器死区算法。
- 保留500ms有效性、完整200Hz样本历史、游标去重、回放与会话隔离。
- 不外推或补造姿态；保留默认20ms显示平滑、默认±60°、当前布局及默认位置。
- 保留所有已有未提交改动；不提交/推送，不连接COM/BLE/JTAG。

## Task 1: 后端刷新周期

**Files:** `backend/main.py`、`backend/test_fd2_hub.py`。

- [x] 先用虚拟单调时钟运行真正Hub.loop，验证新周期、处理耗时抵扣、超期不堆积；观察旧实现失败。
- [x] FD2/ADB1采用目标33.33ms一轮；历史协议继续每轮后等待120ms，Host不可用继续等待500ms。
- [x] 回归完整游标排空、重复数据和损坏分页恢复；验证500ms失效和日志回放未改变。

## Task 2: 前端旋臂跟随

**Files:** `frontend/src/DigitalTwin3D.vue`、`frontend/tests/digitalTwin.test.js`。

- [x] 先用真实SFC watch测试复现连续6°/33ms运动被旧零速/反向D诊断速度长期挡住，观察旧实现失败。
- [x] FD2/ADB1旋臂沿用finite/new tick/session检查，跳过依赖D速度的拒收；历史协议和摆杆筛选不变。
- [x] 验证重复tick、空/非法位置、版本会话切换与±180°插值；不添加预测或速度积分。

## Task 3: 联调与交付

- [x] 在真实桥HTTP→Hub链路用合成200Hz源测试轮询频率、样本保留和停流。
- [x] 在隔离浏览器中以30Hz新姿态、滞后的D速度验证旋臂连续跟随与停止，并记录测量值；离线测试不能代表实机端到端延迟。
- [x] 运行后端与前端全套测试、前端构建、独立代码审查和差异检查。
- [x] 更新使用说明和验证记录，说明需要重启网页后端生效，未处理摆杆死区。

## 结果

后端155项、前端104项及构建通过，独立审查通过。只读HTTP实测20.81Hz轮询，600样本全部保留，无丢重；约522ms停流失效。浏览器旧D速度下目标误差为0，停止及断流保持正确，原布局与默认位置复验通过。完整测量、限制与生效步骤见 `docs/enc-follow-validation-20261101.md`。
