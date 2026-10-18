"""Scene reset and PBR material helpers."""

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from generate_house_runtime import (
    BLENDER_ROOT,
    SCRIPT_DIR,
    bpy,
    export_glb,
    import_asset,
    mathutils,
    place_furniture,
)

def clear_scene():
    """Removes all default objects, meshes, materials, and lights from scene."""
    if bpy is None:
        return
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


# ─── PBR Material System ──────────────────────────────────────────────────────

def hex_to_rgb(hex_str: str) -> List[float]:
    """Converts hex color string to normalized RGB list [r, g, b]."""
    h = str(hex_str).lstrip("#")
    if len(h) == 6:
        try:
            return [int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0]
        except ValueError:
            pass
    return [0.85, 0.85, 0.85]


def apply_box_uv_mapping(obj, tile_meters: float = 1.5):
    """
    Applies world-space triplanar UV mapping to a mesh object based on physical meter dimensions.
    Prevents any texture stretching and ensures seamless repeating across large and small surfaces.
    """
    if bpy is None or obj is None or obj.type != 'MESH':
        return

    # Apply transform scale first so vertices reflect true physical meters
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    except Exception:
        pass

    mesh = obj.data
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active.data

    # Map each polygon's loop vertices according to physical 3D world coordinates
    for poly in mesh.polygons:
        nx = abs(poly.normal.x)
        ny = abs(poly.normal.y)
        nz = abs(poly.normal.z)

        for loop_idx in poly.loop_indices:
            vert_idx = mesh.loops[loop_idx].vertex_index
            v = mesh.vertices[vert_idx].co
            wx = obj.location.x + v.x
            wy = obj.location.y + v.y
            wz = obj.location.z + v.z

            if nz >= nx and nz >= ny:
                # Top / Bottom horizontal face (Floors, Slabs, Ground, Ceilings)
                u = wx / tile_meters
                v_coord = wy / tile_meters
            elif nx >= ny:
                # Side face along YZ (West / East walls)
                u = wy / tile_meters
                v_coord = wz / tile_meters
            else:
                # Side face along XZ (North / South walls)
                u = wx / tile_meters
                v_coord = wz / tile_meters

            uv_layer[loop_idx].uv = (u, v_coord)


def _attach_image_texture(mat, bsdf, img_rel_path: str):
    """Helper to attach an image texture node to Principled BSDF with UV repeating."""
    if bpy is None or not img_rel_path:
        return

    norm_rel = img_rel_path.replace("\\", "/").lstrip("/")
    img_abs_path = os.path.join(BLENDER_ROOT, "assets", norm_rel)

    # Automatic fallback: download directly from Amazon S3 if not cached locally
    if not os.path.isfile(img_abs_path) or os.path.getsize(img_abs_path) == 0:
        try:
            import s3_asset_resolver
            res_path = s3_asset_resolver.download_asset_if_missing(norm_rel, base_blender_dir=BLENDER_ROOT)
            if res_path and os.path.isfile(res_path) and os.path.getsize(res_path) > 0:
                img_abs_path = res_path
        except Exception as e:
            print(f"[S3Resolver] Download failed for {norm_rel}: {e}")

    if not os.path.isfile(img_abs_path) or os.path.getsize(img_abs_path) == 0:
        print(f"[WARN] Texture not found on disk or S3: {norm_rel}")
        return

    try:
        img = bpy.data.images.load(img_abs_path, check_existing=True)
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.image = img
        tex_node.extension = 'REPEAT'

        coord_node = nodes.new(type='ShaderNodeTexCoord')
        map_node = nodes.new(type='ShaderNodeMapping')
        map_node.inputs['Scale'].default_value = (1.0, 1.0, 1.0)

        # Connect standard UV coordinates for 100% glTF 2.0 compatibility
        links.new(coord_node.outputs['UV'], map_node.inputs['Vector'])
        links.new(map_node.outputs['Vector'], tex_node.inputs['Vector'])
        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    except Exception as e:
        print(f"[WARN] Failed to attach texture {img_rel_path}: {e}")


