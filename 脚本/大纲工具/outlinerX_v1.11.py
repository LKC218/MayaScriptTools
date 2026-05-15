## 脚本名称 : outliner X
## 内容     : Outliner X 是一个可停靠的 Maya 大纲工具，
##            用于更快地整理、裁剪、排序和颜色管理场景层级。
##            内嵌 QShade 面板，便于快速浏览和指定材质。
## 作者     : Joe Wu
## 链接     : https://www.youtube.com/@Im3dJoe
## 起始时间 : 2026/03
## 版本     : 1.10 公开测试
##              1.01 添加选择层级功能，修复展开一级的错误
##              1.02 在选择层级按钮上添加弹出菜单：
##                   locator / joint / mesh / curve / surface / camera / light / group
##              1.03 优化选择层级弹出菜单行为：
##                   左键需要先有选择
##                   弹出类型选择会在当前已选层级内搜索，
##                   未选择时搜索整个场景
##                   始终选择 transform / joint 层级，而不是 shape
##                   弹出菜单中增加相似模型选择
##              1.07 在大纲下方添加内嵌 QShade 面板
##                   大纲和 QShade 之间使用分割布局
##                   可滚动的材质网格
##                   快速指定 / 克隆 / 删除未用 / 刷新材质
##                   紧凑材质块界面
##              1.08 添加大纲水平 / 垂直分割切换
##              1.09 为拆分的大纲窗格添加同步上下滚动按钮
##              1.10 使用 QWheelEvent 兜底修复同步滚动，
##                   处理主窗格 Qt 滚动条被分割器销毁的情况
##                   在这里控制速度
##                   OUTLINER_SCROLL_PX = 0.5# 每次滚动条点击的像素数（约 1 行）
##                   OUTLINER_SCROLL_ROWS = 2  # 每次上下滚动的行数
##              1.11 QShade 网格在刷新时会根据当前面板宽度
##                   重新计算每行列数
## 其他说明 : 已在 Maya 2023 Windows 环境测试
## 安装方式 : 将脚本复制粘贴到 Maya 脚本编辑器的 Python 标签页中运行

import maya.cmds as mc
import maya.OpenMaya as om
import maya.OpenMayaUI as omui
import maya.api.OpenMaya as oma
import maya.mel as mel

OUTLINER_PANEL = None
OUTLINER_CTRL = None
MAIN_PANE = None
DIVIDER_VERTICAL = False
WIN = "outlinerXWin"
DOCK = "outlinerXDock"

NOTE_WIN = "jwQuickNoteWin"
NOTE_FIELD = "jwQuickNoteField"

QSHADE_GRID = None
QSHADE_SCROLL = None
QSHADE_AUTO_CHK = "outlinerX_qshadeAutoChk"
QSHADE_AUTO_JOB = None
QSHADE_RESIZE_TIMER = None
QSHADE_LAST_COLS = 4

# 始终在大纲中隐藏这些指定节点
ALWAYS_HIDE_TYPES = ()
ALWAYS_HIDE_NODES = (
    "defaultObjectSet",
    "defaultLightSet",
    "initialParticleSE",
    "initialShadingGroup",
)

COLOR_CHK_OUTLINER = "outlinerX_chk_outliner"
COLOR_CHK_VIEWPORT = "outlinerX_chk_viewport"
COLOR_CHK_SHADER   = "outlinerX_chk_shader"

# ---------------------------------------------------
# 快速场景缓存
# ---------------------------------------------------

SCENE_CACHE = {
    "assemblies": [],
    "objectSets": [],
    "shadingEngines": [],
    "dag": [],
}

COLOR_PRESETS = [
    ("cRed",     (1.000, 0.150, 0.150)),
    ("cLRed",    (1.000, 0.399, 0.321)),
    ("cOrange",  (1.000, 0.479, 0.173)),
    ("cYellow",  (1.000, 1.000, 0.390)),
    ("cGreen",   (0.527, 1.000, 0.276)),
    ("cCyan",    (0.321, 1.000, 0.869)),
    ("cBlue",    (0.456, 0.628, 1.000)),
    ("cPink",    (1.000, 0.442, 0.706)),
    ("cViolet",  (0.763, 0.332, 0.892)),
    ("cDViolet", (0.466, 0.200, 0.892)),
]

QSHADE_TILE_W = 72
QSHADE_TILE_H = 106

# ---------------------------------------------------
# 通用工具函数
# ---------------------------------------------------

def _safe_hidden(node, state):
    try:
        if mc.objExists(node) and mc.attributeQuery("hiddenInOutliner", node=node, exists=True):
            if mc.getAttr(node + ".hiddenInOutliner") != state:
                mc.setAttr(node + ".hiddenInOutliner", state)
    except:
        pass


def _valid_hidden_attr(node):
    try:
        return mc.objExists(node) and mc.attributeQuery("hiddenInOutliner", node=node, exists=True)
    except:
        return False


def _path_chain(node):
    parts = node.split('|')[1:]
    return ['|' + '|'.join(parts[:i]) for i in range(1, len(parts) + 1)]


def _outliner_editor(pnl):
    try:
        return mc.outlinerPanel(pnl, q=True, outlinerEditor=True)
    except:
        return None


def _refresh_all_outliners():
    for pnl in mc.getPanel(type='outlinerPanel') or []:
        ed = _outliner_editor(pnl)
        if ed:
            try:
                mc.outlinerEditor(ed, e=True, refresh=True)
            except:
                pass


def _expand_all(pnl):
    ed = _outliner_editor(pnl)
    if not ed:
        return

    def _do_expand():
        try:
            if mc.outlinerEditor(ed, exists=True):
                mc.outlinerEditor(ed, e=True, expandAllItems=True)
        except:
            pass

    try:
        mc.evalDeferred(lambda: mc.evalDeferred(_do_expand))
    except:
        pass


def _cleanup_unused_outliner_panels():
    for pnl in mc.getPanel(type='outlinerPanel') or []:
        try:
            mc.deleteUI(pnl, panel=True)
        except:
            try:
                mc.deleteUI(pnl)
            except:
                pass

def _build_scene_cache():
    global SCENE_CACHE
    SCENE_CACHE["assemblies"] = mc.ls(assemblies=True, l=True) or []
    SCENE_CACHE["objectSets"] = mc.ls(type="objectSet") or []
    SCENE_CACHE["shadingEngines"] = mc.ls(type="shadingEngine") or []
    SCENE_CACHE["dag"] = mc.ls(dag=True, l=True) or []


def rebuild_cache(*_):
    _build_scene_cache()
    _hide_always_hidden_nodes()
    _refresh_all_outliners()


def _hide_always_hidden_nodes():
    for n in ALWAYS_HIDE_NODES:
        _safe_hidden(n, 1)

    for node_type in ALWAYS_HIDE_TYPES:
        if node_type == "objectSet":
            nodes = SCENE_CACHE["objectSets"]
        elif node_type == "shadingEngine":
            nodes = SCENE_CACHE["shadingEngines"]
        else:
            nodes = mc.ls(type=node_type) or []

        for n in nodes:
            _safe_hidden(n, 1)


