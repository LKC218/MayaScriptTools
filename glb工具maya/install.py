# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import shutil
import sys
import traceback

import maya.cmds as cmds


TOOL_FILES = (
    "maya_glb_tool.py",
    "maya_glb_native.py",
    "maya_bpy_glb_compat.py",
    "blender_glb_bridge.py",
)

DEFAULT_SOURCE_DIR = r"H:\cjiaoben\MayaScriptTools\glb工具maya"


def _source_dir():
    """返回安装源目录。

    Maya Script Editor 使用 exec(open(...).read()) 时，__file__ 可能继承自其他插件，
    所以这里必须验证目录里确实包含本工具文件。
    """
    candidates = []

    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass

    candidates.extend([
        DEFAULT_SOURCE_DIR,
        os.getcwd(),
    ])

    for folder in candidates:
        if not folder:
            continue
        if all(os.path.isfile(os.path.join(folder, filename)) for filename in TOOL_FILES):
            return folder

    raise RuntimeError(
        "找不到工具源目录。请确认工具文件仍在：{}".format(DEFAULT_SOURCE_DIR)
    )


def install(create_shelf=True):
    """安装工具到 Maya 用户 scripts 目录。"""
    source_dir = _source_dir()
    scripts_dir = cmds.internalVar(userScriptDir=True)
    installed = []
    for filename in TOOL_FILES:
        src = os.path.join(source_dir, filename)
        if not os.path.isfile(src):
            raise RuntimeError("找不到工具文件：{}".format(src))
        dst = os.path.join(scripts_dir, filename)
        shutil.copy2(src, dst)
        installed.append(dst)

    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    import maya_glb_tool
    importlib.reload(maya_glb_tool)

    if create_shelf:
        maya_glb_tool.install_shelf_button()

    cmds.inViewMessage(
        amg="<hl>Maya GLB 导入导出工具安装完成</hl>",
        pos="midCenter",
        fade=True,
        fadeStayTime=4000,
    )
    print("已安装文件：")
    for path in installed:
        print(path)
    return installed


if __name__ == "__main__":
    try:
        install(create_shelf=True)
    except Exception:
        traceback.print_exc()
        cmds.confirmDialog(title="安装失败", message=traceback.format_exc(), button=["确定"])
