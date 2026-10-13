# L 形摆杆模型

`l-arm.step` 是用户提供的 `L型摆臂(1).STEP` 原件副本。源单位为毫米，实体共 36 个面，外形尺寸约 36 × 40 × 152 mm。网页加载 `src/assets/models/l-pendulum.glb`，不在浏览器中解析 STEP。

转换以 CAD 坐标 `(0, -2, 67.5)` mm 为原点，即轴端直径 7 mm 孔的中心、板厚中面。轴向从 CAD Y 变为显示 X，自由端指向显示 +Y；网格以米存储，几何比例不变。`l-pendulum.meta.json` 记录源文件 SHA256、坐标变换、网格尺寸和转换精度。

`src/pendulumModel.js` 将摆杆等比缩放到原场景的显示高度，并沿安装轴移至编码器端盖外侧。这些值只用于显示，不代表实物摆长或控制参数。模型仍挂在原 `pendulumPivot` 下，由现有 θ/α 映射和显示标定驱动。

## 重新转换

日常启动和构建直接使用已提交的 GLB，无需安装转换工具。更换 STEP 后，在 `frontend` 目录执行下列 PowerShell 命令；OpenCascade 转换器安装到临时目录，不加入页面运行依赖：

```powershell
$converterDir = Join-Path $env:TEMP 'j280-step-tools'
npm install --prefix $converterDir --no-save --package-lock=false occt-import-js@0.0.23
$env:OCCT_IMPORT_JS = Join-Path $converterDir 'node_modules\occt-import-js'
node tools/convert-pendulum-model.mjs
node --test tests/pendulumModel.test.js
npm run build
```

转换使用 [occt-import-js](https://github.com/kovacsv/occt-import-js) 的 `ReadStepFile` 和 Three.js 的 `GLTFExporter`。更换零件时，先检查新的孔中心、单位和坐标方向，再调整转换脚本中的资产定位；不要随模型替换修改遥测、标定默认值或控制参数。转换后检查向上、下垂及随旋臂转动的姿态；硬件安装方向需拿到实物后确认。
