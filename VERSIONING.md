# 项目版本管理

本项目使用 Git 保存本地版本，用 GitHub 保存远程副本。
保存文件不会自动生成 Git 版本；执行 commit 才会记录快照，push 才会同步到 GitHub。

## 每次修改前后

在本目录打开 PowerShell。大改前先保存当前状态，完成并验证后再提交一次：

```powershell
git status
git diff
git add .
git commit -m "说明本次修改，例如：改善3D灯光和摆杆标定"
git push
```

第一次关联远程仓库后，才可以执行 push。没有需要保存的改动时不必 commit。
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
