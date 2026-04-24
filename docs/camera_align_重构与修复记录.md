# Camera Align Maya 插件重构与问题修复记录

> 适用范围：Maya 2022+  
> 插件目标：将 Maya `persp` 相机快速对齐到选中多边形面的法线方向，并提供 UI、Shelf、快捷键操作入口。  
> 当前最终方案：UI + Shelf 按钮 + Alt / Ctrl+Alt 快捷键共存。  
> 当前最终脚本：`脚本/相机工具/相机对齐_一键安装_UI快捷键.py`

---

## 1. 项目背景

原始插件来源为 `camera_align.pyc` 编译文件，没有源码。本次工作基于反编译和功能还原，将其重构为可维护的 Python 源码，并逐步增加 UI、Shelf 按钮和快捷键安装逻辑。

原始插件主要功能：选择一个多边形面，将 `persp` 相机对齐到该面的法线方向，自动切换为正交相机，可围绕当前视线方向旋转相机，并可恢复到原始透视相机状态。

---

## 2. 当前已实现功能

### 2.1 相机对齐功能

当前已保留并重构原始核心功能：

```python
Camera_Align().set_align_mode()
Camera_Align().rotate_cam(angle=22.5)
Camera_Align().remove_align_mode()
```

对应功能：

- `set_align_mode()`：读取当前选择的多边形面，计算面法线、面中心、面切线方向，将 `persp` 相机移动并旋转到面法线方向，切换为 Orthographic 正交视图，并记录原始相机位置、方向、视野参数，用于恢复。
- `rotate_cam(angle=22.5)`：在对齐模式下旋转相机，默认旋转步长为 `22.5°`，支持 UI 输入自定义步长。
- `remove_align_mode()`：退出对齐模式，恢复 `persp` 相机原始位置和透视状态，并恢复网格显示状态。
- `align_obj_to_cam_plane()`：原始 `.pyc` 中该方法未真正实现，当前版本保留占位接口，避免破坏旧调用。

---

### 2.2 UI 工具窗口

已实现 Maya UI 窗口入口：

```python
import camera_align
camera_align.show_camera_align_ui()
```

UI 当前功能：

- 对齐到当前选中面。
- 顺时针旋转。
- 逆时针旋转。
- 恢复透视相机。
- 旋转步长输入框。
- 旋转步长预设按钮：`15°`、`22.5°`、`45°`、`90°`。
- 状态提示条。
- 创建 / 更新 Shelf 按钮。
- 关闭窗口。

当前 UI 已优化：

- 使用 `scrollLayout` 解决窗口内容裁剪问题。
- 默认窗口尺寸调整为 `430 × 560`。
- 底部按钮区域不再被裁剪。
- UI 分为标题区、状态区、主要操作、旋转设置、工具入口。
- 安装成功提示不再显示冗长的 `NameCommand` 绑定明细。

---

### 2.3 Shelf 按钮

已实现 Shelf 按钮创建：

```python
camera_align.create_or_update_shelf_button()
```

Shelf 按钮信息：

- 按钮名称：`CamAlign`
- 功能：打开 `Camera Align` UI 窗口。
- 若按钮被删除，可在 UI 中点击“创建 / 更新 Shelf”重新生成。

Shelf 按钮执行逻辑：

```python
import importlib
import camera_align
importlib.reload(camera_align)
camera_align.show_camera_align_ui()
```

注意：Shelf 按钮用于打开 UI，可以 `reload`；快捷键操作不建议每次 `reload(camera_align)`，否则可能清空对齐状态。

---

### 2.4 快捷键功能

当前最终快捷键：

| 功能 | 主快捷键 | 备用快捷键 |
|---|---|---|
| 对齐到当前选中面 | `Alt + Q` | `Ctrl + Alt + Q` |
| 顺时针旋转 | `Alt + W` | `Ctrl + Alt + W` |
| 逆时针旋转 | `Alt + E` | `Ctrl + Alt + E` |
| 恢复透视相机 | `Alt + R` | `Ctrl + Alt + R` |

