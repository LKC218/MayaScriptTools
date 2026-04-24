# Maya Python 脚本编写规范

> 适用范围：Maya 2022+、Python 3、项目内所有 `.py` 工具脚本。  
> 目标：让后续 Maya 脚本可读、可装、可回滚、可维护，避免把临时脚本写成不可控的用户环境补丁。

---

## 1. 基础原则

### 1.1 优先级

1. 先满足当前工具需求，不做无明确收益的框架化封装。
2. 优先使用 Maya 官方能力：`maya.cmds`、`maya.api.OpenMaya`、Maya UI 命令、Maya 用户脚本目录。
3. 能用稳定公开 API 解决的，不解析 Script Editor 输出文本。
4. 任何会修改场景、偏好、快捷键、Shelf、文件系统的功能，都必须有明确函数入口和错误提示。

### 1.2 文件编码

所有脚本必须使用 UTF-8：

```python
# -*- coding: utf-8 -*-
```

文件名建议使用英文、数字、下划线，避免 Maya、Windows、插件加载器在非中文系统下出现路径兼容问题。

推荐：

```text
camera_align.py
mesh_cleanup_tool.py
batch_export_fbx.py
```

不推荐：

```text
相机对齐工具最终最终版.py
```

---

## 2. 文件结构规范

单文件工具建议采用以下结构：

```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import traceback

import maya.cmds as cmds

TOOL_NAME = "Camera Align"
WINDOW_NAME = "CameraAlignWindow"


def _info(message):
    print("{}: {}".format(TOOL_NAME, message))


def validate_selection():
    """返回业务需要的选择对象；不合格时抛出 RuntimeError。"""
    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        raise RuntimeError("请先选择对象。")
    return selection


def run_tool():
    selection = validate_selection()
    # 执行业务逻辑
    return selection


def show_ui():
    # 创建 UI
    pass


if __name__ == "__main__":
    show_ui()
```

要求：

- 常量放在文件顶部。
- 入口函数必须清晰，例如 `show_ui()`、`install()`、`run()`。
- 不允许 import 时直接修改场景、创建快捷键、写文件或弹窗。
- 只在 `if __name__ == "__main__":`、Shelf 命令或显式入口里执行动作。

---

## 3. `maya.cmds` 使用规范

### 3.1 导入方式

推荐：

```python
import maya.cmds as cmds
```

禁止：

```python
from maya.cmds import *
```

原因：Autodesk 文档提示，将 `maya.cmds` 导入顶层命名空间会覆盖 Python 内建或其他模块定义，增加排查成本。

### 3.2 命令参数

Maya Python 命令参数遵循 Python 调用方式：

```python
cmds.sphere(radius=4)
cmds.ls(selection=True)
cmds.move(2.0, 1.0, 1.0, "pCube1", objectSpace=True)
```

规则：

- 没有参数值的 MEL flag，在 Python 中写成布尔值：`selection=True`。
- 多值 flag 使用 tuple 或 list：`rgb=(0.2, 0.3, 0.4)`。
- 对象参数必须放在命名参数前面。
- 查询统一使用 `query=True` 或 `q=True`，但同一文件内风格必须一致。

---

## 4. API 选择规范

### 4.1 默认使用 `maya.cmds`

适合：

- UI。
- 简单建模命令。
- 选择、属性、变换、约束、导入导出。
- Shelf、Hotkey、Preference 操作。

### 4.2 几何和高频计算使用 Python API 2.0

推荐：

```python
import maya.api.OpenMaya as om
```

适合：

- 顶点、边、面遍历。
- 法线、矩阵、向量计算。
- 大量节点或组件操作。
- 对性能敏感的工具。

规则：

- 新 API 对象与旧 API 对象不能混用。
- 一个脚本优先只使用 `maya.api.OpenMaya`，不要同时混用 `maya.OpenMaya`。
- 插件类如果使用 Python API 2.0，需要定义：

```python
maya_useNewAPI = True
```

---

## 5. 路径与安装规范

### 5.1 获取 Maya 用户目录

必须用 Maya 提供的路径接口，不硬编码用户路径：

```python
scripts_dir = cmds.internalVar(userScriptDir=True)
shelf_dir = cmds.internalVar(userShelfDir=True)
hotkey_dir = cmds.internalVar(userHotkeyDir=True)
```

### 5.2 `userSetup.py`

`userSetup.py` 只做轻量初始化：

- 可以追加 `sys.path`。
- 可以注册菜单入口。
- 不应直接打开复杂 UI。
- 不应导入大量业务模块。
- 不应在启动时改场景、改快捷键、弹阻塞确认框。

