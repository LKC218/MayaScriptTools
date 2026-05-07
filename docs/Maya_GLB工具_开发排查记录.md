# Maya GLB 工具开发排查记录

## 当前架构

导入优先级：

1. `maya_glb_native.import_glb()`
2. Maya 文件翻译器 / glTF 插件
3. Blender 后台：GLB/GLTF -> FBX -> Maya

导出优先级：

1. `maya_glb_native.export_glb()`，当前对 `.glb` 优先
2. Maya 文件翻译器 / glTF 插件
3. Blender 后台：Maya -> FBX -> GLB/GLTF

关键文件：

- `glb工具maya/maya_glb_tool.py`：UI 和主入口
- `glb工具maya/maya_glb_native.py`：Maya 原生 GLB 核心逻辑
- `glb工具maya/blender_glb_bridge.py`：Blender 兜底桥
- `glb工具maya/install.py`：安装脚本

## 已实现能力摘要

- GLB 2.0 JSON/BIN chunk 解析
- `.gltf` 外部 buffer / data URI 读取
- accessor `normalized / sparse / byteStride` 支持
- 静态 mesh 导入导出
- UV、法线、顶点色支持
- 多材质按面分配
- 多 primitive 合并导入
- baseColor / normal / metallicRoughness / emissive 基础贴图
- `standardSurface` 优先材质映射
- sampler `wrapS / wrapT` 基础映射
- glTF 节点 `matrix / translation / rotation / scale`
- 基础相机
- `KHR_lights_punctual` 基础灯光
- glTF `name / extras` 元数据保留
- 导出 GLB 自校验

## 已遇到并修复的问题

### Maya 没有 GLB/GLTF 文件翻译器

现象：

```text
当前 Maya 没有可用的 GLB/GLTF 文件翻译器
```

处理：

- 加入 `maya_glb_native.py`
- Maya 插件保留为第二路径
- Blender 只做最后兜底

### 安装脚本找错目录

现象：

```text
找不到工具文件：
C:\ProgramData\Autodesk\ApplicationPlugins\UnrealLiveLinkForMaya\Contents\maya_glb_tool.py
```

原因：

`exec(open(...).read())` 时 `__file__` 可能继承到别的插件目录。

处理：

- `install.py` 不再盲信 `__file__`
- 改为验证候选目录里是否存在全部工具文件
- 文档统一改用 `runpy.run_path(...)`

### Steam 版 Blender 无法直接浏览到 exe

原因：

桌面上是 `Blender.url`，不是 `blender.exe`。

处理：

- 增加 Steam 路径自动检测
- 浏览过滤改为 `Executable (*.exe);;All Files (*.*)`

### Blender 备用导入 namespace 非法

现象：

```text
名称空间名 "1" 包含非法字符
```

处理：

- 新增 `_safe_maya_name()`
- 数字开头自动补前缀
- 非法字符替换为下划线

### Blender 备用导入贴图丢失

原因：

GLB -> FBX 的临时目录删除后，Maya file 节点路径失效。

处理：

- 缓存目录改到 Maya 项目：
  `sourceimages/maya_glb_tool/<文件名>/`
- 按文件名自动重连贴图
- 现在优先走原生导入，进一步减少这类问题

### 软硬边显示不对

原因：

最初没有把 glTF `NORMAL` 写回 Maya face-vertex normals。

处理：

- 读取 `NORMAL`
- `setFaceVertexNormals()`
- `polyNormalPerVertex(..., freezeNormal=True)`

### glTF matrix 方向风险

原因：

glTF matrix 是列主序，Maya API 这里按行主序传值。

处理：

- `_matrix_from_node()` 中做列主序到行主序转换

### 多材质结构不理想

问题：

- 导出只取第一个材质会丢失按面材质
- 导入每个 primitive 一个 mesh 会碎对象

处理：

- 导出按 shadingEngine 面分配拆分多个 primitive
- 导入将同一个 glTF mesh 的多个 primitive 合并为一个 Maya mesh
- 再按面分配材质

## 当前限制

- 骨骼 joints 未完成
- skinCluster / 蒙皮权重未完成
- 动画未完成
- morph target / blendShape 未完成
- Draco 未完成
- KTX2 / BasisU 未完成
- 多 UV 集未完成
- 切线未完成
- 复杂 PBR / Arnold 网络只做基础映射
- 不保证恢复四边面拓扑

## 后续修改注意点

1. 优先修改 `glb工具maya/maya_glb_native.py`
2. 不要把 Blender 再抬回主路径
3. 修改 mesh 逻辑时，UV、normal、color、material 必须一起看
4. 修改 matrix 时要记住 glTF 列主序与 Maya 行主序差异
5. 修改安装脚本时不要依赖未经验证的 `__file__`

## 推荐自测

每次修改后至少跑：

```powershell
& "D:\Steam\steamapps\common\Blender\blender.exe" --background --python-expr "import py_compile; files=[r'H:\cjiaoben\MayaScriptTools\glb工具maya\maya_glb_native.py', r'H:\cjiaoben\MayaScriptTools\glb工具maya\maya_glb_tool.py', r'H:\cjiaoben\MayaScriptTools\glb工具maya\blender_glb_bridge.py', r'H:\cjiaoben\MayaScriptTools\glb工具maya\install.py']; [py_compile.compile(f, doraise=True) for f in files]; print('PY_COMPILE_OK')"
```

Maya 内建议按顺序测试：

1. 单模型无材质
2. 带 UV 和贴图模型
3. 软硬边模型
4. 多材质按面分配模型
5. normal map 模型
6. 透明贴图模型
7. 顶点色模型
8. 相机场景
9. 点光 / 聚光 / 平行光场景

## 相关文档

- 发布说明：[docs/Maya_GLB工具_v1.0.0_使用与发布说明.md](/h:/cjiaoben/MayaScriptTools/docs/Maya_GLB工具_v1.0.0_使用与发布说明.md:1)
- 工具说明：[glb工具maya/README.md](/h:/cjiaoben/MayaScriptTools/glb工具maya/README.md:1)
