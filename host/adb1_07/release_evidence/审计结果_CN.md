# 指令拦截、等待和资格条件审计（2026-10-31）

本轮实机卡住的直接原因已确认：新增的 `transfer_ready` 把实际位置误差≤20计数、100ms速度观测绝对值≤40，当成下一条动作的前提。实际停转后位置长期偏58～82计数，这个条件一直不成立，待执行任务又占住唯一队列，后续动作继续报忙。此条件没有失败退出，是错误的调度门槛，不是用户要求。不能因为代码综合通过就认定实机动作通过。

板子已收到明确STOP ACK；停机后mode=1、fault=0、实际输出=0。原测试窗口已关闭，串口已释放。本次审计与修复未重新烧录。

## 实测参照，不能用“达标”掩盖偏差

数据来自刚才试验的两个完整原始会话，快照和哈希见 `field_trial_20261031/SNAPSHOTS.json`。位置单位是旋臂控制计数，1040计数/圈，不是摆杆角度ADC计数。

| 区间 | 时长 | 位置误差范围 | 绝对误差95分位 | 说明 |
|---|---:|---:|---:|---|
| 运动前普通平衡 | 11.265秒，2251帧 | −16～+11 | 12 | 这一段的观察值，不冒充长期标准 |
| 顺时针结束后前5秒 | 5秒，1001帧 | −40～+31 | 37 | 运动后明显没有恢复到前段普通平衡波动带 |
| 后一次停止后 | 32.52秒，6503帧 | +58～+82 | 80 | 全段没有满足新增20计数门槛 |

同一普通平衡段，摆角相对控制零点的范围是−26～+34 ADC12计数，绝对值95分位18计数；按现有上位机345°/4096标度约为−2.19°～+2.86°，绝对值95分位1.52°。旋臂位置−16～+11计数按1040计数/圈约为−5.54°～+3.81°。这是两个不同轴，不能把旋臂位置计数直接当成摆杆角度。

普通平衡段只有60.1%的采样落在±5计数内；20计数和40计数/秒组合的瞬时通过比例约85.8%。所以“±5、速度≤10持续500ms”的旧严格标志不能直接当作本机普通平衡的达标标准，更不能作为指令放行条件。保持原始数值和严格标志的含义，不把放宽评价写成控制性能改善。

顺时针那圈最终目标5500，实际最大5533，真实超调33计数，约11.42°；参考位置本身没有超过5500。这说明之前只保证参考不越界还不够，真实机械超调仍是未关闭的问题。不能写成已无超调或已收敛。

这轮记录没有标记相同扰动下的普通平衡恢复起止时刻，不能捏造一个普通平衡恢复时间。能确认的是：停止后32.52秒仍未回到运动前的波动带，表现明显更差。后续时间评价用“实际重新进入同一平衡波动带所需时间”，与“参考刹停时间”分开。 按用户本轮要求，目标是在实际不过冲的前提下，回稳速度接近原普通平衡的恢复能力，尽量不更慢；位置与摆角同时核对。不能用一条普通平衡本身难以持续达到的门槛，卡住后续指令，也不能只缩短参考曲线就宣称实际恢复更快。当前没有同等扰动下的恢复时间证据，因此尚不能报告“已经不更慢”。

## 当前和历史条件逐项核对

“原有”只说明来源，不代表条件必然正确。对照了25号原始V1/V2/V3、29号快P/ADC/自适应分支、ADB1基线和本轮改动。历史条件检索按内容哈希去重，初始索引包含79种模块实现；它是静态证据，不等于79种实机验收。索引见 `HISTORICAL_CONDITIONS_INDEX.json`，补充的原版运动/多起摆/回位模块见源定位清单。