复杂初始化应延迟到用户点击菜单、Shelf 或调用入口函数时执行。

---

## 6. UI 编写规范

### 6.1 UI 通用强制规范

所有带界面的 Maya Python 脚本必须遵守：

- UI 所有可见文字必须以简体中文为标准，包括窗口标题、按钮、标签、提示、帮助说明和错误反馈。
- UI 面板必须优先设计为可停靠 / 可嵌入 Maya 工作区的面板；面板内的功能分组必须支持折叠，便于在小屏幕和复杂工作区中使用。
- UI 必须以现代化布局为基准：信息层级清晰、分组明确、间距统一、主次按钮区分明显，不使用杂乱堆叠式临时界面。
- 每个脚本必须提供“帮助”UI 按钮；帮助面板内容必须根据当前脚本功能定制，至少说明用途、操作步骤、选择要求、注意事项和常见错误处理。

推荐 UI 分组：

```text
标题区
状态提示区
主要操作区
参数设置区
高级选项区（可折叠）
帮助 / 工具入口区
```

### 6.2 `cmds` UI

小型工具优先使用 `cmds.window`：

```python
if cmds.window(WINDOW_NAME, exists=True):
    cmds.deleteUI(WINDOW_NAME, window=True)

window = cmds.window(WINDOW_NAME, title="Tool", sizeable=True)
cmds.columnLayout(adjustableColumn=True)
cmds.button(label="Run", command=lambda *_: run_tool())
cmds.showWindow(window)
```

规则：

- UI 控件名称必须有项目前缀，避免与其他工具冲突。
- 重建窗口前先判断 `exists=True`。
- 回调函数必须捕获异常并提示用户。
- UI 内不要直接写大段业务逻辑，只调用函数。
- 输入框数值必须校验范围和类型。
- 按钮、标签、状态栏必须使用简体中文。
- 功能分组优先使用 `frameLayout(collapsable=True)` 实现可折叠面板。
- 参数区不要和执行按钮混在一起，主操作按钮应放在用户最容易看到的位置。
- 必须提供帮助按钮，例如 `cmds.button(label="帮助", command=show_help_ui)`。

### 6.3 Dockable UI

需要停靠、记忆布局、随工作区恢复的工具，使用 `workspaceControl`。

注意：`workspaceControl` 的 `uiScript` 必须能在 Maya 下次启动恢复工作区时重新执行，因此里面调用的 Python 模块必须能被 import。

规则：

- 需要长期使用的工具不应只做浮动窗口，必须提供可停靠入口。
- 可停靠 UI 的内部布局仍需支持折叠分组。
- 如果工具功能简单，可以保留浮动窗口，但应在文档中说明暂不提供 Dock 的原因。

### 6.4 帮助面板规范

每个脚本必须提供帮助入口：

```python
def show_help_ui(*_):
    message = "\n".join([
        "工具用途：说明当前工具解决什么问题。",
        "",
        "操作步骤：",
        "1. 选择需要处理的对象。",
        "2. 设置参数。",
        "3. 点击执行。",
        "",
        "注意事项：说明会修改哪些场景内容。",
        "常见错误：说明无选择、选择类型错误等处理方式。",
    ])
    cmds.confirmDialog(title="帮助", message=message, button=["确定"])
```

帮助内容要求：

- 不允许使用通用模板敷衍，必须贴合当前脚本功能。
- 必须说明脚本是否会修改场景、偏好、快捷键、Shelf 或文件。
- 必须说明输入选择要求，例如对象、面、边、骨骼、材质或文件路径。
- 对批量工具，必须说明输出位置、覆盖策略和失败处理方式。

### 6.5 焦点规则

如果使用 Tkinter、PySide 或自定义弹窗，弹出后必须强制前置：

```python
window.raise_()
window.activateWindow()
```

如果是 Tkinter，可使用：

```python
root.lift()
root.focus_force()
```

长耗时逻辑不要阻塞 UI 线程；能拆分的任务应拆分或使用 Maya 安全的延迟执行方式。

---

## 7. 场景修改与 Undo 规范

会修改场景的操作必须纳入一个 undo chunk：

```python
def run_with_undo():
    cmds.undoInfo(openChunk=True, chunkName="My Tool")
    try:
        # 修改场景
        cmds.polyCube()
    finally:
        cmds.undoInfo(closeChunk=True)
```

规则：

- `openChunk` 后必须用 `finally` 关闭。
- 不要在异常路径留下未关闭的 undo chunk。
- 不要随意关闭全局 undo。
- 批量工具如需临时禁用 undo，必须在 `finally` 恢复原状态。

