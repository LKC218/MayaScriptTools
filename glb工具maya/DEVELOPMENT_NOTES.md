# Maya GLB 工具开发与排查记录

本文档记录当前已实现能力、踩过的问题、限制和后续修改注意点，方便继续维护时快速定位。

## 当前文件结构

- `maya_glb_tool.py`：Maya UI 和主入口。优先调用原生 GLB 模块，失败后尝试 Maya glTF 插件，再失败才走 Blender 后台兜底。
- `maya_glb_native.py`：Maya 原生 GLB 读写模块，核心实现都在这里。
- `blender_glb_bridge.py`：Blender 后台转换桥，只作为兜底方案。
- `maya_bpy_glb_compat.py`：极简 `bpy.ops.import_scene.gltf/export_scene.gltf` 兼容层。
- `install.py`：安装到 Maya 用户 scripts 目录并创建 Shelf 按钮。
- `blender_style_example.py` / `migration_template.py`：迁移示例。

## 调用优先级

导入：

1. `maya_glb_native.import_glb()`
2. Maya 文件翻译器 / glTF 插件
3. Blender 后台：GLB/GLTF -> FBX -> Maya

导出：

1. `maya_glb_native.export_glb()`，仅对 `.glb` 优先启用
2. Maya 文件翻译器 / glTF 插件
3. Blender 后台：Maya -> FBX -> GLB/GLTF

不要轻易移除兜底链路。原生模块还不覆盖骨骼、蒙皮、动画等复杂数据。

## 已实现能力

### UI

- 极简主界面：`导入`、`导出选中`、`导出全场景`。
- 点击按钮后才弹出路径选择窗口。
- 选项、备用转换、诊断、日志默认折叠。
- 记住上次导入/导出路径和常用选项。
- 支持打开上次导出目录。

### 原生 GLB 导入

- GLB 2.0 JSON/BIN chunk 解析。
- `.gltf` 外部 buffer / data URI buffer 读取。
- accessor 支持：
  - `SCALAR`
  - `VEC2`
  - `VEC3`
  - `VEC4`
  - `MAT4`
  - `byteStride`
  - `normalized`
  - `sparse`
  - 无 `bufferView` 时默认零值
- mesh primitive 导入。
- 同一个 glTF mesh 的多个 primitive 会合并为一个 Maya mesh。
- 多 primitive 按面分配材质。
- 读取并设置：
  - `POSITION`
  - `NORMAL`
  - `TEXCOORD_0`
  - `COLOR_0`
- glTF `NORMAL` 会写入 Maya face-vertex normals，用于保留软硬边显示。
- 节点变换：
  - `matrix`
  - `translation`
  - `rotation`
  - `scale`
- glTF matrix 是列主序，传给 Maya 前已转成行主序。
- 贴图保存到当前 Maya 项目的：
  `sourceimages/maya_glb_tool/<文件名>/`
- 材质：
  - 优先创建 `standardSurface`
  - 失败回退 `lambert`
  - baseColor
  - baseColorTexture
  - normalTexture
  - metallicRoughnessTexture
  - occlusionTexture
  - emissiveTexture
  - emissiveFactor
  - alphaMode / alphaCutoff
  - doubleSided 信息保存为自定义属性
- sampler：
  - `wrapS`
  - `wrapT`
  - 映射到 `place2dTexture.wrapU/wrapV`
- 相机：
  - perspective camera
  - yfov
  - znear / zfar
- 灯光：
  - `KHR_lights_punctual`
  - point
  - spot
  - directional
- 元数据：
  - glTF `name`
  - glTF `extras`
  - 保存到 Maya 自定义字符串属性
- 导入完成后显示统计：
  mesh / 材质 / 贴图 / 相机 / 灯光

### 原生 GLB 导出

- 静态 mesh 导出。
- 当前选中对象或全场景导出。
- UV、法线、顶点色导出。
- face-vertex normal 导出，用于保留软硬边视觉。
- 按 Maya 面材质分配拆分 glTF primitive。
- 多材质导出。
- baseColor / baseColorTexture。
- normalTexture。
- metallicRoughnessTexture。
- emissiveTexture。
- alphaMode 基础信息。
- 相机导出。
- `KHR_lights_punctual` 灯光导出。
- 导出后执行 GLB 自校验：
  - magic
  - version
  - 文件长度
  - chunk 边界
  - JSON 可解析

### Blender 兜底

- 自动检测 Steam 版 Blender：
  `D:\Steam\steamapps\common\Blender\blender.exe`
- 支持手动选择 `blender.exe`。
- 导出兜底：Maya FBX -> Blender -> GLB/GLTF。
- 导入兜底：GLB/GLTF -> Blender -> FBX -> Maya。
- Blender 只是兜底，当前目标是尽量走 Maya 原生实现。

## 已遇到并修复的问题

### 1. Maya 没有 GLB/GLTF 文件翻译器

现象：

```text
当前 Maya 没有可用的 GLB/GLTF 文件翻译器
```

原因：

Maya 当前环境未安装或未启用 glTF 插件。

处理：

- 加入 Maya 原生 GLB 读写模块。
- 保留 Maya 插件路径作为第二选择。
- 保留 Blender 后台转换作为最后兜底。

### 2. 安装脚本找错目录

现象：

```text
找不到工具文件：
C:\ProgramData\Autodesk\ApplicationPlugins\UnrealLiveLinkForMaya\Contents\maya_glb_tool.py
```

原因：

Maya Script Editor 里使用 `exec(open(...).read())` 时，`__file__` 可能继承自其他插件。

处理：

- `install.py` 不再盲信 `__file__`。
- 会验证候选目录里是否存在全部工具文件。
- README 改用：

