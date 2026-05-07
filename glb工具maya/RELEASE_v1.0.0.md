# Maya GLB 导入导出工具 v1.0.0 发布说明

## 定位

第一版可测试交付。目标是让 Maya 可以直接导入/导出常见静态 GLB 资产，并尽量保留 UV、贴图、软硬边、多材质、基础相机和基础灯光。

## 安装

在 Maya Script Editor 的 Python 标签页执行：

```python
import runpy
runpy.run_path(r"H:\cjiaoben\MayaScriptTools\glb工具maya\install.py", run_name="__main__")
```

安装完成后，当前 Shelf 会出现 `GLB` 按钮。

## 使用

打开工具后：

- 点击 `导入`，选择 `.glb/.gltf`。
- 选择 Maya 模型后点击 `导出选中`，指定 `.glb` 保存路径。
- 点击 `导出全场景`，导出场景中的模型、基础相机和基础灯光。

## v1.0.0 已实现

- Maya 原生 GLB 导入/导出优先。
- Maya glTF 插件和 Blender 后台转换作为兜底。
- 静态 mesh。
- UV。
- face-vertex normals，用于软硬边显示。
- 顶点色 `COLOR_0`。
- 多 primitive 合并导入。
- 多材质按面分配导入/导出。
- `standardSurface` 优先 PBR 映射。
- baseColor 贴图。
- normal 贴图。
- metallicRoughness 贴图。
- emissive 贴图。
- 透明度基础信息。
- sampler wrapS / wrapT 基础映射。
- glTF 节点 matrix / TRS 变换。
- 基础相机。
- `KHR_lights_punctual` 基础灯光。
- glTF `name` / `extras` 元数据保留到 Maya 自定义属性。
- GLB 导出后基础自校验。

## 已知限制

- 不保证恢复四边面拓扑。glTF/GLB 通常以三角面表达。
- 骨骼、蒙皮、动画尚未完整支持。
- morph target / blendShape 尚未支持。
- Draco 压缩尚未支持。
- KTX2 / BasisU 尚未支持。
- 多 UV 集尚未完整支持。
- 切线尚未完整导入/导出。
- 复杂 Arnold/材质网络只能做基础映射。

## 建议测试顺序

1. 单模型无材质导入/导出。
2. 带 UV 和 baseColor 贴图模型。
3. 软硬边模型。
4. 多材质按面分配模型。
5. normal map 模型。
6. 透明贴图模型。
7. 顶点色模型。
8. 带相机/灯光场景。

## 开发排查

后续维护请先阅读：

```text
DEVELOPMENT_NOTES.md
```
