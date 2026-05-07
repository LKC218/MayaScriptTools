# Maya GLB 导入导出工具 v1.0.0 使用与发布说明

## 定位

这是第一版可测试交付。目标是在 Maya 中完成常见静态 GLB 资产的导入和导出，并尽量保留：

- UV
- 贴图
- 软硬边显示
- 多材质按面分配
- 基础相机
- 基础灯光

工具优先走 Maya 原生 GLB 读写；如果原生路径失败，再尝试 Maya glTF 插件；最后才使用 Blender 后台转换兜底。

## 安装

在 Maya Script Editor 的 Python 标签页执行：

```python
import runpy
runpy.run_path(r"H:\cjiaoben\MayaScriptTools\glb工具maya\install.py", run_name="__main__")
```

安装完成后，当前 Shelf 会出现 `GLB` 按钮。

## 临时运行

如果不想安装，可以直接在 Maya Script Editor 中运行最新版：

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

## 使用方式

主界面保留三个常用按钮：

- `导入`：弹出文件窗口，选择 `.glb/.gltf`
- `导出选中`：先选择 Maya 模型，再指定 `.glb` 保存路径
- `导出全场景`：导出当前场景中的模型、基础相机和基础灯光

第一次测试建议：

1. 新建或打开 Maya 项目。
2. 准备一个带 UV、贴图、软硬边的简单模型。
3. 点击 `导出选中` 导出为 `.glb`。
4. 新建空场景。
5. 点击 `导入` 导回刚才的 `.glb`。
6. 检查模型、UV、贴图、材质、软硬边是否符合预期。

## v1.0.0 已实现

- Maya 原生 GLB 导入/导出优先
- Maya glTF 插件和 Blender 后台转换兜底
- 静态 mesh
- UV
- face-vertex normals
- 顶点色 `COLOR_0`
- 多 primitive 合并导入
- 多材质按面分配导入/导出
- `standardSurface` 优先 PBR 映射
- baseColor / normal / metallicRoughness / emissive 贴图
- 透明度基础信息
- sampler `wrapS / wrapT` 基础映射
- glTF 节点 `matrix / TRS`
- 基础相机
- `KHR_lights_punctual` 基础灯光
- glTF `name / extras` 元数据保留
- GLB 导出后基础自校验

## 已知限制

- 不保证恢复四边面拓扑，glTF/GLB 通常以三角面表达
- 骨骼、蒙皮、动画尚未完整支持
- morph target / blendShape 尚未支持
- Draco 压缩尚未支持
- KTX2 / BasisU 尚未支持
- 多 UV 集尚未完整支持
- 切线尚未完整导入/导出
- 复杂 Arnold/材质网络目前只做基础映射

## 相关文件

- 工具入口：[glb工具maya/README.md](/h:/cjiaoben/MayaScriptTools/glb工具maya/README.md:1)
- 开发排查：[docs/Maya_GLB工具_开发排查记录.md](/h:/cjiaoben/MayaScriptTools/docs/Maya_GLB工具_开发排查记录.md:1)
- 工具目录：[glb工具maya](/h:/cjiaoben/MayaScriptTools/glb工具maya)
