# Maya GLB 导入导出工具 v1.0.0

这是第一版可测试交付。工具优先使用 Maya 原生 Python/API 读写 `.glb`，不再默认依赖 Blender；只有原生路径或 Maya glTF 插件无法处理时，才使用 Blender 后台转换兜底。

## 快速安装

在 Maya Script Editor 的 Python 标签页执行：

```python
import runpy
runpy.run_path(r"E:\kc\标准\Maya脚本工具\脚本\建模工具\glb工具maya\install.py", run_name="__main__")
```

安装完成后，当前 Shelf 会出现 `GLB` 按钮。之后点击这个按钮即可打开工具。

## 快速使用

打开工具后主界面只有三个常用按钮：

- `导入`：弹出文件窗口，选择 `.glb/.gltf`。
- `导出选中`：先选择 Maya 模型，再点击按钮指定 `.glb` 保存路径。
- `导出全场景`：导出当前场景中的模型、基础相机和基础灯光。

第一次使用建议：

1. 新建或打开 Maya 项目。
2. 准备一个带 UV、贴图、软硬边的简单模型。
3. 点击 `导出选中` 导出为 `.glb`。
4. 新建空场景。
5. 点击 `导入` 导回刚才的 `.glb`。
6. 检查模型、UV、贴图、材质、软硬边是否符合预期。

## 临时运行

如果不想安装，可以在 Maya Script Editor 的 Python 标签页直接运行最新版：

```python
import sys
import importlib

tool_dir = r"E:\kc\标准\Maya脚本工具\脚本\建模工具\glb工具maya"
if tool_dir not in sys.path:
    sys.path.insert(0, tool_dir)

import maya_glb_native
import maya_glb_tool
importlib.reload(maya_glb_native)
importlib.reload(maya_glb_tool)
maya_glb_tool.show_ui()
```

## 文件说明

- `maya_glb_tool.py`：主工具脚本，包含 UI、插件检测、导入、导出和 Shelf 按钮入口。
- `maya_glb_native.py`：Maya 原生 GLB 静态网格/UV/基础材质/贴图读写模块，不依赖 Blender。
- `install.py`：安装脚本，会把主工具复制到 Maya 用户 `scripts` 目录，并在当前 Shelf 创建按钮。
- `blender_glb_bridge.py`：Blender 后台转换桥，用于在 Maya 没有 GLB/GLTF 插件时通过 FBX 中转。
- `blender_style_example.py`：Blender 风格调用示例，用于把 `bpy.ops.import_scene.gltf` / `bpy.ops.export_scene.gltf` 迁移到 Maya。
- `maya_bpy_glb_compat.py`：极简 `bpy` 兼容层，只代理 GLB/GLTF 导入导出。
- `migration_template.py`：从 Blender 脚本迁移到 Maya 的替换模板。
- `DEVELOPMENT_NOTES.md`：开发与排查记录，包含已实现功能、踩坑记录、限制和后续维护注意点。
- `RELEASE_v1.0.0.md`：第一版发布说明。
- `.gitignore`：忽略本地缓存、日志、临时文件和 Maya 生成文件。

## 依赖与兜底

工具优先使用 `maya_glb_native.py` 进行 Maya 原生 GLB 导入导出，不依赖 Blender。原生路径当前覆盖静态网格、UV、法线、顶点色、多材质、基础 PBR 贴图、基础相机和基础灯光。

如果原生路径失败，工具会继续尝试 Maya glTF 插件。如果仍失败，最后才尝试 Blender 后台转换。Steam 版 Blender 常见路径：

```text
D:\Steam\steamapps\common\Blender\blender.exe
```

可以展开 `备用转换 / 诊断`，点击 `环境诊断` 查看 Maya 版本、用户 scripts 目录、插件检测和 Blender 路径。

## 功能