备用快捷键存在原因：`Alt` 组合键在 Windows / Maya 菜单中可能被截获，`Alt+W` 尤其容易与窗口菜单或系统菜单冲突，所以保留 `Ctrl+Alt+Q/W/E/R` 作为稳定备用方案。

快捷键触发方式最终采用：

```mel
python("import camera_align; camera_align.align_camera_to_selected_polygon()");
```

而不是直接执行 Python 语句。

---

## 3. 版本演进记录

### 3.1 原始阶段：`camera_align.pyc`

状态：只有 `.pyc` 编译文件，没有源码，功能依赖热键调用，使用方式不够透明，后续难维护。

已还原功能：面法线相机对齐、正交视图切换、旋转相机、恢复相机、Manipulator 屏幕空间方向调整。

---

### 3.2 源码重构版：`camera_align.py`

目标：将 `.pyc` 重构为可读源码，兼容 Maya 2022+，保留原始类名和方法名。

保留接口：

```python
Camera_Align().set_align_mode()
Camera_Align().rotate_cam(22.5)
Camera_Align().rotate_cam(-22.5)
Camera_Align().remove_align_mode()
```

新增便捷接口：

```python
align_camera_to_selected_polygon()
rotate_aligned_camera_clockwise()
rotate_aligned_camera_counter_clockwise()
restore_perspective_camera()
```

---

### 3.3 快捷键一键安装版

最早尝试自动写入 `camera_align.py`，自动绑定 `Ctrl+Alt+1/2/3/4`，后续调整为 `Alt+Q/W/E/R`。

遇到问题：

```text
自动保存标志必须单独使用
```

错误写法：

```python
cmds.hotkey(
    keyShortcut="q",
    altModifier=True,
    name="xxx",
    autoSave=True
)
```

正确写法：

```python
cmds.hotkey(
    keyShortcut="q",
    altModifier=True,
    name="xxx"
)

cmds.hotkey(autoSave=True)
```

---

### 3.4 UI NoHotkeys 版

根据需求，暂时取消快捷键功能，增加 UI 按钮，保留快捷键代码，后续再启用。

结果：UI 可以使用，Shelf 可以打开 UI，快捷键不会自动安装。这个版本叫 `ModernUI_NoHotkeys`，所以按快捷键无效是设计结果，不是错误。

---

### 3.5 快捷键修复版 v4 / v5

v4 目标：重新启用快捷键，创建自定义 Hotkey Set，避免默认 Hotkey Set 锁定导致写入失败，查询热键绑定结果。

遇到问题：

```text
camera_align.align_camera_to_selected_polygon();
// 错误: Line 2.47: Syntax error
```

原因：Maya 热键触发链路把命令当成 MEL 解析，直接写 Python 语句会被 MEL 判定为语法错误。

v5 修复：将快捷键命令改为 MEL 调 Python：

```mel
python("import camera_align; camera_align.align_camera_to_selected_polygon()");
```

同时 `nameCommand` 使用：

```python
sourceType="mel"
```

最终测试成功。

---

### 3.6 最终整合版 v6

最终整合内容：UI 裁剪修复、快捷键安装、Shelf 创建、成功提示简化、`Alt+Q/W/E/R` 和 `Ctrl+Alt+Q/W/E/R` 同时绑定、使用补丁块追加方式更新已有 `camera_align.py`。

补丁块标记：

```python
PATCH_BEGIN = "# --- CAMERA ALIGN UI HOTKEY PATCH BEGIN v6 ---"
PATCH_END = "# --- CAMERA ALIGN UI HOTKEY PATCH END v6 ---"
```

作用：避免多次安装导致重复代码。每次安装前会先移除旧补丁块，再追加新补丁。

---

## 4. 已修复问题清单

### 问题 1：`autoSave` 报错

报错：

```text
RuntimeError: 自动保存标志必须单独使用
```

原因：`cmds.hotkey(autoSave=True)` 不能和具体键位绑定参数放在同一次调用中。

