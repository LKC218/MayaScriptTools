# -*- coding: utf-8 -*-
"""
Camera Align 一键完整安装脚本 v7 Standalone
适用：Maya 2022+

本版修复：
- 不再依赖电脑里已经存在 camera_align.py。
- 脚本会自动把完整 camera_align.py 写入当前用户 Maya scripts 目录。
- 自动创建 / 更新 Shelf 按钮。
- 自动安装 Alt+Q/W/E/R 与 Ctrl+Alt+Q/W/E/R 快捷键。
- 自动打开优化后的 UI。

使用：
1. 直接将本文件拖入 Maya 窗口。
2. 或在 Script Editor 的 Python 标签执行本脚本。
"""

import os
import sys
import shutil
import traceback
import importlib
from datetime import datetime

import maya.cmds as cmds

CAMERA_ALIGN_SOURCE = r'''
# -*- coding: utf-8 -*-
"""
Camera Align for Maya 2022+ - Standalone Final

功能：
- 将 persp 相机对齐到当前选中多边形面的法线方向。
- 支持正交对齐视图下顺 / 逆时针旋转。
- 支持恢复透视相机。
- 提供现代化 UI、Shelf 按钮和快捷键。
"""

import os
import json
import maya.cmds as mc
import maya.mel as mel
import maya.api.OpenMaya as om2

WINDOW_NAME = "CameraAlignToolWindow"
WORKSPACE_CONTROL_NAME = "CameraAlignToolWorkspaceControl"
WINDOW_TITLE = "Camera Align"
ROTATE_FIELD_NAME = "CameraAlignRotateField"
STATUS_TEXT_NAME = "CameraAlignStatusText"
HOTKEY_HUD_NAME = "CameraAlignHotkeyHUD"
SHELF_BUTTON_NAME = "CameraAlignShelfButton"
HOTKEY_SET_NAME = "CameraAlign_HotkeySet"
HOTKEY_VERSION = "v7"
HOTKEY_BACKUP_FILE = "camera_align_hotkey_backup_v7.json"


class _AlignState(object):
    def __init__(self):
        self.reset_all()

    def reset_all(self):
        self.dir_view = None
        self.dir_up = None
        self.dir_right = None
        self.dist = None
        self.pos = None
        self.hview = None
        self.asp_rat = None
        self.cam = None

        self.pos_new = None
        self.dir_view_new = None
        self.cam_dir_up_new = None

        self.is_aligned = False
        self.script_job_id = None
        self.timer_callback_id = None

        self.model_panel = None
        self.grid_visible_before_align = None


_STATE = _AlignState()


def _display_info(message):
    om2.MGlobal.displayInfo("Camera Align: {0}".format(message))


def _display_warning(message):
    om2.MGlobal.displayWarning("Camera Align: {0}".format(message))


def _display_error(message):
    om2.MGlobal.displayError("Camera Align: {0}".format(message))


class Camera_Align(object):
    TIMER_INTERVAL = 0.005
    INTERP_STEPS = 100
    DEFAULT_ROTATE_STEP = 22.5

    def __init__(self):
        self.camera = None
        self.face_normal = None
        self.face_median = None
        self.cam_dir_up_new = None
        self.cam_dist = None
        self.cam_pos_new = None
        self.i = 0
        self.timer = None

    @staticmethod
    def _safe_normal(vector):
        vec = om2.MVector(vector)
        length = vec.length()
        if length < 1e-8:
            return om2.MVector()
        return vec / length

    @staticmethod
    def _camera_value(camera, attr_name):
        value = getattr(camera, attr_name)
        return value() if callable(value) else value

    @staticmethod
    def _camera_bool(camera, attr_name):
        value = getattr(camera, attr_name)
        return value() if callable(value) else value

    @staticmethod
    def _get_model_panel():
        focused = mc.getPanel(withFocus=True)
        if focused and mc.getPanel(typeOf=focused) == "modelPanel":
            return focused

        visible = mc.getPanel(visiblePanels=True) or []
        for panel in visible:
            if mc.getPanel(typeOf=panel) == "modelPanel":
                return panel

        panels = mc.getPanel(type="modelPanel") or []
        if panels:
            return panels[0]
        return "modelPanel4"

    @staticmethod
    def _set_grid_visible(visible):
        panel = _STATE.model_panel or Camera_Align._get_model_panel()
        if mc.getPanel(typeOf=panel) != "modelPanel":
            return
        mc.modelEditor(panel, e=True, grid=bool(visible))

    @staticmethod
    def _clear_timer():
        if _STATE.timer_callback_id is not None:
            try:
                om2.MMessage.removeCallback(_STATE.timer_callback_id)
            except RuntimeError:
                pass
            _STATE.timer_callback_id = None

    @staticmethod
    def _clear_script_job():
        if _STATE.script_job_id:
            try:
                mc.scriptJob(kill=_STATE.script_job_id, force=True)
            except RuntimeError:
                pass
            _STATE.script_job_id = None

    def get_trans_matrix(self, name):
        sel = om2.MGlobal.getSelectionListByName(name)
        dag_path = sel.getDagPath(0)
        if dag_path.node().hasFn(om2.MFn.kTransform):
            node_obj = dag_path.node()
        else:
            node_obj = dag_path.transform()

        node_fn = om2.MFnDependencyNode(node_obj)
        matrix_plug = om2.MPlug(node_obj, node_fn.attribute("worldMatrix")).elementByLogicalIndex(0)
        matrix_data = om2.MFnMatrixData(matrix_plug.asMObject())
        return om2.MTransformationMatrix(matrix_data.matrix())

    def _get_active_mesh_face_selection(self):
        sel = om2.MGlobal.getActiveSelectionList()
        if sel.length() == 0:
            raise RuntimeError("请先选择一个多边形面。")

        comp_iter = om2.MItSelectionList(sel, om2.MFn.kMeshPolygonComponent)
        if comp_iter.isDone():
            raise RuntimeError("当前选择不是多边形面，请切换到面选择模式后重试。")

        dag_path, component = comp_iter.getComponent()
        if dag_path.node().hasFn(om2.MFn.kTransform):
            try:
                dag_path.extendToShape()
            except RuntimeError:
                pass

        if not dag_path.node().hasFn(om2.MFn.kMesh):
            raise RuntimeError("当前选择不是网格对象。")

        return sel, dag_path, component

    def get_sel_face_id_normal_median(self, mdag, selection):
        comp_iter = om2.MItSelectionList(selection, om2.MFn.kMeshPolygonComponent)
        if comp_iter.isDone():
            raise RuntimeError("没有检测到有效的面选择。")

        dag_path, component = comp_iter.getComponent()
        face_iter = om2.MItMeshPolygon(dag_path, component)
        face_id = face_iter.index()

        face_normal = self.get_trans_matrix(mdag.fullPathName()).asMatrixInverse() * face_iter.getNormal()
        face_normal = self._safe_normal(face_normal)
        face_median = om2.MVector(face_iter.center(space=om2.MSpace.kWorld))
        return face_id, face_normal, face_median

    def get_face_tangent_cam_based(self, mesh, face, face_normal, cam_dir_view, cam_dir_up, cam_dir_right):
        cam_dir_view_inv = cam_dir_view * -1
        face_verts = mesh.getPolygonVertices(face)
        face_verts_vecs = [om2.MVector(mesh.getPoint(v, space=om2.MSpace.kWorld)) for v in face_verts]
        face_verts_vecs += face_verts_vecs[0:1]

        face_tangent = om2.MVector()
        dot_max = 0.0

        for vec_a, vec_b in zip(face_verts_vecs[1:], face_verts_vecs):
            vec_a1 = self._safe_normal(vec_a - vec_b)
            vec_b1 = vec_a1 * -1

            vec_a1_2d = self._safe_normal(vec_a1 - (vec_a1 * cam_dir_view_inv) * cam_dir_view_inv)
            vec_b1_2d = self._safe_normal(vec_b1 - (vec_b1 * cam_dir_view_inv) * cam_dir_view_inv)

            dot_a = vec_a1_2d * cam_dir_up
            dot_b = vec_b1_2d * cam_dir_up
            dot_c = vec_a1_2d * cam_dir_right
            dot_d = vec_b1_2d * cam_dir_right

            for index, dot in enumerate([dot_a, dot_b, dot_c, dot_d]):
                if dot > dot_max:
                    dot_max = dot
                    if index == 0:
                        face_tangent = vec_a1
                    elif index == 1:
                        face_tangent = vec_b1
                    elif index == 2:
                        face_tangent = self._safe_normal(face_normal ^ vec_a1)
                    elif index == 3:
                        face_tangent = self._safe_normal(face_normal ^ vec_b1)

        if face_tangent.length() < 1e-8:
            face_tangent = cam_dir_up
        return self._safe_normal(face_tangent)

    def store_cam_options(self, camera):
        _STATE.pos = camera.eyePoint(space=om2.MSpace.kWorld)
        _STATE.dir_view = camera.viewDirection(space=om2.MSpace.kWorld)
        _STATE.dir_up = camera.upDirection(space=om2.MSpace.kWorld)
        _STATE.dir_right = camera.rightDirection(space=om2.MSpace.kWorld)
        _STATE.dist = self._camera_value(camera, "centerOfInterest")
        _STATE.hview = camera.horizontalFieldOfView()
        _STATE.asp_rat = camera.aspectRatio()

    def get_presp_cam(self):
        try:
            cam_mdag = om2.MGlobal.getSelectionListByName("perspShape").getDagPath(0)
        except RuntimeError:
            cam_mdag = om2.MGlobal.getSelectionListByName("persp").getDagPath(0)
            if cam_mdag.node().hasFn(om2.MFn.kTransform):
                cam_mdag.extendToShape()
        return om2.MFnCamera(cam_mdag)

    def make_manip_screen_space(self):
        try:
            cam_matrix = self.get_trans_matrix("persp")
            manip_rot = [om2.MAngle(angle).asDegrees() for angle in cam_matrix.rotation()]
            mc.manipPivot(o=manip_rot)
        except Exception:
            pass

    def set_align_mode(self):
        try:
            self.main()
            self.camera.setIsOrtho(True, self.cam_dist)

            _STATE.model_panel = self._get_model_panel()
            if mc.getPanel(typeOf=_STATE.model_panel) == "modelPanel":
                _STATE.grid_visible_before_align = mc.modelEditor(_STATE.model_panel, q=True, grid=True)
            else:
                _STATE.grid_visible_before_align = None

            self._set_grid_visible(False)
            self.make_manip_screen_space()
            self.add_remove_script_job()
            _STATE.is_aligned = True
            _display_info("已对齐到当前选中面。")
            return True
        except Exception as exc:
            self._clear_timer()
            self._clear_script_job()
            _STATE.is_aligned = False
            _display_error(exc)
            return False

    def transform_cam(self, *args, **kwargs):
        cam_pos_quat = om2.MQuaternion(
            om2.MVector(_STATE.pos - self.face_median),
            self.cam_pos_new - self.face_median,
            factor=(self.i / 100.0),
        )
        cam_pos_step = om2.MPoint(
            om2.MVector(_STATE.pos - self.face_median).rotateBy(cam_pos_quat) + self.face_median
        )

        cam_dir_quat = om2.MQuaternion(_STATE.dir_view, self.face_normal * -1, factor=(self.i / 100.0))
        cam_dir_step = _STATE.dir_view.rotateBy(cam_dir_quat)

        cam_dir_up_quat = om2.MQuaternion(_STATE.dir_up, self.cam_dir_up_new, factor=(self.i / 100.0))
        cam_dir_up_step = _STATE.dir_up.rotateBy(cam_dir_up_quat)

        self.camera.set(cam_pos_step, cam_dir_step, cam_dir_up_step, _STATE.hview, _STATE.asp_rat)
        _STATE.cam = self.camera

        if self.i >= self.INTERP_STEPS:
            self._clear_timer()
            _STATE.pos_new = cam_pos_step
            _STATE.dir_view_new = cam_dir_step
            _STATE.cam_dir_up_new = cam_dir_up_step
            self.make_manip_screen_space()
            return

        self.i += 1

    def rotate_cam(self, angle=22.5):
        if not _STATE.is_aligned or _STATE.cam is None:
            _display_warning("当前还没有进入对齐模式。")
            return None

        if not self._camera_bool(_STATE.cam, "isOrtho"):
            _display_warning("当前相机不是正交模式，无法旋转。")
            return None

        if _STATE.dir_view_new is None:
            _STATE.dir_view_new = _STATE.cam.viewDirection(space=om2.MSpace.kWorld)
        if _STATE.cam_dir_up_new is None:
            _STATE.cam_dir_up_new = _STATE.cam.upDirection(space=om2.MSpace.kWorld)
        if _STATE.pos_new is None:
            _STATE.pos_new = _STATE.cam.eyePoint(space=om2.MSpace.kWorld)

        angle_as_rad = om2.MAngle(angle, om2.MAngle.kDegrees).asRadians() * -1
        quat_a = om2.MQuaternion(_STATE.dir_view_new, om2.MVector(0, 0, 1))
        new_dir_up = _STATE.cam_dir_up_new.rotateBy(quat_a)
        new_dir_up = new_dir_up.rotateBy(om2.MEulerRotation(0, 0, angle_as_rad)).rotateBy(quat_a.inverse())

        _STATE.pos_new = _STATE.cam.eyePoint(space=om2.MSpace.kWorld)
        _STATE.cam_dir_up_new = new_dir_up
        _STATE.cam.set(_STATE.pos_new, _STATE.dir_view_new, _STATE.cam_dir_up_new, _STATE.hview, _STATE.asp_rat)
        self.make_manip_screen_space()
        _display_info("已旋转 {0}°".format(angle))
        return True

    def add_remove_script_job(self, rem=False):
        self._clear_script_job()
        if rem:
            return
        _STATE.script_job_id = mc.scriptJob(e=("SelectionChanged", lambda *unused: self.make_manip_screen_space()))

    def remove_align_mode(self):
        if not _STATE.is_aligned:
            _display_warning("当前未处于对齐模式。")
            return None

        self.add_remove_script_job(rem=True)
        self._clear_timer()
        camera = self.get_presp_cam()

        try:
            up_axis_name = str(mc.upAxis(q=True, axis=True)).lower()
        except Exception:
            up_axis_name = str(mc.upAxis(q=True, ax=True)).lower()
        up_axis = om2.MVector(0, 1, 0) if up_axis_name == "y" else om2.MVector(0, 0, 1)

        dot_dir_up_a = _STATE.dir_up * up_axis
        dot_dir_up_b = _STATE.dir_up * (up_axis * -1)
        if dot_dir_up_a > dot_dir_up_b:
            quat = om2.MQuaternion(_STATE.dir_up, up_axis)
        else:
            quat = om2.MQuaternion(_STATE.dir_up, up_axis * -1)

        camera.set(_STATE.pos, _STATE.dir_view, _STATE.dir_up.rotateBy(quat), _STATE.hview, _STATE.asp_rat)

        if _STATE.grid_visible_before_align is None:
            self._set_grid_visible(True)
        else:
            self._set_grid_visible(_STATE.grid_visible_before_align)

        camera.setIsOrtho(False)
        _STATE.is_aligned = False
        _display_info("已恢复透视相机。")
        return True

    def align_obj_to_cam_plane(self):
        if not _STATE.is_aligned:
            return None
        _display_warning("align_obj_to_cam_plane() 在原始脚本中未完成，当前版本保留占位接口。")
        return None

    def main(self):
        self.camera = self.get_presp_cam()
        self.store_cam_options(self.camera)

        selection, mdag, component = self._get_active_mesh_face_selection()
        mesh = om2.MFnMesh(mdag)
        face, self.face_normal, self.face_median = self.get_sel_face_id_normal_median(mdag, selection)

        self.cam_dir_up_new = self.get_face_tangent_cam_based(
            mesh,
            face,
            self.face_normal,
            _STATE.dir_view,
            _STATE.dir_up,
            _STATE.dir_right,
        )
        self.cam_dist = (om2.MVector(_STATE.pos) - self.face_median).length()
        self.cam_pos_new = self.face_normal * self.cam_dist + self.face_median

        self.i = 0
        self._clear_timer()
        self.timer = om2.MTimerMessage.addTimerCallback(self.TIMER_INTERVAL, self.transform_cam)
        _STATE.timer_callback_id = self.timer
        return True


# -----------------------------
# 功能封装
# -----------------------------
def align_camera_to_selected_polygon():
    return Camera_Align().set_align_mode()


def rotate_aligned_camera(angle=22.5):
    return Camera_Align().rotate_cam(angle)


def rotate_aligned_camera_clockwise(step=22.5):
    return Camera_Align().rotate_cam(step)


def rotate_aligned_camera_counter_clockwise(step=22.5):
    return Camera_Align().rotate_cam(-step)


def restore_perspective_camera():
    return Camera_Align().remove_align_mode()


def get_rotate_step_from_ui(default_value=22.5):
    if mc.control(ROTATE_FIELD_NAME, exists=True):
        try:
            return float(mc.floatField(ROTATE_FIELD_NAME, q=True, value=True))
        except Exception:
            return float(default_value)
    return float(default_value)


# -----------------------------
# UI
# -----------------------------
def _ui_color(name):
    colors = {
        "primary": (0.22, 0.45, 0.76),
        "secondary": (0.27, 0.27, 0.30),
        "muted": (0.18, 0.18, 0.20),
        "success": (0.20, 0.42, 0.26),
        "danger": (0.50, 0.23, 0.20),
        "panel": (0.20, 0.20, 0.21),
        "status": (0.16, 0.16, 0.17),
        "warn": (0.50, 0.36, 0.18),
    }
    return colors.get(name, colors["secondary"])


def _ui_button(label, command, height=32, color="secondary", annotation=None):
    kwargs = {
        "label": label,
        "height": height,
        "command": command,
        "backgroundColor": _ui_color(color),
    }
    if annotation:
        kwargs["annotation"] = annotation
    try:
        return mc.button(**kwargs)
    except Exception:
        kwargs.pop("backgroundColor", None)
        return mc.button(**kwargs)


def _set_status(message, level="info"):
    if mc.control(STATUS_TEXT_NAME, exists=True):
        try:
            bg = _ui_color("status")
            if level == "ok":
                bg = _ui_color("success")
            elif level == "warn":
                bg = _ui_color("warn")
            elif level == "error":
                bg = _ui_color("danger")
            mc.text(STATUS_TEXT_NAME, edit=True, label=message, backgroundColor=bg)
        except Exception:
            try:
                mc.text(STATUS_TEXT_NAME, edit=True, label=message)
            except Exception:
                pass

    if level == "error":
        _display_error(message)
    elif level == "warn":
        _display_warning(message)
    else:
        _display_info(message)


def _safe_call(func, success=None, fail=None, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
        if result not in (None, False):
            if success:
                _set_status(success, "ok")
        else:
            if fail:
                _set_status(fail, "warn")
        return result
    except Exception as exc:
        _set_status(str(exc), "error")
        return None


def _set_rotate_step(value):
    try:
        if mc.control(ROTATE_FIELD_NAME, exists=True):
            mc.floatField(ROTATE_FIELD_NAME, edit=True, value=float(value))
        _set_status("旋转步长已设为 {0:g}°".format(float(value)), "ok")
    except Exception as exc:
        _set_status("旋转步长设置失败：{0}".format(exc), "error")


def close_camera_align_ui():
    if mc.workspaceControl(WORKSPACE_CONTROL_NAME, exists=True):
        try:
            mc.deleteUI(WORKSPACE_CONTROL_NAME)
        except Exception:
            pass
    if mc.window(WINDOW_NAME, exists=True):
        mc.deleteUI(WINDOW_NAME, window=True)


def _hotkey_hud_text():
    return "Alt+Q 对齐   Alt+W 顺转   Alt+E 逆转   Alt+R 恢复"


def _find_free_hud_slot():
    preferred_slots = [
        (5, 0), (5, 1), (5, 2),
        (6, 0), (6, 1), (6, 2),
        (4, 0), (4, 1), (4, 2),
        (7, 0), (7, 1), (7, 2),
        (8, 0), (8, 1), (8, 2),
        (9, 0), (9, 1), (9, 2),
    ]
    for section, block in preferred_slots:
        try:
            occupied = mc.headsUpDisplay(section=section, block=block, blockOccupied=True)
        except Exception:
            occupied = True
        if not occupied:
            return section, block

    for section in range(10):
        try:
            block = mc.headsUpDisplay(nextFreeBlock=section)
        except Exception:
            block = None
        if block is not None:
            return section, block
    return 5, 0


def show_shortcut_hud():
    hide_shortcut_hud()
    section, block = _find_free_hud_slot()
    try:
        mc.headsUpDisplay(
            HOTKEY_HUD_NAME,
            section=section,
            block=block,
            blockSize="medium",
            label="Camera Align",
            labelFontSize="small",
            dataFontSize="small",
            command=_hotkey_hud_text,
            attachToRefresh=True,
            allowOverlap=True,
        )
    except Exception:
        try:
            mc.headsUpDisplay(
                HOTKEY_HUD_NAME,
                section=section,
                block=block,
                blockSize="medium",
                label="Camera Align",
                command=_hotkey_hud_text,
            )
        except Exception as exc:
            _display_warning("视窗快捷键提示创建失败：{0}".format(exc))
            return None
    return HOTKEY_HUD_NAME


def hide_shortcut_hud():
    try:
        if mc.headsUpDisplay(HOTKEY_HUD_NAME, exists=True):
            mc.headsUpDisplay(HOTKEY_HUD_NAME, remove=True)
    except Exception:
        pass
    return True


def create_or_update_shelf_button():
    top_level = mel.eval("$tmpVar=$gShelfTopLevel")
    if not top_level or not mc.control(top_level, exists=True):
        raise RuntimeError("未找到 Maya Shelf 区域。")

    current_shelf = mc.tabLayout(top_level, q=True, selectTab=True)
    if not current_shelf:
        raise RuntimeError("未找到当前 Shelf 页签。")

    if mc.control(SHELF_BUTTON_NAME, exists=True):
        try:
            mc.deleteUI(SHELF_BUTTON_NAME)
        except Exception:
            pass

    command = (
        "import importlib\n"
        "import camera_align\n"
        "importlib.reload(camera_align)\n"
        "camera_align.show_camera_align_ui()\n"
    )

    mc.shelfButton(
        SHELF_BUTTON_NAME,
        parent=current_shelf,
        label="CamAlign",
        annotation="打开 Camera Align 工具窗口",
        command=command,
        sourceType="python",
        image1="commandButton.png",
        imageOverlayLabel="CA",
        style="iconAndTextVertical",
    )

    try:
        mc.saveShelf(current_shelf, os.path.join(mc.internalVar(userShelfDir=True), current_shelf + ".mel"))
    except Exception:
        pass

    _set_status("Shelf 按钮已创建 / 更新。", "ok")
    return SHELF_BUTTON_NAME


def _build_camera_align_ui_content(parent):
    mc.setParent(parent)
    scroll = mc.scrollLayout(childResizable=True, horizontalScrollBarThickness=0)
    root = mc.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10))

    try:
        mc.frameLayout(labelVisible=False, borderVisible=False, marginWidth=12, marginHeight=10, backgroundColor=_ui_color("panel"))
    except Exception:
        mc.frameLayout(labelVisible=False, borderVisible=False, marginWidth=12, marginHeight=10)
    mc.columnLayout(adjustableColumn=True, rowSpacing=5)
    mc.text(label="Camera Align", align="left", height=24, font="boldLabelFont")
    mc.text(label="选择一个多边形面，将 persp 相机对齐到该面的法线方向。", align="left", wordWrap=True)
    mc.text(label="快捷键：Alt+Q/W/E/R；备用：Ctrl+Alt+Q/W/E/R。", align="left", wordWrap=True)
    mc.setParent(root)

    try:
        mc.text(
            STATUS_TEXT_NAME,
            label="就绪：选择一个面后，点击对齐或使用 Alt+Q。",
            align="left",
            wordWrap=True,
            height=34,
            backgroundColor=_ui_color("status"),
        )
    except Exception:
        mc.text(STATUS_TEXT_NAME, label="就绪：选择一个面后，点击对齐或使用 Alt+Q。", align="left", wordWrap=True, height=34)

    mc.frameLayout(label="主要操作", collapsable=True, collapse=False, marginWidth=10, marginHeight=8, borderVisible=True)
    mc.columnLayout(adjustableColumn=True, rowSpacing=8)
    _ui_button(
        "01  对齐到当前选中面",
        lambda *a: _safe_call(
            align_camera_to_selected_polygon,
            "已进入对齐模式，可旋转或恢复。",
            "对齐失败：请确认已选择多边形面。",
        ),
        height=42,
        color="primary",
    )

    mc.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 188), (2, 188)], columnSpacing=[(1, 6), (2, 6)])
    _ui_button(
        "顺时针旋转",
        lambda *a: _safe_call(
            rotate_aligned_camera_clockwise,
            "已顺时针旋转 {0:g}°。".format(get_rotate_step_from_ui()),
            "当前未处于对齐模式。",
            get_rotate_step_from_ui(),
        ),
        height=36,
        color="secondary",
    )
    _ui_button(
        "逆时针旋转",
        lambda *a: _safe_call(
            rotate_aligned_camera_counter_clockwise,
            "已逆时针旋转 {0:g}°。".format(get_rotate_step_from_ui()),
            "当前未处于对齐模式。",
            get_rotate_step_from_ui(),
        ),
        height=36,
        color="secondary",
    )
    mc.setParent("..")

    _ui_button(
        "恢复透视相机",
        lambda *a: _safe_call(restore_perspective_camera, "已恢复透视相机。", "当前未处于对齐模式。"),
        height=36,
        color="danger",
    )
    mc.setParent(root)

    mc.frameLayout(label="旋转设置", collapsable=True, collapse=False, marginWidth=10, marginHeight=8, borderVisible=True)
    mc.columnLayout(adjustableColumn=True, rowSpacing=8)
    mc.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(82, 235, 35), columnAlign3=("left", "left", "left"))
    mc.text(label="旋转步长")
    mc.floatField(ROTATE_FIELD_NAME, value=22.5, precision=3, minValue=0.001)
    mc.text(label="度")
    mc.setParent("..")

    mc.rowColumnLayout(numberOfColumns=4, columnWidth=[(1, 92), (2, 92), (3, 92), (4, 92)], columnSpacing=[(1, 5), (2, 5), (3, 5), (4, 5)])
    for preset in (15.0, 22.5, 45.0, 90.0):
        _ui_button("{0:g}°".format(preset), lambda *a, v=preset: _set_rotate_step(v), height=28, color="muted")
    mc.setParent(root)

    mc.frameLayout(label="视窗提示", collapsable=True, collapse=False, marginWidth=10, marginHeight=8, borderVisible=True)
    mc.columnLayout(adjustableColumn=True, rowSpacing=8)
    mc.text(label="在 3D 视窗左下角显示 Camera Align 快捷键。", align="left", wordWrap=True)
    mc.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 188), (2, 188)], columnSpacing=[(1, 6), (2, 6)])
    _ui_button("显示快捷键提示", lambda *a: _safe_call(show_shortcut_hud, "视窗快捷键提示已显示。"), height=32, color="success")
    _ui_button("隐藏快捷键提示", lambda *a: _safe_call(hide_shortcut_hud, "视窗快捷键提示已隐藏。"), height=32, color="muted")
    mc.setParent(root)

    mc.frameLayout(label="工具入口", collapsable=True, collapse=True, marginWidth=10, marginHeight=8, borderVisible=True)
    mc.columnLayout(adjustableColumn=True, rowSpacing=8)
    mc.text(label="Shelf 按钮丢失时，可在这里重新创建。", align="left", wordWrap=True)
    mc.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 188), (2, 188)], columnSpacing=[(1, 6), (2, 6)])
    _ui_button("创建 / 更新 Shelf", lambda *a: _safe_call(create_or_update_shelf_button, "Shelf 按钮已更新。"), height=32, color="success")
    _ui_button("关闭窗口", lambda *a: close_camera_align_ui(), height=32, color="muted")
    mc.setParent(root)

    mc.separator(style="none", height=4)
    return scroll


def show_camera_align_ui():
    close_camera_align_ui()

    if hasattr(mc, "workspaceControl"):
        try:
            workspace = mc.workspaceControl(
                WORKSPACE_CONTROL_NAME,
                label=WINDOW_TITLE,
                retain=False,
                floating=True,
                initialWidth=430,
                initialHeight=560,
                minimumWidth=360,
                widthProperty="preferred",
            )
            _build_camera_align_ui_content(workspace)
            mc.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, visible=True)
            try:
                mc.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, restore=True)
            except Exception:
                pass
            show_shortcut_hud()
            return workspace
        except Exception as exc:
            _display_warning("停靠面板创建失败，将使用普通窗口：{0}".format(exc))

    win = mc.window(WINDOW_NAME, title=WINDOW_TITLE, sizeable=True, widthHeight=(430, 560))
    _build_camera_align_ui_content(win)

    mc.showWindow(win)
    try:
        mc.window(win, edit=True, widthHeight=(430, 560))
    except Exception:
        pass
    show_shortcut_hud()
    return win


# -----------------------------
# Hotkey
# -----------------------------
def _ensure_hotkey_set():
    try:
        current_set = mc.hotkeySet(q=True, current=True)
    except Exception:
        current_set = None

    try:
        if mc.hotkeySet(HOTKEY_SET_NAME, exists=True):
            mc.hotkeySet(HOTKEY_SET_NAME, edit=True, current=True)
            return HOTKEY_SET_NAME
        if current_set:
            mc.hotkeySet(HOTKEY_SET_NAME, source=current_set, current=True)
        else:
            mc.hotkeySet(HOTKEY_SET_NAME, current=True)
        return HOTKEY_SET_NAME
    except Exception as exc:
        print("Camera Align: 创建 Hotkey Set 失败，将继续尝试当前热键集：{0}".format(exc))
        return current_set or "<unknown>"


def _clear_hotkey(key, alt=False, ctrl=False, shift=False):
    base = dict(keyShortcut=key, altModifier=alt, ctrlModifier=ctrl, shiftModifier=shift)
    try:
        args = dict(base)
        args["name"] = ""
        mc.hotkey(**args)
    except Exception:
        pass
    try:
        args = dict(base)
        args["releaseName"] = ""
        mc.hotkey(**args)
    except Exception:
        pass


def _name_command(command_id, combo_name, label, mel_command):
    name = "CameraAlign_{0}_{1}_{2}_NameCommand".format(command_id, combo_name, HOTKEY_VERSION)
    try:
        mc.nameCommand(name, annotation="Camera Align: {0}".format(label), command=mel_command, sourceType="mel")
    except RuntimeError:
        pass
    return name


def _bind_hotkey(key, name_command, alt=False, ctrl=False, shift=False):
    _clear_hotkey(key, alt=alt, ctrl=ctrl, shift=shift)
    mc.hotkey(keyShortcut=key, altModifier=alt, ctrlModifier=ctrl, shiftModifier=shift, name=name_command, pressCommandRepeat=True)


def install_hotkeys(show_dialog=True):
    commands = [
        ("Align", "q", "对齐到当前选中面", 'python("import camera_align; camera_align.align_camera_to_selected_polygon()");'),
        ("RotateCW", "w", "顺时针旋转 22.5 度", 'python("import camera_align; camera_align.rotate_aligned_camera_clockwise()");'),
        ("RotateCCW", "e", "逆时针旋转 22.5 度", 'python("import camera_align; camera_align.rotate_aligned_camera_counter_clockwise()");'),
        ("Restore", "r", "恢复透视相机", 'python("import camera_align; camera_align.restore_perspective_camera()");'),
    ]
    combos = [
        ("Alt", dict(alt=True, ctrl=False, shift=False)),
        ("CtrlAlt", dict(alt=True, ctrl=True, shift=False)),
    ]

    active_set = _ensure_hotkey_set()
    for command_id, key, label, mel_command in commands:
        for combo_name, mods in combos:
            nc = _name_command(command_id, combo_name, label, mel_command)
            _bind_hotkey(key, nc, **mods)

    try:
        mc.hotkey(autoSave=True)
    except Exception:
        pass
    try:
        mc.savePrefs(hotkeys=True)
    except Exception:
        pass

    if show_dialog:
        message = "快捷键已启用。\n\nAlt+Q/W/E/R：对齐 / 顺转 / 逆转 / 恢复\nCtrl+Alt+Q/W/E/R：备用组合\n\n当前 Hotkey Set：{0}".format(active_set)
        mc.confirmDialog(title="Camera Align", message=message, button=["OK"])
    return True


def remove_reserved_hotkeys():
    for key in ("q", "w", "e", "r"):
        _clear_hotkey(key, alt=True, ctrl=False, shift=False)
        _clear_hotkey(key, alt=True, ctrl=True, shift=False)
    try:
        mc.hotkey(autoSave=True)
    except Exception:
        pass
    try:
        mc.savePrefs(hotkeys=True)
    except Exception:
        pass
    _set_status("Camera Align 快捷键已清理。", "ok")
    return True


CameraAlign = Camera_Align
'''


