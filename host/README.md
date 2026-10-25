# 配套 Host 与历史交付

日常入口已切换为 2026-10-25 的 FD2 V1～V5，使用 `START_HOST.bat`，来源与离线回放见 [FD2 说明](fd2/README.md)。以下仅记录历史版本来源，旧版参数和操作不能套用到 FD2。

## SG21 / SA21 / SP24 历史 Host

SP24 精确遥测版：原始运行依赖在 `sp24/gesture/host`，预设在 `sp24/presets`，来源及逐文件哈希见 `sp24/SOURCE.md`、`sp24/MANIFEST_SHA256.json`。历史命令入口为 `.venv\Scripts\python.exe -B -X utf8 launch_host.py precise`。身份为 `53503234 / 53505424`。`sp24_bridge.py` 仅在外层添加受原本机访问检查保护的 `/waveform` 批量只读接口，原交付文件与控制/串口/ACK规则保持不变。SP24离线预览使用 `--offline-preview --headless --bridge-port <空闲端口>`，不连接硬件。

这里原样保存用户提供的 `J280_SWM2_Gesture_Adaptive_20261015.zip` 中两版 Host、测试、模板、指南及 API 合同。运行代码未修改；逐文件哈希见 `MANIFEST_SHA256.json`。仅打包配套 Host，不包含位流或 FPGA 构建工具。原 ZIP SHA-256：`6873f5d3e82e5180ac29cf9150a71fcb6175e3cb07c743885b1dd5dbd844031d`。

SG21 身份 `53473231 / 53475421`，SA21 身份 `53413231 / 53415421`。两版历史命令入口分别为 `launch_host.py gesture`、`launch_host.py adaptive`。默认桥端口均为 8371，同时只运行一个对应 Host。窗口启动不会自动连接串口，需在 Host 中明确确认固件并连接。

启动入口 `launch_host.py` 在当前进程内补全所选 Python 安装目录下的 Tcl/Tk 库路径，解决 Windows 虚拟环境创建窗口时报 `Can't find a usable init.tcl` 的情况。它根据 `sys.base_prefix` 定位已安装的库，只在文件存在且未显式配置时设置路径；不修改系统环境、Python 安装或两版交付源码。直接使用 `.venv` 启动时也可在工程根目录运行 `.venv\Scripts\python.exe -B -X utf8 launch_host.py gesture`（SA21 将 `gesture` 改为 `adaptive`），Host 的 `--offline-preview`、`--headless` 等参数可接在后面。

网页通过 FastAPI 服务端调用 Host 的本机 HTTP 接口，串口始终由 Host 单独管理。网页不自动恢复参数或启动运动。只做离线检查可使用 `--offline-preview --headless --bridge-port <空闲端口>`，它禁止连接设备。

核对打包源码：在两个版本的 `host` 子目录分别运行 `python -B -m unittest test_tune_host`；SA21 额外加 `test_adaptive_profile`。Host 的 `verify_host.py` 会更新其本地报告，因此本工程不以运行该脚本代替对原包验证证据的保存。

位流仍使用用户交付的对应 `.fs`。SG21 SHA-256：`b1bcccab2af2bd59e01ddbad80e1689cb8d41428e3edf8810761a50a7a722a89`；SA21：`ad7cba23ba9748ab683cc7ee94f360001042bd3b8440dafeff5b83d307fb56a9`。烧录与实机验收由用户按交付指南显式执行。