修复：

```python
cmds.hotkey(keyShortcut="q", altModifier=True, name=name_command)
cmds.hotkey(autoSave=True)
```

---

### 问题 2：快捷键安装后无法触发

原因：使用的是 `NoHotkeys` 安装器。该版本只安装 UI，不调用：

```python
install_hotkeys()
```

修复：最终版安装器会自动调用：

```python
module.install_hotkeys(show_dialog=False)
```

---

### 问题 3：热键查询显示 `<query failed>`

截图中出现：

```text
Alt+Q 原绑定: <query failed>
Alt+Q 新绑定: <query failed>
```

原因：`cmds.hotkey` 查询写法不稳定。

修复为更稳定的写法：

```python
cmds.hotkey(
    "q",
    query=True,
    altModifier=True,
    name=True
)
```

---

### 问题 4：热键触发时报 MEL 语法错误

报错：

```text
camera_align.align_camera_to_selected_polygon();
// 错误: Line 2.47: Syntax error
```

原因：热键触发时，Maya 把 Python 语句当成 MEL 解析。

错误命令：

```python
command="import camera_align\ncamera_align.align_camera_to_selected_polygon()"
sourceType="python"
```

修复命令：

```python
command='python("import camera_align; camera_align.align_camera_to_selected_polygon()");'
sourceType="mel"
```

---

### 问题 5：默认 Hotkey Set 可能不可写

表现：脚本看似运行成功，但快捷键没有真正绑定，或重启 Maya 后丢失。

原因：Maya 默认热键集可能是锁定状态，不适合直接写入。

修复：创建专用 Hotkey Set：

```python
HOTKEY_SET_NAME = "CameraAlign_HotkeySet"

if cmds.hotkeySet(HOTKEY_SET_NAME, exists=True):
    cmds.hotkeySet(HOTKEY_SET_NAME, edit=True, current=True)
else:
    cmds.hotkeySet(HOTKEY_SET_NAME, source=current_set, current=True)
```

---

### 问题 6：`nameCommand` 旧命令无法更新

原因：`nameCommand` 不适合反复 edit。同名命令已存在时，新的 command 内容可能不会更新。

修复：每个修复版本使用新后缀：

```python
HOTKEY_VERSION = "v6"
```

生成命令名：

```python
CameraAlign_Align_Alt_v6_NameCommand
CameraAlign_RotateCW_Alt_v6_NameCommand
```

这样避免旧 `nameCommand` 污染新绑定。

---

### 问题 7：`Alt+W` 可能无效

原因：`Alt` 组合键可能被 Windows / Maya 菜单系统截获。

修复：同时绑定备用快捷键：

```text
Ctrl+Alt+Q/W/E/R
```

建议测试顺序：先测试 `Alt+Q/W/E/R`；如果某个无效，测试 `Ctrl+Alt+Q/W/E/R`；如果快捷键仍无效，先点击 Maya 视口，避免 Script Editor 获得焦点。

---

### 问题 8：UI 底部内容被裁剪

表现：工具入口区域被裁剪，底部按钮无法完整显示，窗口高度不足时内容丢失。

修复：

```python
mc.scrollLayout(childResizable=True, horizontalScrollBarThickness=0)
mc.window(WINDOW_NAME, title=WINDOW_TITLE, sizeable=True, widthHeight=(430, 560))
```

同时压缩工具入口区域，调整控件宽度：按钮列宽 `188`、旋转输入区域宽度 `235`、预设按钮宽度 `92`。

---

### 问题 9：安装成功提示内容过多

表现：安装成功提示显示了大量：

```text
CameraAlign_Align_Alt_v5_NameCommand
CameraAlign_RotateCW_Alt_v5_NameCommand
...
```

问题：这些内容对最终用户没有意义，只适合调试。

修复：最终提示只保留 UI 入口、快捷键、备用快捷键、Shelf 状态、使用提示。

---

### 问题 10：快捷键中使用 `reload(camera_align)` 会清空状态

