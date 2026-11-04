# V8.3 兼容、配置与回退

当前匹配组合为 `SmartCarSteeringV83.exe` 与RC83固件。V8.3新增轨迹U更新与有效目标反馈语义，必须同时更新固件和窗口。正式舵机配置与V8.1/V8.2共用，默认仍620/750/980。

## 回退V8.2

关闭控制窗口，按主说明进入ROM模式。`$car`为本V8.3目录，COM15替换为当前CH340实际端口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$car\flash.ps1" -Mode Flash -Firmware V82 -Port COM15 -ReadFactoryInfoViaRam
```

这会选择 `recovery/car_steering_v82.bin`，SHA256为 `add64c5f778ee1a73c8079305599e57e4fa1383d8bc5a788873ef39cd11d0854`。成功后关闭S1/拔USB、恢复BOOT0=GND（BOOT1仍GND），再上电，使用原 `SmartCar_Steering_V8_2_FastTurn_20261017.zip` 中的 `SmartCarSteeringV82.exe`。回退V8.2会恢复其旧轨迹限速和时序。

## 回退用户原V8.1

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$car\flash.ps1" -Mode Flash -Firmware V8 -Port COM15 -ReadFactoryInfoViaRam
```

这会选择 `recovery/car_steering_v8.bin`，其哈希与用户原V8.1包内的V8固件相同。成功后按同样步骤恢复启动跳帽，使用原 `SmartCar_Steering_V8_1_20261017.zip` 中的 `SmartCarSteeringV8.exe`。

原ZIP与旧版本目录保留。本版recovery只交付回退固件，旧窗口从各自原始ZIP取得。更早V7/V6/V5/V3/HoldV2固件选项保留，须搭配各自版本窗口。

## 配置与整片备份

V8.1/V8.2/V8.3共用 `%LOCALAPPDATA%\SmartCarSteeringV8\steering_limits.json`。回退程序不自动恢复端点配置。若明确要恢复用户确认620/980，可自行运行 `apply_confirmed_limits.ps1` 后重开窗口；离线验证不会改正式配置。

实车整片备份位于执行烧录的工程 `backups` 中，恢复需核对UID、容量和哈希。原ROM loader与RAM helper未改，不自动解读保护、不自动重试擦写。仅打开控制窗口不会烧录。源码、固件与EXE不一致时烧录和发布校验会拒绝当前镜像。