```python
import runpy
runpy.run_path(r"H:\cjiaoben\MayaScriptTools\glb工具maya\install.py", run_name="__main__")
```

### 3. 桌面 Blender 不是 exe

现象：

Maya 文件选择窗口找不到 `blender.exe`。

原因：

桌面上的是 `Blender.url`，内容是：

```text
steam://rungameid/365670
```

处理：

- 自动检测 Steam 版 Blender 路径。
- 浏览过滤改成 `Executable (*.exe);;All Files (*.*)`。

### 4. Blender 备用导入 namespace 非法

现象：

```text
名称空间名 "1" 包含非法字符
```

原因：

GLB 文件名可能数字开头或包含 Maya namespace 非法字符。

处理：

- 新增 `_safe_maya_name()`。
- 数字开头自动加前缀。
- 非法字符替换为下划线。

### 5. Blender 备用导入贴图丢失

原因：

GLB -> FBX 的临时目录被删除后，Maya file 节点路径失效。

处理：

- 导入缓存改到 Maya 项目：
  `sourceimages/maya_glb_tool/<文件名>/`
- 导入后按文件名尝试自动重连贴图。
- 后续又改为优先走原生 GLB 导入，减少这类链路问题。

### 6. 软硬边不对

原因：

最初没有把 glTF `NORMAL` 写入 Maya face-vertex normals。

处理：

- 读取 `NORMAL` accessor。
- 根据 face vertex 顺序写入 `setFaceVertexNormals()`。
- 执行 `polyNormalPerVertex(..., freezeNormal=True)`。

### 7. glTF matrix 方向错误风险

原因：

glTF matrix 是列主序，Maya Python API 使用行主序值。

处理：

- `_matrix_from_node()` 中做列主序到行主序转换。

### 8. 多材质模型导出/导入结构不理想

问题：

- 导出如果只取第一个材质，会丢面材质分配。
- 导入如果每个 primitive 一个 mesh，会碎对象。

处理：

- 导出按 shadingEngine 面分配拆分多个 primitive。
- 导入将同一个 glTF mesh 的多个 primitive 合并为一个 Maya mesh。
- 导入后按面分配材质。

### 9. 工具 UI 太复杂

处理：

- 主 UI 只保留导入、导出选中、导出全场景。
- 点击按钮后再弹路径选择窗口。
- 诊断、选项、日志全部折叠。

## 当前限制

以下能力尚未完整实现：

- 骨骼 joints。
- skinCluster / 蒙皮权重。
- 动画。
- morph target / blendShape。
- Draco 压缩。
- KTX2 / BasisU 纹理。
- 完整 PBR 网络精确映射。
- 多 UV 集。
- 切线导入导出。
- 贴图 sampler 的 filter 参数只做了很浅的处理，目前主要映射 wrap。
- 严格保留四边面拓扑无法保证。glTF/GLB 通常以三角面表达。

## 后续修改注意点

1. 优先修改 `maya_glb_native.py`，不要再把 Blender 作为主路径。
2. 每次修改后至少运行：

```powershell
& "D:\Steam\steamapps\common\Blender\blender.exe" --background --python-expr "import py_compile; files=[r'H:\cjiaoben\MayaScriptTools\glb工具maya\maya_glb_native.py', r'H:\cjiaoben\MayaScriptTools\glb工具maya\maya_glb_tool.py', r'H:\cjiaoben\MayaScriptTools\glb工具maya\blender_glb_bridge.py', r'H:\cjiaoben\MayaScriptTools\glb工具maya\install.py']; [py_compile.compile(f, doraise=True) for f in files]; print('PY_COMPILE_OK')"
```

3. Blender 启动时可能输出本机 startup 脚本警告，不一定是本工具错误。重点看是否出现 `PY_COMPILE_OK`。
4. Maya API 真场景测试仍必须在 Maya 内做，因为本机没有 `mayapy`。
5. 修改导入 mesh 逻辑时，注意以下数据必须同步：
   - `face_counts`
   - `face_connects`
   - UV face vertex assignment
   - normals face vertex assignment
   - colorSet face vertex assignment
   - face material assignment
6. 修改导出 mesh 逻辑时，注意 glTF primitive 的顶点拆分必须考虑：
   - position
   - normal
   - uv
   - color
   - material
   否则软硬边、UV seam 或颜色会错。
7. 修改 matrix 时记住 glTF column-major 与 Maya row-major 的差异。
8. 修改 install 时不要依赖不验证的 `__file__`。

## 推荐 Maya 内测试清单

每次大改后建议按以下顺序测试：

1. 单 cube，无材质，导出再导入。
2. cube 软硬边，导出再导入，看法线。
3. 带 UV 和 baseColor 贴图的模型。
4. 一个 mesh 多个面材质。
5. normal map 材质。
6. 透明贴图材质。
7. 顶点色模型。
8. 带相机的场景。
9. 带点光、聚光、平行光的场景。
10. GLB 导出后再用 Blender 或其他查看器打开，确认 JSON/chunk 没坏。

## 临时运行最新版

```python
import sys
import importlib

tool_dir = r"H:\cjiaoben\MayaScriptTools\glb工具maya"
if tool_dir not in sys.path:
    sys.path.insert(0, tool_dir)

import maya_glb_native
import maya_glb_tool
importlib.reload(maya_glb_native)
importlib.reload(maya_glb_tool)
maya_glb_tool.show_ui()
```

## 重新安装 Shelf 版本

```python
import runpy
runpy.run_path(r"H:\cjiaoben\MayaScriptTools\glb工具maya\install.py", run_name="__main__")
```