def _selection_to_prune_nodes():
    sel = mc.ls(sl=True, l=True) or []
    result = []

    for s in sel:
        obj = s.split('.')[0]
        if not mc.objExists(obj):
            continue

        try:
            ntype = mc.nodeType(obj)
        except:
            continue

        if ntype in ("objectSet", "shadingEngine"):
            continue

        if ntype == "transform":
            result.append(obj)
            continue

        parent = mc.listRelatives(obj, p=True, fullPath=True) or []
        if parent:
            try:
                if mc.nodeType(parent[0]) not in ("objectSet", "shadingEngine"):
                    result.extend(parent)
            except:
                pass

    return list(dict.fromkeys(result))


def _group_by_parent(nodes):
    groups = {}
    for n in nodes:
        parent = mc.listRelatives(n, p=True, fullPath=True)
        parent = parent[0] if parent else "|WORLD|"
        groups.setdefault(parent, []).append(n)
    return groups


def _all_restore_candidates():
    nodes = []
    nodes.extend(SCENE_CACHE["dag"])
    nodes.extend(SCENE_CACHE["objectSets"])
    nodes.extend(SCENE_CACHE["shadingEngines"])
    return list(dict.fromkeys(nodes))


def _is_camera_transform(node):
    try:
        if mc.nodeType(node) != "transform":
            return False
        shapes = mc.listRelatives(node, s=True, ni=True, fullPath=True) or []
        for s in shapes:
            if mc.nodeType(s) == "camera":
                return True
    except:
        pass
    return False


def _sort_type_rank(node):
    try:
        ntype = mc.nodeType(node)
    except:
        return 50

    if ntype == "objectSet":
        return 99

    if ntype == "transform":
        if _is_camera_transform(node):
            return 0
        return 10

    return 50


def _sort_key(node):
    return (_sort_type_rank(node), node.split('|')[-1].lower())


def _unique_long(nodes):
    return list(dict.fromkeys(nodes or []))


def _scene_transform_candidates():
    result = []

    all_transforms = mc.ls(type="transform", l=True) or []
    all_joints = mc.ls(type="joint", l=True) or []

    result.extend(all_transforms)
    result.extend(all_joints)

    return _unique_long(result)


def _hierarchy_nodes_from_selection_or_scene():
    sel = mc.ls(sl=True, l=True) or []

    # 如果没有选择对象，则搜索整个场景
    if not sel:
        return _scene_transform_candidates()

    result = []
    for obj in sel:
        if not mc.objExists(obj):
            continue

        base = obj.split('.')[0]
        if not mc.objExists(base):
            continue

        result.append(base)
        result.extend(mc.listRelatives(base, ad=True, fullPath=True) or [])

    return _unique_long(result)


def _is_shape_transform(node, shape_types):
    try:
        if mc.nodeType(node) != "transform":
            return False

        shapes = mc.listRelatives(node, s=True, ni=True, fullPath=True) or []
        if not shapes:
            return False

        for s in shapes:
            try:
                if mc.nodeType(s) in shape_types:
                    return True
            except:
                pass
    except:
        pass
    return False


def _is_group_transform(node):
    try:
        if mc.nodeType(node) != "transform":
            return False

        shapes = mc.listRelatives(node, s=True, ni=True, fullPath=True) or []
        if shapes:
            return False

        return True
    except:
        return False


def select_hierarchy_by_kind(kind, *_):
    nodes = _hierarchy_nodes_from_selection_or_scene()
    if not nodes:
        mc.select(cl=True)
        return

    result = []

    shape_map = {
        "locator": {"locator"},
        "mesh": {"mesh"},
        "curve": {"nurbsCurve"},
        "surface": {"nurbsSurface"},
        "camera": {"camera"},
        "light": {
            "ambientLight",
            "directionalLight",
            "pointLight",
            "spotLight",
            "areaLight",
            "volumeLight"
        },
    }

    if kind in shape_map:
        shape_types = shape_map[kind]
        for n in nodes:
            if _is_shape_transform(n, shape_types):
                result.append(n)

    elif kind == "joint":
        for n in nodes:
            try:
                if mc.nodeType(n) == "joint":
                    result.append(n)
            except:
                pass

    elif kind == "group":
        for n in nodes:
            if _is_group_transform(n):
                result.append(n)

    result = _unique_long(result)

    if result:
        mc.select(result, r=True)
    else:
        mc.select(cl=True)


def select_hierarchy_or_all(*_):
    sel = mc.ls(sl=True, l=True) or []
    if not sel:
        return
    mc.select(hi=True)


def jw_select_similar(comp_face=False, *_):
    sel = mc.ls(sl=True, long=True) or []
    if not sel:
        oma.MGlobal.displayWarning("请先选择网格或变换节点。")
        return []

    shape = next((
        s for obj in sel
        for s in ([obj] if mc.nodeType(obj) == "mesh"
                  else mc.listRelatives(obj, s=True, ni=True, f=True) or [])
        if mc.nodeType(s) == "mesh"
    ), None)

    if not shape:
        oma.MGlobal.displayWarning("未找到有效网格。")
        return []

    parent_tfm = mc.listRelatives(shape, p=True, f=True)
    if not parent_tfm:
        oma.MGlobal.displayWarning("网格没有父级变换节点。")
        return []

    tfm = parent_tfm[0]

    # 获取所选对象的顶层节点
    long_path = mc.ls(tfm, long=True) or []
    if not long_path:
        oma.MGlobal.displayWarning("无法解析所选变换节点。")
        return []

    long_path = long_path[0]
    parts = long_path.split("|")[1:]  # 移除开头的空项

    # 如果对象位于组下方，则仅在该顶层节点内搜索
    # 如果对象在根层级，则搜索整个场景
    top_node = "|" + parts[0] if len(parts) > 1 else None

    sl = oma.MSelectionList()
    sl.add(shape)
    dag0 = sl.getDagPath(0)
    fn0 = oma.MFnMesh(dag0)

    vtx0 = fn0.numVertices
    face0 = fn0.numPolygons

    result = []
    it = oma.MItDag(oma.MItDag.kDepthFirst, oma.MFn.kMesh)

    while not it.isDone():
        dag = it.getPath()

        try:
            fn = oma.MFnMesh(dag)
        except:
            it.next()
            continue

        if fn.isIntermediateObject:
            it.next()
            continue

        mesh_path = dag.fullPathName()
        parent = mc.listRelatives(mesh_path, p=True, f=True)
        if not parent:
            it.next()
            continue
        parent = parent[0]

        # 范围限制：
        # 如果所选对象有顶层组，则仅在该组内搜索
        # 否则搜索整个场景
        if top_node and not parent.startswith(top_node + "|") and parent != top_node:
            it.next()
            continue

        if fn.numVertices == vtx0 and (not comp_face or fn.numPolygons == face0):
            result.append(parent)

        it.next()

    result = _unique_long(result)

    if result:
        mc.select(result, r=True)
    else:
        mc.select(cl=True)
        oma.MGlobal.displayWarning("未找到相似模型。")

    return result


# ---------------------------------------------------
# QShade
# ---------------------------------------------------

def qshade_get_materials():
    mats = mc.ls(materials=True) or []
    return sorted(list(dict.fromkeys(mats)), key=lambda x: x.lower())