原因：相机对齐状态保存在模块级变量 `_STATE` 中。如果每次按快捷键都执行：

```python
importlib.reload(camera_align)
```

会重置 `_STATE`，导致旋转和恢复失败。

修复：快捷键命令不使用 `reload`：

```mel
python("import camera_align; camera_align.rotate_aligned_camera_clockwise()");
```

Shelf 按钮可以使用 `reload`，因为它只是打开 UI，不负责连续对齐状态操作。

---

## 5. 当前最终脚本结构说明

当前最终脚本不是完整重写 `camera_align.py`，而是执行以下流程：

1. 导入现有 `camera_align`。
2. 找到 `camera_align.py` 文件路径。
3. 移除旧补丁块。
4. 追加 v6 补丁块。
5. `importlib.reload(camera_align)`。
6. 创建 / 更新 Shelf。
7. 调用 `install_hotkeys(show_dialog=False)`。
8. 打开 UI。
9. 弹出简洁完成提示。

核心流程：

```python
module = _import_camera_align()
py_path = _get_camera_align_py_path(module)
_patch_camera_align_file(py_path)

importlib.invalidate_caches()
module = importlib.reload(module)

module.create_or_update_shelf_button()
module.install_hotkeys(show_dialog=False)
module.show_camera_align_ui()
```

---

## 6. 当前最终快捷键绑定逻辑

命令表：

```python
commands = [
    ("Align", "q", "对齐到当前选中面",
     'python("import camera_align; camera_align.align_camera_to_selected_polygon()");'),

    ("RotateCW", "w", "顺时针旋转 22.5 度",
     'python("import camera_align; camera_align.rotate_aligned_camera_clockwise()");'),

    ("RotateCCW", "e", "逆时针旋转 22.5 度",
     'python("import camera_align; camera_align.rotate_aligned_camera_counter_clockwise()");'),

    ("Restore", "r", "恢复透视相机",
     'python("import camera_align; camera_align.restore_perspective_camera()");'),
]
```

组合键：

```python
combos = [
    ("Alt", dict(alt=True, ctrl=False, shift=False)),
    ("CtrlAlt", dict(alt=True, ctrl=True, shift=False)),
]
```

安装流程：

```python
active_set = _ca_ensure_hotkey_set()

for command_id, key, label, mel_command in commands:
    for combo_name, mods in combos:
        nc = _ca_name_command(command_id, combo_name, label, mel_command)
        _ca_bind_hotkey(key, nc, **mods)
```

保存：

```python
mc.hotkey(autoSave=True)
mc.savePrefs(hotkeys=True)
```

---

## 7. 当前最终 UI 结构

UI 入口：

```python
show_camera_align_ui()
```

主要结构：

```text
window
└── scrollLayout
    └── columnLayout
        ├── 标题区
        ├── 状态条
        ├── 主要操作 frameLayout
        │   ├── 对齐到当前选中面
        │   ├── 顺时针旋转 / 逆时针旋转
        │   └── 恢复透视相机
        ├── 旋转设置 frameLayout
        │   ├── 旋转步长 floatField
        │   └── 15 / 22.5 / 45 / 90 预设
        └── 工具入口 frameLayout
            ├── 创建 / 更新 Shelf
            └── 关闭窗口
```

关键修复：

```python
scroll = mc.scrollLayout(childResizable=True, horizontalScrollBarThickness=0)
win = mc.window(WINDOW_NAME, title=WINDOW_TITLE, sizeable=True, widthHeight=(430, 560))
```

---

## 8. 后续排查流程

### 8.1 UI 无法打开

检查：

```python
import camera_align
camera_align.show_camera_align_ui()
```

若失败：确认 `camera_align.py` 在用户 scripts 目录；确认 Maya Script Editor 使用 Python 标签；执行以下命令查看用户 scripts 目录是否在路径里：

```python
import sys
print(sys.path)
```

---

### 8.2 快捷键无效

