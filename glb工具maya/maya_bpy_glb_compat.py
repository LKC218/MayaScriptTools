# -*- coding: utf-8 -*-
from __future__ import annotations

import maya_glb_tool


class _GltfImportOps(object):
    @staticmethod
    def gltf(filepath=None, **kwargs):
        return maya_glb_tool.import_scene_gltf(filepath=filepath, **kwargs)


class _GltfExportOps(object):
    @staticmethod
    def gltf(filepath=None, **kwargs):
        return maya_glb_tool.export_scene_gltf(filepath=filepath, **kwargs)


class _Ops(object):
    import_scene = _GltfImportOps()
    export_scene = _GltfExportOps()


ops = _Ops()


def show_ui():
    return maya_glb_tool.show_ui()