def qshade_assign_material(mat, *_):
    if not mc.objExists(mat):
        return

    sel_faces = mc.filterExpand(ex=True, sm=34) or []
    if sel_faces:
        try:
            mel.eval("polyConvertToShell;")
        except:
            pass

    sel = mc.ls(sl=True) or []
    if not sel:
        oma.MGlobal.displayWarning("请先选择对象或面。")
        return

    try:
        mc.hyperShade(assign=mat)
    except:
        oma.MGlobal.displayWarning("无法指定材质。")
        return

    qshade_highlight_from_selection()


def qshade_delete_unused(*_):
    save_sel = mc.ls(sl=True) or []
    try:
        mel.eval('hyperShadePanelMenuCommand("hyperShadePanel1", "deleteUnusedNodes")')
    except:
        try:
            mel.eval('MLdeleteUnused;')
        except:
            pass

    qshade_refresh()
    if save_sel:
        try:
            mc.select(save_sel, r=True)
        except:
            pass


def qshade_get_selected_material():
    sel = mc.ls(sl=True, l=True) or []
    if not sel:
        return None

    base = sel[0].split('.')[0]
    if not mc.objExists(base):
        return None

    if mc.nodeType(base) == 'transform':
        shapes = mc.listRelatives(base, s=True, ni=True, f=True) or []
    elif mc.nodeType(base) in ('mesh', 'nurbsSurface', 'nurbsCurve', 'subdiv'):
        shapes = [base]
    else:
        shapes = []

    for sh in shapes:
        sgs = mc.listConnections(sh, type='shadingEngine') or []
        for sg in sgs:
            mats = mc.listConnections(sg + '.surfaceShader', s=True, d=False) or []
            if mats:
                return mats[0]
    return None


def qshade_clone_shader(*_):
    save_sel = mc.ls(sl=True, l=True) or []
    if not save_sel:
        oma.MGlobal.displayWarning("请先选择对象。")
        return

    mat = qshade_get_selected_material()
    if not mat:
        oma.MGlobal.displayWarning("所选对象没有材质。")
        return

    try:
        dup = mc.duplicate(mat, upstreamNodes=True)[0]
    except:
        oma.MGlobal.displayWarning("无法克隆材质。")
        return

    try:
        mc.select(save_sel, r=True, noExpand=True)
        mc.hyperShade(assign=dup)
    except:
        pass

    qshade_refresh()

    try:
        mc.select(dup, r=True)
        mel.eval('showEditorExact "{}"'.format(dup))
    except:
        pass


def qshade_open_material(mat, *_):
    qshade_highlight_button(mat)
    try:
        mc.select(mat, r=True)
        mel.eval('showEditorExact "{}"'.format(mat))
    except:
        pass


def qshade_clear_highlight():
    global QSHADE_GRID
    mats = qshade_get_materials()
    for mat in mats:
        btn = "qshade_btn_" + mat.replace('|', '_').replace(':', '_')
        if mc.control(btn, exists=True):
            try:
                mc.button(btn, e=True, bgc=(0.28, 0.28, 0.28))
            except:
                pass


def qshade_highlight_button(mat):
    qshade_clear_highlight()
    btn = "qshade_btn_" + mat.replace('|', '_').replace(':', '_')
    if mc.control(btn, exists=True):
        try:
            mc.button(btn, e=True, bgc=(0.2, 0.7, 0.7))
        except:
            pass


def qshade_highlight_from_selection(force=False, *_):
    if not force:
        try:
            if mc.checkBox(QSHADE_AUTO_CHK, exists=True) and not mc.checkBox(QSHADE_AUTO_CHK, q=True, value=True):
                return
        except:
            pass

    mat = qshade_get_selected_material()
    if mat:
        qshade_highlight_button(mat)
    else:
        qshade_clear_highlight()


def qshade_picker(*_):
    qshade_highlight_from_selection(force=True)


