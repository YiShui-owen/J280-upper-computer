# V1～V5 SRAM 一键切换

用户已于2026-10-25确认实施先前评估方案：选择版本后自动下载；仅SRAM，断电不保留；Programmer路径可跨电脑配置。已保存基线 `fd2-v1-v5-before-auto-programming-20261025`。本次在原目录的 `feature/sram-programming` 分支实施，不执行真实下载或连接设备，不自动提交/推送。

## 行为

设置中新增“固件切换”，首次配置Programmer目录、下载器及USB串口后，在专用选择器选择V1～V5即可启动一次任务。原“预期版本”仍只做通信校验。加载页面、保存设置、恢复选择、刷新状态、回放不启动下载。

任务顺序：校验原位流与设置 → 禁止并发运动 → 停止小车输入 → 原Host排他准备（阻止GUI/键盘/Web新控制、一次STOP、实际新鲜零输出和停止状态）→ 关闭旧owner和窗口 → 精确下载器/单芯片JTAG核验 → `--run 4` SRAM Program and Verify一次 → 启动目标版原Host并显式恢复USB连接 → 读回完整firmware/schema/wire身份、新会话及500ms新鲜状态 → 完成。没有自动ZERO、RUN、PID恢复或Flash操作。

若无可用Host，只有本次操作明确勾选“电机电源已断开”且填写USB串口，才允许首次/失联下载；该确认不持久化，提交后清除。已连接但身份/状态无效、回放、日志异常、排他准备失败均不能由该勾选绕过。CLI超时/输出不明不重试；失败保留日志、阶段和任务ID，需用户明确新操作。

## 分工与接口

### 原位流与官方工具（任务A）

`firmware/Vn/J280_Vn.fs`、`firmware/manifest.json`：从三个用户ZIP指定bitstream路径导入原字节，记录归档/文件SHA256、大小及GW2A-55C。禁止执行归档脚本或修改上游文件；`.gitattributes`添加 `firmware/** -text`。

`backend/gowin_programmer.py`：

```python
class ProgrammerError(RuntimeError): pass
def discover_programmers() -> list[str]: ... # 返回存在的exe绝对路径；仅文件系统，优先新版本
def resolve_programmer(value: str) -> Path: ... # bin目录/安装根/完整exe；拒绝额外命令参数
def validate_cable(value: dict) -> dict: ... # cable_index 0/1/5，channel整数，location整数或None，uid合法或None
def load_firmware(variant: str, root: Path = PROJECT_ROOT) -> dict: ... # V1..V5，path/sha256/size/device，验证文件
class GowinProgrammer:
    def __init__(self, executable: Path, *, runner=None): ...
    def probe(self) -> dict: ... # 只--help，核验GW2A-55C与SRAM Program and Verify
    def scan_cables(self) -> list[dict]: ... # 显式调用--scan-cables，含可用于validate_cable的字段及label
    def scan_device(self, cable: dict) -> dict: ... # --scan，严格单设备GW2A-55C，否则报错
    def program(self, variant: str, cable: dict, emit=None) -> dict: ... # --run 4唯一写模式，verify+exit+错误输出判定；返回verified:true/log
```

官方CLI必须使用argv数组、shell=False、工具bin为cwd、Windows隐藏控制台、超时杀止仅本进程，不重试；支持空格/中文路径。命令白名单不接受客户端任意args/device/文件。精确选择缆线，拒绝不确定/多目标；未知输出失败关闭。CLI文本/图形驱动实机差异须明确记录，不能伪造探测结果。

### 原Host排他交接（任务B）

`host/fd2_automation.py`负责排他准备与生命周期，外层集成 `host/fd2_bridge.py`、`launch_host.py`，上游原字节不变。

`GET /status`新增 `automation:{supported:true,busy:false,job_id:null}`。

`POST /automation/prepare` body `{job_id:str}`：唯一lease，重复同ID返回同结果；等待原STOP真实ACK+独立更新实际停止状态，阻止所有来源非STOP/ESTOP的控制写入；不持桥/状态锁等待。成功关闭owner（等待closed），返回 `{job_id,token,prepared:true,connection:{port,mode,ble_address,log_dir},session}`。USB必须实际存在；BLE-only禁止。失败保留排他，`POST /automation/release`配同job_id/token只能在未关闭旧进程时解除排他，不重发STOP或动作。

