# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
import math
import mimetypes
import os
import shutil
import struct

import maya.api.OpenMaya as om
import maya.cmds as cmds


NATIVE_VERSION = "v1.0.0"

COMPONENT_FORMAT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}

NORMALIZED_SCALE = {
    5120: 127.0,
    5121: 255.0,
    5122: 32767.0,
    5123: 65535.0,
    5125: 4294967295.0,
}

TYPE_COUNT = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT4": 16,
}


def _align4(data, pad=b"\x00"):
    rest = len(data) % 4
    if rest:
        data += pad * (4 - rest)
    return data


def _safe_name(name, prefix="glb"):
    chars = []
    for char in os.path.splitext(os.path.basename(name or ""))[0]:
        chars.append(char if char.isalnum() or char == "_" else "_")
    safe = "".join(chars).strip("_") or prefix
    if safe[0].isdigit():
        safe = "{}_{}".format(prefix, safe)
    return safe


def _matrix_from_node(node):
    if "matrix" in node:
        values = [float(v) for v in node["matrix"]]
        # glTF 矩阵是列主序，Maya Python API 这里按行主序传值。
        row_major = [values[col * 4 + row] for row in range(4) for col in range(4)]
        return om.MMatrix(row_major)

    translation = node.get("translation", [0.0, 0.0, 0.0])
    rotation = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    scale = node.get("scale", [1.0, 1.0, 1.0])

    t_matrix = om.MTransformationMatrix()
    t_matrix.setTranslation(om.MVector(float(translation[0]), float(translation[1]), float(translation[2])), om.MSpace.kTransform)
    quat = om.MQuaternion(float(rotation[0]), float(rotation[1]), float(rotation[2]), float(rotation[3]))
    t_matrix.setRotation(quat)
    t_matrix.setScale([float(scale[0]), float(scale[1]), float(scale[2])], om.MSpace.kTransform)
    return t_matrix.asMatrix()


def _transform_point(point, matrix):
    return om.MPoint(float(point[0]), float(point[1]), float(point[2])) * matrix


def _transform_vector(vector, matrix):
    normal_matrix = matrix.inverse().transpose()
    transformed = om.MVector(float(vector[0]), float(vector[1]), float(vector[2])) * normal_matrix
    try:
        transformed.normalize()
    except Exception:
        pass
    return transformed


def _workspace_root():
    try:
        root = cmds.workspace(query=True, rootDirectory=True)
        if root:
            return root
    except Exception:
        pass
    return os.path.expanduser("~")


def _set_string_attr(node, attr, value):
    if not node or value is None:
        return
    try:
        if not cmds.attributeQuery(attr, node=node, exists=True):
            cmds.addAttr(node, longName=attr, dataType="string")
        cmds.setAttr("{}.{}".format(node, attr), value, type="string")
    except Exception:
        pass


def _store_gltf_metadata(node, data, prefix="glb"):
    if not data:
        return
    for key in ("name", "extras"):
        if key in data:
            value = data[key]
            if not isinstance(value, str):
                try:
                    value = json.dumps(value, ensure_ascii=False)
                except Exception:
                    value = str(value)
            _set_string_attr(node, "{}_{}".format(prefix, key), value)


def _cache_dir(path):
    folder = os.path.join(_workspace_root(), "sourceimages", "maya_glb_tool", _safe_name(path))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def _read_data_uri(uri):
    header, payload = uri.split(",", 1)
    if ";base64" in header:
        return base64.b64decode(payload)
    return payload.encode("utf-8")


def _read_gltf(path):
    ext = os.path.splitext(path)[1].lower()
    base_dir = os.path.dirname(path)
    if ext == ".glb":
        with open(path, "rb") as handle:
            data = handle.read()
        magic, version, total_len = struct.unpack_from("<III", data, 0)
        if magic != 0x46546C67 or version != 2:
            raise RuntimeError("不是有效的 glTF 2.0 GLB 文件。")
        offset = 12
        json_chunk = None
        bin_chunk = b""
        while offset < total_len:
            chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
            offset += 8
            chunk = data[offset:offset + chunk_len]
            offset += chunk_len
            if chunk_type == 0x4E4F534A:
                json_chunk = chunk
            elif chunk_type == 0x004E4942:
                bin_chunk = chunk
        if json_chunk is None:
            raise RuntimeError("GLB 缺少 JSON chunk。")
        doc = json.loads(json_chunk.decode("utf-8").rstrip(" \t\r\n\x00"))
        buffers = [bin_chunk]
        return doc, buffers, base_dir

    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    buffers = []
    for buffer_info in doc.get("buffers", []):
        uri = buffer_info.get("uri", "")
        if uri.startswith("data:"):
            buffers.append(_read_data_uri(uri))
        else:
            with open(os.path.join(base_dir, uri), "rb") as handle:
                buffers.append(handle.read())
    return doc, buffers, base_dir


