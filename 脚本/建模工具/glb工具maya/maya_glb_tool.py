# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import glob
import json
import os
import re
import shutil
import sys
import subprocess
import tempfile
import threading
import time
import traceback

import maya.cmds as cmds
import maya.mel as mel

try:
    import maya_glb_native
except Exception:
    maya_glb_native = None


TOOL_NAME = "Maya GLB 导入导出工具"
TOOL_VERSION = "v1.0.0"
WINDOW_NAME = "MayaGlbToolWindow"
WORKSPACE_NAME = "MayaGlbToolWorkspaceControl"
OPTION_IMPORT_PATH = "MayaGlbTool_importPath"
OPTION_EXPORT_PATH = "MayaGlbTool_exportPath"
OPTION_SELECTED_ONLY = "MayaGlbTool_selectedOnly"
OPTION_BLENDER_PATH = "MayaGlbTool_blenderPath"
OPTION_PREFIX = "MayaGlbTool_"

SUPPORTED_EXTENSIONS = (".glb", ".gltf")

PLUGIN_CANDIDATES = (
    "glTFTranslator",
    "glTFTranslator.py",
    "gltfTranslator",
    "gltfTranslator.py",
    "glTFExport",
    "glTFExport.py",
    "maya_gltf",
    "maya_gltf.py",
    "maya-glTF",
    "maya-glTF.py",
    "Maya2glTF",
    "Maya2glTF.py",
    "BabylonJS",
    "BabylonJS.py",
    "BabylonJSExport",
    "BabylonJSExport.py",
    "GLTFExporter",
    "GLTFExporter.py",
    "gltfImporter",
    "gltfImporter.py",
    "gltfImport",
    "gltfImport.py",
)

IMPORT_TRANSLATOR_TYPES = (
    "glTF2",
    "glTF",
    "GLTF",
    "GLB",
    "glb",
    "gltf",
)

EXPORT_TRANSLATOR_TYPES = (
    "glTF2",
    "glTF",
    "GLTF",
    "GLB",
    "glb",
    "gltf",
)

BLENDER_UNSUPPORTED_OPTIONS = (
    "export_draco_mesh_compression_enable",
    "export_morph",
    "export_skins",
    "export_def_bones",
)

_UI = {
    "import_path": None,
    "export_path": None,
    "blender_path": None,
    "selected_only": None,
    "embed_textures": None,
    "export_format": None,
    "export_materials": None,
    "export_image_format": None,
    "export_keep_originals": None,
    "export_texcoords": None,
    "export_normals": None,
    "export_tangents": None,
    "export_animations": None,
    "export_cameras": None,
    "export_lights": None,
    "export_yup": None,
    "export_apply": None,
    "import_pack_images": None,
    "merge_vertices": None,
    "import_shading": None,
    "quadrangulate": None,
    "status": None,
}


def _info(message):
    print("{}: {}".format(TOOL_NAME, message))


def _warn(message):
    cmds.warning("{}: {}".format(TOOL_NAME, message))


def _status(message):
    _info(message)
    field = _UI.get("status")
    if field and cmds.control(field, exists=True):
        old_text = cmds.scrollField(field, query=True, text=True) or ""
        new_text = "{}{}\n".format(old_text, message)
        cmds.scrollField(field, edit=True, text=new_text, insertionPosition=len(new_text))


def _get_option_string(name, default=""):
    try:
        if cmds.optionVar(exists=name):
            return cmds.optionVar(query=name) or default
    except Exception:
        pass
    return default


def _get_option_bool(name, default=True):
    try:
        if cmds.optionVar(exists=name):
            return bool(cmds.optionVar(query=name))
    except Exception:
        pass
    return default


def _set_option_string(name, value):
    try:
        cmds.optionVar(stringValue=(name, value or ""))
    except Exception:
        pass


def _set_option_bool(name, value):
    try:
        cmds.optionVar(intValue=(name, 1 if value else 0))
    except Exception:
        pass


def _tool_option(name):
    return "{}{}".format(OPTION_PREFIX, name)


def _get_checkbox(name, default=True):
    control = _UI.get(name)
    if control and cmds.control(control, exists=True):
        return bool(cmds.checkBox(control, query=True, value=True))
    return _get_option_bool(_tool_option(name), default)


def _set_checkbox_option(name, value):
    _set_option_bool(_tool_option(name), value)


def _get_menu(name, default):
    control = _UI.get(name)
    if control and cmds.control(control, exists=True):
        return cmds.optionMenu(control, query=True, value=True)
    return _get_option_string(_tool_option(name), default)


