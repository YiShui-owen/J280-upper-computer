# J280 V1、V2、V5 总交付包

三套已验收的独立工程按版本归档。每次选择一个版本及其配套上位机使用。

| 目录 | 功能 | 提示词 | 源码、上位机和说明 |
|---|---|---|---|
| V1 | 三种起摆，已修复起摆接平衡的位置和新帧逻辑 | [V1提示词](V1/CONTINUE_PROMPT_CN.txt) | [V1原包说明](V1/Code_and_Host/README_CN.md) |
| V2 | 起摆、手势与单圈/连续旋转，同样已修复接入 | [V2提示词](V2/CONTINUE_PROMPT_CN.txt) | [V2原包说明](V2/Code_and_Host/README_CN.md) |
| V5 | 手动扶直后平衡、六位置、六条现有轨迹、BT10键盘命令及USB日志 | [V5提示词](V5/CONTINUE_PROMPT_CN.txt) | [V5原包说明](V5/Code_and_Host/README_CN.md) |

每个版本目录内都有 CONTINUE_PROMPT_CN.txt、单独FS，以及已解开的 Code_and_Host/；提示词与该版本代码归在一起。源码位于 Code_and_Host/V对应数字/project/，窗口分别为 Code_and_Host/Start_V1.cmd、Start_V2.cmd、Start_V5.cmd。给另一台电脑接续时，把整个对应版本目录一起交给它。

FS只用于J280的GW2A-LV55PG484C8/I7。本次只是打包，未改源码、Host、位流或原证据，未重新编译或操作硬件。每份Code_and_Host目录完整保留原ZIP的所有文件及原校验清单，可以继续使用原包中的验证工具。三套CST、协议、窗口分别配套，勿互相替换。

V1原50MHz验收：Setup+1.251ns、Hold+0.314ns；V2：+0.043ns、+0.213ns；V5：+0.032ns、+0.077ns，均通过原编译时的时序验收。实物效果以对应硬件实测为准。各版编译设置、验证范围和剩余限制见原包说明及接续提示词。

总包MANIFEST.json逐文件记录SHA256；PROVENANCE.json记录三个原交付ZIP与FS的哈希。没有修改原始交付文件。
