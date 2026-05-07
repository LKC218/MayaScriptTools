# -*- coding: utf-8 -*-
from __future__ import annotations

import sys


TOOL_DIR = r"H:\cjiaoben\MayaScriptTools\glb工具maya"
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

import maya_glb_tool


def import_like_blender(path):
    """对应 Blender: bpy.ops.import_scene.gltf(filepath=path)"""
    return maya_glb_tool.import_scene_gltf(filepath=path)


def export_like_blender(path, selected_only=True):
    """对应 Blender: bpy.ops.export_scene.gltf(filepath=path, export_format="GLB")"""
    return maya_glb_tool.export_scene_gltf(
        filepath=path,
        export_format="GLB",
        use_selection=selected_only,
    )


def show_tool():
    return maya_glb_tool.show_ui()