检查顺序：执行最终安装脚本，确认安装完成提示出现，点击 Maya 视口，测试 `Alt+Q`，再测试 `Ctrl+Alt+Q`。如果仍不生效，检查当前 Hotkey Set：

```python
import maya.cmds as cmds
print(cmds.hotkeySet(q=True, current=True))
```

应为：

```text
CameraAlign_HotkeySet
```

---

### 8.3 热键触发但报 Syntax Error

说明又回到了错误命令格式。

正确格式：

```mel
python("import camera_align; camera_align.align_camera_to_selected_polygon()");
```

错误格式：

```python
camera_align.align_camera_to_selected_polygon()
```

---

### 8.4 旋转或恢复无效

可能原因：没有先执行对齐；快捷键命令中误用了 `importlib.reload(camera_align)`；`_STATE` 被重置。

检查快捷键命令中是否存在：

```python
importlib.reload(camera_align)
```

如果存在，应去掉。

---

### 8.5 UI 又出现裁剪

优先检查：

```python
mc.window(WINDOW_NAME, title=WINDOW_TITLE, sizeable=True, widthHeight=(430, 560))
mc.scrollLayout(childResizable=True, horizontalScrollBarThickness=0)
```

如果改小窗口尺寸，应保留 `scrollLayout`。

---

## 9. 后续修改建议

### 9.1 若要改快捷键

只改这里：

```python
commands = [...]
combos = [...]
```

例如改成 `Shift+Q/W/E/R`：

```python
combos = [
    ("Shift", dict(alt=False, ctrl=False, shift=True)),
]
```

并建议更新：

```python
HOTKEY_VERSION = "v7"
```

避免旧 `nameCommand` 污染。

---

### 9.2 若要改 UI 尺寸

优先改：

```python
widthHeight=(430, 560)
```

建议不要低于：

```python
widthHeight=(400, 520)
```

否则 Maya 旧主题下可能仍然裁剪。

---

### 9.3 若要改旋转默认值

改 UI 默认值：

```python
mc.floatField(ROTATE_FIELD_NAME, value=22.5, precision=3, minValue=0.001)
```

改快捷键默认值需要改便捷函数或快捷键命令。当前默认仍是 `22.5°`。

---

### 9.4 若要做 Dock 停靠面板

当前是普通 `window`。后续可改为 `workspaceControl` 或 Maya 自定义 Dockable UI。

注意：Maya 2022+ 的 workspaceControl 状态保存可能导致旧 UI 缓存，需要增加删除旧 workspaceControl 的逻辑。

---

## 10. 重要注意事项

### 10.1 不要删除原始核心接口

旧热键和旧调用可能依赖：

```python
Camera_Align().set_align_mode()
Camera_Align().rotate_cam()
Camera_Align().remove_align_mode()
```

这些接口需要保留。

---

### 10.2 不要在旋转 / 恢复热键中 reload 模块

错误：

```python
import importlib
import camera_align
importlib.reload(camera_align)
camera_align.rotate_aligned_camera_clockwise()
```

原因：`reload` 会清空 `_STATE`。

正确：

```python
import camera_align
camera_align.rotate_aligned_camera_clockwise()
```

---

### 10.3 Hotkey Set 必须考虑默认集锁定

不要直接假设默认 Hotkey Set 可写。应使用：

```python
CameraAlign_HotkeySet
```

---

### 10.4 nameCommand 每次大改建议换版本号

例如：

```python
HOTKEY_VERSION = "v7"
```

避免 Maya 内部缓存旧命令。

---

### 10.5 Alt 快捷键不是 100% 稳定

部分环境下 `Alt+W`、`Alt+Q` 可能被菜单或系统截获。因此保留备用：

```text
Ctrl+Alt+Q/W/E/R
```

---

## 11. 当前最终可交付文件建议

建议保留以下文件：

```text
脚本/相机工具/相机对齐_一键安装_UI快捷键.py
docs/camera_align_重构与修复记录.md
```

可选保留：

