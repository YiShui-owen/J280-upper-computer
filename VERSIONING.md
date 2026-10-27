# 项目版本管理

本项目使用 Git 保存本地版本，用 GitHub 保存远程副本。
保存文件不会自动生成 Git 版本；执行 commit 才会记录快照，push 才会同步到 GitHub。

## 仓库与已保存版本

远端仓库：https://github.com/YiShui-owen/J280-upper-computer

### 2026-10-27：统一 Host 窗口前的展示版本

固定标签：`showcase-before-host-unification-20261027`。按用户要求保存当前可恢复版本，包含较宽且稳定的波形量程、大图标手势反馈、V5主页面六位置/六轨迹操作、基于未裁切Q4的3D姿态及独立标定修复，以及20261027交付记录。

当前五版FS及哈希清单一并保存在 `firmware/`；V1/V2/V5为新交付，V3/V4保留原版本。FS采用Git二进制属性保持原字节。完整原始ZIP和替换前FS仅备份在本机工作区 `历史版本备份/`，不属于仓库文件。此快照尚未实现网页选串口及后台Host统一管理，也未执行硬件烧录。

恢复此版可在另一目录运行：

```powershell
git clone --branch showcase-before-host-unification-20261027 https://github.com/YiShui-owen/J280-upper-computer.git J280-before-host-unification
```

### 2026-10-25：自动烧录前基线

固定标签：`fd2-v1-v5-before-auto-programming-20261025`。此版包含 FD2 V1～V5 展示、原样 Host / CPython 运行时、120秒波形缓存及离线回放；自动烧录仍处于评估阶段，尚未加入程序。用户于当日要求将当前版提交并同步到 GitHub，作为后续自动化修改前的恢复点。

需要找回这一版时，可以在另一个目录检出标签，保留当前工程：

```powershell
git clone --branch fd2-v1-v5-before-auto-programming-20261025 https://github.com/YiShui-owen/J280-upper-computer.git J280-before-auto-programming
```

源码、原样Host运行时及前端锁文件随Git保存；`.venv`、`node_modules` 等本机环境不保存到仓库。新目录首次运行按 `README_CN.md` 安装展示程序依赖。

- `main`：当前项目，包含提亮后的 3D 场景。
- `baseline-3d-readable` 标签：建立版本管理时的当前源码基线。
- `archive/previous-zip` 分支和 `previous-zip-snapshot` 标签：从用户提供的 `上位机2.zip` 恢复的上一个版本，15 个原始源码/配置文件保持原内容，另外补了 .gitignore。

旧版是单独导入的历史快照，未合并或覆盖 main。可直接比较两个快照：

```powershell
git diff previous-zip-snapshot baseline-3d-readable -- frontend/src/DigitalTwin3D.vue
```

## 每次修改前后

在本目录打开 PowerShell。大改前先保存当前状态，完成并验证后再提交一次：

```powershell
git status
git diff
git add .
git commit -m "说明本次修改，例如：改善3D灯光和摆杆标定"
git push
```

远端 origin 已关联，main 使用 git push 同步。没有需要保存的改动时不必 commit。
依赖、构建产物、Python 缓存、运行日志和本地环境变量文件已通过 .gitignore 排除；源码和 package-lock.json 会记录。

## 大改使用分支

先提交当前改动，再开始尝试：

```powershell
git switch -c experiment/3d-appearance
```

在这个分支上正常提交；验证满意后再合并。main 可以继续保留原来的版本。

## 查找与恢复旧版本

查看记录和某次提交里的文件，不会覆盖当前文件：

```powershell
git log --oneline --decorate --all
git show 提交编号:frontend/src/DigitalTwin3D.vue
```

确定需要恢复时，先提交当前改动，再恢复指定文件并提交新的记录：

```powershell
git restore --source=提交编号 -- frontend/src/DigitalTwin3D.vue
git diff
git add frontend/src/DigitalTwin3D.vue
git commit -m "恢复选定版本的3D场景"
git push
```

`提交编号` 需要替换为 git log 中的实际编号。
不要用强制推送或硬重置作为日常保存、回退方式。

## 建立 Git 之前的阶段备份

项目旁边的 `../历史版本备份/20260926-3d/` 保存了本次会话找到的 8 份前端文件备份，详见其中的说明。
这些是部分文件的历史快照，并非每个阶段的完整项目；未保存的更早改动无法由新建的 Git 历史自动找回。

用户提供的 ZIP 另存于 `../历史版本备份/原始压缩包/上位机2.zip`，提取的源码和 SHA-256 清单位于同一备份目录。
`../历史版本备份/repository-with-previous-version.bundle` 包含新旧两个版本的 Git 历史，可在新目录用 git clone 恢复。