def _user_scripts_dir():
    path = cmds.internalVar(userScriptDir=True)
    path = os.path.normpath(path)
    if not os.path.isdir(path):
        os.makedirs(path)
    if path not in sys.path:
        sys.path.insert(0, path)
    return path


def _camera_align_path():
    return os.path.join(_user_scripts_dir(), "camera_align.py")


def _backup_existing_file(path):
    if not os.path.isfile(path):
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(os.path.dirname(path), "camera_align_backup_{0}.py".format(stamp))
    shutil.copy2(path, backup_path)
    return backup_path


def _write_camera_align():
    path = _camera_align_path()
    backup_path = _backup_existing_file(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(CAMERA_ALIGN_SOURCE)
    return path, backup_path


def _import_camera_align():
    importlib.invalidate_caches()
    if "camera_align" in sys.modules:
        module = importlib.reload(sys.modules["camera_align"])
    else:
        module = importlib.import_module("camera_align")
    return module


def install():
    module_path, backup_path = _write_camera_align()
    module = _import_camera_align()

    shelf_status = "Shelf 按钮：已创建 / 更新"
    try:
        module.create_or_update_shelf_button()
    except Exception as exc:
        shelf_status = "Shelf 按钮：创建失败，可在 UI 内重试（{0}）".format(exc)

    try:
        module.install_hotkeys(show_dialog=False)
    except Exception as exc:
        raise RuntimeError("快捷键安装失败：{0}".format(exc))

    try:
        module.show_camera_align_ui()
    except Exception as exc:
        print("Camera Align: UI 打开失败：{0}".format(exc))
        try:
            module.show_shortcut_hud()
        except Exception:
            pass

    lines = [
        "Camera Align 安装完成。",
        "",
        "UI 入口：Shelf 按钮 CamAlign，可拖拽停靠到 Maya 界面。",
        "面板分组：主要操作 / 旋转设置 / 视窗提示 / 工具入口均可折叠。",
        "视窗提示：3D 视窗会显示快捷键 HUD。",
        "快捷键：Alt+Q / W / E / R",
        "备用键：Ctrl+Alt+Q / W / E / R",
        shelf_status,
        "",
        "已写入：{0}".format(module_path),
    ]
    if backup_path:
        lines.append("旧文件备份：{0}".format(backup_path))
    lines.extend([
        "",
        "提示：执行后先点击 Maya 视口，再使用快捷键。",
    ])

    message = "\n".join(lines)
    print(message)
    cmds.confirmDialog(title="Camera Align", message=message, button=["OK"])
    return True


def onMayaDroppedPythonFile(*args):
    try:
        install()
    except Exception as exc:
        msg = "Camera Align 安装失败：{0}\n\n{1}".format(exc, traceback.format_exc())
        print(msg)
        try:
            cmds.confirmDialog(title="Camera Align 安装失败", message=msg, button=["OK"])
        except Exception:
            pass
        raise


if __name__ == "__main__":
    install()