def _qshade_calc_columns():
    """Calculate how many material tiles fit per row based on scroll layout width."""
    num_cols = 4  # fallback default
    try:
        if QSHADE_SCROLL and mc.scrollLayout(QSHADE_SCROLL, exists=True):
            pw = mc.scrollLayout(QSHADE_SCROLL, q=True, w=True)
            sb_w = mc.scrollLayout(QSHADE_SCROLL, q=True, verticalScrollBarThickness=True) or 12
            usable = pw - sb_w
            if usable > 0:
                num_cols = max(1, int(usable // QSHADE_TILE_W))
    except:
        pass
    return num_cols


def qshade_refresh(force_cols=None, *_):
    global QSHADE_GRID, QSHADE_LAST_COLS
    if not QSHADE_GRID or not mc.layout(QSHADE_GRID, exists=True):
        return

    # 根据可用宽度动态计算列数，也可使用强制列数
    if force_cols:
        num_cols = force_cols
    else:
        num_cols = _qshade_calc_columns()
    QSHADE_LAST_COLS = num_cols
    mc.gridLayout(QSHADE_GRID, e=True, numberOfColumns=num_cols, cellWidthHeight=(QSHADE_TILE_W, QSHADE_TILE_H))

    kids = mc.layout(QSHADE_GRID, q=True, ca=True) or []
    for k in kids:
        try:
            mc.deleteUI(k)
        except:
            pass

    mats = qshade_get_materials()
    for mat in mats:
        cell = mc.columnLayout(parent=QSHADE_GRID, adj=True)
        try:
            mc.swatchDisplayPort(
                parent=cell,
                sn=mat,
                rs=QSHADE_TILE_W,
                h=QSHADE_TILE_W,
                pressCommand=lambda *_ , m=mat: qshade_assign_material(m)
            )
        except:
            mc.button(parent=cell, label='指定', h=64, c=lambda *_ , m=mat: qshade_assign_material(m))

        btn = "qshade_btn_" + mat.replace('|', '_').replace(':', '_')
        mc.button(
            btn,
            parent=cell,
            label=mat,
            h=24,
            bgc=(0.28, 0.28, 0.28),
            c=lambda *_ , m=mat: qshade_open_material(m)
        )
        mc.setParent(QSHADE_GRID)

    qshade_highlight_from_selection()


def build_qshade_ui(parent):
    global QSHADE_GRID, QSHADE_SCROLL

    qshade_form = mc.formLayout(parent=parent)

    top_col = mc.columnLayout(parent=qshade_form, adj=True)
    mc.separator(h=6, style='none')

    top_row = mc.rowLayout(parent=top_col, numberOfColumns=7, adjustableColumn=7, columnAttach=[(1, 'left', 0), (2, 'left', 1), (3, 'left', 1), (4, 'left', 10), (5, 'left', 1), (6, 'left', 1), (7, 'both', 0)])
    mc.button(label='删未用', w=65, h=22, c=qshade_delete_unused)
    mc.separator(w=1, style='none')
    mc.button(label='克隆', w=65, h=22, c=qshade_clone_shader)
    mc.separator(w=1, style='none')
    picker_btn = mc.button(label='拾取', w=65, h=22, c=qshade_picker)
    mc.button(label='刷新', w=65, h=22, c=qshade_refresh)
    mc.text(label='')
    mc.button(picker_btn, e=True, visible=False, manage=False)

    mc.setParent(top_col)
    mc.separator(height=20, style='in')

    auto_chk = mc.checkBox(QSHADE_AUTO_CHK, parent=qshade_form, label='自动', value=True, visible=False, manage=False, cc=qshade_toggle_auto_highlight)

    QSHADE_SCROLL = mc.scrollLayout(parent=qshade_form, cr=True, childResizable=True, horizontalScrollBarThickness=12, verticalScrollBarThickness=12)
    grid_wrap = mc.columnLayout(parent=QSHADE_SCROLL, adj=True)
    QSHADE_GRID = mc.gridLayout(parent=grid_wrap, numberOfColumns=4, cellWidthHeight=(QSHADE_TILE_W, QSHADE_TILE_H))

    mc.formLayout(
        qshade_form, e=True,
        attachForm=[
            (top_col, 'top', 0),
            (top_col, 'left', 0),
            (top_col, 'right', 0),
            (QSHADE_SCROLL, 'left', 0),
            (QSHADE_SCROLL, 'right', 0),
            (QSHADE_SCROLL, 'bottom', 0),
            (auto_chk, 'top', 0),
            (auto_chk, 'left', 0),
        ],
        attachControl=[
            (QSHADE_SCROLL, 'top', 4, top_col),
        ]
    )

    qshade_refresh(force_cols=4)
    return qshade_form


class _QShadeResizeFilter(object):
    """Qt event filter on the dock widget that triggers debounced QShade grid reflow."""
    _instance = None

    def __init__(self, dock_widget):
        from PySide2 import QtCore
        super(_QShadeResizeFilter, self).__init__()

        class _Filter(QtCore.QObject):
            def __init__(self, callback):
                super(_Filter, self).__init__()
                self._callback = callback
                self._timer = QtCore.QTimer()
                self._timer.setSingleShot(True)
                self._timer.setInterval(300)  # ms debounce
                self._timer.timeout.connect(self._on_timeout)

            def eventFilter(self, obj, event):
                if event.type() == QtCore.QEvent.Resize:
                    self._timer.start()
                return False

            def _on_timeout(self):
                self._callback()

        self._filter = _Filter(self._do_refresh)
        dock_widget.installEventFilter(self._filter)
        # 防止对象被垃圾回收
        dock_widget._qshade_resize_filter = self._filter
        _QShadeResizeFilter._instance = self

    @staticmethod
    def _do_refresh():
        global QSHADE_LAST_COLS
        new_cols = _qshade_calc_columns()
        if new_cols != QSHADE_LAST_COLS:
            QSHADE_LAST_COLS = new_cols
            try:
                mc.evalDeferred(qshade_refresh)
            except:
                pass


def _install_qshade_resize_watcher():
    """Attach a resize event filter to the DOCK workspaceControl widget."""
    global QSHADE_LAST_COLS
    try:
        import maya.OpenMayaUI as omui
        from PySide2 import QtWidgets
        import shiboken2

        ptr = omui.MQtUtil.findControl(DOCK)
        if not ptr:
            ptr = omui.MQtUtil.findLayout(DOCK)
        if not ptr:
            # workspaceControl 通常需要使用完整名称调用 findControl
            ptr = omui.MQtUtil.findControl(DOCK + "WorkspaceControl")
        if not ptr:
            print("[OutlinerX] 尺寸监听器：找不到 DOCK 控件")
            return

        widget = shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
        if not shiboken2.isValid(widget):
            print("[OutlinerX] 尺寸监听器：DOCK 控件无效")
            return

        QSHADE_LAST_COLS = _qshade_calc_columns()
        _QShadeResizeFilter(widget)
        print("[OutlinerX] 尺寸监听器已安装到 DOCK")
    except Exception as ex:
        print("[OutlinerX] 尺寸监听器安装失败：{}".format(ex))



def qshade_set_auto_highlight(enabled):
    global QSHADE_AUTO_JOB

    if QSHADE_AUTO_JOB is not None:
        try:
            if mc.scriptJob(exists=QSHADE_AUTO_JOB):
                mc.scriptJob(kill=QSHADE_AUTO_JOB, force=True)
        except:
            pass
        QSHADE_AUTO_JOB = None

    if not enabled:
        return

    try:
        if mc.workspaceControl(DOCK, exists=True):
            QSHADE_AUTO_JOB = mc.scriptJob(event=["SelectionChanged", qshade_highlight_from_selection], parent=DOCK)
    except:
        QSHADE_AUTO_JOB = None


def qshade_toggle_auto_highlight(*_):
    enabled = True
    try:
        if mc.checkBox(QSHADE_AUTO_CHK, exists=True):
            enabled = mc.checkBox(QSHADE_AUTO_CHK, q=True, value=True)
    except:
        pass
    qshade_set_auto_highlight(enabled)

# ---------------------------------------------------
# 快速备注
# ---------------------------------------------------

def jw_trim_string(s):
    if not s:
        return ""
    return s.strip()


def jw_build_note_name(note, total_len=50):
    note = jw_trim_string(note)
    if not note:
        note = "bookMark"

    max_note_len = max(1, total_len - 2)
    if len(note) > max_note_len:
        note = note[:max_note_len]

    underscore_total = total_len - len(note)

    if underscore_total % 2 != 0:
        underscore_total -= 1

    if underscore_total < 2:
        underscore_total = 2

    side_count = underscore_total // 2
    left = "_" * side_count
    right = "_" * side_count

    return left + note + right


def jw_quick_node_create(*_):
    if mc.textField(NOTE_FIELD, exists=True):
        note = mc.textField(NOTE_FIELD, q=True, text=True)
    else:
        note = "bookMark"

    final_name = jw_build_note_name(note, total_len=50)

    node = mc.group(em=True, name="tmpQuickNote#")
    try:
        mc.rename(node, final_name)
    except RuntimeError:
        mc.rename(node, final_name + "#")

    rebuild_cache()


def moveItemUp():
    mc.reorder(relative=-1)


def moveItemDown():
    mc.reorder(relative=1)


def jw_quick_node_ui(*_):
    if mc.window(NOTE_WIN, exists=True):
        mc.deleteUI(NOTE_WIN)

    mc.window(
        NOTE_WIN,
        title="大纲备注",
        widthHeight=(320, 60),
        mxb=False,
        mnb=False
    )
    mc.columnLayout(adj=True)
    mc.frameLayout(lv=0, h=60, w=300, mw=6, mh=6)

    mc.rowColumnLayout(
        nc=4,
        cw=[(1, 40), (2, 180), (3, 10), (4, 60)]
    )
    mc.text(label="备注：")
    mc.textField(NOTE_FIELD, width=180, text="书签")
    mc.text(label="")
    mc.button(label="创建", h=24, w=55, c=jw_quick_node_create)

    mc.showWindow(NOTE_WIN)


# ---------------------------------------------------
# 展开一级
# ---------------------------------------------------

def expand_selected_one_level(panel):
    ed = _outliner_editor(panel)
    if not ed:
        return

    parents = mc.ls(sl=True, l=True) or []
    if not parents:
        return

    clean_parents = []
    for p in parents:
        obj = p.split('.')[0]
        if not mc.objExists(obj):
            continue

        try:
            ntype = mc.nodeType(obj)
        except:
            continue

        if ntype in ("objectSet", "shadingEngine"):
            continue

        if ntype == "transform":
            clean_parents.append(obj)
        else:
            par = mc.listRelatives(obj, p=True, fullPath=True) or []
            if par:
                try:
                    if mc.nodeType(par[0]) not in ("objectSet", "shadingEngine"):
                        clean_parents.extend(par)
                except:
                    pass

    parents = list(dict.fromkeys(clean_parents))
    if not parents:
        return

    # 直接子级就是需要显示的一级
    children = []
    for p in parents:
        for c in mc.listRelatives(p, children=True, fullPath=True) or []:
            children.append(c)
    children = list(dict.fromkeys(children))

    # 这些子级下方的全部更深层后代
    descendants_to_hide = []
    for c in children:
        for d in mc.listRelatives(c, ad=True, fullPath=True) or []:
            descendants_to_hide.append(d)
    descendants_to_hide = list(dict.fromkeys(descendants_to_hide))

    # 只保留变换节点，通常对应大纲中视觉上闪烁的项目
    filtered_descendants = []
    for n in descendants_to_hide:
        try:
            if mc.nodeType(n) == "transform":
                filtered_descendants.append(n)
        except:
            pass
    descendants_to_hide = filtered_descendants

    # 只记录实际修改过的节点，便于安全恢复
    hidden_restore = {}

    def _restore_hidden_descendants():
        for n, old_state in hidden_restore.items():
            try:
                if mc.objExists(n) and _valid_hidden_attr(n):
                    mc.setAttr(n + ".hiddenInOutliner", old_state)
            except:
                pass


    def _finish():
        try:
            _restore_hidden_descendants()
            _hide_always_hidden_nodes()
            _refresh_all_outliners()
        except:
            pass

    def _do_collapse():
        try:
            if mc.outlinerEditor(ed, exists=True):
                mc.outlinerEditor(ed, e=True, expandAllSelectedItems=False)
        except:
            pass

        mc.evalDeferred(_finish)

    def _select_children_then_collapse():
        try:
            live_children = [n for n in children if mc.objExists(n)]
            if not live_children:
                _finish()
                return

            mc.select(live_children, r=True, noExpand=True)
        except:
            _finish()
            return

        mc.evalDeferred(lambda: mc.evalDeferred(_do_collapse))

    def _do_expand():
        try:
            if mc.outlinerEditor(ed, exists=True):
                mc.outlinerEditor(ed, e=True, expandAllSelectedItems=True)
        except:
            pass

        mc.evalDeferred(_select_children_then_collapse)

    def _select_parents_then_expand():
        try:
            live_parents = [n for n in parents if mc.objExists(n)]
            if not live_parents:
                _finish()
                return

            mc.select(live_parents, r=True, noExpand=True)
        except:
            _finish()
            return

        mc.evalDeferred(lambda: mc.evalDeferred(_do_expand))

    def _expand_parents():
        try:
            live_parents = [n for n in parents if mc.objExists(n)]
            if not live_parents:
                _restore_hidden_descendants()
                return

            for n in descendants_to_hide:
                try:
                    if _valid_hidden_attr(n):
                        old_state = mc.getAttr(n + ".hiddenInOutliner")
                        if old_state != 1:
                            hidden_restore[n] = old_state
                            _safe_hidden(n, 1)
                except:
                    pass

            _hide_always_hidden_nodes()
            _refresh_all_outliners()

        except:
            _restore_hidden_descendants()
            return

        # 额外延迟一次，让大纲有时间响应 hiddenInOutliner
        mc.evalDeferred(lambda: mc.evalDeferred(_select_parents_then_expand))

    mc.evalDeferred(_expand_parents)


# ---------------------------------------------------
# 排序工具
# ---------------------------------------------------

def sort_alpha_selected():
    sel = mc.ls(sl=True, tr=True, l=True) or []
    if not sel:
        return

    groups = _group_by_parent(sel)

    for parent in groups:
        children = sorted(groups[parent], key=lambda x: x.split('|')[-1].lower())

        for obj in children:
            try:
                mc.reorder(obj, b=True)
            except:
                pass


def sort_color_outliner():
    sel = mc.ls(sl=True, tr=True, l=True) or []
    if not sel:
        return

    groups = _group_by_parent(sel)
    preset_colors = [rgb for _, rgb in COLOR_PRESETS]

    def _color_distance(a, b):
        return (
            (a[0] - b[0]) ** 2 +
            (a[1] - b[1]) ** 2 +
            (a[2] - b[2]) ** 2
        )

    for parent in groups:
        nodes = groups[parent]
        order_data = {}

        for n in nodes:
            idx = len(preset_colors)
            try:
                if mc.attributeQuery("useOutlinerColor", node=n, exists=True) and mc.getAttr(n + ".useOutlinerColor"):
                    v = mc.getAttr(n + ".outlinerColor")[0]
                    distances = [_color_distance(v, p) for p in preset_colors]
                    idx = distances.index(min(distances))
            except:
                pass

            order_data[n] = idx

        ordered_nodes = sorted(
            nodes,
            key=lambda x: (order_data[x], x.split('|')[-1].lower())
        )

        for obj in ordered_nodes:
            try:
                mc.reorder(obj, b=True)
            except:
                pass


def _sort_children_alpha(parent):
    children = mc.listRelatives(parent, c=True, type="transform", fullPath=True) or []
    if not children:
        return

    children_sorted = sorted(children, key=_sort_key)

    for c in children_sorted:
        try:
            mc.reorder(c, b=True)
        except:
            pass

    for c in children_sorted:
        _sort_children_alpha(c)


def sort_all_hierarchy():
    roots = []
    roots.extend(mc.ls(assemblies=True, l=True) or [])
    roots.extend(SCENE_CACHE["objectSets"])
    roots = list(dict.fromkeys(roots))

    if not roots:
        return

    roots_sorted = sorted(roots, key=_sort_key)

    for r in roots_sorted:
        try:
            mc.reorder(r, b=True)
        except:
            pass

    for r in roots_sorted:
        try:
            if mc.objExists(r) and mc.nodeType(r) == "transform":
                _sort_children_alpha(r)
        except:
            pass


def _center_outliner_divider():
    """Find the QSplitter inside the outliner panel and set it to 50/50."""
    try:
        import maya.OpenMayaUI as omui
        from PySide2 import QtWidgets, QtCore
        import shiboken2

        # 先尝试 OUTLINER_CTRL，再使用 OUTLINER_PANEL 兜底
        ptr = None
        for name in (OUTLINER_CTRL, OUTLINER_PANEL):
            if not name:
                continue
            ptr = omui.MQtUtil.findControl(name)
            if not ptr:
                ptr = omui.MQtUtil.findLayout(name)
            if ptr:
                break

        if not ptr:
            return

        widget = shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
        if not shiboken2.isValid(widget):
            return

        for splitter in widget.findChildren(QtWidgets.QSplitter):
            try:
                if not shiboken2.isValid(splitter):
                    continue
                if splitter.count() < 2:
                    continue

                if splitter.orientation() == QtCore.Qt.Vertical:
                    total = splitter.height()
                else:
                    total = splitter.width()

                half = total // 2
                splitter.setSizes([half, total - half])
                return
            except RuntimeError:
                continue
    except Exception:
        pass


def toggle_outliner_divider(*_):
    global DIVIDER_VERTICAL, OUTLINER_PANEL

    DIVIDER_VERTICAL = not DIVIDER_VERTICAL
    divider_value = 1 if DIVIDER_VERTICAL else 0
    icon_name = 'hsShowTopTabsOnly.png' if DIVIDER_VERTICAL else 'hsShowRightTabsOnly.png'

    try:
        if OUTLINER_PANEL and mc.outlinerPanel(OUTLINER_PANEL, exists=True):
            mc.outlinerPanel(OUTLINER_PANEL, e=True, divider=divider_value)
    except:
        pass

    try:
        if mc.iconTextButton('outlinerState', exists=True):
            mc.iconTextButton('outlinerState', e=True, image1=icon_name)
    except:
        pass

        # Maya 创建分割后再居中分割条
    if divider_value:
        mc.evalDeferred(_center_outliner_divider)


# ---------------------------------------------------
# 将所选节点滚动到大纲顶部
# ---------------------------------------------------

def _get_scene_outliners():
    """Dynamically find all visible scene outliner editors, ignoring dopeSheet/graphEditor etc."""
    ignore = ['dopeSheet', 'dynRel', 'graphEditor', 'relationshipPanel']
    editors = mc.lsUI(editors=True) or []
    return [
        e for e in editors
        if mc.outlinerEditor(e, exists=True)
        and not any(i in e for i in ignore)
    ]


def _scroll_outliner_panel_to_top(editor_name):
    """Scroll a single outliner editor to the top via its Qt vertical scrollbar."""
    try:
        import maya.OpenMayaUI as omui
        from PySide2 import QtWidgets, QtCore
        import shiboken2

        ptr = omui.MQtUtil.findControl(editor_name)
        if not ptr:
            return
        widget = shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
        for sb in widget.findChildren(QtWidgets.QScrollBar):
            if sb.orientation() == QtCore.Qt.Vertical:
                sb.setValue(0)
    except Exception:
        pass


OUTLINER_SCROLL_PX = 0.5# pixels per scrollbar click (~1 row)
OUTLINER_SCROLL_ROWS = 2  # number of rows to scroll per up/down action


def scroll_outliners_by(direction, *_):
    """Scroll both outliner panes.
    Uses Qt scrollbar setValue where possible.
    For editors whose scrollbars are deleted, sends a synthetic
    QWheelEvent to the editor widget directly.
    """
    import maya.OpenMayaUI as omui
    from PySide2 import QtWidgets, QtCore, QtGui
    import shiboken2

    delta = OUTLINER_SCROLL_PX * direction
    editors = _get_scene_outliners()

    # 查询当前分割状态
    divider_val = 0
    try:
        if OUTLINER_PANEL and mc.outlinerPanel(OUTLINER_PANEL, exists=True):
            divider_val = mc.outlinerPanel(OUTLINER_PANEL, q=True, divider=True)
    except:
        pass

    if divider_val == 0:
        pass
        #print("水平步进")

    for ed in editors:
        try:
            ptr = omui.MQtUtil.findControl(ed)
            if not ptr:
                continue
            widget = shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
            if not shiboken2.isValid(widget):
                continue

            # 优先尝试滚动条方案
            scrolled = False
            for sb in widget.findChildren(QtWidgets.QScrollBar):
                try:
                    if not shiboken2.isValid(sb):
                        continue
                    if sb.orientation() == QtCore.Qt.Vertical:
                        new_val = max(sb.minimum(), min(sb.maximum(), sb.value() + delta))
                        sb.setValue(new_val)
                        scrolled = True
                        break
                except RuntimeError:
                    continue

            # 兜底：直接向控件发送滚轮事件
            if not scrolled:
                try:
                    # 查找最深层的可见子控件并发送事件
                    target = widget
                    children = widget.findChildren(QtWidgets.QWidget)
                    for child in children:
                        try:
                            if shiboken2.isValid(child) and child.isVisible() and child.height() > 100:
                                target = child
                                break
                        except RuntimeError:
                            continue

                    # Qt 中一个鼠标滚轮刻度等于 120 单位
                    wheel_delta = 120 * direction
                    angle = QtCore.QPoint(0, -wheel_delta)
                    pos = QtCore.QPointF(target.width() / 2, target.height() / 2)
                    event = QtGui.QWheelEvent(
                        pos, target.mapToGlobal(pos.toPoint()),
                        QtCore.QPoint(0, 0), angle,
                        QtCore.Qt.NoButton, QtCore.Qt.NoModifier,
                        QtCore.Qt.NoScrollPhase, False
                    )
                    QtWidgets.QApplication.sendEvent(target, event)
                except (RuntimeError, Exception) as ex:
                    print("WheelEvent 兜底滚动失败：{}：{}".format(ed, ex))

        except (RuntimeError, Exception):
            continue



def scroll_outliners_up(*_):
    scroll_outliners_by(-OUTLINER_SCROLL_ROWS)


def scroll_outliners_down(*_):
    scroll_outliners_by(OUTLINER_SCROLL_ROWS)



# ---------------------------------------------------
# 裁剪显示逻辑
# ---------------------------------------------------

def _prune(nodes):
    nodes = [n for n in dict.fromkeys(nodes or []) if mc.objExists(n)]

    filtered = []
    for n in nodes:
        try:
            if mc.nodeType(n) in ("objectSet", "shadingEngine"):
                continue
        except:
            continue

        if _valid_hidden_attr(n):
            filtered.append(n)

    nodes = filtered

    if not nodes:
        _hide_always_hidden_nodes()
        _refresh_all_outliners()
        return

    visible = set()
    for n in nodes:
        visible.update(_path_chain(n))

    for n in SCENE_CACHE["assemblies"]:
        _safe_hidden(n, 1)

    for n in SCENE_CACHE["objectSets"]:
        _safe_hidden(n, 1)

    for n in SCENE_CACHE["shadingEngines"]:
        _safe_hidden(n, 1)

    for n in visible:
        for c in mc.listRelatives(n, children=True, fullPath=True) or []:
            if _valid_hidden_attr(c):
                _safe_hidden(c, 1)

    for n in visible:
        try:
            if mc.nodeType(n) in ("objectSet", "shadingEngine"):
                continue
        except:
            continue
        _safe_hidden(n, 0)

    _hide_always_hidden_nodes()
    _refresh_all_outliners()
    _expand_all(OUTLINER_PANEL)


def prune_selected():
    _prune(_selection_to_prune_nodes())


def prune_coloured():
    hits = []
    for n in SCENE_CACHE["dag"]:
        try:
            if mc.nodeType(n) in ("objectSet", "shadingEngine"):
                continue

            if (mc.attributeQuery("useOutlinerColor", node=n, exists=True) and
                mc.attributeQuery("outlinerColor", node=n, exists=True) and
                mc.getAttr(n + ".useOutlinerColor")):
                c = mc.getAttr(n + ".outlinerColor")
                if c and sum(c[0]) != 0.0:
                    hits.append(n)
        except:
            pass
    _prune(hits)


def prune_off():
    for n in _all_restore_candidates():
        if _valid_hidden_attr(n):
            _safe_hidden(n, 0)

    _hide_always_hidden_nodes()
    _refresh_all_outliners()

    def _collapse_all():
        for pnl in mc.getPanel(type='outlinerPanel') or []:
            ed = _outliner_editor(pnl)
            if not ed:
                continue
            try:
                if mc.outlinerEditor(ed, exists=True):
                    mc.outlinerEditor(ed, e=True, expandAllItems=False)
            except:
                pass

    mc.evalDeferred(lambda: mc.evalDeferred(_collapse_all))


# ---------------------------------------------------
# 颜色标记逻辑
# ---------------------------------------------------

def _chk_value(name, default=0):
    try:
        return mc.checkBox(name, q=True, v=True)
    except:
        return default


def _color_targets():
    targets = mc.ls(sl=True, tr=True, l=True) or []
    no_selection = len(targets) < 1

    if no_selection:
        all_tr = mc.ls(type="transform", l=True) or []
        cams = {"|persp", "|top", "|front", "|side"}
        targets = [obj for obj in all_tr if obj not in cams]

    return targets, no_selection


def _set_outliner_color(obj, rgb):
    try:
        if mc.attributeQuery("useOutlinerColor", node=obj, exists=True):
            mc.setAttr(obj + ".useOutlinerColor", 1)
            mc.setAttr(obj + ".outlinerColor", rgb[0], rgb[1], rgb[2], type="double3")
    except:
        pass


def _reset_outliner_color_attr(obj):
    try:
        if mc.attributeQuery("useOutlinerColor", node=obj, exists=True):
            if mc.getAttr(obj + ".useOutlinerColor"):
                mc.setAttr(obj + ".useOutlinerColor", 0)
                if mc.attributeQuery("outlinerColor", node=obj, exists=True):
                    mc.setAttr(obj + ".outlinerColor", 0, 0, 0, type="double3")
    except:
        pass


def _set_viewport_color(obj, rgb):
    try:
        if mc.attributeQuery("overrideEnabled", node=obj, exists=True):
            mc.setAttr(obj + ".overrideEnabled", 1)
        if mc.attributeQuery("overrideRGBColors", node=obj, exists=True):
            mc.setAttr(obj + ".overrideRGBColors", 1)
        if mc.attributeQuery("overrideColorRGB", node=obj, exists=True):
            mc.setAttr(obj + ".overrideColorRGB", rgb[0], rgb[1], rgb[2], type="double3")
    except:
        pass


def _reset_viewport_color(obj):
    try:
        if mc.attributeQuery("overrideColorRGB", node=obj, exists=True):
            mc.setAttr(obj + ".overrideColorRGB", 0, 0, 0, type="double3")
        if mc.attributeQuery("overrideRGBColors", node=obj, exists=True):
            mc.setAttr(obj + ".overrideRGBColors", 0)
        if mc.attributeQuery("overrideEnabled", node=obj, exists=True):
            mc.setAttr(obj + ".overrideEnabled", 0)
    except:
        pass


def _ensure_color_shader(shader_name, rgb):
    if mc.objExists(shader_name):
        return shader_name

    try:
        shader = mc.shadingNode("lambert", name=shader_name, asShader=True)
    except:
        shader = shader_name

    sg_name = shader_name + "SG"
    if not mc.objExists(sg_name):
        try:
            sg_name = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg_name)
        except:
            pass

    try:
        mc.connectAttr(shader + ".outColor", sg_name + ".surfaceShader", f=True)
    except:
        pass

    r, g, b = rgb

    if r > g and r > b:
        g += 0.2
        b += 0.2
    elif g > r and g > b:
        r += 0.2
        b += 0.2
    else:
        g += 0.2
        r += 0.2

    if shader_name == "cBlue":
        r, g, b = 0.4, 0.55, 1.0
    elif shader_name == "cCyan":
        r, g, b = 0.7, 1.0, 1.0

    r = min(max(r, 0.0), 1.0)
    g = min(max(g, 0.0), 1.0)
    b = min(max(b, 0.0), 1.0)

    try:
        mc.setAttr(shader + ".color", r, g, b, type="double3")
    except:
        pass

    return shader


def jw_apply_color(r, g, b, shader_name):
    chk_outliner = _chk_value(COLOR_CHK_OUTLINER, 1)
    chk_viewport = _chk_value(COLOR_CHK_VIEWPORT, 0)
    chk_shader = _chk_value(COLOR_CHK_SHADER, 0)

    color_targets = mc.ls(sl=True, tr=True, l=True) or []
    if not color_targets:
        return

    rgb = (r, g, b)

    for each in color_targets:
        if chk_outliner:
            _set_outliner_color(each, rgb)
        if chk_viewport:
            _set_viewport_color(each, rgb)

    if chk_shader:
        _ensure_color_shader(shader_name, rgb)
        try:
            mc.select(color_targets, r=True, noExpand=True)
            mc.hyperShade(assign=shader_name)
        except:
            pass

    try:
        mc.select(cl=True)
    except:
        pass

    if chk_outliner:
        def _refresh_and_rehide():
            _hide_always_hidden_nodes()
            _refresh_all_outliners()
        mc.evalDeferred(_refresh_and_rehide)


def _transform_uses_any_color_shader(obj, shader_names):
    shapes = mc.listRelatives(obj, s=True, ni=True, fullPath=True) or []
    if not shapes:
        return False

    for sh in shapes:
        sgs = mc.listConnections(sh, type="shadingEngine") or []
        for sg in sgs:
            mats = mc.listConnections(sg + ".surfaceShader", s=True, d=False) or []
            for mat in mats:
                if mat in shader_names:
                    return True
    return False


def reset_outliner_color():
    chk_outliner = _chk_value(COLOR_CHK_OUTLINER, 1)
    chk_viewport = _chk_value(COLOR_CHK_VIEWPORT, 0)
    chk_shader = _chk_value(COLOR_CHK_SHADER, 0)

    color_mats = [name for name, _ in COLOR_PRESETS]
    targets, no_selection = _color_targets()
    if not targets:
        return

    for obj in targets:
        if chk_outliner:
            _reset_outliner_color_attr(obj)
        if chk_viewport:
            _reset_viewport_color(obj)

    if chk_shader:
        restore = []

        if not no_selection:
            restore = list(targets)
        else:
            for obj in targets:
                if _transform_uses_any_color_shader(obj, color_mats):
                    restore.append(obj)

        if restore:
            fallback_shader = None
            if mc.objExists("standardSurface1"):
                fallback_shader = "standardSurface1"
            elif mc.objExists("lambert1"):
                fallback_shader = "lambert1"

            if fallback_shader:
                try:
                    mc.select(restore, r=True, noExpand=True)
                    mc.hyperShade(assign=fallback_shader)
                except:
                    pass

    try:
        mc.select(cl=True)
    except:
        pass

    def _refresh_and_rehide():
        _hide_always_hidden_nodes()
        _refresh_all_outliners()

    mc.evalDeferred(_refresh_and_rehide)


# ---------------------------------------------------
# UI
# ---------------------------------------------------

def build_outliner_x_ui():
    global OUTLINER_PANEL, OUTLINER_CTRL, MAIN_PANE, DIVIDER_VERTICAL

    _cleanup_unused_outliner_panels()

    if mc.window(WIN, exists=True):
        mc.deleteUI(WIN)

    if mc.workspaceControl(DOCK, exists=True):
        mc.deleteUI(DOCK)

    _cleanup_unused_outliner_panels()
    OUTLINER_PANEL = None
    OUTLINER_CTRL = None
    MAIN_PANE = None
    DIVIDER_VERTICAL = False

    mc.workspaceControl(
        DOCK,
        label="Outliner X 大纲工具",
        initialWidth=380,
        minimumWidth=320,
        retain=False
    )

    try:
        mc.workspaceControl(
            DOCK,
            e=True,
            dockToControl=("MainPane", "left")
        )
    except:
        mc.workspaceControl(
            DOCK,
            e=True,
            dockToMainWindow=("left", True)
        )

    form = mc.formLayout(parent=DOCK)

    toolbar = mc.rowColumnLayout(
        parent=form,
        nc=16,
        columnWidth=[(1,22),(2,22),(3,22),(4,22),(5,22),(6,22),(7,5),(8,20),(9,20),(10,22),(11,22),(12,20),(13,15),(14,20),(15,20),(16,20)]
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='nodeGrapherModeSimpleLarge.png',
        w=22, h=30,
        c=lambda *_: prune_selected(),
        ann='仅显示所选'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='nodeGrapherModeSimpleLarge.png',
        bgc=[0.28, 0.4, 0.16],
        w=22, h=30,
        c=lambda *_: prune_coloured(),
        ann='仅显示已标色'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='nodeGrapherModeAllLarge.png',
        w=22, h=30,
        c=lambda *_: prune_off(),
        ann='显示全部'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='QR_add.png',
        w=22, h=30,
        c=lambda *_: expand_selected_one_level(OUTLINER_PANEL),
        ann='展开所选一级'
    )

    btn_showDag = mc.iconTextButton(
        style='iconOnly',
        image1='showDag.png',
        w=22, h=30,
        c=select_hierarchy_or_all,
        ann='选择层级'
    )

    pm_showDag = mc.popupMenu(parent=btn_showDag, button=3)

    for label, kind in [
        ("定位器", "locator"),
        ("关节", "joint"),
        ("网格", "mesh"),
        ("曲线", "curve"),
        ("曲面", "surface"),
        ("摄像机", "camera"),
        ("灯光", "light"),
    ]:
        mc.menuItem(
            parent=pm_showDag,
            label=label,
            c=lambda *_ , k=kind: select_hierarchy_by_kind(k)
        )

    mc.menuItem(parent=pm_showDag, divider=True)

    mc.menuItem(
        parent=pm_showDag,
        label='组',
        c=lambda *_: select_hierarchy_by_kind("group")
    )

    mc.menuItem(
        parent=pm_showDag,
        label='相似模型',
        c=jw_select_similar
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='setEdEditMode.png',
        w=22, h=30,
        c=jw_quick_node_ui,
        ann='快速备注'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='UVEditorVAxis.png',
        w=5, h=30, en=0
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='nodeGrapherArrowUp.png',
        w=22, h=30,
        c=lambda *_: moveItemUp(),
        ann='上移一位'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='nodeGrapherArrowDown.png',
        w=22, h=30,
        c=lambda *_: moveItemDown(),
        ann='下移一位'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='sortName.png',
        w=20, h=20,
        c=lambda *_: sort_alpha_selected(),
        ann='按名称排序'
    )



    mc.iconTextButton(
        style='iconOnly',
        image1='ramp.svg',
        w=20, h=20,
        c=lambda *_: sort_color_outliner(),
        ann='按大纲颜色排序'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='sortName.png',
        bgc=[0.12, 0.12, 0.12],
        w=20, h=20,
        c=lambda *_: sort_all_hierarchy(),
        ann='排序整个层级'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='UVEditorVAxis.png',
        w=5, h=30, en=0
    )

    mc.iconTextButton('outlinerState',
        style='iconOnly',
        image1='hsShowRightTabsOnly.png',
        w=20, h=20,
        c=toggle_outliner_divider,
        ann='切换分割方向'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='nudgeUp.png',
        w=15, h=20,
        rpt=True,
        c=scroll_outliners_up,
        ann='大纲向上滚动'
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='nudgeDown.png',
        w=15, h=20,
        rpt=True,
        c=scroll_outliners_down,
        ann='大纲向下滚动'
    )
    # ---------------- 颜色区域 ----------------

    color_wrap = mc.columnLayout(adj=True, parent=form)

    mc.rowColumnLayout(
        parent=color_wrap,
        numberOfColumns=5,
        columnWidth=[(1, 60), (2, 10), (3, 75), (4, 80), (5, 75)]
    )

    mc.text(l="设置颜色", h=18)
    mc.text(l="", h=18)
    mc.checkBox(COLOR_CHK_OUTLINER, label="大纲", value=1)
    mc.checkBox(COLOR_CHK_VIEWPORT, label="线框", value=0)
    mc.checkBox(COLOR_CHK_SHADER, label="材质", value=0)

    mc.setParent(color_wrap)

    mc.gridLayout(numberOfColumns=12, cellWidthHeight=(26, 30))

    for shader_name, rgb in COLOR_PRESETS:
        mc.button(
            label="",
            w=25,
            h=20,
            bgc=list(rgb),
            c=lambda *_ , s=shader_name, cval=rgb: jw_apply_color(cval[0], cval[1], cval[2], s)
        )

    mc.iconTextButton(
        style='iconOnly',
        image1='UVEditorVAxis.png',
        en=0
    )

    mc.iconTextButton(
        style='iconOnly',
        image1='render_imagePlane.png',
        rpt=True,
        c=lambda *_: reset_outliner_color(),
        ann='重置颜色标记'
    )

    mc.setParent(form)

    # ---------------- 大纲 + QShade ----------------

    MAIN_PANE = mc.paneLayout(parent=form, configuration="horizontal2", st=50, ps=(1, 1, 100))

    mc.frameLayout(parent=MAIN_PANE, labelVisible=False, borderVisible=False)
    OUTLINER_PANEL = mc.outlinerPanel()
    try:
        OUTLINER_CTRL = mc.outlinerPanel(OUTLINER_PANEL, q=True, control=True)
        outliner_ed = mc.outlinerPanel(OUTLINER_PANEL, q=True, outlinerEditor=True)
        mc.outlinerEditor(
            outliner_ed,
            e=True,
            mainListConnection='worldList',
            selectionConnection='modelList',
            showShapes=False,
            showAttributes=False,
            showConnected=False,
            showAnimCurvesOnly=False,
            autoExpand=False,
            showDagOnly=True,
            ignoreDagHierarchy=False,
            expandConnections=False,
            showCompounds=True,
            showNumericAttrsOnly=False,
            highlightActive=True,
            autoSelectNewObjects=False,
            doNotSelectNewObjects=False,
            transmitFilters=False,
            showSetMembers=True,
            setFilter='defaultSetFilter'
        )
    except:
        pass
    mc.setParent('..')
    mc.setParent('..')

    build_qshade_ui(MAIN_PANE)
    mc.setParent('..')

    mc.formLayout(
        form, e=True,
        attachForm=[
            (toolbar, 'top', 4),
            (toolbar, 'left', 4),
            (toolbar, 'right', 4),

            (color_wrap, 'left', 4),
            (color_wrap, 'right', 4),

            (MAIN_PANE, 'left', 4),
            (MAIN_PANE, 'right', 4),
            (MAIN_PANE, 'bottom', 4),
        ],
        attachControl=[
            (color_wrap, 'top', 4, toolbar),
            (MAIN_PANE, 'top', 4, color_wrap),
        ]
    )

    qshade_set_auto_highlight(True)

    _build_scene_cache()
    _hide_always_hidden_nodes()
    _refresh_all_outliners()

    # UI 完全创建后安装尺寸监听器
    mc.evalDeferred(_install_qshade_resize_watcher)


build_outliner_x_ui()