---

## 8. 选择与节点规范

### 8.1 不隐式依赖选择

底层函数应尽量接收显式参数：

```python
def freeze_transforms(nodes):
    for node in nodes:
        cmds.makeIdentity(node, apply=True, translate=True, rotate=True, scale=True)
```

入口函数可以读取当前选择：

```python
def freeze_selected():
    nodes = cmds.ls(selection=True, long=True) or []
    if not nodes:
        raise RuntimeError("请先选择对象。")
    freeze_transforms(nodes)
```

### 8.2 使用长路径

涉及场景节点时优先使用长路径：

```python
nodes = cmds.ls(selection=True, long=True) or []
```

原因：同名节点、引用、命名空间在生产文件中很常见，短名容易误操作。

### 8.3 修改前校验

任何节点操作前必须确认：

```python
if not cmds.objExists(node):
    raise RuntimeError("节点不存在：{}".format(node))
```

---

## 9. 快捷键与 Shelf 规范

### 9.1 Shelf 命令

Shelf 按钮只做入口，不写复杂逻辑：

```python
command = (
    "import importlib\n"
    "import my_tool\n"
    "importlib.reload(my_tool)\n"
    "my_tool.show_ui()\n"
)
```

规则：

- Shelf 可以 `reload`，方便开发调试。
- 会依赖运行状态的快捷键不要每次 `reload`，否则可能丢失内存状态。

### 9.2 Shelf 工具栏图标

后续新建的功能插件，凡是会创建 Shelf / 工具栏按钮，都必须提供专属图标，用于提升工具栏辨识度。

图标设计原则：

- 图标必须根据脚本核心功能生成，不能只使用通用字母、默认 `commandButton.png` 或无语义装饰图。
- 图标主体应表达工具的主要动作。例如相机对齐工具应体现“相机 + 多边形面 + 法线 / 对齐方向”。
- 文字缩写只能作为辅助识别，例如 `CA`，不能作为唯一主体。
- 图标只用于 Shelf / 工具栏按钮；普通 UI 面板按钮默认不增加图标，避免界面变复杂。
- 图标应适配 Maya 深色工具栏，优先使用高对比、少细节、32x32 下仍可识别的图形。
- 推荐输出 `32x32` PNG；必要时可额外准备 `64x64` 高分屏备用。

实现规范：

- 图标文件建议写入 `cmds.internalVar(userBitmapsDir=True)` 返回的 Maya 用户图标目录。
- Shelf 按钮优先使用专属图标，写入失败时回退到 `commandButton.png`。
- 可保留 `imageOverlayLabel` 作为辅助标签，但不能替代功能图标。
- 发布为单文件安装器时，推荐将 PNG 转为 base64 内嵌，安装时写入图标目录，避免外部素材丢失。

示例命名：

```python
SHELF_ICON_NAME = "my_tool_function_icon.png"
```

### 9.3 快捷键

快捷键使用 `nameCommand` + `hotkey`：

```python
cmds.nameCommand(
    "MyTool_Run_NameCommand",
    annotation="Run My Tool",
    command='python("import my_tool; my_tool.run()");',
    sourceType="mel",
)
cmds.hotkey(keyShortcut="q", altModifier=True, name="MyTool_Run_NameCommand")
cmds.hotkey(autoSave=True)
```

规则：

- `nameCommand` 名称必须带工具前缀。
- 绑定前应查询或清理旧绑定，避免重复覆盖不可知命令。
- `cmds.hotkey(autoSave=True)` 必须单独调用。
- Alt 组合键可能被系统或 Maya 菜单截获，重要工具应提供备用组合，例如 `Ctrl+Alt`。
- 若命令链路被 MEL 执行，使用 `python("...")` 包裹 Python 调用。

---

## 10. `scriptJob` 规范

`scriptJob` 必须可清理：

```python
job_id = cmds.scriptJob(
    event=["SelectionChanged", on_selection_changed],
    parent=WINDOW_NAME,
    replacePrevious=True,
)
```

规则：

- UI 相关 job 必须绑定 `parent`，UI 删除时自动清理。
- 场景相关 job 优先使用 `killWithScene=True`。
- 避免 `idleEvent`，Autodesk 文档明确提示它会在空闲时持续执行，可能占满 CPU。
- 创建 job 后保存 job id，必要时显式 kill。
- 高频事件回调内不要做重计算和文件 IO。

---

## 11. 时间与等待规范

禁止用 `sleep(1)` 累加计时：

```python
elapsed = 0
while elapsed < timeout:
    time.sleep(1)
    elapsed += 1
```

必须使用系统时间差：

