# 2026-10-27 现成 V5 重新编译

本次直接使用已修改并通过验收的 A25 独立 V5，36项构建输入与原包逐字节相同，RTL和原配上位机均无新增改动。没有加入新的120°移植草稿。

本次重新运行完整综合、布局布线和原50MHz时序检查：Fmax50.079MHz，Setup +0.032ns，Hold +0.077ns，违例0；Recovery +8.867ns、Removal +1.372ns、Pulse width +7.315ns。Logic33378/54720，FF14598/42000，CLS21276/27360，BSRAM31/140，DSP10.5/20。

本次位流：`V5/bitstream/J280_V5.fs`。完整解压到较短目录，例如 `D:/J280_V5`，双击 `Start_V5.cmd`；原Tk运行时在过长路径下可能找不到init.tcl。用 `Verify_V5.cmd` 核验完整包。

功能：手动扶直后ZERO/RUN、六个相对位置、六条有限轨迹、BT10蓝牙键盘命令/ACK、USB200Hz完整数据。V5已删除自动起摆，没有自适应、光学手势或独立纯BLE波形回传。当前现成源码仍保留六条轨迹，未发现另一份删减轨迹子集的正式V5。

新编译的原生报告在 `V5/native/`，独立复核在 `reports/NATIVE_V5_EXISTING_INDEPENDENT.json`。源码完全相同，因此原有63项Host测试、实际V5整机/规划器/坐标及传输证明沿用有效源绑定；本次另做随包Python的断连界面启动。旧阶段记录保留作历史，不冒称本次重新仿真。未连接、烧录或操作实物，机械效果和新增外部ADC电气时序仍未验证。

接线与操作见 `docs/WIRING_CN.md`、`docs/README_CN.md`、`docs/KEYBOARD_CN.md`。