def _accessor_values(doc, buffers, accessor_index):
    accessor = doc["accessors"][accessor_index]
    component_type = accessor["componentType"]
    fmt, component_size = COMPONENT_FORMAT[component_type]
    count = accessor["count"]
    value_count = TYPE_COUNT[accessor["type"]]
    normalized = bool(accessor.get("normalized", False))
    item_size = component_size * value_count

    if "bufferView" in accessor:
        view = doc["bufferViews"][accessor["bufferView"]]
        buffer_data = buffers[view.get("buffer", 0)]
        start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        stride = view.get("byteStride", item_size)
    else:
        buffer_data = b""
        start = 0
        stride = item_size

    values = []
    for index in range(count):
        if buffer_data:
            offset = start + index * stride
            raw = buffer_data[offset:offset + item_size]
            unpacked = struct.unpack("<{}{}".format(value_count, fmt), raw)
        else:
            unpacked = tuple(0 for _ in range(value_count))
        if normalized and component_type in NORMALIZED_SCALE:
            scale = NORMALIZED_SCALE[component_type]
            if component_type in (5120, 5122):
                unpacked = tuple(max(-1.0, float(v) / scale) for v in unpacked)
            else:
                unpacked = tuple(float(v) / scale for v in unpacked)
        if value_count == 1:
            values.append(unpacked[0])
        else:
            values.append(tuple(unpacked))

    sparse = accessor.get("sparse")
    if sparse:
        indices_info = sparse["indices"]
        values_info = sparse["values"]
        index_view = doc["bufferViews"][indices_info["bufferView"]]
        value_view = doc["bufferViews"][values_info["bufferView"]]
        index_fmt, index_size = COMPONENT_FORMAT[indices_info["componentType"]]
        value_start = value_view.get("byteOffset", 0) + values_info.get("byteOffset", 0)
        index_start = index_view.get("byteOffset", 0) + indices_info.get("byteOffset", 0)
        index_buffer = buffers[index_view.get("buffer", 0)]
        value_buffer = buffers[value_view.get("buffer", 0)]
        for sparse_id in range(sparse["count"]):
            index_offset = index_start + sparse_id * index_size
            target_index = struct.unpack("<{}".format(index_fmt), index_buffer[index_offset:index_offset + index_size])[0]
            value_offset = value_start + sparse_id * item_size
            raw = value_buffer[value_offset:value_offset + item_size]
            unpacked = struct.unpack("<{}{}".format(value_count, fmt), raw)
            if normalized and component_type in NORMALIZED_SCALE:
                scale = NORMALIZED_SCALE[component_type]
                if component_type in (5120, 5122):
                    unpacked = tuple(max(-1.0, float(v) / scale) for v in unpacked)
                else:
                    unpacked = tuple(float(v) / scale for v in unpacked)
            values[target_index] = unpacked[0] if value_count == 1 else tuple(unpacked)
    return values


def _image_bytes(doc, buffers, base_dir, image_index):
    image = doc.get("images", [])[image_index]
    uri = image.get("uri", "")
    mime = image.get("mimeType", "")
    if uri:
        if uri.startswith("data:"):
            return _read_data_uri(uri), mime
        image_path = os.path.join(base_dir, uri)
        with open(image_path, "rb") as handle:
            return handle.read(), mime or mimetypes.guess_type(image_path)[0] or "image/png"

    view = doc["bufferViews"][image["bufferView"]]
    buffer_data = buffers[view.get("buffer", 0)]
    start = view.get("byteOffset", 0)
    end = start + view.get("byteLength", 0)
    return buffer_data[start:end], mime or "image/png"


def _save_image(doc, buffers, base_dir, image_index, folder):
    data, mime = _image_bytes(doc, buffers, base_dir, image_index)
    ext = mimetypes.guess_extension(mime) or ".png"
    if ext == ".jpe":
        ext = ".jpg"
    name = doc.get("images", [])[image_index].get("name") or "image_{}".format(image_index)
    filename = "{}{}".format(_safe_name(name, "image"), ext)
    path = os.path.join(folder, filename)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def _texture_data(doc, buffers, base_dir, texture_info, cache_dir):
    if not texture_info:
        return "", {}
    tex_index = texture_info.get("index")
    if tex_index is None:
        return "", {}
    texture = doc.get("textures", [])[tex_index]
    image_index = texture.get("source")
    if image_index is None:
        return "", {}
    sampler = {}
    sampler_index = texture.get("sampler")
    if sampler_index is not None and sampler_index < len(doc.get("samplers", [])):
        sampler = doc.get("samplers", [])[sampler_index]
    return _save_image(doc, buffers, base_dir, image_index, cache_dir), sampler


def _texture_path(doc, buffers, base_dir, texture_info, cache_dir):
    path, _ = _texture_data(doc, buffers, base_dir, texture_info, cache_dir)
    return path


def _material_info(doc, buffers, base_dir, material_index, cache_dir):
    material = doc.get("materials", [])[material_index] if material_index is not None else {}
    pbr = material.get("pbrMetallicRoughness", {})
    return {
        "name": material.get("name") or "glb_material",
        "base_color": pbr.get("baseColorFactor", [0.8, 0.8, 0.8, 1.0]),
        "base_color_texture": _texture_data(doc, buffers, base_dir, pbr.get("baseColorTexture"), cache_dir),
        "normal_texture": _texture_data(doc, buffers, base_dir, material.get("normalTexture"), cache_dir),
        "metallic_roughness_texture": _texture_data(doc, buffers, base_dir, pbr.get("metallicRoughnessTexture"), cache_dir),
        "occlusion_texture": _texture_data(doc, buffers, base_dir, material.get("occlusionTexture"), cache_dir),
        "emissive_texture": _texture_data(doc, buffers, base_dir, material.get("emissiveTexture"), cache_dir),
        "emissive_factor": material.get("emissiveFactor", [0.0, 0.0, 0.0]),
        "metallic_factor": pbr.get("metallicFactor", 1.0),
        "roughness_factor": pbr.get("roughnessFactor", 1.0),
        "alpha_mode": material.get("alphaMode", "OPAQUE"),
        "alpha_cutoff": material.get("alphaCutoff", 0.5),
        "double_sided": bool(material.get("doubleSided", False)),
    }