def create_pbr_material(
    name: str,
    mat_type: str = "wall",
    color_rgb: Optional[List[float]] = None,
    roughness: float = 0.5,
    metalness: float = 0.0
) -> Any:
    """
    Creates physically based Principled BSDF materials with realistic PBR texture maps from S3 assets.
    """
    if bpy is None:
        return None

    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")

    if not bsdf:
        return mat

    c = color_rgb if color_rgb and len(color_rgb) >= 3 else [0.93, 0.91, 0.88]

    if mat_type == "glass":
        bsdf.inputs["Base Color"].default_value = (0.9, 0.95, 1.0, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.05
        bsdf.inputs["IOR"].default_value = 1.52
        if "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = 0.95
        elif "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 0.95
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = 'DITHERED'
        elif hasattr(mat, "blend_method"):
            mat.blend_method = 'BLEND'
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = 'NONE'

    elif mat_type == "wood":
        # Hardwood floor planks from floor assets
        wood_color = (c[0] * 0.9, c[1] * 0.85, c[2] * 0.75, 1.0)
        bsdf.inputs["Base Color"].default_value = wood_color
        bsdf.inputs["Roughness"].default_value = 0.40
        if "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.45
        _attach_image_texture(mat, bsdf, "textures/floors/dark_wooden_planks_diff_2k.jpg")

    elif mat_type in ["marble"]:
        # Polished luxury marble from floor assets
        tile_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = tile_color
        bsdf.inputs["Roughness"].default_value = 0.18
        if "Clearcoat" in bsdf.inputs:
            bsdf.inputs["Clearcoat"].default_value = 0.6
        elif "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.6
        _attach_image_texture(mat, bsdf, "textures/floors/marble_01_diff_2k.jpg")

    elif mat_type in ["tile", "mosaic"]:
        # Mosaic porcelain tiles from floor assets
        tile_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = tile_color
        bsdf.inputs["Roughness"].default_value = 0.22
        _attach_image_texture(mat, bsdf, "textures/floors/marble_mosaic_tiles_diff_2k.jpg")

    elif mat_type == "metal":
        bsdf.inputs["Base Color"].default_value = (0.15, 0.18, 0.22, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.85
        bsdf.inputs["Roughness"].default_value = 0.35

    elif mat_type == "trim":
        bsdf.inputs["Base Color"].default_value = (0.24, 0.18, 0.14, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55

    elif mat_type == "deck":
        # Slatted outdoor teak patio deck
        bsdf.inputs["Base Color"].default_value = (0.50, 0.32, 0.20, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.60
        _attach_image_texture(mat, bsdf, "textures/floors/dark_wooden_planks_diff_2k.jpg")

    elif mat_type == "concrete":
        # Interlocking architectural stone pavers from grounds assets
        bsdf.inputs["Base Color"].default_value = (0.35, 0.36, 0.38, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.85
        _attach_image_texture(mat, bsdf, "textures/grounds/concrete_pavers_diff_2k.jpg")

    elif mat_type == "grass":
        # Lush outdoor landscape lawn from grounds assets
        bsdf.inputs["Base Color"].default_value = (0.18, 0.38, 0.20, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.95
        _attach_image_texture(mat, bsdf, "textures/grounds/leafy_grass_diff_1k.jpg")

    elif mat_type in ["wall_brick", "brick"]:
        # Exposed architectural brick wall from wall assets
        wall_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = wall_color
        bsdf.inputs["Roughness"].default_value = 0.85
        _attach_image_texture(mat, bsdf, "textures/walls/brick_wall_diff_2k.jpg")

    elif mat_type in ["wall_wood", "wood_panel"]:
        # Modern wood panel / slats wall from wall assets
        wall_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = wall_color
        bsdf.inputs["Roughness"].default_value = 0.50
        _attach_image_texture(mat, bsdf, "textures/walls/wood_panel_diff_2k.jpg")

    elif mat_type in ["wall_painted", "painted_plaster"]:
        # Clean painted plaster wall from wall assets
        wall_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = wall_color
        bsdf.inputs["Roughness"].default_value = 0.80
        _attach_image_texture(mat, bsdf, "textures/walls/painted_plaster_wall_diff_2k.jpg")

    else:
        # High-end tactile plaster wall from wall assets
        wall_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = wall_color
        bsdf.inputs["Roughness"].default_value = 0.82
        if "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.25
        _attach_image_texture(mat, bsdf, "textures/walls/plaster_wall_diff_2k.jpg")

    return mat