def _set_menu_option(name, value):
    _set_option_string(_tool_option(name), value)


def _normalize_path(path):
    return os.path.normpath(os.path.expandvars(os.path.expanduser(path.strip())))


def _validate_glb_path(path, must_exist):
    if not path:
        raise RuntimeError("路径为空。")

    normalized = _normalize_path(path)
    ext = os.path.splitext(normalized)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise RuntimeError("只支持 .glb 或 .gltf 文件。")

    if must_exist and not os.path.isfile(normalized):
        raise RuntimeError("文件不存在：{}".format(normalized))

    if not must_exist:
        folder = os.path.dirname(normalized)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)

    return normalized


def _safe_maya_name(name, prefix="glb"):
    base = os.path.splitext(os.path.basename(name or ""))[0]
    safe = re.sub(r"[^0-9A-Za-z_]+", "_", base).strip("_")
    if not safe:
        safe = prefix
    if safe[0].isdigit():
        safe = "{}_{}".format(prefix, safe)
    return safe


def _maya_workspace_root():
    try:
        root = cmds.workspace(query=True, rootDirectory=True)
        if root:
            return root
    except Exception:
        pass
    return os.path.expanduser("~")


def _import_cache_dir(path):
    folder = os.path.join(_maya_workspace_root(), "sourceimages", "maya_glb_tool", _safe_maya_name(path))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def _plugin_exists(plugin_name):
    try:
        return bool(cmds.pluginInfo(plugin_name, query=True, loaded=True))
    except Exception:
        return False


def _try_load_plugin(plugin_name):
    if _plugin_exists(plugin_name):
        return True
    try:
        cmds.loadPlugin(plugin_name, quiet=True)
        return _plugin_exists(plugin_name)
    except Exception:
        return False


def check_gltf_plugin():
    """检测并尝试加载常见 glTF/GLB 插件。"""
    loaded = []
    failed = []

    for plugin_name in PLUGIN_CANDIDATES:
        if _try_load_plugin(plugin_name):
            loaded.append(plugin_name)
        else:
            failed.append(plugin_name)

    active_plugins = []
    try:
        active_plugins = cmds.pluginInfo(query=True, listPlugins=True) or []
    except Exception:
        active_plugins = []

    possible_active = [
        name for name in active_plugins
        if "gltf" in name.lower() or "glb" in name.lower() or "babylon" in name.lower()
    ]

    return {
        "loaded": loaded,
        "possible_active": possible_active,
        "failed": failed,
        "has_hint": bool(loaded or possible_active),
    }


def _script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def _is_valid_blender_path(path):
    return bool(path and os.path.isfile(path) and os.path.basename(path).lower() == "blender.exe")


def find_blender_executable():
    saved = _get_option_string(OPTION_BLENDER_PATH)
    if _is_valid_blender_path(saved):
        return saved

    env_path = os.environ.get("BLENDER_EXE", "")
    if _is_valid_blender_path(env_path):
        return env_path

    which_path = shutil.which("blender")
    if _is_valid_blender_path(which_path):
        return which_path

    candidates = []
    patterns = [
        r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender\blender.exe",
        r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
        r"C:\Program Files\Steam\steamapps\common\Blender\blender.exe",
        r"D:\Steam\steamapps\common\Blender\blender.exe",
        r"E:\Steam\steamapps\common\Blender\blender.exe",
    ]
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))

    candidates = sorted(set(candidates), reverse=True)
    for candidate in candidates:
        if _is_valid_blender_path(candidate):
            return candidate
    return ""


def _get_blender_path():
    ui_value = _get_text_field_value(_UI.get("blender_path"))
    if _is_valid_blender_path(ui_value):
        _set_option_string(OPTION_BLENDER_PATH, ui_value)
        return ui_value

    detected = find_blender_executable()
    if _is_valid_blender_path(detected):
        _set_option_string(OPTION_BLENDER_PATH, detected)
        _set_text_field_value(_UI.get("blender_path"), detected)
        return detected

    raise RuntimeError(
        "没有找到 blender.exe。请在工具里设置 Blender 路径，"
        "例如 C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe。"
    )