| 项目 | 来源和当前作用 | 是否可能长期不执行 / 退出方式 | 本轮处理 |
|---|---|---|---|
| 实际误差≤20、速度≤40才接下一项 | 本轮新增，当前卡死直接原因 | 可能永久等待，没有失败退出 | 修复分支已删除对指令调度的依赖 |
| 一个待执行任务占满后继续报忙 | 本轮新增，和上项连锁 | 前项不放行，后续请求一直拒绝 | 间隔到期的新请求可替换旧的待执行意图；不累积影子动作 |
| 待执行任务真正派发时再开1秒保护 | 本轮加入的计时语义 | 内部接续会再加一次等待 | 改为每次接受指令只计一次；内部派发不重启 |
| 约1秒的新指令间隔 | 用户明确要求 | 有界；默认1000ms，可设0/200/300/500/750/1000/1500/2000；拒绝的重复动作不续期 | 保留；光学层在生成运动事件之前屏蔽，STOP例外 |
| 参考单圈尚未完成时保存下一项 | 本轮为“一次左滑不丢失”增加 | 等当前有限参考结束，不再等实际到位；默认单圈参考3.835秒 | 保留完整一圈语义，公开其等待的是动作本身而非质量门槛；新意图可替换 |
| 待执行派发跳过起点大误差检查 | 本轮队列路径的另一处不一致 | 可能先答应任务，后续直接带很大误差启动 | 统一原有200计数检查；失败立即报原因12并清空任务，不无限等待 |
| 受控制动按钮恰在结束边界无法清队列 | 本轮队列与旧重复命令拒绝规则相互作用 | 有待执行动作时，制动可能被当成重复，之后旧任务又启动 | 已修：此时受控制动优先清空待执行意图；增加边界回归 |
| 制动速度比例逼近0的长尾 | ADB1通用规划器已有的算法 | 非无限等待，但这轮参考刹停实测2730ms | 修复分支改为同样加速度/跃度上限内的有限精确刹停；520速度仿真参考刹停535ms，不冒充实机到位时间 |
| 严格到位±5、速度≤10持续500ms | ADB1原有结果指标 | 可以一直为false；15秒只是报告超时，并未让标志变true | 保留其原始评价含义，不再用于下一条正常指令的准入 |
| 新任务起点误差超过200计数 | ADB1原有软准入限制 | 会明确拒绝，原因12；反复尝试也可能一直拒绝，不是自动等待 | 公开数值与来源；不冒充已删除。未擅自取消大误差保护 |
| 连续转动中直接请求单圈 / 同向重复 | 25号原始V2及ADB1已有状态规则 | 单圈在连续转状态会报忙；同向重复不重启；反向滑动是制动停止 | 原有语义仍存在，明确列出。当前修复没有擅自把反向滑动改成反向连续转 |
| 快P切换两套输出差必须≤138 | 29号旧快P比较模块的 `handoff` | **没有超时**，可能请求已记录而active_fast始终不变 | 已确认旧版问题；当前ADB1未包含该模块。本轮没有重新发布那个旧版的修复位流 |
| 快P准备完成且I必须为0 | 同一旧快P比较模块 | 准备通常有界；I非零会一直使用原路径 | 列为明确资格条件；不能只显示请求模式而不显示实际模式 |
| V5轨迹开始前实际误差≤5、速度≤10保持500ms | 通用规划器WAVE_CAPTURE分支 | **没有退出超时**，可能一直等不到轨迹起步 | 已确认同类风险；当前ADB1使用VARIANT2，V5分支未启用，不将其写成已修或已实机验证 |
| RUN后等摆杆进入准入角度 | 原始安全状态机ARMED | 可以等到人手扶直，或STOP；属于明确人机等待 | 保留。应显示“已RUN，等待扶直摆杆”，不能显示成莫名不动作 |
| 两次中性光学样本重新识别 | 原始手势译码器 | 手一直不释放可能不生成第二次事件 | 保留去重；保护期内被屏蔽的手势不会在到期后补触发。下滑STOP独立优先，不能被普通重新使能挡住 |
| 手势传感器出错后重试 | 原始I2C reader | 单次事务10ms超时，间隔500ms重试；硬件持续异常会一直not-ready | 有错误计数，但正常串口不代表手势正常；应明确显示手势未就绪，按钮与手势路径分开说明 |
| 心跳回复覆盖动作拒绝文字 | 之前上位机实现 | 动作错误很快被“0x01已接受”盖住 | 已修；18项上位机离线测试包含“拒绝经过多次心跳/读回仍保留” |
| 500ms无有效帧后锁定控制 | 之前上位机连接守卫 | 即使帧恢复也需要明确重连；不是自动解锁 | 保留通信状态不明时不重放动作的规则，并明确退出方式。本轮卡住时fresh/authenticated为true，未触发此条件 |
| 固件/协议/能力不匹配 | 上位机身份守卫 | 可以持续拒绝，需匹配固件和上位机后重连 | 保留；记录镜像哈希，不能仅看相同UserCode判断是同一程序 |
| 命令ACK超过500ms未返回 | 上位机事务处理 | 记录结果未知，不自动重放动作；不会凭空认定成功 | 保留；未知结果必须显示。与机械到位无关 |
| 日志写入失败后单次STOP并断连 | 之前上位机加入的运行规则 | 会真的影响运行；最多250ms等待STOP结果，随后断连 | 明确列出，不能只说“只是记录”。本轮原始日志完整、记录器无错误，不是本次卡死原因 |
| 自适应非零I/增益资格/饱和/噪声/幅度限制 | 25号V3及后续自适应模块 | 可以长期冻结学习；普通PID继续控制，不应锁运动命令 | 逐条保留原因码。I非零、角误差≥256、位置误差≥300、请求幅度≥6000/实际幅度≥30000、8次差分内≥5次反转均可能限制学习；是否过严需真实数据评价 |
| 自适应参考过渡时冻结、连续历史预热 | 29号整合的adaptive_features | 每次参考速度/加速度改变会重置，需连续稳定事务；变化一直持续则一直冻结 | 只影响自适应证据，不是动作准入。不能将“已开启”当成“实际正在调参” |
| 自适应观察窗与试探冷却 | V3算法 | 64个5ms样本是一窗320ms；预热2窗、冷却4窗，且仅有效证据推进 | 公开实际时间；守卫反复重置时可能学不到，不据此报“自适应已经有效” |
| SWM4起摆静止下垂确认 | 原起摆模块 | 典型确认60ms，等待上限3000ms，不满足进入失败原因10 | 保留有界失败，不是本轮无限运动等待；失败需明确显示，而非只一个数字 |
| 起摆其他等待和接管 | 原SWM4/其他起摆策略 | SWM4有各阶段时限/失败码；其他策略也可能有等过顶、下垂、回落等条件 | 未因为其不在本轮运动流程就判“肯定没问题”。原始三起摆与整合版分支已列入检索；不擅自改已封存起摆参数 |
| ADC采样资格/缓存 | 之前ADC对照与64点版本 | 安静缓存有30µs年龄上限并有原始通道回退；失配触发采集故障，不是等待位置收敛 | 当前ADC、采样器源码和时序未改；不再靠给ADC/PID另加滤波来处理调度卡死 |
| 编码器/角度/过速/算术故障、急停 | 原始驱动安全链 | 故障可锁存，需停止后按明确条件恢复；持续硬件异常可能再次触发 | 保留。与“运动指标没达标就不许发下一条”区分，不把故障保护偷偷叫成普通到位判断 |
| PWM换向空白与限幅 | 原始电机驱动 | 非零换向有100µs空白，输出有限幅；有界 | 不是数秒等待来源。真实驱动输出与请求值分开记录 |
| 停止后再RUN的坐标目标 | 原系统motion_session与普通平衡坐标切换 | 源码存在回到普通校零坐标的路径，可能解释重新启动时目标变化；不是本轮已证实卡死的原因 | 列为待进一步验证的既有行为，不把未经实机验证的疑点说成已经修复，不自动RUN验证 |

