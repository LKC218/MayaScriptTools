# -*- coding: utf-8 -*-
from __future__ import annotations

import sys


TOOL_DIR = r"E:\kc\标准\Maya脚本工具\脚本\建模工具\glb工具maya"
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

# Blender 原脚本如果只用了 bpy.ops.import_scene.gltf / export_scene.gltf，
# 可以先把 import bpy 替换为下面这一行。
import maya_bpy_glb_compat as bpy


def import_glb(path):
    return bpy.ops.import_scene.gltf(filepath=path)


def export_glb(path):
    return bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)


def export_scene(path):
    return bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=False)