def _connect_file_texture(material, channel_attr, texture_data, suffix, color_space="sRGB"):
    if isinstance(texture_data, (tuple, list)):
        texture_path = texture_data[0]
        sampler = texture_data[1] if len(texture_data) > 1 else {}
    else:
        texture_path = texture_data
        sampler = {}
    if not texture_path:
        return ""
    safe = _safe_name("{}_{}".format(material, suffix), "glb_file")
    file_node = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=safe)
    place = cmds.shadingNode("place2dTexture", asUtility=True, name="{}_place2d".format(safe))
    for attr in (
        "coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV", "stagger",
        "wrapU", "wrapV", "repeatUV", "offset", "rotateUV", "noiseUV",
        "vertexUvOne", "vertexUvTwo", "vertexUvThree", "vertexCameraOne",
    ):
        try:
            cmds.connectAttr("{}.{}".format(place, attr), "{}.{}".format(file_node, attr), force=True)
        except Exception:
            pass
    try:
        cmds.connectAttr("{}.outUV".format(place), "{}.uvCoord".format(file_node), force=True)
        cmds.connectAttr("{}.outUvFilterSize".format(place), "{}.uvFilterSize".format(file_node), force=True)
        cmds.setAttr("{}.fileTextureName".format(file_node), texture_path, type="string")
        cmds.setAttr("{}.colorSpace".format(file_node), color_space, type="string")
        wrap_s = sampler.get("wrapS", 10497)
        wrap_t = sampler.get("wrapT", 10497)
        cmds.setAttr("{}.wrapU".format(place), 0 if wrap_s == 33071 else 1)
        cmds.setAttr("{}.wrapV".format(place), 0 if wrap_t == 33071 else 1)
    except Exception:
        pass
    try:
        cmds.connectAttr("{}.outColor".format(file_node), "{}.{}".format(material, channel_attr), force=True)
    except Exception:
        pass
    return file_node


def _connect_alpha_texture(material, texture_path):
    if isinstance(texture_path, (tuple, list)):
        texture_path = texture_path[0]
    if not texture_path:
        return
    file_node = _connect_file_texture(material, "color", texture_path, "alpha", "sRGB")
    if not file_node:
        return
    try:
        cmds.disconnectAttr("{}.outColor".format(file_node), "{}.color".format(material))
    except Exception:
        pass
    try:
        reverse = cmds.shadingNode("reverse", asUtility=True, name="{}_alpha_reverse".format(_safe_name(material, "mat")))
        cmds.connectAttr("{}.outAlpha".format(file_node), "{}.inputX".format(reverse), force=True)
        cmds.connectAttr("{}.outAlpha".format(file_node), "{}.inputY".format(reverse), force=True)
        cmds.connectAttr("{}.outAlpha".format(file_node), "{}.inputZ".format(reverse), force=True)
        cmds.connectAttr("{}.output".format(reverse), "{}.transparency".format(material), force=True)
    except Exception:
        pass


def _create_material(info):
    name = info.get("name") or "glb_material"
    safe = _safe_name(name, "glb_mat")
    try:
        mat = cmds.shadingNode("standardSurface", asShader=True, name=safe)
        shader_type = "standardSurface"
    except Exception:
        mat = cmds.shadingNode("lambert", asShader=True, name=safe)
        shader_type = "lambert"
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="{}SG".format(safe))
    out_attr = "outColor"
    cmds.connectAttr("{}.{}".format(mat, out_attr), "{}.surfaceShader".format(sg), force=True)
    color = info.get("base_color", [0.8, 0.8, 0.8, 1.0])
    try:
        color_attr = "baseColor" if shader_type == "standardSurface" else "color"
        cmds.setAttr("{}.{}".format(mat, color_attr), float(color[0]), float(color[1]), float(color[2]), type="double3")
        if shader_type == "standardSurface":
            cmds.setAttr("{}.metalness".format(mat), float(info.get("metallic_factor", 1.0)))
            cmds.setAttr("{}.specularRoughness".format(mat), float(info.get("roughness_factor", 1.0)))
    except Exception:
        pass
    if len(color) > 3 and float(color[3]) < 1.0:
        try:
            transparency = 1.0 - float(color[3])
            if shader_type == "standardSurface" and cmds.objExists("{}.opacity".format(mat)):
                cmds.setAttr("{}.opacity".format(mat), float(color[3]), float(color[3]), float(color[3]), type="double3")
            else:
                cmds.setAttr("{}.transparency".format(mat), transparency, transparency, transparency, type="double3")
        except Exception:
            pass
    base_texture = info.get("base_color_texture")
    _connect_file_texture(mat, "baseColor" if shader_type == "standardSurface" else "color", base_texture, "baseColor", "sRGB")
    if info.get("alpha_mode") in ("BLEND", "MASK") and base_texture:
        _connect_alpha_texture(mat, base_texture)
    normal_file = _connect_file_texture(mat, "normalCamera", info.get("normal_texture"), "normal", "Raw")
    if normal_file:
        try:
            bump = cmds.shadingNode("bump2d", asUtility=True, name="{}_normal_bump".format(safe))
            cmds.setAttr("{}.bumpInterp".format(bump), 1)
            cmds.connectAttr("{}.outAlpha".format(normal_file), "{}.bumpValue".format(bump), force=True)
            normal_attr = "normalCamera" if cmds.objExists("{}.normalCamera".format(mat)) else "normal"
            cmds.connectAttr("{}.outNormal".format(bump), "{}.{}".format(mat, normal_attr), force=True)
        except Exception:
            pass
    emissive_file = ""
    for label, texture_path in (
        ("metallicRoughness", info.get("metallic_roughness_texture")),
        ("occlusion", info.get("occlusion_texture")),
        ("emissive", info.get("emissive_texture")),
    ):
        node = _connect_file_texture(mat, "color", texture_path, label, "Raw")
        if node:
            try:
                cmds.disconnectAttr("{}.outColor".format(node), "{}.color".format(mat))
            except Exception:
                pass
        if label == "emissive":
            emissive_file = node
    emissive = info.get("emissive_factor", [0.0, 0.0, 0.0])
    try:
        if any(float(v) > 0.0 for v in emissive):
            cmds.setAttr("{}.incandescence".format(mat), float(emissive[0]), float(emissive[1]), float(emissive[2]), type="double3")
    except Exception:
        pass
    if emissive_file:
        try:
            cmds.connectAttr("{}.outColor".format(emissive_file), "{}.incandescence".format(mat), force=True)
        except Exception:
            pass
    try:
        cmds.setAttr("{}.glb_metallicFactor".format(mat), float(info.get("metallic_factor", 1.0)))
    except Exception:
        try:
            cmds.addAttr(mat, longName="glb_metallicFactor", attributeType="double", defaultValue=float(info.get("metallic_factor", 1.0)))
        except Exception:
            pass
    try:
        cmds.addAttr(mat, longName="glb_roughnessFactor", attributeType="double", defaultValue=float(info.get("roughness_factor", 1.0)))
    except Exception:
        pass
    try:
        cmds.addAttr(mat, longName="glb_doubleSided", attributeType="bool", defaultValue=bool(info.get("double_sided", False)))
    except Exception:
        pass
    try:
        cmds.addAttr(mat, longName="glb_alphaMode", dataType="string")
        cmds.setAttr("{}.glb_alphaMode".format(mat), info.get("alpha_mode", "OPAQUE"), type="string")
    except Exception:
        pass
    return sg