## 已执行的修复和验证边界

修复代码位于 `audit_flow_fix`，与已烧录/封存文件分开。位置/速度的实际质量不再决定已完成参考后能否接新指令；待执行任务可替换，取消优先，内部派发不重新计时；超出原有200计数起点范围会明确失败并清队。纯板侧计算保留，未增加电脑控制计算。

受控制动使用原来的加速度1966与跃度98（Q16/5ms单位）上限，去掉原指数尾部；267个制动状态剖面验证有限结束、不反转和原有上限，计算最慢223个FPGA时钟。内部算术异常有512时钟明确失败出口，不能无限卡在计算等待。535ms是520计数/秒参考速度的仿真刹停时间，未证明真实电机能在此时刻到位。

另做了实际驱动数值的同拍等价改写来缩短实现时序链：先计算各分支的有符号诊断数值，再选择分支。2,097,152项穷举证明选中输入的19个有效位和全部选择分支值一致，没有增加寄存器级；没有改驱动、ADC、PID参数或采样周期。

已通过的离线检查包括：运动/调度回归52,851项、有限参考64,677项、坐标6495项、光学保护231项、制动95,066项；上位机18项及隐藏离线窗口检查。全系统UART/ADC/编码器和下滑STOP回归另有绑定源码的报告。完整50MHz原生实现R09已通过：Fmax 50.210MHz，setup +0.084ns，hold +0.211ns，所有适用时序检查0违例、未布通0。位流SHA256：41b9192fed5b4e887e458e1a69689ad7a660964ca8cf1ccacd6c4e31f7b4bf45。此结论只确认实现与离线回归，不代表机械超调已经消除。