def _run_blender_bridge(mode, input_path, output_path, export_format="GLB", options=None):
    blender_path = _get_blender_path()
    bridge_script = os.path.join(_script_dir(), "blender_glb_bridge.py")
    if not os.path.isfile(bridge_script):
        raise RuntimeError("找不到 Blender 转换桥脚本：{}".format(bridge_script))

    command = [
        blender_path,
        "--background",
        "--python",
        bridge_script,
        "--",
        "--mode",
        mode,
        "--input",
        input_path,
        "--output",
        output_path,
        "--format",
        export_format,
        "--options",
        json.dumps(options or {}, ensure_ascii=False),
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr or result.stdout or "Blender 后台转换没有返回详细错误。"
        raise RuntimeError("Blender 后台转换失败：\n{}".format(detail[-2000:]))
    return result


def _load_fbx_plugin():
    try:
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            cmds.loadPlugin("fbxmaya", quiet=True)
        return True
    except Exception as exc:
        raise RuntimeError("无法加载 Maya FBX 插件 fbxmaya：{}".format(exc))


def _translator_error_message(action, errors):
    lines = [
        "{}失败：当前 Maya 没有可用的 GLB/GLTF 文件翻译器。".format(action),
        "",
        "建议先安装或启用支持 GLB/GLTF 的 Maya 插件，例如 Autodesk App Store 或团队内部提供的 glTF 插件。",
        "已尝试的翻译器类型：{}".format(", ".join(sorted(set(IMPORT_TRANSLATOR_TYPES + EXPORT_TRANSLATOR_TYPES)))),
    ]
    if errors:
        lines.append("")
        lines.append("最后一次错误：{}".format(errors[-1]))
    return "\n".join(lines)


def _candidate_types(path, types):
    ext = os.path.splitext(path)[1].lower()
    preferred = []
    if ext == ".glb":
        preferred = ["GLB", "glb", "glTF2", "glTF", "GLTF"]
    elif ext == ".gltf":
        preferred = ["glTF2", "glTF", "GLTF", "gltf"]

    result = []
    for type_name in preferred + list(types):
        if type_name not in result:
            result.append(type_name)
    return result


def _get_export_options_from_ui():
    options = {
        "embed_textures": _get_checkbox("embed_textures", True),
        "export_format": _get_menu("export_format", "GLB"),
        "export_materials": _get_menu("export_materials", "EXPORT"),
        "export_image_format": _get_menu("export_image_format", "AUTO"),
        "export_keep_originals": _get_checkbox("export_keep_originals", False),
        "export_texcoords": _get_checkbox("export_texcoords", True),
        "export_normals": _get_checkbox("export_normals", True),
        "export_tangents": _get_checkbox("export_tangents", False),
        "export_animations": _get_checkbox("export_animations", False),
        "export_cameras": _get_checkbox("export_cameras", False),
        "export_lights": _get_checkbox("export_lights", False),
        "export_yup": _get_checkbox("export_yup", True),
        "export_apply": _get_checkbox("export_apply", False),
    }
    for key, value in options.items():
        if isinstance(value, bool):
            _set_checkbox_option(key, value)
        else:
            _set_menu_option(key, value)
    return options


def _get_import_options_from_ui():
    options = {
        "import_pack_images": _get_checkbox("import_pack_images", True),
        "embed_textures": True,
        "merge_vertices": _get_checkbox("merge_vertices", False),
        "import_shading": _get_menu("import_shading", "NORMALS"),
        "quadrangulate": _get_checkbox("quadrangulate", True),
    }
    for key, value in options.items():
        if isinstance(value, bool):
            _set_checkbox_option(key, value)
        else:
            _set_menu_option(key, value)
    return options


def _import_with_file_translator(path, import_options=None):
    errors = []
    namespace = _safe_maya_name(path)

    for type_name in _candidate_types(path, IMPORT_TRANSLATOR_TYPES):
        try:
            new_nodes = cmds.file(
                path,
                i=True,
                type=type_name,
                ignoreVersion=True,
                ra=True,
                mergeNamespacesOnClash=False,
                namespace=namespace,
                options="",
                preserveReferences=True,
                returnNewNodes=True,
            )
            if (import_options or {}).get("quadrangulate", False):
                _quadrangulate_imported_nodes(new_nodes)
            return type_name
        except Exception as exc:
            errors.append("{}: {}".format(type_name, exc))

    return _import_with_blender_bridge(path, errors, import_options or {})


def _export_with_file_translator(path, selected_only, export_options=None):
    errors = []
    for type_name in _candidate_types(path, EXPORT_TRANSLATOR_TYPES):
        try:
            kwargs = {
                "force": True,
                "options": "",
                "type": type_name,
                "preserveReferences": True,
            }
            if selected_only:
                kwargs["exportSelected"] = True
            else:
                kwargs["exportAll"] = True
            cmds.file(path, **kwargs)
            return type_name
        except Exception as exc:
            errors.append("{}: {}".format(type_name, exc))

    try:
        return _export_with_gltfexport_module(path, selected_only, errors)
    except RuntimeError:
        return _export_with_blender_bridge(path, selected_only, errors, export_options or {})


def _export_with_gltfexport_module(path, selected_only, errors):
    if selected_only:
        raise RuntimeError(_translator_error_message("导出选中对象", errors))

    try:
        module = importlib.import_module("glTFExport")
    except Exception as exc:
        errors.append("glTFExport 模块: {}".format(exc))
        raise RuntimeError(_translator_error_message("导出", errors))

    try:
        resource_format = "bin" if os.path.splitext(path)[1].lower() == ".glb" else "gltf"
        module.export(path, resource_format=resource_format, anim="keyed", vflip=True)
        return "glTFExport Python 模块"
    except Exception as exc:
        errors.append("glTFExport.export: {}".format(exc))
        raise RuntimeError(_translator_error_message("导出", errors))


def _export_with_blender_bridge(path, selected_only, errors, export_options=None):
    export_options = export_options or {}
    _load_fbx_plugin()
    temp_dir = tempfile.mkdtemp(prefix="maya_glb_tool_")
    temp_fbx = os.path.join(temp_dir, "maya_glb_export.fbx")
    ext = os.path.splitext(path)[1].lower()
    export_format = export_options.get("export_format") or ("GLTF_EMBEDDED" if ext == ".gltf" else "GLB")

    try:
        try:
            mel.eval("FBXResetExport;")
            mel.eval("FBXExportEmbeddedTextures -v {};".format("true" if export_options.get("embed_textures", True) else "false"))
        except Exception:
            pass
        kwargs = {
            "force": True,
            "options": "",
            "type": "FBX export",
            "preserveReferences": True,
        }
        if selected_only:
            kwargs["exportSelected"] = True
        else:
            kwargs["exportAll"] = True
        cmds.file(temp_fbx, **kwargs)
        _run_blender_bridge("fbx_to_gltf", temp_fbx, path, export_format=export_format, options=export_options)
        return "Blender 后台转换：FBX -> GLB"
    except Exception as exc:
        errors.append("Blender 备用导出: {}".format(exc))
        raise RuntimeError(_translator_error_message("导出", errors))
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def _quadrangulate_imported_nodes(nodes):
    mesh_shapes = cmds.ls(nodes or [], dag=True, type="mesh", long=True) or []
    transforms = []
    for shape in mesh_shapes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        for parent in parents:
            if parent not in transforms:
                transforms.append(parent)

    for transform in transforms:
        try:
            cmds.polyQuad(transform, angle=30, constructionHistory=False)
        except Exception as exc:
            _status("四边面化跳过：{}，原因：{}".format(transform, exc))


def _relink_missing_textures(search_dir):
    if not os.path.isdir(search_dir):
        return

    texture_index = {}
    for root_dir, _, filenames in os.walk(search_dir):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".bmp", ".exr", ".webp"):
                texture_index.setdefault(filename.lower(), os.path.join(root_dir, filename))

    if not texture_index:
        return

    fixed = 0
    for node in cmds.ls(type="file") or []:
        attr = "{}.fileTextureName".format(node)
        try:
            current = cmds.getAttr(attr) or ""
        except Exception:
            continue
        if current and os.path.isfile(current):
            continue
        basename = os.path.basename(current).lower()
        if basename in texture_index:
            try:
                cmds.setAttr(attr, texture_index[basename], type="string")
                fixed += 1
            except Exception:
                pass

    if fixed:
        _status("已重连贴图文件节点：{} 个".format(fixed))


