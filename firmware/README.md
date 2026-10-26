# J280 V1～V5 SRAM 原始位流

五个 `Vn/J280_Vn.fs` 均从用户交付 ZIP 的 `Vn/bitstream/J280_Vn.fs` 原字节复制，每个文件为 18,588,969 字节，目标为 `GW2A-55C`。未执行归档内容。`manifest.json` 记录文件及归档 SHA256、文件大小、归档成员路径和来源包名；运行时另用适配器内固定的五个 SHA256 验证，修改清单不能使替换文件通过。

来源包：

- V1～V3：`J280_V1_V2_V3_Qualified_20261025_1041.zip`
- V4：`J280_V4_Qualified_20261025_1046.zip`
- V5：`J280_V5_Standalone_20261025(1).zip`

`backend/gowin_programmer.py` 仅允许固定目标、原位流和 `--run 4`（SRAM Program and Verify）。路径发现仅访问文件系统；工具安装根、Programmer 目录、bin 或完整 exe 路径均可配置，不依赖某台电脑的绝对安装路径。进程使用 argv、`shell=False`、bin 工作目录、隐藏窗口、有界输出和超时；不重试，也不终止其他进程。

输出契约依据官方 [SUG502E](https://cdn.gowinsemi.com.cn/SUG502E.pdf) 第4章，并只读检查本机 SUG502-2.5.1E 对应的 CLI 截图。已兼容 `Cable found:`、路径中的 channel/location/UID、可选 SN、null UID 和 `Cost ... second(s)`，以及完整 `Device Info / Family / Name / ID / device(s) found` 块。多个器件、`One of them` 型号歧义、未知格式、扫描字段冲突和实际目标不符全部拒绝；GUI 导出表格不作为 CLI 探测结果。

用户首次接板提供的真实日志使用 `Target Cable: Gowin USB Cable(GWU2X)/0/20/null@1.33 MHz`，频率数值与MHz之间含空格。解析现接受此处可选空白，下载器类型/channel/location/UID仍按原规则核对。同次扫描的 `GW2A-55C GW2AN-55C (One of them)` 仍阻止下载，并明确提示核对芯片丝印；未因该日志扩大型号白名单。

CLI 帮助对默认缆线及 UID/location 优先级有不一致说明，因此始终显式传 cable-index/channel，并且最多传一个身份选择器。UID 或 location 会忽略 channel；若身份选择器匹配多个通道则拒绝。GWU2X/WINUSB 的 location/UID 支持与 FT2CH 可能不同，因此仅当前扫描中该类型恰好一个端口时可继续，并核对工具报告的目标。扫描、下载仅在用户明确发起操作后的调度流程中进行。

开发验证全部使用注入 runner 和伪造进程，不接触实际缆线、FPGA 或串口。官方指南的成功截图是 SRAM Program（操作2），不能用来证明操作4的校验成功；适配器只接受明确的编程成功及 Verify Success 类消息或完整 SRAM Program and Verify 成功消息，并同时要求退出码0且无错误。单独 `Finished.`、100% 或操作标题均报结果未知。不同驱动/CLI 的实际输出若不满足这些结构，会保留日志并失败；需在用户授权的硬件验收中采集真实日志后再补充有依据的格式，不能猜测放行。

`ProgrammerError.log` 为有界日志。已经启动操作4后发生超时或无法确认输出时，`indeterminate=True`；调度器应保留任务且禁止自动重试。预检失败不会设置该标记。
