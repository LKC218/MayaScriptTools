# intersectionSolver Maya 插件汉化与功能调整记录

> 适用范围：Maya 2018 / 2022 及兼容版本  
> 插件目标：辅助显示、检测和修复多边形模型穿插问题。  
> 当前版本：`v1.1`  
> 当前脚本：`脚本/建模工具/intersectionSolver.py`  
> 记录日期：2026-04-25  

---

## 1. 项目背景

`intersectionSolver.py` 原始脚本为 GORIOSHI SCRIPTS 的 Maya 工具，主要用于显示模型穿插线、检查碰撞、通过布尔和属性传递尝试修复模型穿插，并提供松弛和 NaN 顶点修复辅助功能。

本次调整目标是将脚本整理到项目分类目录中，完成中文 UI、本地化交互优化、线条显示控制、帮助面板和版本号整理，方便后续维护与排查。

---

## 2. 文件整理记录

当前脚本已从项目根目录移动到建模工具目录：

```text
E:\kc\标准\Maya脚本工具\脚本\建模工具\intersectionSolver.py
```

整理原则：

- 根目录不保留重复副本，避免后续维护两个版本。
- 保留原始函数名和核心算法，降低破坏旧调用的风险。
- UI 文案汉化，内部节点名和 Maya API 调用尽量保持原结构。

---

## 3. 当前已实现功能

### 3.1 穿插线显示

对应函数：

```python
createPfxToon()
removePfxToon()
```

功能说明：

- 对当前选中模型创建或复用 `pfxToonCollisionDetectShape`。
- 开启 `intersectionLines` 和 `selfIntersect`。
- 使用红色线条显示模型穿插区域。
- 支持移除 `pfxToon` 穿插线显示。

已修复：

- 原脚本中 `pfxToonCollisioneDetect` 拼写不一致，已统一为 `pfxToonCollisionDetect`。
- 该修复避免“移除穿插线显示”按钮清理不到创建节点。

---

### 3.2 红色穿插线半透明

新增参数：

```python
defaultLineOpacity = 0.45
```

功能说明：

- 创建穿插线时自动设置 `pfxToonCollisionDetectShape.lineOpacity`。
- 默认透明度为 `0.45`。
- UI 中新增“穿插线透明度”滑条和输入框。
- 数值越小越透明，`1.0` 为不透明。

防错处理：

- 设置透明度前检查 `lineOpacity` 属性是否存在。
- 未创建 `pfxToon` 节点时，拖动透明度滑条不会直接报错。

---

### 3.3 线宽控制优化

对应函数：

```python
setPfxToonLineWidth()
displayWidthFieldChange()
displayWidthSliderChange()
updateLineWidthSliderRange()
```

当前线宽 UI：

- 输入框：`lineWidth`
- 滑条：`displayWidthSlider`
- 精细模式开关：`lineWidthFineMode`

线宽范围：

```python
lineWidthSliderMin = 0.001
lineWidthFineMax = 2.0
lineWidthWideMax = 20.0
```

功能说明：

- 默认开启“线宽精细模式”，滑条范围为 `0.001 ~ 2.0`。
- 关闭精细模式后，滑条范围为 `0.001 ~ 20.0`。
- 输入框输入超过 `2.0` 时，会自动切到大范围模式。
- 线宽输入框精度为 `pre=3`，便于观察低值变化。

已修复：

- 原线宽滑条范围为 `0.001 ~ 100`，低值段难以控制。
- 现在低值区间拥有更多滑条分辨率，适合调整 `0.05`、`0.1` 等细线宽。
- 设置线宽前检查 `lineWidth` 属性是否存在，避免未创建穿插线节点时报错。

---

### 3.4 Ctrl + 鼠标左键慢速微调

新增参数：

```python
slowSliderRatio = 0.1
ctrlModifierMask = 4
sliderSlowMinStep = {
    'nearClipSlider': 0.0001,
    'displayWidthSlider': 0.0005,
    'lineOpacitySlider': 0.001,
}
```

对应函数：

```python
isCtrlPressed()
getSliderValue()
setSliderValue()
```

功能说明：

- 支持按住 `Ctrl + 鼠标左键拖动滑条` 进行慢速微调。
- 覆盖三个滑条：
  - `nearClipSlider`
  - `displayWidthSlider`
  - `lineOpacitySlider`
- 普通拖动保持原速度。
- 手动输入框不受 Ctrl 慢速逻辑影响。

已修复：

