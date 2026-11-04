# G3 C1 原始 Host 来源

`upstream/host` 完整提取自 `MANIFEST_SHA256.json` 中所列 ZIP 的 `GOWIN_G3_C1_Teammate_20261103_R2/Host/`，包含原计划、字库和 vendor pyserial，文件保持原字节。清单记录 ZIP 和逐文件 SHA-256。Python runtime 未随包提供。

外层 `host/g3_c1_bridge.py` 用原 SerialOwner 与 GowinController；显式连接、手动启动平衡、准备上传与播放都须由用户触发。`/gowin` 按独立游标分页，点是基于真实 ENC 的字形映射显示，不是二维实物轨迹；`/status` 包含原映射的 manifest、来源及元数据。物理 ACK 不等于实际到位。ForestFive.Physical.v2 原始日志支持只读波形回放；由于缺少可核验的映射任务信息，回放不重建 GOWIN 映射。