def _import_with_blender_bridge(path, errors, import_options=None):
    import_options = import_options or {}
    _load_fbx_plugin()
    cache_dir = _import_cache_dir(path)
    temp_fbx = os.path.join(cache_dir, "{}.fbx".format(_safe_maya_name(path)))

    try:
        _run_blender_bridge("gltf_to_fbx", path, temp_fbx, export_format="GLB", options=import_options)
        fbx_errors = []
        for type_name in ("FBX", "FBX import", "fbx"):
            try:
                new_nodes = cmds.file(
                    temp_fbx,
                    i=True,
                    type=type_name,
                    ignoreVersion=True,
                    ra=True,
                    mergeNamespacesOnClash=False,
                    namespace=_safe_maya_name(path),
                    options="",
                    preserveReferences=True,
                    returnNewNodes=True,
                )
                if import_options.get("quadrangulate", True):
                    _quadrangulate_imported_nodes(new_nodes)
                _relink_missing_textures(cache_dir)
                _status("导入贴图缓存目录：{}".format(cache_dir))
                return "Blender 后台转换：GLB/GLTF -> FBX"
            except Exception as exc:
                fbx_errors.append("{}: {}".format(type_name, exc))
        raise RuntimeError("Maya FBX 导入失败：{}".format(fbx_errors[-1] if fbx_errors else "未知错误"))
    except Exception as exc:
        errors.append("Blender 备用导入: {}".format(exc))
        raise RuntimeError(_translator_error_message("导入", errors))