```text
脚本/相机工具/camera_align.py
docs/Camera_Align_ModernUI_说明.txt
脚本/相机工具/相机对齐_快捷键修复_v5_MEL调用Python.py
```

不建议继续使用：

```text
相机对齐_一键安装_仅UI无快捷键.py
相机对齐_现代UI_无快捷键.py
相机对齐_启用AltQWER快捷键补丁.py
```

原因：NoHotkeys 版本不会启用快捷键；早期 Patch 版本存在 MEL / Python 解析问题；最终 v6 已整合 UI、Shelf、快捷键和提示优化。

---

## 12. 最终使用流程

用户侧使用：

1. 安装基础 Camera Align UI 版，确保 Maya 可以：

```python
import camera_align
```

2. 拖入最终脚本：

```text
脚本/相机工具/相机对齐_一键安装_UI快捷键.py
```

3. 安装完成后使用：

```text
Shelf 按钮 CamAlign
Alt+Q / W / E / R
Ctrl+Alt+Q / W / E / R
```

4. 操作顺序：

```text
选择多边形面
Alt+Q 对齐
Alt+W / Alt+E 旋转
Alt+R 恢复
```

---

## 13. 快速错误对照表

| 报错 / 现象 | 原因 | 修复方式 |
|---|---|---|
| `自动保存标志必须单独使用` | `autoSave=True` 和热键绑定参数放在同一次 `hotkey()` 调用 | 单独执行 `cmds.hotkey(autoSave=True)` |
| 快捷键完全无效 | 使用了 `NoHotkeys` 安装器 | 使用最终 v6 脚本或调用 `install_hotkeys()` |
| `<query failed>` | 热键查询参数写法不稳定 | 使用位置参数查询：`cmds.hotkey("q", query=True, ...)` |
| `Line 2.47: Syntax error` | Python 命令被 MEL 解析 | 使用 `python("...");` 包裹 Python |
| Alt+W 无效 | 被 Maya / Windows 菜单截获 | 使用 `Ctrl+Alt+W` |
| 旋转无效 | 没有先对齐，或 `_STATE` 被 reload 清空 | 先对齐；快捷键中不要 reload |
| UI 底部裁剪 | 窗口高度不足，没有滚动容器 | 使用 `scrollLayout` 和 `430×560` |
| 安装提示信息太多 | 显示了 nameCommand 调试信息 | 最终版只显示用户必要信息 |
| 重启后热键丢失 | 没保存 hotkey prefs 或 Hotkey Set 不正确 | `hotkey(autoSave=True)` + `savePrefs(hotkeys=True)` |
| 默认热键集不可写 | Maya 默认 Hotkey Set 锁定 | 创建 `CameraAlign_HotkeySet` |

---

## 14. 维护原则

后续维护时建议遵守：

1. UI 入口、快捷键入口、核心相机逻辑分开维护。
2. 快捷键不要直接执行 Python 语句，统一使用 MEL `python("...");`。
3. 大改快捷键时更新 `HOTKEY_VERSION`。
4. 安装提示只保留用户需要的信息。
5. 旋转和恢复依赖 `_STATE`，不要在快捷键中 reload。
6. UI 尺寸调整时保留 scrollLayout。
7. 旧补丁块必须通过 `PATCH_BEGIN / PATCH_END` 移除后再写入。

---

## 15. 当前状态总结

当前插件已经实现：

- 原始 Camera Align 核心功能。
- Maya 2022+ 源码化。
- 现代化 UI。
- Shelf 按钮入口。
- 快捷键入口。
- 备用快捷键入口。
- 安装成功提示简化。
- UI 裁剪修复。
- MEL / Python 热键解析问题修复。
- Hotkey Set 锁定问题规避。
- nameCommand 旧命令污染规避。

当前仍需注意：

- 最终脚本依赖已有 `camera_align.py` 可导入。
- 纯 `Alt` 快捷键在部分系统中可能被截获，因此保留 `Ctrl+Alt` 备用。
- 原始 `align_obj_to_cam_plane()` 仍未实现，仅保留占位。
