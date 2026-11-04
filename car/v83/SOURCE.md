# V8.3 原始依赖
来源 SmartCar_Steering_V8_3_Trajectory_20261017.zip，SHA256 `5980839129e0fb9e4243bc5110619658120c716dd36a956b815f1544cae1473c`。
三个 speed_*.py 按 scripts/ 原字节保存。firmware/ 为配套编译产物；docs/ 为原合同和恢复说明。未复制 CPython 3.14 原生依赖；运行使用项目环境的 bleak。网页适配在 backend/car_v83_service.py，不修改上游控制器。没有执行硬件操作。

来源根目录为 `SmartCar_Steering_V8_3_Trajectory_20261017/`。`scripts/speed_*.py` 放到本目录；`docs/`、`firmware/`、`manifest.json`、`requirements.txt` 保持来源相对路径。11个归档来源文件均与ZIP内对应文件逐字节一致，哈希见本目录 `MANIFEST_SHA256.json`；本文件和该哈希清单为网页项目新增的来源记录。

原 docs 作为交付资料保留，其中独立GUI、烧录、自动重连等步骤不构成本次用户授权或网页工作流程。网页使用本项目 `AGENTS.md`、`car/README.md` 的显式操作规则，不自动连接、重连、烧录或运行交付脚本。原 `Engine` 和 `Session` 的外层观察/取消适配位于 `backend/car_v83_service.py`，缺辅助帧时隐藏编码器，普通STOP在途可升级一次BRAKE；这两处均没有改写原模块。