def import_glb(path, import_options=None):
    """导入 .glb/.gltf 文件。"""
    file_path = _validate_glb_path(path, must_exist=True)
    if maya_glb_native is not None:
        try:
            created = maya_glb_native.import_glb(
                file_path,
                quadrangulate=(import_options or {}).get("quadrangulate", False),
            )
            _status("导入完成：{}，方式：Maya 原生 GLB，节点数：{}".format(file_path, len(created)))
            return file_path
        except Exception as exc:
            _status("Maya 原生 GLB 导入失败，尝试插件/备用转换：{}".format(exc))
    check_gltf_plugin()
    translator = _import_with_file_translator(file_path, import_options=import_options or {})
    _status("导入完成：{}，翻译器：{}".format(file_path, translator))
    return file_path


def export_glb(path, selected_only=True, export_options=None):
    """导出 .glb/.gltf 文件。"""
    file_path = _validate_glb_path(path, must_exist=False)
    if selected_only:
        selection = cmds.ls(selection=True, long=True) or []
        if not selection:
            raise RuntimeError("导出选中对象前，请先在场景中选择对象。")

    if maya_glb_native is not None and os.path.splitext(file_path)[1].lower() == ".glb":
        try:
            maya_glb_native.export_glb(
                file_path,
                selected_only=selected_only,
                embed_textures=(export_options or {}).get("embed_textures", True),
            )
            report = maya_glb_native.validate_glb(file_path)
            _status("导出完成：{}，方式：Maya 原生 GLB，大小：{} 字节".format(file_path, report.get("byteLength")))
            return file_path
        except Exception as exc:
            _status("Maya 原生 GLB 导出失败，尝试插件/备用转换：{}".format(exc))
    check_gltf_plugin()
    translator = _export_with_file_translator(file_path, selected_only, export_options=export_options or {})
    _status("导出完成：{}，翻译器：{}".format(file_path, translator))
    return file_path


def _report_unsupported_options(options):
    used = []
    for key in BLENDER_UNSUPPORTED_OPTIONS:
        if key in options:
            used.append("{}={}".format(key, options[key]))
    if used:
        _status("已忽略 Blender 专用参数：{}".format(", ".join(used)))


def import_scene_gltf(filepath=None, **kwargs):
    """Blender 风格导入入口，方便迁移 bpy.ops.import_scene.gltf。"""
    _report_unsupported_options(kwargs)
    path = filepath or kwargs.get("path") or kwargs.get("filename")
    return import_glb(path, import_options=kwargs)


def export_scene_gltf(filepath=None, use_selection=True, **kwargs):
    """Blender 风格导出入口，方便迁移 bpy.ops.export_scene.gltf。"""
    _report_unsupported_options(kwargs)
    path = filepath or kwargs.get("path") or kwargs.get("filename")
    selected_only = kwargs.get("selected_only", use_selection)
    return export_glb(path, selected_only=bool(selected_only), export_options=kwargs)


def _get_text_field_value(control_name):
    if not control_name or not cmds.control(control_name, exists=True):
        return ""
    return cmds.textFieldButtonGrp(control_name, query=True, text=True)


def _set_text_field_value(control_name, value):
    if control_name and cmds.control(control_name, exists=True):
        cmds.textFieldButtonGrp(control_name, edit=True, text=value)