def import_glb(path, quadrangulate=False):
    doc, buffers, base_dir = _read_gltf(path)
    cache = _cache_dir(path)
    created = []
    scene = doc.get("scenes", [{}])[doc.get("scene", 0)]
    nodes = doc.get("nodes", [])
    material_cache = {}
    punctual_lights = doc.get("extensions", {}).get("KHR_lights_punctual", {}).get("lights", [])
    stats = {"meshes": 0, "cameras": 0, "lights": 0, "materials": 0, "textures": 0}

    def import_node(node_index, parent_matrix=None):
        node = nodes[node_index]
        local_matrix = _matrix_from_node(node)
        world_matrix = local_matrix if parent_matrix is None else local_matrix * parent_matrix
        mesh_index = node.get("mesh")
        camera_index = node.get("camera")
        light_ref = node.get("extensions", {}).get("KHR_lights_punctual", {}).get("light")
        if camera_index is not None:
            camera_info = doc.get("cameras", [])[camera_index]
            transform, camera_shape = cmds.camera(name=_safe_name(node.get("name") or camera_info.get("name") or "glb_camera", "camera"))
            try:
                matrix_values = [world_matrix(row, col) for row in range(4) for col in range(4)]
                cmds.xform(transform, matrix=matrix_values, worldSpace=True)
            except Exception:
                pass
            if camera_info.get("type") == "perspective":
                persp = camera_info.get("perspective", {})
                if "yfov" in persp:
                    try:
                        cmds.setAttr("{}.verticalFieldOfView".format(camera_shape), math.degrees(float(persp["yfov"])))
                    except Exception:
                        pass
                if "znear" in persp:
                    cmds.setAttr("{}.nearClipPlane".format(camera_shape), float(persp["znear"]))
                if "zfar" in persp:
                    cmds.setAttr("{}.farClipPlane".format(camera_shape), float(persp["zfar"]))
            _store_gltf_metadata(transform, node)
            _store_gltf_metadata(camera_shape, camera_info)
            created.append(transform)
            stats["cameras"] += 1
        if light_ref is not None and light_ref < len(punctual_lights):
            light_info = punctual_lights[light_ref]
            light_type = light_info.get("type", "point")
            if light_type == "directional":
                maya_type = "directionalLight"
            elif light_type == "spot":
                maya_type = "spotLight"
            else:
                maya_type = "pointLight"
            light_shape = cmds.shadingNode(maya_type, asLight=True, name=_safe_name(node.get("name") or light_info.get("name") or "glb_light", "light"))
            parents = cmds.listRelatives(light_shape, parent=True, fullPath=True) or []
            transform = parents[0] if parents else light_shape
            try:
                matrix_values = [world_matrix(row, col) for row in range(4) for col in range(4)]
                cmds.xform(transform, matrix=matrix_values, worldSpace=True)
            except Exception:
                pass
            color = light_info.get("color", [1.0, 1.0, 1.0])
            try:
                cmds.setAttr("{}.color".format(light_shape), float(color[0]), float(color[1]), float(color[2]), type="double3")
                cmds.setAttr("{}.intensity".format(light_shape), float(light_info.get("intensity", 1.0)))
            except Exception:
                pass
            _store_gltf_metadata(transform, node)
            _store_gltf_metadata(light_shape, light_info)
            created.append(transform)
            stats["lights"] += 1
        if mesh_index is not None:
            mesh = doc.get("meshes", [])[mesh_index]
            all_points = []
            all_uvs = []
            all_normals = []
            all_colors = []
            face_counts = []
            face_connects = []
            normal_ids = []
            face_materials = []

            for primitive in mesh.get("primitives", []):
                if primitive.get("mode", 4) != 4:
                    continue
                attrs = primitive.get("attributes", {})
                positions = _accessor_values(doc, buffers, attrs["POSITION"])
                normals = _accessor_values(doc, buffers, attrs["NORMAL"]) if "NORMAL" in attrs else []
                texcoords = _accessor_values(doc, buffers, attrs["TEXCOORD_0"]) if "TEXCOORD_0" in attrs else []
                colors = _accessor_values(doc, buffers, attrs["COLOR_0"]) if "COLOR_0" in attrs else []
                indices = _accessor_values(doc, buffers, primitive["indices"]) if "indices" in primitive else list(range(len(positions)))
                vertex_offset = len(all_points)
                all_points.extend([_transform_point(p, world_matrix) for p in positions])
                all_uvs.extend([(float(uv[0]), 1.0 - float(uv[1])) for uv in texcoords] if texcoords else [(0.0, 0.0) for _ in positions])
                all_normals.extend([_transform_vector(n, world_matrix) for n in normals] if normals else [om.MVector(0.0, 1.0, 0.0) for _ in positions])
                all_colors.extend([
                    om.MColor((float(c[0]), float(c[1]), float(c[2]), float(c[3]) if len(c) > 3 else 1.0))
                    for c in colors
                ] if colors else [om.MColor((1.0, 1.0, 1.0, 1.0)) for _ in positions])

                for i in range(0, len(indices), 3):
                    tri = indices[i:i + 3]
                    if len(tri) == 3:
                        face_counts.append(3)
                        face_connects.extend([vertex_offset + int(v) for v in tri])
                        normal_ids.extend([vertex_offset + int(v) for v in tri])
                        face_materials.append(primitive.get("material"))

            if all_points and face_counts:
                mesh_fn = om.MFnMesh()
                mesh_obj = mesh_fn.create(all_points, face_counts, face_connects)
                dag = om.MDagPath.getAPathTo(mesh_obj)
                created_path = cmds.rename(dag.fullPathName(), _safe_name(mesh.get("name") or node.get("name") or path))
                if cmds.nodeType(created_path) == "mesh":
                    shape = created_path
                    parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
                    transform = parents[0] if parents else shape
                else:
                    transform = created_path
                    shape = (cmds.listRelatives(transform, shapes=True, fullPath=True) or [None])[0]
                if shape:
                    sel = om.MSelectionList()
                    sel.add(shape)
                    mesh_fn = om.MFnMesh(sel.getDagPath(0))
                    us = [float(uv[0]) for uv in all_uvs]
                    vs = [float(uv[1]) for uv in all_uvs]
                    try:
                        mesh_fn.setUVs(us, vs, "map1")
                        mesh_fn.assignUVs(face_counts, face_connects, "map1")
                    except Exception:
                        pass
                if shape:
                    try:
                        normal_values = [all_normals[index] for index in normal_ids]
                        face_ids = []
                        vertex_ids = []
                        cursor = 0
                        for face_id, count in enumerate(face_counts):
                            for _ in range(count):
                                face_ids.append(face_id)
                                vertex_ids.append(face_connects[cursor])
                                cursor += 1
                        mesh_fn.setFaceVertexNormals(normal_values, face_ids, vertex_ids)
                        cmds.polyNormalPerVertex(shape, freezeNormal=True)
                    except Exception:
                        pass
                if shape:
                    try:
                        color_values = []
                        face_ids = []
                        vertex_ids = []
                        cursor = 0
                        for face_id, count in enumerate(face_counts):
                            for _ in range(count):
                                vertex_id = face_connects[cursor]
                                color_values.append(all_colors[vertex_id])
                                face_ids.append(face_id)
                                vertex_ids.append(vertex_id)
                                cursor += 1
                        mesh_fn.createColorSetWithName("colorSet1")
                        mesh_fn.setCurrentColorSetName("colorSet1")
                        mesh_fn.setFaceVertexColors(color_values, face_ids, vertex_ids)
                    except Exception:
                        pass
                faces_by_material = {}
                for face_id, mat_index in enumerate(face_materials):
                    faces_by_material.setdefault(mat_index, []).append(face_id)
                for mat_index, face_ids_for_mat in faces_by_material.items():
                    if mat_index in material_cache:
                        sg = material_cache[mat_index]
                    else:
                        material_info = _material_info(doc, buffers, base_dir, mat_index, cache)
                        sg = _create_material(material_info)
                        material_cache[mat_index] = sg
                        stats["materials"] += 1
                        for key in ("base_color_texture", "normal_texture", "metallic_roughness_texture", "occlusion_texture", "emissive_texture"):
                            tex_data = material_info.get(key)
                            if tex_data and tex_data[0]:
                                stats["textures"] += 1
                    components = ["{}.f[{}]".format(transform, face_id) for face_id in face_ids_for_mat]
                    try:
                        cmds.sets(components, edit=True, forceElement=sg)
                    except Exception:
                        cmds.sets(transform, edit=True, forceElement=sg)
                if quadrangulate:
                    try:
                        cmds.polyQuad(transform, angle=30, constructionHistory=False)
                    except Exception:
                        pass
                _store_gltf_metadata(transform, node)
                _store_gltf_metadata(transform, mesh, prefix="glb_mesh")
                created.append(transform)
                stats["meshes"] += 1
        for child in node.get("children", []):
            import_node(child, world_matrix)

    for root_node in scene.get("nodes", []):
        import_node(root_node)
    if created:
        cmds.select(created, replace=True)
    try:
        cmds.inViewMessage(
            amg="GLB 原生导入：mesh <hl>{meshes}</hl> / 材质 <hl>{materials}</hl> / 贴图 <hl>{textures}</hl> / 相机 <hl>{cameras}</hl> / 灯光 <hl>{lights}</hl>".format(**stats),
            pos="midCenter",
            fade=True,
        )
    except Exception:
        pass
    return created


