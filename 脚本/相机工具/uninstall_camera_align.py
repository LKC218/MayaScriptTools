# -*- coding: utf-8 -*-
"""
Camera Align 插件卸载脚本
适用：Maya 2022+

功能：
- 删除 camera_align.py 脚本文件
- 删除 Shelf 按钮
- 关闭并删除 UI 窗口 / WorkspaceControl
- 移除 HUD 显示
- 清理所有 Camera Align 相关快捷键和 nameCommand
- 删除图标文件和配置文件
- 清理 Hotkey Set

使用：
1. 直接将本文件拖入 Maya 窗口。
2. 或在 Script Editor 的 Python 标签执行本脚本。
"""

import os
import sys
import traceback

import maya.cmds as cmds
import maya.mel as mel


def _display_info(message):
    print("[Camera Align Uninstall] {0}".format(message))


def _display_warning(message):
    sys.stdout.write("[Camera Align Uninstall] 警告: {0}\n".format(message))


def _display_error(message):
    sys.stderr.write("[Camera Align Uninstall] 错误: {0}\n".format(message))


# -----------------------------
# 文件清理
# -----------------------------
def _user_scripts_dir():
    path = cmds.internalVar(userScriptDir=True)
    path = os.path.normpath(path)
    return path


def _user_icons_dir():
    path = cmds.internalVar(userBitmapsDir=True)
    path = os.path.normpath(path)
    return path


def _remove_script_file():
    path = os.path.join(_user_scripts_dir(), "camera_align.py")
    removed = []
    if os.path.isfile(path):
        try:
            os.remove(path)
            removed.append(path)
            _display_info("已删除脚本文件: {0}".format(path))
        except Exception as exc:
            _display_error("删除脚本文件失败: {0} - {1}".format(path, exc))
    else:
        _display_info("脚本文件不存在，跳过: {0}".format(path))

    # 同时尝试删除 pyc 缓存
    for ext in (".pyc", ".pyo"):
        cache_path = path + ext
        if os.path.isfile(cache_path):
            try:
                os.remove(cache_path)
                removed.append(cache_path)
            except Exception:
                pass

    # 清理 __pycache__ 中的缓存
    pycache_dir = os.path.join(_user_scripts_dir(), "__pycache__")
    if os.path.isdir(pycache_dir):
        for fname in os.listdir(pycache_dir):
            if fname.startswith("camera_align."):
                try:
                    fpath = os.path.join(pycache_dir, fname)
                    os.remove(fpath)
                    removed.append(fpath)
                except Exception:
                    pass
    return removed


def _remove_icon_file():
    path = os.path.join(_user_icons_dir(), "camera_align_face_normal_icon.png")
    if os.path.isfile(path):
        try:
            os.remove(path)
            _display_info("已删除图标文件: {0}".format(path))
            return True
        except Exception as exc:
            _display_error("删除图标文件失败: {0} - {1}".format(path, exc))
    else:
        _display_info("图标文件不存在，跳过: {0}".format(path))
    return False


def _remove_config_file():
    path = os.path.join(_user_scripts_dir(), "camera_align_hotkeys.json")
    if os.path.isfile(path):
        try:
            os.remove(path)
            _display_info("已删除配置文件: {0}".format(path))
            return True
        except Exception as exc:
            _display_error("删除配置文件失败: {0} - {1}".format(path, exc))
    else:
        _display_info("配置文件不存在，跳过: {0}".format(path))
    return False


# -----------------------------
# UI / HUD / Shelf 清理
# -----------------------------
def _close_ui():
    window_name = "CameraAlignToolWindow"
    workspace_name = "CameraAlignToolWorkspaceControl"
    hud_name = "CameraAlignHotkeyHUD"

    if cmds.workspaceControl(workspace_name, exists=True):
        try:
            cmds.deleteUI(workspace_name)
            _display_info("已删除 WorkspaceControl: {0}".format(workspace_name))
        except Exception as exc:
            _display_error("删除 WorkspaceControl 失败: {0}".format(exc))
    else:
        _display_info("WorkspaceControl 不存在，跳过: {0}".format(workspace_name))

    if cmds.window(window_name, exists=True):
        try:
            cmds.deleteUI(window_name, window=True)
            _display_info("已删除窗口: {0}".format(window_name))
        except Exception as exc:
            _display_error("删除窗口失败: {0}".format(exc))
    else:
        _display_info("窗口不存在，跳过: {0}".format(window_name))

    if cmds.headsUpDisplay(hud_name, exists=True):
        try:
            cmds.headsUpDisplay(hud_name, remove=True)
            _display_info("已删除 HUD: {0}".format(hud_name))
        except Exception as exc:
            _display_error("删除 HUD 失败: {0}".format(exc))
    else:
        _display_info("HUD 不存在，跳过: {0}".format(hud_name))