def _choose_import_path():
    start_dir = os.path.dirname(_get_option_string(OPTION_IMPORT_PATH))
    kwargs = {
        "fileMode": 1,
        "dialogStyle": 2,
        "caption": "选择要导入的 GLB/GLTF 文件",
        "fileFilter": "GLB/GLTF (*.glb *.gltf)",
    }
    if start_dir and os.path.isdir(start_dir):
        kwargs["startingDirectory"] = start_dir
    result = cmds.fileDialog2(**kwargs)
    if result:
        _set_text_field_value(_UI["import_path"], result[0])
        _set_option_string(OPTION_IMPORT_PATH, result[0])
        return result[0]
    return ""


def _choose_export_path():
    start_dir = os.path.dirname(_get_option_string(OPTION_EXPORT_PATH))
    kwargs = {
        "fileMode": 0,
        "dialogStyle": 2,
        "caption": "选择导出位置",
        "fileFilter": "GLB (*.glb);;GLTF (*.gltf)",
    }
    if start_dir and os.path.isdir(start_dir):
        kwargs["startingDirectory"] = start_dir
    result = cmds.fileDialog2(**kwargs)
    if result:
        _set_text_field_value(_UI["export_path"], result[0])
        _set_option_string(OPTION_EXPORT_PATH, result[0])
        return result[0]
    return ""


def _choose_blender_path():
    result = cmds.fileDialog2(
        fileMode=1,
        dialogStyle=2,
        caption="选择 blender.exe",
        fileFilter="Executable (*.exe);;All Files (*.*)",
    )
    if result:
        _set_text_field_value(_UI["blender_path"], result[0])
        _set_option_string(OPTION_BLENDER_PATH, result[0])


def _auto_detect_blender_path(*_):
    path = find_blender_executable()
    if path:
        _set_text_field_value(_UI["blender_path"], path)
        _set_option_string(OPTION_BLENDER_PATH, path)
        _status("已检测到 Blender：{}".format(path))
    else:
        _status("未自动检测到 Blender，请手动选择 blender.exe。")


def _run_import(*_):
    try:
        path = _choose_import_path()
        if not path:
            return
        _set_option_string(OPTION_IMPORT_PATH, path)
        import_glb(path, import_options=_get_import_options_from_ui())
        cmds.inViewMessage(amg="<hl>GLB/GLTF 导入完成</hl>", pos="midCenter", fade=True)
    except Exception as exc:
        _warn(str(exc))
        _status("导入失败：{}".format(exc))
        cmds.confirmDialog(title="导入失败", message=str(exc), button=["确定"])


def _run_export(selected_only=None):
    try:
        if selected_only is None:
            selected_only = cmds.checkBox(_UI["selected_only"], query=True, value=True)
        path = _choose_export_path()
        if not path:
            return
        _set_option_string(OPTION_EXPORT_PATH, path)
        _set_option_bool(OPTION_SELECTED_ONLY, selected_only)
        export_glb(path, selected_only=selected_only, export_options=_get_export_options_from_ui())
        cmds.inViewMessage(amg="<hl>GLB/GLTF 导出完成</hl>", pos="midCenter", fade=True)
    except Exception as exc:
        _warn(str(exc))
        _status("导出失败：{}".format(exc))
        cmds.confirmDialog(title="导出失败", message=str(exc), button=["确定"])


def _run_plugin_check(*_):
    result = check_gltf_plugin()
    if result["loaded"]:
        _status("已加载插件：{}".format(", ".join(result["loaded"])))
    elif result["possible_active"]:
        _status("检测到疑似 glTF 插件：{}".format(", ".join(result["possible_active"])))
    else:
        _status("未检测到可用 GLB/GLTF 插件，请先安装或在插件管理器中启用。")


def _clear_log(*_):
    field = _UI.get("status")
    if field and cmds.control(field, exists=True):
        cmds.scrollField(field, edit=True, text="")


def _open_export_folder(*_):
    try:
        path = _get_text_field_value(_UI["export_path"]) or _get_option_string(OPTION_EXPORT_PATH)
        file_path = _validate_glb_path(path, must_exist=False)
        folder = os.path.dirname(file_path)
        if not folder:
            raise RuntimeError("导出路径没有有效目录。")
        if not os.path.isdir(folder):
            os.makedirs(folder)
        os.startfile(folder)
        _status("已打开导出目录：{}".format(folder))
    except Exception as exc:
        _warn(str(exc))
        cmds.confirmDialog(title="打开目录失败", message=str(exc), button=["确定"])