- 导入 `.glb` / `.gltf`
- 导出当前选中对象
- 导出整个场景
- 自动创建导出目录
- 记住上次导入路径、导出路径和选中导出选项
- Blender 后台备用转换
- Maya 原生 GLB 静态网格/UV/基础材质/贴图导入导出
- 原生导入会读取 glTF 法线并写入 Maya face-vertex normals，用于保留软硬边显示
- 原生导入会应用 glTF 节点的 matrix / translation / rotation / scale 变换
- 原生导出会按 Maya 面材质分配拆分为多个 glTF primitive，尽量保留多材质分面
- 原生导入会将同一个 glTF mesh 的多个 primitive 合并为一个 Maya mesh，并按面分配材质
- 原生导入优先使用 `standardSurface` 映射 PBR，失败时回退 `lambert`
- 原生导入会尽量映射 sampler wrapS/wrapT 到 Maya place2dTexture
- 原生导入会将 glTF `name` / `extras` 写入 Maya 自定义字符串属性，减少元数据丢失
- 原生导入支持 accessor normalized / sparse，提升顶点色、权重类数据读取兼容性
- 原生导入导出支持基础相机，以及 `KHR_lights_punctual` 点光、聚光、平行光
- 原生导出后会做 GLB header / chunk / JSON 基础自校验
- 常用导入导出选项：材质、贴图格式、UV、法线、切线、动画、相机、灯光、Y 轴向上、应用变换
- FBX 中转时嵌入贴图
- 导入后尝试四边面化
- 打开上次导出目录
- 清空日志
- Maya 环境诊断
- 中文可停靠 UI
- 插件检测日志
- 帮助说明

## Blender 到 Maya 的迁移说明

Blender 常见调用是：

```python
bpy.ops.import_scene.gltf(filepath=path)
bpy.ops.export_scene.gltf(filepath=path, export_format="GLB")
```

Maya 中不能直接使用这些参数。当前工具将其转换为：

```python
import maya_glb_tool

maya_glb_tool.import_glb(path)
maya_glb_tool.export_glb(path, selected_only=True)
```

也可以使用更接近 Blender 的兼容入口：

```python
import maya_glb_tool

maya_glb_tool.import_scene_gltf(filepath=path)
maya_glb_tool.export_scene_gltf(filepath=path, export_format="GLB", use_selection=True)
```

当前兼容入口会接收常见 Blender 参数，但只有路径和是否导出选中对象会稳定映射到 Maya。材质、动画、法线、切线、坐标轴等细节参数需要看实际安装的 Maya glTF 插件支持哪些选项。

如果原 Blender 源码只用到了 `bpy.ops.import_scene.gltf` 和 `bpy.ops.export_scene.gltf`，可以把：

```python
import bpy
```

替换为：

```python
import sys
tool_dir = r"E:\kc\标准\Maya脚本工具\脚本\建模工具\glb工具maya"
if tool_dir not in sys.path:
    sys.path.insert(0, tool_dir)

import maya_bpy_glb_compat as bpy
```

然后保留原来的调用形态：

```python
bpy.ops.import_scene.gltf(filepath=path)
bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)
```

如果后续提供原始 Blender 源码，可以继续把具体参数逐项映射到 Maya 插件支持的选项中。

## 注意事项

- 导出选中对象前必须先选择对象。
- `.glb` 会优先尝试二进制 GLB 类型，`.gltf` 会优先尝试文本 glTF 类型。
- 原生 GLB 路径当前主要支持静态网格、UV、法线、节点变换、顶点色、多材质分面、基础材质、baseColor 贴图、法线贴图、金属度/粗糙度贴图、自发光贴图、透明度基础信息、基础相机和 `KHR_lights_punctual` 灯光；骨骼、蒙皮、动画、完整复杂 PBR 网络仍属于后续扩展范围。
- 走 Blender 备用转换导入时，转换文件和贴图缓存会保留在当前 Maya 项目的 `sourceimages/maya_glb_tool` 下，避免导入后贴图路径失效。
- 导入后如果 Maya 文件节点贴图路径失效，工具会在本次缓存目录里按文件名搜索并尝试自动重连。
- 走 Blender 备用转换导出时，贴图依赖 Maya 材质是否正确连接到文件节点；建议开启“FBX 中转时嵌入贴图”和材质 `EXPORT`。
- glTF/GLB 通常以三角面方式存储。工具提供“导入后尝试四边面化”，但无法保证恢复原始建模时的四边面拓扑。
- 本工具不会在导入模块时自动修改场景，只有显式调用入口函数才执行操作。