def _get_mesh_dag(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return sel.getDagPath(0)


def _mesh_shapes(selected_only=True):
    roots = cmds.ls(selection=True, long=True) if selected_only else cmds.ls(assemblies=True, long=True)
    shapes = []
    for root in roots or []:
        found = cmds.listRelatives(root, allDescendents=True, type="mesh", fullPath=True) or []
        if cmds.nodeType(root) == "mesh":
            found.append(root)
        for shape in found:
            if not cmds.getAttr("{}.intermediateObject".format(shape)):
                shapes.append(shape)
    return shapes


def _first_texture_for_shape(shape):
    sgs = cmds.listConnections(shape, type="shadingEngine") or []
    for sg in sgs:
        mats = cmds.ls(cmds.listConnections("{}.surfaceShader".format(sg), source=True, destination=False) or [], materials=True) or []
        for mat in mats:
            files = cmds.listConnections(mat, type="file") or []
            for file_node in files:
                try:
                    path = cmds.getAttr("{}.fileTextureName".format(file_node))
                    if path and os.path.isfile(path):
                        return path
                except Exception:
                    pass
    return ""


def _materials_for_shape(shape):
    result = []
    sgs = cmds.listConnections(shape, type="shadingEngine") or []
    for sg in sgs:
        mats = cmds.ls(cmds.listConnections("{}.surfaceShader".format(sg), source=True, destination=False) or [], materials=True) or []
        for mat in mats:
            if mat not in result:
                result.append(mat)
    return result


def _face_material_map(shape):
    mapping = {}
    sgs = cmds.listConnections(shape, type="shadingEngine") or []
    for sg in sgs:
        members = cmds.sets(sg, query=True) or []
        for member in members:
            if not member.startswith(shape):
                continue
            if ".f[" not in member:
                continue
            try:
                faces = cmds.filterExpand(member, selectionMask=34, expand=True) or []
            except Exception:
                faces = [member]
            for face in faces:
                try:
                    face_id = int(face.split(".f[", 1)[1].split("]", 1)[0])
                    mapping[face_id] = sg
                except Exception:
                    pass
    return mapping


def _material_from_sg(sg):
    mats = cmds.ls(cmds.listConnections("{}.surfaceShader".format(sg), source=True, destination=False) or [], materials=True) or []
    return mats[0] if mats else ""


def _texture_for_material_attr(material, attrs):
    for attr in attrs:
        plug = "{}.{}".format(material, attr)
        if not cmds.objExists(plug):
            continue
        files = cmds.listConnections(plug, source=True, destination=False, type="file") or []
        if not files:
            upstream = cmds.listConnections(plug, source=True, destination=False) or []
            for node in upstream:
                files.extend(cmds.listConnections(node, source=True, destination=False, type="file") or [])
        for file_node in files:
            try:
                path = cmds.getAttr("{}.fileTextureName".format(file_node))
                if path and os.path.isfile(path):
                    return path
            except Exception:
                pass
    return ""


def _material_scalar(material, attrs, default):
    for attr in attrs:
        plug = "{}.{}".format(material, attr)
        if cmds.objExists(plug):
            try:
                return float(cmds.getAttr(plug))
            except Exception:
                pass
    return default


def _material_color(material, default=None):
    default = default or [0.8, 0.8, 0.8, 1.0]
    if cmds.objExists("{}.color".format(material)):
        try:
            value = cmds.getAttr("{}.color".format(material))[0]
            default = [float(value[0]), float(value[1]), float(value[2]), default[3]]
        except Exception:
            pass
    if cmds.objExists("{}.transparency".format(material)):
        try:
            value = cmds.getAttr("{}.transparency".format(material))[0]
            alpha = 1.0 - max(float(value[0]), float(value[1]), float(value[2]))
            default[3] = max(0.0, min(1.0, alpha))
        except Exception:
            pass
    return default


def _append_blob(blob, payload):
    blob = _align4(blob)
    offset = len(blob)
    blob += payload
    return blob, offset


def _pack_floats(values):
    return struct.pack("<{}f".format(len(values)), *values) if values else b""


def _pack_uints(values):
    return struct.pack("<{}I".format(len(values)), *values) if values else b""


def _mesh_vertex_colors(mesh_fn, face_id, vertex_id):
    try:
        color = mesh_fn.getFaceVertexColor(face_id, vertex_id, "colorSet1")
        return (float(color.r), float(color.g), float(color.b), float(color.a))
    except Exception:
        return (1.0, 1.0, 1.0, 1.0)


def export_glb(path, selected_only=True, embed_textures=True):
    shapes = _mesh_shapes(selected_only)
    if not shapes:
        raise RuntimeError("没有可导出的 mesh。")

    doc = {
        "asset": {"version": "2.0", "generator": "Maya GLB Native"},
        "scenes": [{"nodes": []}],
        "scene": 0,
        "nodes": [],
        "meshes": [],
        "cameras": [],
        "buffers": [{"byteLength": 0}],
        "bufferViews": [],
        "accessors": [],
        "materials": [],
    }
    bin_blob = b""

    def add_accessor(payload, component_type, type_name, count, target=None, min_value=None, max_value=None):
        nonlocal bin_blob
        bin_blob, offset = _append_blob(bin_blob, payload)
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(payload)}
        if target:
            view["target"] = target
        view_index = len(doc["bufferViews"])
        doc["bufferViews"].append(view)
        accessor = {"bufferView": view_index, "componentType": component_type, "count": count, "type": type_name}
        if min_value is not None:
            accessor["min"] = min_value
        if max_value is not None:
            accessor["max"] = max_value
        accessor_index = len(doc["accessors"])
        doc["accessors"].append(accessor)
        return accessor_index

    def add_image_texture(texture_path):
        nonlocal bin_blob
        if not texture_path or not os.path.isfile(texture_path):
            return None
        if "images" not in doc:
            doc["images"] = []
            doc["textures"] = []
        with open(texture_path, "rb") as handle:
            image_bytes = handle.read()
        bin_blob, image_offset = _append_blob(bin_blob, image_bytes)
        mime = mimetypes.guess_type(texture_path)[0] or "image/png"
        view_index = len(doc["bufferViews"])
        doc["bufferViews"].append({"buffer": 0, "byteOffset": image_offset, "byteLength": len(image_bytes)})
        image_index = len(doc["images"])
        doc["images"].append({"bufferView": view_index, "mimeType": mime, "name": _safe_name(texture_path, "image")})
        texture_index = len(doc["textures"])
        doc["textures"].append({"source": image_index})
        return texture_index

    def add_material(material, fallback_shape):
        material_doc = {
            "name": _safe_name(material or fallback_shape, "mat"),
            "pbrMetallicRoughness": {
                "baseColorFactor": _material_color(material) if material else [0.8, 0.8, 0.8, 1.0],
                "roughnessFactor": _material_scalar(material, ["glb_roughnessFactor", "roughness", "specularRoughness"], 0.5) if material else 0.5,
                "metallicFactor": _material_scalar(material, ["glb_metallicFactor", "metalness", "metallic"], 0.0) if material else 0.0,
            },
        }
        if material_doc["pbrMetallicRoughness"]["baseColorFactor"][3] < 1.0:
            material_doc["alphaMode"] = "BLEND"

        if embed_textures and material:
            base_texture = _texture_for_material_attr(material, ["color", "baseColor", "base_color"])
            normal_texture = _texture_for_material_attr(material, ["normalCamera", "normal", "normalMap"])
            mr_texture = _texture_for_material_attr(material, ["roughness", "metalness", "metallic", "specularRoughness"])
            emissive_texture = _texture_for_material_attr(material, ["incandescence", "emissionColor", "emissive"])
            base_index = add_image_texture(base_texture)
            normal_index = add_image_texture(normal_texture)
            mr_index = add_image_texture(mr_texture)
            emissive_index = add_image_texture(emissive_texture)
            if base_index is not None:
                material_doc["pbrMetallicRoughness"]["baseColorTexture"] = {"index": base_index}
            if mr_index is not None:
                material_doc["pbrMetallicRoughness"]["metallicRoughnessTexture"] = {"index": mr_index}
            if normal_index is not None:
                material_doc["normalTexture"] = {"index": normal_index}
            if emissive_index is not None:
                material_doc["emissiveTexture"] = {"index": emissive_index}

        material_index = len(doc["materials"])
        doc["materials"].append(material_doc)
        return material_index

    for shape in shapes:
        dag = _get_mesh_dag(shape)
        mesh_fn = om.MFnMesh(dag)
        iterator = om.MItMeshPolygon(dag)
        face_materials = _face_material_map(shape)
        default_material = (_materials_for_shape(shape) or [""])[0]
        primitive_data = {}

        def data_for_face(face_id):
            sg = face_materials.get(face_id, "")
            material = _material_from_sg(sg) if sg else default_material
            key = material or "__default__"
            if key not in primitive_data:
                primitive_data[key] = {
                    "material": material,
                    "vertex_map": {},
                    "positions": [],
                    "normals": [],
                    "uvs": [],
                    "colors": [],
                    "indices": [],
                }
            return primitive_data[key]

        while not iterator.isDone():
            face_id = iterator.index()
            polygon_vertices = list(iterator.getVertices())
            tri_points, tri_vertices = iterator.getTriangles(om.MSpace.kWorld)
            prim = data_for_face(face_id)
            for tri_offset in range(0, len(tri_vertices), 3):
                for local in range(3):
                    vertex_id = int(tri_vertices[tri_offset + local])
                    point = mesh_fn.getPoint(vertex_id, om.MSpace.kWorld)
                    try:
                        normal = mesh_fn.getFaceVertexNormal(face_id, vertex_id, om.MSpace.kWorld)
                    except Exception:
                        normal = om.MVector(0.0, 1.0, 0.0)
                    try:
                        local_vertex_id = polygon_vertices.index(vertex_id)
                        uv = iterator.getUV(local_vertex_id, "map1")
                    except Exception:
                        uv = (0.0, 0.0)
                    color = _mesh_vertex_colors(mesh_fn, face_id, vertex_id)
                    key = (
                        round(point.x, 7), round(point.y, 7), round(point.z, 7),
                        round(normal.x, 7), round(normal.y, 7), round(normal.z, 7),
                        round(float(uv[0]), 7), round(float(uv[1]), 7),
                        round(color[0], 7), round(color[1], 7), round(color[2], 7), round(color[3], 7),
                    )
                    if key not in prim["vertex_map"]:
                        prim["vertex_map"][key] = len(prim["positions"])
                        prim["positions"].append((point.x, point.y, point.z))
                        prim["normals"].append((normal.x, normal.y, normal.z))
                        prim["uvs"].append((float(uv[0]), 1.0 - float(uv[1])))
                        prim["colors"].append(color)
                    prim["indices"].append(prim["vertex_map"][key])
            iterator.next()

        primitives = []
        for prim in primitive_data.values():
            if not prim["positions"] or not prim["indices"]:
                continue
            positions = prim["positions"]
            normals = prim["normals"]
            uvs = prim["uvs"]
            colors = prim["colors"]
            indices = prim["indices"]
            flat_positions = [c for value in positions for c in value]
            flat_normals = [c for value in normals for c in value]
            flat_uvs = [c for value in uvs for c in value]
            flat_colors = [c for value in colors for c in value]
            pos_min = [min(v[i] for v in positions) for i in range(3)]
            pos_max = [max(v[i] for v in positions) for i in range(3)]
            pos_accessor = add_accessor(_pack_floats(flat_positions), 5126, "VEC3", len(positions), 34962, pos_min, pos_max)
            normal_accessor = add_accessor(_pack_floats(flat_normals), 5126, "VEC3", len(normals), 34962)
            uv_accessor = add_accessor(_pack_floats(flat_uvs), 5126, "VEC2", len(uvs), 34962)
            color_accessor = add_accessor(_pack_floats(flat_colors), 5126, "VEC4", len(colors), 34962)
            index_accessor = add_accessor(_pack_uints(indices), 5125, "SCALAR", len(indices), 34963)
            material_index = add_material(prim["material"], shape)
            primitives.append({
                "attributes": {"POSITION": pos_accessor, "NORMAL": normal_accessor, "TEXCOORD_0": uv_accessor, "COLOR_0": color_accessor},
                "indices": index_accessor,
                "material": material_index,
                "mode": 4,
            })

        if not primitives:
            continue

        mesh_index = len(doc["meshes"])
        doc["meshes"].append({
            "name": _safe_name(shape, "mesh"),
            "primitives": primitives,
        })
        node_index = len(doc["nodes"])
        doc["nodes"].append({"mesh": mesh_index, "name": _safe_name(shape, "node")})
        doc["scenes"][0]["nodes"].append(node_index)

    camera_shapes = cmds.ls(selection=True, dag=True, type="camera", long=True) if selected_only else cmds.ls(type="camera", long=True)
    for camera_shape in camera_shapes or []:
        parents = cmds.listRelatives(camera_shape, parent=True, fullPath=True) or []
        if not parents:
            continue
        transform = parents[0]
        try:
            yfov = math.radians(float(cmds.getAttr("{}.verticalFieldOfView".format(camera_shape))))
        except Exception:
            yfov = math.radians(45.0)
        camera_index = len(doc["cameras"])
        doc["cameras"].append({
            "name": _safe_name(transform, "camera"),
            "type": "perspective",
            "perspective": {
                "yfov": yfov,
                "znear": float(cmds.getAttr("{}.nearClipPlane".format(camera_shape))),
                "zfar": float(cmds.getAttr("{}.farClipPlane".format(camera_shape))),
            },
        })
        try:
            matrix = cmds.xform(transform, query=True, matrix=True, worldSpace=True)
        except Exception:
            matrix = None
        node = {"camera": camera_index, "name": _safe_name(transform, "camera")}
        if matrix:
            node["matrix"] = [matrix[col * 4 + row] for row in range(4) for col in range(4)]
        node_index = len(doc["nodes"])
        doc["nodes"].append(node)
        doc["scenes"][0]["nodes"].append(node_index)

    if not doc["cameras"]:
        doc.pop("cameras", None)

    light_shapes = cmds.ls(selection=True, dag=True, lights=True, long=True) if selected_only else cmds.ls(lights=True, long=True)
    lights_ext = []
    for light_shape in light_shapes or []:
        parents = cmds.listRelatives(light_shape, parent=True, fullPath=True) or []
        transform = parents[0] if parents else light_shape
        node_type = cmds.nodeType(light_shape)
        if node_type == "directionalLight":
            gltf_type = "directional"
        elif node_type == "spotLight":
            gltf_type = "spot"
        elif node_type == "pointLight":
            gltf_type = "point"
        else:
            continue
        try:
            color = cmds.getAttr("{}.color".format(light_shape))[0]
        except Exception:
            color = (1.0, 1.0, 1.0)
        try:
            intensity = float(cmds.getAttr("{}.intensity".format(light_shape)))
        except Exception:
            intensity = 1.0
        light_index = len(lights_ext)
        lights_ext.append({
            "name": _safe_name(transform, "light"),
            "type": gltf_type,
            "color": [float(color[0]), float(color[1]), float(color[2])],
            "intensity": intensity,
        })
        try:
            matrix = cmds.xform(transform, query=True, matrix=True, worldSpace=True)
        except Exception:
            matrix = None
        node = {
            "name": _safe_name(transform, "light"),
            "extensions": {"KHR_lights_punctual": {"light": light_index}},
        }
        if matrix:
            node["matrix"] = [matrix[col * 4 + row] for row in range(4) for col in range(4)]
        node_index = len(doc["nodes"])
        doc["nodes"].append(node)
        doc["scenes"][0]["nodes"].append(node_index)

    if lights_ext:
        doc.setdefault("extensionsUsed", [])
        if "KHR_lights_punctual" not in doc["extensionsUsed"]:
            doc["extensionsUsed"].append("KHR_lights_punctual")
        doc.setdefault("extensions", {})
        doc["extensions"]["KHR_lights_punctual"] = {"lights": lights_ext}

    bin_blob = _align4(bin_blob)
    doc["buffers"][0]["byteLength"] = len(bin_blob)
    json_blob = _align4(json.dumps(doc, separators=(",", ":")).encode("utf-8"), b" ")
    total_len = 12 + 8 + len(json_blob) + 8 + len(bin_blob)
    with open(path, "wb") as handle:
        handle.write(struct.pack("<III", 0x46546C67, 2, total_len))
        handle.write(struct.pack("<II", len(json_blob), 0x4E4F534A))
        handle.write(json_blob)
        handle.write(struct.pack("<II", len(bin_blob), 0x004E4942))
        handle.write(bin_blob)
    validate_glb(path)
    return path


def validate_glb(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) < 20:
        raise RuntimeError("GLB 文件过短。")
    magic, version, total_len = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise RuntimeError("GLB magic 无效。")
    if version != 2:
        raise RuntimeError("仅支持 GLB 2.0。")
    if total_len != len(data):
        raise RuntimeError("GLB 长度不匹配：header={} actual={}".format(total_len, len(data)))
    offset = 12
    has_json = False
    has_bin = False
    while offset < len(data):
        if offset + 8 > len(data):
            raise RuntimeError("GLB chunk header 不完整。")
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        if offset + chunk_len > len(data):
            raise RuntimeError("GLB chunk 数据越界。")
        if chunk_type == 0x4E4F534A:
            has_json = True
            json.loads(data[offset:offset + chunk_len].decode("utf-8").rstrip(" \t\r\n\x00"))
        elif chunk_type == 0x004E4942:
            has_bin = True
        offset += chunk_len
    if not has_json:
        raise RuntimeError("GLB 缺少 JSON chunk。")
    return {"has_json": has_json, "has_bin": has_bin, "byteLength": len(data)}