def _show_environment_report(*_):
    result = check_gltf_plugin()
    try:
        active_plugins = cmds.pluginInfo(query=True, listPlugins=True) or []
    except Exception:
        active_plugins = []

    maya_version = cmds.about(version=True)
    api_version = cmds.about(apiVersion=True)
    scripts_dir = cmds.internalVar(userScriptDir=True)

    possible_plugins = [
        name for name in active_plugins
        if "gltf" in name.lower() or "glb" in name.lower() or "babylon" in name.lower()
    ]

    lines = [
        "Maya 版本：{}".format(maya_version),
        "Maya API：{}".format(api_version),
        "用户 scripts 目录：{}".format(scripts_dir),
        "",
        "本次成功加载：{}".format(", ".join(result["loaded"]) if result["loaded"] else "无"),
        "疑似相关插件：{}".format(", ".join(possible_plugins) if possible_plugins else "无"),
        "Blender 路径：{}".format(find_blender_executable() or "未检测到"),
        "",
        "如果 glTF 插件显示无，工具会尝试用 Maya FBX 加 Blender 后台转换兜底。",
    ]
    message = "\n".join(lines)
    _status("已生成环境诊断。")
    cmds.confirmDialog(title="环境诊断", message=message, button=["确定"])


def _show_help(*_):
    message = (
        "用途：在 Maya 中导入和导出 .glb/.gltf 文件。\n\n"
        "操作步骤：\n"
        "1. 导入：选择 .glb 或 .gltf 文件，然后点击“导入文件”。\n"
        "2. 导出选中：选择场景对象，设置导出路径，然后点击“导出选中”。\n"
        "3. 导出全场景：设置导出路径，然后点击“导出全场景”。\n\n"
        "注意事项：\n"
        "此工具不解析 GLB 二进制数据，而是调用 Maya 可用的 glTF/GLB 插件。"
        "如果 Maya 没有安装对应插件，导入导出会失败并给出提示。"
    )
    cmds.confirmDialog(title="帮助 - {}".format(TOOL_NAME), message=message, button=["我知道了"])


def _create_option_menu(name, label, items, default):
    control = cmds.optionMenu(label=label, changeCommand=lambda value, key=name: _set_menu_option(key, value))
    for item in items:
        cmds.menuItem(label=item)
    value = _get_option_string(_tool_option(name), default)
    if value in items:
        cmds.optionMenu(control, edit=True, value=value)
    _UI[name] = control
    return control


def _create_checkbox(name, label, default=True):
    control = cmds.checkBox(
        label=label,
        value=_get_option_bool(_tool_option(name), default),
        changeCommand=lambda value, key=name: _set_checkbox_option(key, value),
    )
    _UI[name] = control
    return control