停止证据按原RTL区分：正常coherent事务要求晚于ACK且control_epoch递增；未ZERO时的原生10Hz状态T只在IDLE、zero_valid关闭、epoch=0、故障/PWM/输出许可均0且晚于ACK时有效，sequence和board_ms还必须严格推进于STOP实际写入及ACK两次基线。状态T不变成控制或绘图样本。bootstrap完成同样接受这类真实停止状态，不为获得控制帧自动ZERO。准备结束后允许用户显式关闭旧窗口；bootstrap窗口也允许用户关闭，中途关闭会令后台任务失败而非成功。

`POST /automation/close` body `{job_id,token}`：只在prepared后，先返回应答，再通过主线程关闭原GUI和HTTP；headless通过退出事件结束。原窗口不遗留为可重新连接的第二owner。

launcher增加 `--automation-connect <JSON路径>`：仅这个显式参数允许启动后连接，JSON含connection、job_id和一次token。新Host在bootstrap忙锁中只允许该次受托连接；GUI/键盘/Web普通写仍禁止。状态追加automation.launch_job_id。后台验证新身份并保存版本配置后，调用 `POST /automation/complete {job_id,token}` 幂等解除bootstrap控制锁，才报告完成。GUI采用原App.connect和原TraceLogger/log_policy；headless测试使用原owner及相同日志。保持USB+BLE地址仅在原已选择/连接时恢复；不自动启用键盘、ZERO/RUN、写PID。`--headless`本身仍不连设备，禁止与replay/offline-preview/once组合自动连接；参数严格校验。正常启动START_HOST行为保持。

### 后端调度与API（根任务）

`backend/firmware_service.py`：单任务锁、每机本地配置 `.local/firmware/programming.json`、任务journal及有界日志；不在启动时连接或扫描硬件。request_id相同内容返回原任务、冲突拒绝，保存重启后未知状态且不自动重做；磁盘文件名用任务ID的SHA256，避免Windows保留名/冒号问题。settings/jobs写入原子替换。后台线程协调上述步骤；HostClient用独立timeout调用automation。启动目标Host用随包Python和明确connection JSON，等待实际新身份；不依据退出码单独宣称完成。连接配置仅核验成功后更新。

`backend/firmware_api.py` 路由 `/firmware`：

- `GET /config` -> `{programmer_path,detected_paths,cable,usb_port,configured,firmwares:[V1..V5]}`，仅文件检查。
- `POST /config` body `{programmer_path,cable,usb_port}`，忽略文件只保存本机。
- `POST /scan` body `{programmer_path}` -> `{cables:[...]}`，显式扫描下载线；串行化，不扫描FPGA或下载。
- `GET /status` -> `{busy,phase,job:null|{request_id,target,state,phase,message,created_at,updated_at,log:[str]},error:null|str}`。
- `POST /jobs` body `{request_id,target,motor_isolated:false}` -> job；只提交一次，立即202；失败用明确409/400。
- `GET /jobs/{request_id}` -> job。

所有写API要求 `X-J280-Local:1`、loopback Host和受支持Origin，严格body；不暴露通用进程执行。下载期间摆控普通命令、设置更改和小车输入/连接拒绝；STOP保留。Hub状态及WebSocket带 `programming:{busy,phase,target,request_id}`，旧轮询不得重新显示在线。回放时禁止全部烧录接口。

## 前端（任务C）

`FirmwarePanel.vue`加入设置对话框，不重排主画面。配置区显示工具路径、显式扫描/选择下载器和USB串口；专用选择器默认空值，只有用户change且满足准备条件才POST job，选择目标后自动开始。未连接Host时显示本次电机隔离勾选。显示真实阶段与日志，不能造百分比；网络失败保留任务ID查询，不重发。轮询状态保存当前任务；卸载取消定时器/请求。带 `X-J280-Local:1`。

App整合后端和前端任务状态，立即取消小车输入，下载时禁用运动及连接设置，顶部显示切换阶段。回放禁用扫描、配置及目标选择。状态断流后不能恢复此前的控制许可。纯函数 `firmwarePresentation.js`覆盖选择/禁用/未知状态规则。仅测试夹具模拟CLI与硬件，截图标注离线。

## 验证

失败测试先行：路径带空格/中文，跨电脑发现，五版hash/错文件，CLI仅SRAM4，设备多目标/错型号/未知输出/非零码/超时；Host真实STOP ACK与新状态、错ACK、忙锁GUI/键盘命令、重复准备、会话变化、owner释放；后台重复ID、并发、离线/回放、失败不重试、身份错配、崩溃恢复；HTTP同源保护；前端仅用户change一次提交、刷新不提交、忙/回放守卫。最后跑后端与前端全套、构建、三尺寸离线UI及原件hash。真实CLI仅运行--help，不扫描或下载实物。