```python
import time

start_time = time.time()
while time.time() - start_time < timeout:
    # 检查状态
    pass
```

原因：累计 sleep 会受调度、卡顿、UI 阻塞影响，误差会越来越大。

---

## 12. 异常处理与用户提示

工具入口必须捕获异常：

```python
def safe_run():
    try:
        run_tool()
    except Exception as exc:
        message = "执行失败：{}".format(exc)
        cmds.warning(message)
        print(traceback.format_exc())
```

规则：

- 给用户显示短错误。
- 给开发者输出 traceback。
- 不吞异常后假装成功。
- 批量工具必须统计成功、失败、跳过数量。

---

## 13. 命名规范

### 13.1 函数命名

使用小写加下划线：

```python
show_ui()
install_hotkeys()
create_shelf_button()
align_camera_to_face()
```

### 13.2 类命名

使用大驼峰：

```python
class CameraAlignTool:
    pass
```

### 13.3 Maya 控件命名

必须带项目前缀：

```python
WINDOW_NAME = "CameraAlignWindow"
STATUS_TEXT_NAME = "CameraAlignStatusText"
```

---

## 14. 注释与文档规范

必须写：

- 文件顶部用途说明。
- 公开入口函数说明。
- 非显而易见算法说明。
- 会改 Maya 偏好、快捷键、Shelf 的函数说明。

不写：

- “给变量赋值”这类无信息注释。
- 与代码不一致的历史注释。
- 大段无维护价值的聊天式说明。

---

## 15. 测试清单

每个 Maya 工具交付前至少检查：

- [ ] Maya Script Editor 能 import 模块。
- [ ] `show_ui()` 能打开 UI。
- [ ] 重复打开 UI 不报错、不重复堆控件。
- [ ] 无选择、错误选择、正确选择都有明确反馈。
- [ ] 修改场景后 Ctrl+Z 能按预期回退。
- [ ] Shelf 按钮能重新打开 UI。
- [ ] 快捷键能触发，并有备用快捷键。
- [ ] 重启 Maya 后工具仍可导入。
- [ ] 中文提示在 Script Editor 和 UI 中不乱码。
- [ ] 不把私人路径、用户配置、临时文件写入仓库。

---

## 16. 推荐模板

```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback

import maya.cmds as cmds

TOOL_NAME = "My Maya Tool"
WINDOW_NAME = "MyMayaToolWindow"


def info(message):
    print("{}: {}".format(TOOL_NAME, message))


def warn(message):
    cmds.warning("{}: {}".format(TOOL_NAME, message))


def run():
    cmds.undoInfo(openChunk=True, chunkName=TOOL_NAME)
    try:
        selection = cmds.ls(selection=True, long=True) or []
        if not selection:
            raise RuntimeError("请先选择对象。")

        # TODO: 编写核心功能
        info("执行完成。")
        return True
    finally:
        cmds.undoInfo(closeChunk=True)


def safe_run(*_):
    try:
        return run()
    except Exception as exc:
        warn("执行失败：{}".format(exc))
        print(traceback.format_exc())
        return False


def show_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME, window=True)

    window = cmds.window(WINDOW_NAME, title=TOOL_NAME, sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 8))
    cmds.button(label="执行", height=32, command=safe_run)
    cmds.showWindow(window)
    return window


if __name__ == "__main__":
    show_ui()
```

---

## 17. 资料来源

- Autodesk Maya Help：Using Python  
  https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Scripting/files/GUID-55B63946-CDC9-42E5-9B6E-45EE45CFC7FC.htm
- Autodesk Maya Python API 2.0 Reference  
  https://help.autodesk.com/cloudhelp/2024/ENU/MAYA-API-REF/py_ref/index.html
- Autodesk Maya Commands Python：hotkey  
  https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/hotkey.html
- Autodesk Maya Commands Python：nameCommand  
  https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/nameCommand.html
- Autodesk Maya Commands Python：scriptJob  
  https://download.autodesk.com/us/maya/docs/maya85/CommandsPython/scriptJob.html
- Autodesk Maya Commands Python：undoInfo  
  https://help.autodesk.com/cloudhelp/2022/ENU/Maya-Tech-Docs/CommandsPython/undoInfo.html
- Autodesk Maya Commands Python：internalVar  
  https://help.autodesk.com/cloudhelp/2017/CHS/Maya-Tech-Docs/CommandsPython/internalVar.html
- Autodesk Maya SDK：Writing Workspace controls  
  https://help.autodesk.com/cloudhelp/2022/ENU/Maya-SDK/Maya-Python-API/Writing-Workspace-controls.html
