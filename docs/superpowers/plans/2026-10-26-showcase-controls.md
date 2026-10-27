# 比赛展示界面实施计划

**目标：** 按用户已确认的设计，扩大波形量程、突出新手势识别，并在 V5 主页面提供六位置与六轨迹操作。

**实现方式：** 使用现有 Vue、ECharts 和 FD2 数据；右侧复用 `Fd2ControlPanel.vue` 的发送、禁用条件和请求记录。前端显示与原始遥测、控制算法保持独立。直接在当前工作目录修改，保留已有 `backend/config.json` 改动，不提交或推送。

## 任务与验收

- [x] 波形：先在 `frontend/tests/fd2.test.js` 增加小波动量程、超范围扩展、旋臂目标完整显示、量程保持的测试，运行并确认失败；修改 `frontend/src/fd2Waveform.js` 和 `WaveformPanel.vue`。摆角默认 ±30°，提供 ±60°选择与重置；角度及旋臂量程只向外扩展，实时与历史窗口独立保存，固件/会话变化时重置。PWM 保持 ±100%。
- [x] 展示逻辑：先测试 `frontend/src/fd2Presentation.js` 中的新手势事件判定（首次/重连不闪亮、同手势新序号重新反馈）与运动动作名称映射；实现后运行测试。原始计数保留字符串。
- [x] 右侧：修改 `Fd2FeaturePanel.vue`，使用大图标、识别名称与短时强调；将通信统计收进详情。V4/V5 加入位置按钮，V5 加入轨迹切换和六轨迹按钮、取消并保持、抓零、独立参考完成/实际到位反馈。
- [x] 命令共用：`Fd2ControlPanel.vue` 暴露 `send/canSend/records/query`，请求保留动作参数和来源会话；`App.vue` 将其传给右侧。断流、回放和请求忙碌继续使用现有守卫，STOP 始终可独立发送。顶部显示 USB/BT10 状态。
- [x] 离线浏览器：在 `.workbench` 保存检查脚本，拦截所有 API/WebSocket 请求。检查三种桌面尺寸、空态/断流/回放、同手势重触发、V5 六位置/六轨迹参数、共享记录、请求中 STOP、拒绝/结果未知、无重试和无遮挡波形。
- [x] 验证：运行前端 `node --test tests/*.test.js`、`npm run build`，后端 `.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s backend`；检查截图和变更差异，完成代码审查。

只使用离线 fixture 检查；不连接串口或运行硬件命令。