def _remove_shelf_button():
    button_name = "CameraAlignShelfButton"
    if cmds.control(button_name, exists=True):
        try:
            cmds.deleteUI(button_name)
            _display_info("已删除 Shelf 按钮: {0}".format(button_name))
            return True
        except Exception as exc:
            _display_error("删除 Shelf 按钮失败: {0}".format(exc))
    else:
        _display_info("Shelf 按钮不存在，跳过: {0}".format(button_name))
    return False


# -----------------------------
# 快捷键 / nameCommand 清理
# -----------------------------
def _list_camera_align_name_commands():
    result = []
    try:
        all_names = cmds.nameCommand(queryAll=True) or []
        for name in all_names:
            if name and str(name).startswith("CameraAlign_"):
                result.append(name)
    except Exception as exc:
        _display_warning("获取 nameCommand 列表失败: {0}".format(exc))
    return result


def _remove_name_commands():
    names = _list_camera_align_name_commands()
    if not names:
        _display_info("没有检测到 Camera Align 相关的 nameCommand。")
        return False

    removed_count = 0
    for name in names:
        try:
            cmds.nameCommand(name, remove=True)
            removed_count += 1
        except Exception as exc:
            _display_warning("删除 nameCommand 失败 [{0}]: {1}".format(name, exc))
    _display_info("已删除 {0} 个 nameCommand。".format(removed_count))
    return removed_count > 0


def _clear_camera_align_hotkeys():
    # 尝试清理已知的快捷键组合
    keys_to_clear = []
    for key in ("q", "w", "e", "r"):
        keys_to_clear.append((key, True, False, False))   # Alt
        keys_to_clear.append((key, True, True, False))    # Ctrl+Alt

    cleared = 0
    for key, alt, ctrl, shift in keys_to_clear:
        try:
            press_name = ""
            release_name = ""
            try:
                press_name = cmds.hotkey(keyShortcut=key, altModifier=alt, ctrlModifier=ctrl, shiftModifier=shift, query=True, name=True) or ""
            except Exception:
                pass
            try:
                release_name = cmds.hotkey(keyShortcut=key, altModifier=alt, ctrlModifier=ctrl, shiftModifier=shift, query=True, releaseName=True) or ""
            except Exception:
                pass

            is_ours = False
            if press_name and str(press_name).startswith("CameraAlign_"):
                is_ours = True
            if release_name and str(release_name).startswith("CameraAlign_"):
                is_ours = True

            if is_ours:
                kwargs = {
                    "keyShortcut": key,
                    "altModifier": alt,
                    "ctrlModifier": ctrl,
                    "shiftModifier": shift,
                    "name": "",
                    "releaseName": "",
                }
                cmds.hotkey(**kwargs)
                cleared += 1
        except Exception:
            pass

    if cleared:
        _display_info("已清理 {0} 组 Camera Align 快捷键绑定。".format(cleared))
    else:
        _display_info("没有检测到需要清理的 Camera Align 快捷键绑定。")
    return cleared


def _remove_hotkey_set():
    hotkey_set_name = "CameraAlign_HotkeySet"
    if cmds.hotkeySet(hotkey_set_name, exists=True):
        try:
            # 如果当前正在使用这个 hotkey set，尝试切换回默认或上一个
            current = ""
            try:
                current = cmds.hotkeySet(query=True, current=True) or ""
            except Exception:
                pass

            if current == hotkey_set_name:
                # 尝试切换到 Maya 默认的 hotkey set
                fallback_sets = ["Maya_Default", "Maya", "Default"]
                switched = False
                for fallback in fallback_sets:
                    if cmds.hotkeySet(fallback, exists=True):
                        try:
                            cmds.hotkeySet(fallback, edit=True, current=True)
                            _display_info("已将当前 Hotkey Set 切换为: {0}".format(fallback))
                            switched = True
                            break
                        except Exception:
                            pass
                if not switched:
                    _display_warning("当前 Hotkey Set 是 CameraAlign_HotkeySet，但无法自动切换。请手动切换。")

            cmds.hotkeySet(hotkey_set_name, remove=True)
            _display_info("已删除 Hotkey Set: {0}".format(hotkey_set_name))
            return True
        except Exception as exc:
            _display_error("删除 Hotkey Set 失败: {0}".format(exc))
    else:
        _display_info("Hotkey Set 不存在，跳过: {0}".format(hotkey_set_name))
    return False