- 早期慢速微调在小数值变化时不够明显。
- 当前增加了最小步进逻辑，避免小值区域拖动无反馈。
- 增加范围钳制，防止慢速计算后越过滑条最小值或最大值。

---

### 3.5 相机近裁剪调整

对应函数：

```python
nearClipChange()
```

功能说明：

- 读取当前模型面板相机。
- 修改当前相机的 `nearClipPlane`。
- UI 实时显示当前近裁剪数值。
- 支持 Ctrl 慢速微调。

用途：

- 方便近距离观察模型穿插区域。
- 减少视口近裁剪导致的查看问题。

---

### 3.6 碰撞检测与结果选择

对应函数：

```python
findCollision()
selectResults()
```

功能说明：

- 临时三角化选中模型。
- 创建 Maya rigidBody 并触发时间轴评估。
- 使用 `rigidSolver.collisionTolerance = 0.0001` 检测碰撞。
- 将 Maya 自动选中的碰撞结果保存到全局变量 `collisionResults`。
- 可通过“选择结果”按钮重新选择上次检测结果。

注意：

- 该功能依赖 Maya 旧版刚体系统。
- 对复杂模型、异常历史或非标准拓扑可能不稳定。

---

### 3.7 穿插修复

对应函数：

```python
applyCollision()
```

主要流程：

- 清理旧临时对象。
- 复制选中模型。
- 创建远处 `dummy_plane` 参与布尔流程。
- 对复制体执行 `polyCBoolOp`。
- 追踪 face set，分离 shell。
- 补洞并根据“间隙距离”移动顶点。
- 使用 `transferAttributes()` 将处理后的形态传回原模型。
- 删除历史和临时对象。

使用前提：

- 建议先备份模型。
- 建议确认 UV 干净。
- 建议先删除历史。

风险：

- 该操作会修改原模型形态。
- 复杂拓扑、重叠 shell、绑定模型或历史复杂模型可能出现不可控结果。

---

### 3.8 松弛工具

对应函数：

```python
relaxBrush()
relaxFlood()
```

功能说明：

- `松弛笔刷`：切换到 Maya Sculpt Relax 工具。
- `整体松弛`：执行多次 `sculptMeshFlood`。

用途：

- 修复穿插后，对局部不平整区域进行二次平滑。

---

### 3.9 NaN 顶点修复

对应函数：

```python
fixNanVerts()
```

功能说明：

- 遍历选中模型顶点。
- 如果检测到 `.pnts[]` 偏移值为 `nan`，将其重置为 `(0, 0, 0)`。

注意：

- 该功能只处理顶点 offset 数据异常。
- 不等同于完整模型修复工具。

---

### 3.10 帮助面板

新增窗口：

```python
helpWindowName = 'intersectionSolverHelp'
showHelpWindow()
```

功能说明：

- 主界面新增“帮助”按钮。
- 点击后弹出独立帮助面板。
- 帮助内容包括：
  - 插件用途
  - 推荐流程
  - 参数说明
  - 注意事项

窗口行为：

- 重复点击帮助按钮会重新创建帮助窗口。
- 帮助面板使用 `scrollField`，方便后续增加说明内容。

---

## 4. UI 汉化记录

当前已汉化的主要 UI：

- `Intersection_Solver` → `穿插修复工具`
- `Intersection Solver v1.0` → `穿插修复工具 v1.1`
- `Cam Near Clip` → `相机近裁剪`
- `Show Intersections on Selected` → `显示选中物体穿插线`
- `Display Width` → `显示线宽`
- `Remove pfxToon` → `移除穿插线显示`
- `Inspect Selected` → `检测选中物体`
- `Select Results` → `选择结果`
- `Gap Distance` → `间隙距离`
- `Solve Intersection` → `修复穿插`
- `Clean up junk Caused by Error` → `清理错误残留`
- `Relax Brush` → `松弛笔刷`
- `Relax Flood` → `整体松弛`
- `Fix NaN Verts` → `修复 NaN 顶点`

版本号：

```python
mc.frameLayout('穿插修复工具 v1.1', ...)
```

---

## 5. 已回退功能记录

曾尝试新增“选中穿插点”功能：

- UI：`点选阈值`
- UI：`选中穿插点`
- 临时节点：`tempIntersectionPickMesh*`
- 临时节点：`tempIntersectionPickDup*`
- 临时节点：`tempIntersectionPickCPOM*`
- 核心方案：临时布尔交集网格 + closestPointOnMesh 映射回原模型顶点

