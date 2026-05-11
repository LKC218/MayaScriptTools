# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import sys

import bpy


def _clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _enable_addon(module_name):
    try:
        bpy.ops.preferences.addon_enable(module=module_name)
    except Exception:
        pass


def _fallback_operator_call(operator, kwargs):
    pending = dict(kwargs)
    while True:
        try:
            return operator(**pending)
        except TypeError as exc:
            message = str(exc)
            removed = None
            for key in list(pending.keys()):
                if key in message:
                    removed = key
                    break
            if not removed:
                raise
            pending.pop(removed, None)


def fbx_to_gltf(input_path, output_path, options=None):
    options = options or {}
    _clear_scene()
    _enable_addon("io_scene_fbx")
    _enable_addon("io_scene_gltf2")

    bpy.ops.import_scene.fbx(filepath=input_path)
    export_kwargs = {
        "filepath": output_path,
        "export_format": options.get("export_format", "GLB"),
        "use_selection": False,
        "export_materials": options.get("export_materials", "EXPORT"),
        "export_image_format": options.get("export_image_format", "AUTO"),
        "export_keep_originals": bool(options.get("export_keep_originals", False)),
        "export_texcoords": bool(options.get("export_texcoords", True)),
        "export_normals": bool(options.get("export_normals", True)),
        "export_tangents": bool(options.get("export_tangents", False)),
        "export_animations": bool(options.get("export_animations", False)),
        "export_cameras": bool(options.get("export_cameras", False)),
        "export_lights": bool(options.get("export_lights", False)),
        "export_yup": bool(options.get("export_yup", True)),
        "export_apply": bool(options.get("export_apply", False)),
    }
    _fallback_operator_call(bpy.ops.export_scene.gltf, export_kwargs)


def gltf_to_fbx(input_path, output_path, options=None):
    options = options or {}
    _clear_scene()
    _enable_addon("io_scene_fbx")
    _enable_addon("io_scene_gltf2")

    import_kwargs = {
        "filepath": input_path,
        "import_pack_images": bool(options.get("import_pack_images", True)),
        "merge_vertices": bool(options.get("merge_vertices", False)),
        "import_shading": options.get("import_shading", "NORMALS"),
    }
    _fallback_operator_call(bpy.ops.import_scene.gltf, import_kwargs)
    export_kwargs = {
        "filepath": output_path,
        "use_selection": False,
        "bake_space_transform": False,
        "path_mode": "COPY",
        "embed_textures": bool(options.get("embed_textures", True)),
    }
    _fallback_operator_call(bpy.ops.export_scene.fbx, export_kwargs)


def main(argv):
    parser = argparse.ArgumentParser(description="Maya GLB 工具的 Blender 后台转换桥。")
    parser.add_argument("--mode", choices=("fbx_to_gltf", "gltf_to_fbx"), required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--format", choices=("GLB", "GLTF_SEPARATE", "GLTF_EMBEDDED"), default="GLB")
    parser.add_argument("--options", default="{}")
    args = parser.parse_args(argv)
    options = json.loads(args.options or "{}")
    options.setdefault("export_format", args.format)

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    if args.mode == "fbx_to_gltf":
        fbx_to_gltf(input_path, output_path, options=options)
    else:
        gltf_to_fbx(input_path, output_path, options=options)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