def _build_ui():
    if cmds.workspaceControl(WORKSPACE_NAME, exists=True):
        cmds.deleteUI(WORKSPACE_NAME, control=True)

    workspace = cmds.workspaceControl(
        WORKSPACE_NAME,
        label=TOOL_NAME,
        retain=False,
        floating=True,
        widthProperty="preferred",
        initialWidth=300,
        initialHeight=360,
    )
    cmds.setParent(workspace)

    root = cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.separator(height=8, style="none")

    cmds.text(label="{} {}".format(TOOL_NAME, TOOL_VERSION), align="center", font="boldLabelFont", height=24)

    cmds.frameLayout(label="操作", collapsable=False, marginWidth=8, marginHeight=6)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
    _UI["import_path"] = None
    _UI["export_path"] = None
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(96, 96, 96))
    cmds.button(label="导入", height=34, backgroundColor=(0.25, 0.45, 0.34), command=_run_import)
    cmds.button(label="导出选中", height=34, backgroundColor=(0.29, 0.39, 0.58), command=lambda *_: _run_export(True))
    cmds.button(label="导出全场景", height=34, command=lambda *_: _run_export(False))
    cmds.setParent("..")
    cmds.button(label="打开上次导出目录", height=26, command=_open_export_folder)
    cmds.setParent(root)

    cmds.frameLayout(label="选项", collapsable=True, collapse=True, marginWidth=8, marginHeight=6)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    _UI["selected_only"] = cmds.checkBox(
        label="只导出当前选中对象",
        value=_get_option_bool(OPTION_SELECTED_ONLY, True),
        changeCommand=lambda value: _set_option_bool(OPTION_SELECTED_ONLY, value),
    )
    _create_checkbox("embed_textures", "FBX 中转时嵌入贴图", True)
    _create_checkbox("import_pack_images", "导入时打包贴图", True)
    _create_checkbox("quadrangulate", "导入后尝试四边面化", True)
    _create_option_menu("export_format", "导出格式", ["GLB", "GLTF_EMBEDDED", "GLTF_SEPARATE"], "GLB")
    _create_option_menu("export_materials", "材质", ["EXPORT", "PLACEHOLDER", "NONE"], "EXPORT")
    _create_option_menu("export_image_format", "贴图格式", ["AUTO", "JPEG", "PNG"], "AUTO")
    _create_checkbox("export_keep_originals", "尽量保留原始贴图文件", False)
    _create_checkbox("export_texcoords", "导出 UV", True)
    _create_checkbox("export_normals", "导出法线", True)
    _create_checkbox("export_tangents", "导出切线", False)
    _create_checkbox("export_animations", "导出动画", False)
    _create_checkbox("export_cameras", "导出相机", False)
    _create_checkbox("export_lights", "导出灯光", False)
    _create_checkbox("export_yup", "导出为 Y 轴向上", True)
    _create_checkbox("export_apply", "应用变换", False)
    _create_checkbox("merge_vertices", "导入时合并顶点", False)
    _create_option_menu("import_shading", "导入着色", ["NORMALS", "FLAT", "SMOOTH"], "NORMALS")
    cmds.setParent(root)

    cmds.frameLayout(label="备用转换 / 诊断", collapsable=True, collapse=True, marginWidth=8, marginHeight=6)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
    _UI["blender_path"] = cmds.textFieldButtonGrp(
        label="Blender",
        buttonLabel="浏览",
        text=_get_option_string(OPTION_BLENDER_PATH, find_blender_executable()),
        columnWidth3=(58, 330, 54),
        adjustableColumn=2,
        buttonCommand=_choose_blender_path,
    )
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(150, 150, 150))
    cmds.button(label="自动检测 Blender", height=26, command=_auto_detect_blender_path)
    cmds.button(label="检测插件", height=26, command=_run_plugin_check)
    cmds.button(label="环境诊断", height=26, command=_show_environment_report)
    cmds.setParent(root)

    cmds.frameLayout(label="日志", collapsable=True, collapse=True, marginWidth=8, marginHeight=6)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
    _UI["status"] = cmds.scrollField(editable=False, wordWrap=True, height=120, text="")
    cmds.button(label="清空日志", height=24, command=_clear_log)
    cmds.button(label="帮助", height=28, command=_show_help)
    cmds.setParent(root)

    cmds.separator(height=8, style="none")
    _run_plugin_check()
    _force_focus_async(workspace)
    return workspace


def _focus_once(workspace):
    try:
        if cmds.workspaceControl(workspace, exists=True):
            cmds.workspaceControl(workspace, edit=True, visible=True)
            cmds.workspaceControl(workspace, edit=True, restore=True)
            cmds.workspaceControl(workspace, edit=True, **{"raise": True})
    except Exception:
        pass

    try:
        import maya.OpenMayaUI as omui
        try:
            from shiboken6 import wrapInstance
        except Exception:
            from shiboken2 import wrapInstance
        try:
            from PySide6 import QtWidgets
        except Exception:
            from PySide2 import QtWidgets

        ptr = omui.MQtUtil.findControl(workspace)
        if ptr:
            widget = wrapInstance(int(ptr), QtWidgets.QWidget)
            widget.raise_()
            widget.activateWindow()
            widget.setFocus()
    except Exception:
        pass


def _force_focus_async(workspace):
    def worker():
        end_time = time.time() + 1.2
        while time.time() < end_time:
            try:
                cmds.evalDeferred(lambda w=workspace: _focus_once(w), lowestPriority=True)
            except Exception:
                pass
            threading.Event().wait(0.12)

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()


def show_ui():
    """显示工具 UI。"""
    return _build_ui()


def install_shelf_button():
    """在当前 Shelf 上创建工具按钮。"""
    current_shelf = mel.eval("global string $gShelfTopLevel; tabLayout -q -selectTab $gShelfTopLevel;")
    if not current_shelf:
        raise RuntimeError("找不到当前激活的 Shelf。")

    command = (
        "import maya_glb_tool\n"
        "import importlib\n"
        "importlib.reload(maya_glb_tool)\n"
        "maya_glb_tool.show_ui()"
    )
    cmds.shelfButton(
        parent=current_shelf,
        label="GLB",
        imageOverlayLabel="GLB",
        annotation=TOOL_NAME,
        command=command,
        sourceType="python",
    )
    _status("已创建 Shelf 按钮：{}".format(current_shelf))


if __name__ == "__main__":
    try:
        show_ui()
    except Exception:
        traceback.print_exc()