回退原因：

- 已按需求回退到上个版本。
- 当前正式版本不包含该功能。

当前状态：

- `selectIntersectionVerts()` 已删除。
- `点选阈值` 和 `选中穿插点` UI 已删除。
- `flushCBB()` 中相关临时节点清理项已删除。
- 窗口高度恢复到 `420 × 345`。

后续如需重新实现，建议重新评估方案，不要直接恢复旧实现。

---

## 6. 当前关键参数

```python
windowName = 'intersectionSolver'
helpWindowName = 'intersectionSolverHelp'
defaultLineOpacity = 0.45
slowSliderRatio = 0.1
ctrlModifierMask = 4
lineWidthSliderMin = 0.001
lineWidthFineMax = 2.0
lineWidthWideMax = 20.0
```

慢速滑条最小步进：

```python
sliderSlowMinStep = {
    'nearClipSlider': 0.0001,
    'displayWidthSlider': 0.0005,
    'lineOpacitySlider': 0.001,
}
```

---

## 7. 排查建议

### 7.1 穿插线不显示

优先检查：

- 是否已选择 mesh transform 或 mesh shape。
- `pfxToonCollisionDetectShape` 是否创建成功。
- `pfxToonCollisionDetectShape.intersectionLines` 是否为 `1`。
- `pfxToonCollisionDetectShape.selfIntersect` 是否为 `1`。
- `pfxToonCollisionDetectShape.lineOpacity` 是否过低。
- `pfxToonCollisionDetectShape.lineWidth` 是否过低。

相关函数：

```python
createPfxToon()
displayWidthSliderChange()
lineOpacitySliderChange()
```

---

### 7.2 移除穿插线失败

优先检查：

- 节点是否为 `pfxToonCollisionDetect`。
- shape 是否为 `pfxToonCollisionDetectShape`。
- 是否存在历史版本残留的错误拼写节点 `pfxToonCollisioneDetect`。

相关函数：

```python
removePfxToon()
flushCBB()
```

---

### 7.3 线宽滑条不好控制

优先检查：

- `lineWidthFineMode` 是否开启。
- 当前线宽是否超过 `2.0`，超过后应切换大范围模式。
- `sliderSlowMinStep['displayWidthSlider']` 是否过大。
- 是否使用 `Ctrl + 鼠标左键拖动` 进行微调。

相关函数：

```python
updateLineWidthSliderRange()
getSliderValue()
displayWidthSliderChange()
```

---

### 7.4 透明度无效

优先检查：

- 当前 Maya 版本的 `pfxToon` 是否支持 `lineOpacity`。
- `mc.objExists('pfxToonCollisionDetectShape.lineOpacity')` 是否为 True。
- 是否已经点击过“显示选中物体穿插线”创建节点。

相关函数：

```python
setPfxToonOpacity()
lineOpacitySliderChange()
```

---

### 7.5 修复穿插结果异常

优先检查：

- 模型是否有复杂历史。
- UV 是否干净。
- 是否有非流形几何、重叠 shell 或异常法线。
- `gapDistanceFloat` 数值是否过大。
- `polyCBoolOp` 是否在当前 Maya 版本中稳定。

相关函数：

```python
applyCollision()
flushCBB()
```

建议：

- 始终在模型副本上测试。
- 修复前保存场景。
- 复杂模型先手动简化拓扑再执行。

---

## 8. 验证记录

已执行的本地验证：

```text
python -m py_compile 脚本/建模工具/intersectionSolver.py
```

结果：

- Python 语法检查通过。
- 每次检查后已清理本次生成的 `intersectionSolver.cpython-312.pyc`。

未验证内容：

- 当前环境不是 Maya Python 运行时，未在 Maya 内进行 UI 点击、视口显示和布尔修复实测。

---

## 9. 后续维护建议

建议优先级：

1. 给 `createPfxToon()` 增加空选择保护。
2. 给 `findCollision()` 增加无选择和 rigidBody 失败保护。
3. 给 `applyCollision()` 增加 `try/finally`，确保异常时也能自动清理临时节点。
4. 给 `fixNanVerts()` 增加无选择保护。
5. 如果重新实现“选中穿插点”，建议先做独立测试脚本，不直接合入主工具。

不建议短期处理：

- 大规模重构核心布尔修复算法。
- 改动原始节点命名和函数名。
- 将 UI 和核心逻辑完全拆分，除非后续确认要长期维护该插件。