旧快P切换、旧V5实际到位等待尚未重新发布修复镜像；单圈真实33计数超调、停后约70计数偏置也仍未在实机关闭。本报告不将这些问题删掉或写成通过。

## 可核对的源码位置

- motion_admission: [forest_motion_planner.v:210](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_motion_planner.v:210>)
- queue: [forest_motion_planner.v:234](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_motion_planner.v:234>)
- original200: [forest_motion_planner.v:213](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_motion_planner.v:213>)
- strict_result: [forest_motion_planner.v:179](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_motion_planner.v:179>)
- legacy_v5_wait: [forest_motion_planner.v:407](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_motion_planner.v:407>)
- old_fastp: [forest_d1_p_compare.v:57](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adc64_fastp_compare_20261029/project/src/forest_d1_p_compare.v:57>)
- old_v2_motion: [forest_d1_motion_target.v:166](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/fd2_log_analysis_sources/V2/forest_d1_motion_target.v:166>)
- host_reject_display: [client.py:192](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/host/client.py:192>)
- communication_latch: [client.py:331](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/host/client.py:331>)
- logging_stop: [client.py:265](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/host/client.py:265>)
- arming: [forest_d1_safety.v:154](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_d1_safety.v:154>)
- adaptive_eligibility: [forest_d1_adaptive.v:71](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_d1_adaptive.v:71>)
- adaptive_transition: [forest_d1_adaptive_features.v:27](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_d1_adaptive_features.v:27>)
- swing_deadline: [j280_swing_source_swm4.v:812](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/j280_swing_source_swm4.v:812>)
- recognition_release: [forest_d1_gesture_decode.v:63](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_d1_gesture_decode.v:63>)
- sampler_fault: [forest_d1_window_sampler.v:73](<C:/Users/董晨阳/Documents/Codex/2026-10-24/forest-d1-online-tuning-5ms-config/work/adb1_motion_brake_queue_20261030/audit_flow_fix/work/project/src/forest_d1_window_sampler.v:73>)

完整去重源索引：332份不同实现，见FULL_SOURCE_CONDITION_INDEX.json；按内容哈希保留全部历史路径。该索引包含非当前启用分支，不把检索数量当作已逐一上板验收数量。