# -----------------------------
# 模块卸载
# -----------------------------
def _unload_module():
    module_name = "camera_align"
    if module_name in sys.modules:
        try:
            del sys.modules[module_name]
            _display_info("已从 Python 内存中卸载模块: {0}".format(module_name))
            return True
        except Exception as exc:
            _display_warning("卸载模块失败: {0}".format(exc))
    else:
        _display_info("模块未加载，跳过卸载: {0}".format(module_name))
    return False


# -----------------------------
# 主流程
# -----------------------------
def uninstall():
    _display_info("开始卸载 Camera Align 插件...")
    _display_info("=" * 50)

    results = {
        "script_file": False,
        "icon_file": False,
        "config_file": False,
        "ui_closed": False,
        "shelf_button": False,
        "name_commands": False,
        "hotkeys": False,
        "hotkey_set": False,
        "module_unloaded": False,
    }

    try:
        results["script_file"] = bool(_remove_script_file())
    except Exception as exc:
        _display_error("清理脚本文件时出错: {0}".format(exc))

    try:
        results["icon_file"] = _remove_icon_file()
    except Exception as exc:
        _display_error("清理图标文件时出错: {0}".format(exc))

    try:
        results["config_file"] = _remove_config_file()
    except Exception as exc:
        _display_error("清理配置文件时出错: {0}".format(exc))

    try:
        _close_ui()
        results["ui_closed"] = True
    except Exception as exc:
        _display_error("关闭 UI 时出错: {0}".format(exc))

    try:
        results["shelf_button"] = _remove_shelf_button()
    except Exception as exc:
        _display_error("删除 Shelf 按钮时出错: {0}".format(exc))

    try:
        results["name_commands"] = _remove_name_commands()
    except Exception as exc:
        _display_error("删除 nameCommand 时出错: {0}".format(exc))

    try:
        results["hotkeys"] = bool(_clear_camera_align_hotkeys())
    except Exception as exc:
        _display_error("清理快捷键时出错: {0}".format(exc))

    try:
        results["hotkey_set"] = _remove_hotkey_set()
    except Exception as exc:
        _display_error("删除 Hotkey Set 时出错: {0}".format(exc))

    try:
        results["module_unloaded"] = _unload_module()
    except Exception as exc:
        _display_error("卸载模块时出错: {0}".format(exc))

    # 保存快捷键偏好设置
    try:
        cmds.hotkey(autoSave=True)
    except Exception:
        pass
    try:
        cmds.savePrefs(hotkeys=True)
    except Exception:
        pass

    _display_info("=" * 50)
    _display_info("Camera Align 插件卸载完成。")

    summary_lines = ["卸载摘要:"]
    summary_lines.append("  脚本文件: {0}".format("已清理" if results["script_file"] else "未找到/失败"))
    summary_lines.append("  图标文件: {0}".format("已清理" if results["icon_file"] else "未找到/失败"))
    summary_lines.append("  配置文件: {0}".format("已清理" if results["config_file"] else "未找到/失败"))
    summary_lines.append("  UI / HUD: {0}".format("已关闭" if results["ui_closed"] else "失败"))
    summary_lines.append("  Shelf 按钮: {0}".format("已删除" if results["shelf_button"] else "未找到/失败"))
    summary_lines.append("  NameCommands: {0}".format("已清理" if results["name_commands"] else "未找到/失败"))
    summary_lines.append("  快捷键绑定: {0}".format("已清理" if results["hotkeys"] else "未找到/失败"))
    summary_lines.append("  Hotkey Set: {0}".format("已删除" if results["hotkey_set"] else "未找到/失败"))
    summary_lines.append("  内存模块: {0}".format("已卸载" if results["module_unloaded"] else "未加载"))
    summary = "\n".join(summary_lines)

    _display_info(summary)

    try:
        cmds.confirmDialog(
            title="Camera Align 卸载完成",
            message=summary,
            button=["OK"],
        )
    except Exception:
        pass

    return results


def onMayaDroppedPythonFile(*args):
    try:
        uninstall()
    except Exception as exc:
        msg = "Camera Align 卸载失败：{0}\n\n{1}".format(exc, traceback.format_exc())
        _display_error(msg)
        try:
            cmds.confirmDialog(title="Camera Align 卸载失败", message=msg, button=["OK"])
        except Exception:
            pass
        raise


if __name__ == "__main__":
    uninstall()
