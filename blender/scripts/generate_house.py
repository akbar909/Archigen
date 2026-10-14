"""
generate_house.py
=================
Hyperrealistic ArchGen Headless 3D Architectural House Generator in Blender.

Procedurally constructs:
- Dual-tier beveled architectural foundation & slatted outdoor patio deck
- Room floor slabs with procedural PBR materials (wood, marble, tile)
- Cutaway/full-height walls with architectural baseboards and top caps
- Boolean door and window cutouts with aluminum/timber frames & glass panes
- Multi-room high-detail 3D furniture placement via catalog lookup
- Soft physical sun lighting & ambient fill
- Web-optimized GLB export for Three.js
"""

import os
import sys
import json
import math
import argparse
from typing import Dict, Any, List, Optional, Tuple

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None
    mathutils = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLENDER_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

try:
    import import_asset
    import place_furniture
    import export_glb
except ImportError as err:
    print(f"[WARN] Failed to import helper modules: {err}")


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


# ─── Foundation & Landscape Grounds ───────────────────────────────────────────

def build_foundation_and_patio(rooms: List[Dict[str, Any]]) -> List[Any]:
    """
    Creates the ground-floor foundation and landscape.  Patios/driveways are
    generated only from explicit canonical exterior definitions.
    """
    if bpy is None or not rooms:
        return []

    created_objs = []
    min_x, max_x = float("inf"), float("-inf")
    min_y, max_y = float("inf"), float("-inf")

    for r in rooms:
        b = r.get("bounds", {})
        x, y = b.get("x", 0.0), b.get("y", 0.0)
        w, d = b.get("width", 4.0), b.get("depth", 4.0)
        min_x = min(min_x, x)
        max_x = max(max_x, x + w)
        min_y = min(min_y, y)
        max_y = max(max_y, y + d)

    hw = max_x - min_x
    hd = max_y - min_y
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    concrete_mat = create_pbr_material("mat_foundation_podium", "concrete")
    grass_mat = create_pbr_material("mat_landscape_grass", "grass")

    # 0. Surrounding Lush Garden Lawn (elevation: top at -0.22 to prevent z-fighting)
    lawn_w = max(hw * 2.2, 50.0)
    lawn_d = max(hd * 2.2, 50.0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, -0.30))
    lawn = bpy.context.active_object
    lawn.name = "Lush_Garden_Ground"
    lawn.scale = (lawn_w, lawn_d, 0.16)
    if grass_mat:
        lawn.data.materials.append(grass_mat)
    apply_box_uv_mapping(lawn, tile_meters=3.5)
    created_objs.append(lawn)

    # 1. Main Foundation Slab (podium top at -0.02)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, -0.12))
    base = bpy.context.active_object
    base.name = "Architectural_Foundation_Podium"
    base.scale = (hw + 1.8, hd + 1.8, 0.20)
    if concrete_mat:
        base.data.materials.append(concrete_mat)
    apply_box_uv_mapping(base, tile_meters=1.5)
    created_objs.append(base)

    return created_objs


# ─── Room Floors ──────────────────────────────────────────────────────────────

def build_floor_slab(rooms: List[Dict[str, Any]], slab_thickness: float = 0.2) -> List[Any]:
    """Procedurally builds room floor slabs with customized PBR materials and clean UV tiling."""
    if bpy is None:
        return []

    floor_objects = []
    for room in rooms:
        bounds = room.get("bounds", {})
        x, y = bounds.get("x", 0.0), bounds.get("y", 0.0)
        w, d = bounds.get("width", 4.0), bounds.get("depth", 4.0)
        room_type = str(room.get("type", "general")).lower()

        cx = x + (w / 2.0)
        cy = y + (d / 2.0)
        elevation = float(bounds.get("z", room.get("elevation", 0.0)))
        # Canonical Z is the finished floor; slab mass extends below it.
        cz = elevation - slab_thickness / 2.0

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
        slab = bpy.context.active_object
        slab.name = f"Floor_L{room.get('floor_level', 0)}_{room.get('id', 'room')}"
        slab.scale = (w, d, slab_thickness)
        slab["archgen_room_id"] = room.get("id", "")
        slab["archgen_floor_level"] = int(room.get("floor_level", 0))

        flooring = room.get("flooring", {})
        pattern = str(flooring.get("material", "")).lower()
        color = flooring.get("color", [0.8, 0.75, 0.7])

        if "tile" in pattern or "mosaic" in pattern or "bath" in room_type or "kitchen" in room_type or "toilet" in room_type:
            mat = create_pbr_material("mat_floor_tile_shared", "tile", color)
            tile_scale = 1.2
        elif "marble" in pattern or "dining" in room_type or "foyer" in room_type:
            mat = create_pbr_material("mat_floor_marble_shared", "marble", color)
            tile_scale = 1.5
        else:
            mat = create_pbr_material("mat_floor_wood_shared", "wood", color)
            tile_scale = 1.5

        if mat:
            slab.data.materials.append(mat)

        apply_box_uv_mapping(slab, tile_meters=tile_scale)
        floor_objects.append(slab)

    return floor_objects


def build_walls_from_network(
    walls: List[Dict[str, Any]], rooms: List[Dict[str, Any]], wall_height: float = 2.8,
    default_thickness: float = 0.20,
) -> List[Any]:
    """Build the approved wall network exactly once; never infer it from rooms."""
    if bpy is None:
        return []
    room_map = {str(room.get("id")): room for room in rooms}
    default_mat = create_pbr_material("mat_architectural_wall", "wall", [0.93, 0.91, 0.88], roughness=0.82)
    result = []
    for index, wall_data in enumerate(walls):
        start, end = wall_data.get("start", {}), wall_data.get("end", {})
        x1, y1 = float(start.get("x", 0.0)), float(start.get("y", 0.0))
        x2, y2 = float(end.get("x", 0.0)), float(end.get("y", 0.0))
        base_z = float(start.get("z", wall_data.get("position", {}).get("z", 0.0)))
        length = math.hypot(x2 - x1, y2 - y1)
        if length <= 0.01:
            print(f"[ERROR] Skipping zero-length canonical wall '{wall_data.get('id')}'.")
            continue
        thickness = float(wall_data.get("thickness", default_thickness))
        height = min(float(wall_data.get("height", wall_height)), wall_height)
        horizontal = abs(x2 - x1) >= abs(y2 - y1)
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=((x1 + x2) / 2.0, (y1 + y2) / 2.0, base_z + height / 2.0),
        )
        wall = bpy.context.active_object
        wall_id = str(wall_data.get("id") or f"wall_{index + 1:03d}")
        level = int(wall_data.get("floor_level", round(base_z / max(wall_height, 0.1))))
        wall.name = f"Wall_L{level}_{wall_id}"
        wall.scale = (length, thickness, height) if horizontal else (thickness, length, height)
        wall["archgen_wall_id"] = wall_id
        wall["archgen_floor_level"] = level
        wall["archgen_connected_rooms"] = ",".join(str(v) for v in wall_data.get("connected_rooms", []))
        wall["archgen_wall_vertical"] = not horizontal
        wall["archgen_wall_length"] = length
        wall["archgen_wall_thickness"] = thickness
        wall["archgen_wall_height"] = height
        wall["archgen_wall_base_z"] = base_z

        connected = wall_data.get("connected_rooms", [])
        target_room = room_map.get(str(connected[0])) if connected else None
        cfg = (target_room or {}).get("walls", {})
        pattern, color = str(cfg.get("pattern", "")).lower(), cfg.get("color")
        if "brick" in pattern: material = create_pbr_material("mat_wall_brick_shared", "wall_brick", color)
        elif any(token in pattern for token in ("wood", "slat", "panel")): material = create_pbr_material("mat_wall_wood_shared", "wall_wood", color)
        elif "paint" in pattern: material = create_pbr_material("mat_wall_painted_shared", "wall_painted", color)
        else: material = default_mat
        if material:
            wall.data.materials.append(material)
        apply_box_uv_mapping(wall, tile_meters=1.8)
        result.append(wall)
    return result


# ─── Walls with Baseboards & Dollhouse Caps ────────────────────────────────────

def build_walls(
    rooms: List[Dict[str, Any]],
    wall_height: float = 2.8,
    wall_thickness: float = 0.20,
    add_baseboards: bool = False
) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """
    Constructs clean perimeter and partition walls for all rooms.
    Eliminates corner overlap to prevent Z-fighting and blinking.
    Automatically generates interior doorways between adjacent rooms so the home is connected.
    """
    if bpy is None or not rooms:
        return [], []

    wall_objects = []
    auto_doors = []
    wall_mat = create_pbr_material("mat_architectural_wall", "wall", [0.93, 0.91, 0.88], roughness=0.82)

    # Collect proposed wall segments with non-overlapping corners
    raw_wall_segments = []
    for room in rooms:
        bounds = room.get("bounds", {})
        rx, ry = bounds.get("x", 0.0), bounds.get("y", 0.0)
        rw, rd = bounds.get("width", 4.0), bounds.get("depth", 4.0)
        room_id = room.get("id", "room")

        # North & South run full width rw
        # East & West run strictly BETWEEN North & South to eliminate corner overlap and blinking
        inner_d = max(rd - (2.0 * wall_thickness), 0.20)
        segments = [
            # South wall (y min)
            (rx + rw / 2.0, ry + wall_thickness / 2.0, rw, wall_thickness, 0, room_id, rx, ry, rw, rd),
            # North wall (y max)
            (rx + rw / 2.0, ry + rd - wall_thickness / 2.0, rw, wall_thickness, 1, room_id, rx, ry, rw, rd),
            # West wall (x min)
            (rx + wall_thickness / 2.0, ry + rd / 2.0, wall_thickness, inner_d, 2, room_id, rx, ry, rw, rd),
            # East wall (x max)
            (rx + rw - wall_thickness / 2.0, ry + rd / 2.0, wall_thickness, inner_d, 3, room_id, rx, ry, rw, rd),
        ]
        raw_wall_segments.extend(segments)

    # Deduplicate shared partition walls between adjacent rooms & record connecting doorways
    deduped_segments = []
    connected_pairs = set()

    for seg in raw_wall_segments:
        wx, wy, sx, sy, sidx, room_id, rx, ry, rw, rd = seg
        is_duplicate = False

        for existing in deduped_segments:
            ex, ey, esx, esy, _, e_room_id, erx, ery, erw, erd = existing
            is_same_orientation = (sx > sy and esx > esy) or (sx <= sy and esx <= esy)
            if is_same_orientation:
                dist = math.hypot(wx - ex, wy - ey)
                if dist < wall_thickness * 1.5:
                    is_duplicate = True
                    pair_key = tuple(sorted([room_id, e_room_id]))
                    if pair_key not in connected_pairs and room_id != e_room_id:
                        connected_pairs.add(pair_key)
                        # Add an automatic architectural doorway between the two touching rooms
                        mid_x = round((wx + ex) / 2.0, 2)
                        mid_y = round((wy + ey) / 2.0, 2)
                        is_vert = (sx <= sy)
                        auto_doors.append({
                            "id": f"door_auto_{room_id}_{e_room_id}",
                            "type": "interior_door",
                            "position": [mid_x, mid_y, 0.0],
                            "width": 1.0,
                            "height": 2.1,
                            "wall": "left" if is_vert else "front",
                        })
                    break

        if not is_duplicate:
            deduped_segments.append(seg)

    room_map = {r.get("id"): r for r in rooms}

    # Construct clean single partition walls with proper elevations and UV tiling
    for seg in deduped_segments:
        wx, wy, sx, sy, sidx, room_id, rx, ry, rw, rd = seg
        # Wall base sits right on top of floor slab at +0.01
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, 0.01 + wall_height / 2.0))
        wall = bpy.context.active_object
        wall.name = f"wall_{room_id}_{sidx}"
        wall.scale = (sx, sy, wall_height)
        wall["archgen_wall_vertical"] = sx <= sy
        wall["archgen_wall_length"] = sy if sx <= sy else sx
        wall["archgen_wall_thickness"] = sx if sx <= sy else sy
        wall["archgen_wall_height"] = wall_height
        wall["archgen_wall_base_z"] = 0.01

        target_room = room_map.get(room_id, {})
        wall_cfg = target_room.get("walls", {})
        pattern = str(wall_cfg.get("pattern", "")).lower()
        w_color = wall_cfg.get("color")

        if "brick" in pattern:
            r_wall_mat = create_pbr_material("mat_wall_brick_shared", "wall_brick", w_color)
        elif "wood" in pattern or "slat" in pattern or "panel" in pattern:
            r_wall_mat = create_pbr_material("mat_wall_wood_shared", "wall_wood", w_color)
        elif "paint" in pattern:
            r_wall_mat = create_pbr_material("mat_wall_painted_shared", "wall_painted", w_color)
        else:
            r_wall_mat = wall_mat

        if r_wall_mat:
            wall.data.materials.append(r_wall_mat)

        apply_box_uv_mapping(wall, tile_meters=1.8)
        wall_objects.append(wall)

    return wall_objects, auto_doors


# ─── Door & Window Boolean Openings & Frames ──────────────────────────────────

def _safe_opening_coords(item: Dict[str, Any], default_z: float = 0.0) -> Tuple[float, float, float, float, float]:
    """Safely extracts (x, y, z, width, height) whether item uses list or dict coordinates."""
    pos = item.get("position", [0.0, 0.0, default_z])
    if isinstance(pos, (list, tuple)):
        x = float(pos[0]) if len(pos) > 0 else 0.0
        y = float(pos[1]) if len(pos) > 1 else 0.0
        z = float(pos[2]) if len(pos) > 2 else default_z
    elif isinstance(pos, dict):
        x = float(pos.get("x", 0.0))
        if "y" in pos and "z" in pos:
            # If layout engine coordinates (y is depth, z is elevation <= 1.0)
            if float(pos.get("z", 0.0)) <= 1.0 and float(pos.get("y", 0.0)) > 1.0:
                y = float(pos.get("y", 0.0))
                z = float(pos.get("z", default_z))
            else:
                y = float(pos.get("z", 0.0))
                z = float(pos.get("y", default_z))
        elif "y" in pos:
            y = float(pos.get("y", 0.0))
            z = default_z
        else:
            y = float(pos.get("z", 0.0))
            z = default_z
    else:
        x, y, z = 0.0, 0.0, default_z

    dim = item.get("dimensions", {})
    w = float(item.get("width") or (dim.get("w") if isinstance(dim, dict) else None) or 1.0)
    h = float(item.get("height") or (dim.get("h") if isinstance(dim, dict) else None) or 2.1)
    return x, y, z, w, h


def _is_opening_vertical(ox: float, oy: float, wall_hint: Optional[str], wall_objects: List[Any]) -> bool:
    """
    Determines if an opening sits on a vertical wall (runs along Y axis) or horizontal wall (runs along X axis).
    Uses explicit wall orientation hint first, then resolves using closest wall geometry based on perpendicular distance.
    """
    if wall_hint and isinstance(wall_hint, str):
        hint = wall_hint.lower().strip()
        if hint in ("left", "right", "west", "east"):
            return True
        if hint in ("front", "back", "north", "south"):
            return False

    closest_wall = None
    min_dist = float("inf")
    for wall in wall_objects:
        # Distance from opening (ox, oy) to the wall's rectangular bounding box
        vertical = bool(wall.get("archgen_wall_vertical", wall.scale.y > wall.scale.x))
        length = float(wall.get("archgen_wall_length", wall.scale.y if vertical else wall.scale.x))
        thickness = float(wall.get("archgen_wall_thickness", wall.scale.x if vertical else wall.scale.y))
        half_sx = (thickness if vertical else length) / 2.0
        half_sy = (length if vertical else thickness) / 2.0
        dx = max(wall.location.x - half_sx - ox, 0.0, ox - (wall.location.x + half_sx))
        dy = max(wall.location.y - half_sy - oy, 0.0, oy - (wall.location.y + half_sy))
        dist = math.hypot(dx, dy)
        if dist < min_dist:
            min_dist = dist
            closest_wall = wall

    if closest_wall:
        # If wall length along Y is greater than along X, it is a vertical wall
        return bool(closest_wall.get("archgen_wall_vertical", closest_wall.scale.y > closest_wall.scale.x))
    return False


def _wall_is_vertical(wall: Any) -> bool:
    return bool(wall.get("archgen_wall_vertical", wall.scale.y > wall.scale.x))


def _wall_half_extents(wall: Any) -> Tuple[float, float]:
    vertical = _wall_is_vertical(wall)
    length = float(wall.get("archgen_wall_length", wall.scale.y if vertical else wall.scale.x))
    thickness = float(wall.get("archgen_wall_thickness", wall.scale.x if vertical else wall.scale.y))
    return (
        (thickness if vertical else length) / 2.0,
        (length if vertical else thickness) / 2.0,
    )


def _try_import_door_model(
    dx: float, dy: float, dz: float, dw: float, dh: float, idx: int, is_vertical: bool = False
) -> Optional[Any]:
    """Attempts to import a real 3D door GLB model into the opening cutout, rotated and scaled to match wall."""
    door_candidates = [
        os.path.join(BLENDER_ROOT, "assets", "doors", "door_standard.glb"),
        os.path.join(BLENDER_ROOT, "assets", "doors", "door_standard_02.glb"),
        os.path.join(BLENDER_ROOT, "assets", "doors", "door_standard_03.glb"),
    ]
    for p in door_candidates:
        if os.path.isfile(p):
            try:
                door_obj = import_asset.load_model(p, name_prefix=f"door_asset_{idx}")
                cur_w, cur_d, cur_h = import_asset.get_bounding_dimensions(door_obj)
                cur_w = max(cur_w, 0.5)
                cur_d = max(cur_d, 0.05)
                cur_h = max(cur_h, 1.0)

                target_h = min(dh, 2.3)
                wall_t = 0.20

                door_obj.location = (dx, dy, dz)
                if is_vertical:
                    door_obj.rotation_euler = (0.0, 0.0, math.radians(90))
                    # Normalize in asset-local axes first (X=opening width,
                    # Y=wall depth), then rotate the complete normalized asset.
                    door_obj.scale = (dw / cur_w, wall_t / cur_d, target_h / cur_h)
                else:
                    door_obj.rotation_euler = (0.0, 0.0, 0.0)
                    door_obj.scale = (dw / cur_w, wall_t / cur_d, target_h / cur_h)
                return door_obj
            except Exception as e:
                print(f"[WARN] Could not load door model {p}: {e}")
    return None


def _try_import_window_model(
    wx: float, wy: float, wz: float, ww: float, wh: float, idx: int, is_vertical: bool = False
) -> Optional[Any]:
    """Attempts to import a real 3D window GLB model into the opening cutout, rotated and scaled to match wall."""
    win_candidates = [
        os.path.join(BLENDER_ROOT, "assets", "windows", "window_standard_01.glb"),
        os.path.join(BLENDER_ROOT, "assets", "windows", "window_standard_02.glb"),
        os.path.join(BLENDER_ROOT, "assets", "windows", "window_standard_03.glb"),
    ]
    for p in win_candidates:
        if os.path.isfile(p):
            try:
                win_obj = import_asset.load_model(p, name_prefix=f"win_asset_{idx}")
                cur_w, cur_d, cur_h = import_asset.get_bounding_dimensions(win_obj)
                cur_w = max(cur_w, 0.5)
                cur_d = max(cur_d, 0.05)
                cur_h = max(cur_h, 0.5)

                wall_t = 0.20

                win_obj.location = (wx, wy, wz - wh / 2.0)
                if is_vertical:
                    win_obj.rotation_euler = (0.0, 0.0, math.radians(90))
                    win_obj.scale = (ww / cur_w, wall_t / cur_d, wh / cur_h)
                else:
                    win_obj.rotation_euler = (0.0, 0.0, 0.0)
                    win_obj.scale = (ww / cur_w, wall_t / cur_d, wh / cur_h)
                return win_obj
            except Exception as e:
                print(f"[WARN] Could not load window model {p}: {e}")
    return None


def _try_import_gate_model(
    gx: float, gy: float, gz: float, gw: float, gh: float
) -> Optional[Any]:
    """Attempts to import a real 3D gate GLB model into the entrance gate cutout."""
    gate_candidates = [
        os.path.join(BLENDER_ROOT, "assets", "architecture", "doors", "exterior", "Gate.glb"),
        os.path.join(BLENDER_ROOT, "assets", "architecture", "doors", "exterior", "gate.glb"),
        os.path.join(BLENDER_ROOT, "assets", "doors", "exterior", "Gate.glb"),
        os.path.join(BLENDER_ROOT, "assets", "doors", "Gate.glb"),
        os.path.join(BLENDER_ROOT, "assets", "doors", "gate.glb"),
    ]
    for p in gate_candidates:
        local_p = p
        if not os.path.isfile(local_p):
            try:
                import s3_asset_resolver
                norm_rel = os.path.relpath(local_p, BLENDER_ROOT).replace("\\", "/")
                res_path = s3_asset_resolver.download_asset_if_missing(norm_rel, base_blender_dir=BLENDER_ROOT)
                if res_path and os.path.isfile(res_path) and os.path.getsize(res_path) > 0:
                    local_p = res_path
            except Exception as e:
                print(f"[S3Resolver] Download failed for {local_p}: {e}")

        if os.path.isfile(local_p) and os.path.getsize(local_p) > 0:
            try:
                gate_obj = import_asset.load_model(local_p, name_prefix="Exterior_Entrance_Gate")
                cur_w, cur_d, cur_h = import_asset.get_bounding_dimensions(gate_obj)
                cur_w = max(cur_w, 0.5)
                cur_d = max(cur_d, 0.05)
                cur_h = max(cur_h, 0.5)

                scale_x = gw / cur_w
                scale_z = gh / cur_h
                target_d = min(0.20, cur_d * min(scale_x, scale_z))
                scale_y = max(target_d / cur_d, 0.1)

                gate_obj.location = (gx, gy, gz)
                # Gate.glb is authored vertically inverted (decorative spikes
                # point downward). Flip the asset around its horizontal axis,
                # then re-seat it from evaluated geometry instead of trusting
                # its source pivot.
                gate_obj.rotation_euler = (math.radians(180.0), 0.0, 0.0)
                gate_obj.scale = (scale_x, scale_y, scale_z)
                bpy.context.view_layer.update()
                meshes = [obj for obj in gate_obj.children_recursive if obj.type == "MESH"]
                min_z = min(
                    (obj.matrix_world @ mathutils.Vector(corner)).z
                    for obj in meshes
                    for corner in obj.bound_box
                )
                gate_obj.location.z += gz - min_z
                bpy.context.view_layer.update()
                gate_obj["archgen_exterior_feature"] = "main_gate"
                gate_obj["archgen_axis_corrected"] = True
                gate_obj["archgen_target_width"] = gw
                gate_obj["archgen_target_height"] = gh
                print(f"[ARCHGEN] Loaded 3D entrance gate model from {local_p} (scale={gate_obj.scale})")
                return gate_obj
            except Exception as e:
                print(f"[WARN] Could not load gate model {local_p}: {e}")
    return None


def _create_garage_door_model(
    dx: float, dy: float, dz: float, dw: float, dh: float, is_vertical: bool
) -> Any:
    """Build a correctly oriented sectional garage shutter, not a stretched room door."""
    root = bpy.data.objects.new("Garage_Rollup_Door", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (dx, dy, dz)
    material = create_pbr_material("mat_garage_door", "metal", [0.18, 0.20, 0.22], roughness=0.48)
    sections = 8
    gap = 0.018
    section_h = max(0.05, dh / sections - gap)
    for index in range(sections):
        local_z = (index + 0.5) * (dh / sections)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
        panel = bpy.context.active_object
        panel.name = f"Garage_Rollup_Panel_{index + 1:02d}"
        panel.parent = root
        panel.location = (0.0, 0.0, local_z)
        panel.scale = (0.10, dw, section_h) if is_vertical else (dw, 0.10, section_h)
        if material:
            panel.data.materials.append(material)
        apply_box_uv_mapping(panel, tile_meters=1.0)
    return root


def _create_hinged_door_model(
    dx: float,
    dy: float,
    dz: float,
    dw: float,
    dh: float,
    is_vertical: bool,
    door_type: str,
    swing: str,
) -> Any:
    """Build a clean frame and an open leaf without relying on asset pivots."""
    root = bpy.data.objects.new("Architectural_Hinged_Door", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (dx, dy, dz)
    root.rotation_euler = (0.0, 0.0, math.radians(90.0) if is_vertical else 0.0)
    root["archgen_procedural_door"] = True

    is_main = door_type == "main_entrance"
    frame_mat = create_pbr_material(
        "mat_main_door_frame" if is_main else "mat_interior_door_frame",
        "wood",
        [0.22, 0.12, 0.065] if is_main else [0.48, 0.34, 0.22],
        roughness=0.48,
    )
    leaf_mat = create_pbr_material(
        "mat_main_door_leaf" if is_main else "mat_interior_door_leaf",
        "wood",
        [0.30, 0.16, 0.08] if is_main else [0.58, 0.42, 0.27],
        roughness=0.42,
    )
    frame_width = min(0.09, max(0.055, dw * 0.08))
    frame_depth = 0.16

    def add_part(name: str, location: Tuple[float, float, float], dimensions: Tuple[float, float, float], material: Any) -> Any:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
        part = bpy.context.active_object
        part.name = name
        part.parent = root
        part.location = location
        part.scale = dimensions
        if material:
            part.data.materials.append(material)
        apply_box_uv_mapping(part, tile_meters=0.8)
        return part

    add_part(
        "DoorFrame_Left_Jamb",
        (-dw / 2.0 + frame_width / 2.0, 0.0, dh / 2.0),
        (frame_width, frame_depth, dh),
        frame_mat,
    )
    add_part(
        "DoorFrame_Right_Jamb",
        (dw / 2.0 - frame_width / 2.0, 0.0, dh / 2.0),
        (frame_width, frame_depth, dh),
        frame_mat,
    )
    add_part(
        "DoorFrame_Header",
        (0.0, 0.0, dh - frame_width / 2.0),
        (dw, frame_depth, frame_width),
        frame_mat,
    )

    # Keep the leaf visibly open so the exported model agrees with the 2D
    # circulation graph and walkthrough route. The hinge empty provides a real
    # pivot instead of rotating a centre-origin GLB through the wall.
    hinge_on_right = "right" in str(swing or "").lower()
    hinge_x = (dw / 2.0 - frame_width) if hinge_on_right else (-dw / 2.0 + frame_width)
    leaf_width = max(0.45, dw - frame_width * 2.0)
    leaf_height = max(0.8, dh - frame_width)
    hinge = bpy.data.objects.new("DoorLeaf_Hinge", None)
    bpy.context.scene.collection.objects.link(hinge)
    hinge.parent = root
    hinge.location = (hinge_x, 0.0, 0.0)
    hinge.rotation_euler = (0.0, 0.0, math.radians(-82.0 if hinge_on_right else 82.0))
    leaf_x = -leaf_width / 2.0 if hinge_on_right else leaf_width / 2.0
    leaf = add_part(
        "DoorLeaf_Open",
        (0.0, 0.0, leaf_height / 2.0),
        (leaf_width, 0.045, leaf_height),
        leaf_mat,
    )
    leaf.parent = hinge
    leaf.location = (leaf_x, 0.0, leaf_height / 2.0)
    leaf["archgen_open_door_leaf"] = True
    bpy.context.view_layer.update()
    return root


def apply_openings(
    openings: Dict[str, Any],
    wall_objects: List[Any],
    wall_height: float = 2.8
) -> List[Any]:
    """
    Carves clean boolean openings for doors and windows through walls,
    correctly oriented along horizontal (X) or vertical (Y) walls,
    and inserts 3D door/window models or architectural frames and glass panes.
    """
    if bpy is None or not wall_objects:
        return []

    created_frames = []
    metal_mat = create_pbr_material("mat_casing_aluminum", "metal")
    glass_mat = create_pbr_material("mat_window_glass", "glass")
    door_mat = create_pbr_material("mat_door_timber", "wood", [0.45, 0.32, 0.22])

    doors = openings.get("doors", [])
    windows = openings.get("windows", [])
    opening_errors = []

    def target_wall(item, ox, oy):
        wall_id = str(item.get("wall_id") or "")
        if wall_id:
            for candidate in wall_objects:
                if str(candidate.get("archgen_wall_id", "")) == wall_id:
                    return candidate
        vertical = _is_opening_vertical(ox, oy, item.get("wall_side") or item.get("wall"), wall_objects)
        compatible = [wall for wall in wall_objects if _wall_is_vertical(wall) == vertical]
        if not compatible:
            return None
        def distance(wall):
            hx, hy = _wall_half_extents(wall)
            dx = max(wall.location.x - hx - ox, 0.0, ox - wall.location.x - hx)
            dy = max(wall.location.y - hy - oy, 0.0, oy - wall.location.y - hy)
            return math.hypot(dx, dy)
        closest = min(compatible, key=distance)
        return closest if distance(closest) <= 0.25 else None

    # 1. Process Doors
    for idx, d_item in enumerate(doors):
        try:
            dx, dy, dz, dw, raw_dh = _safe_opening_coords(d_item, default_z=0.0)
            dh = min(raw_dh, wall_height)
            wall = target_wall(d_item, dx, dy)
            if wall is None:
                raise ValueError(f"door '{d_item.get('id')}' has no matching wall")
            is_vert = _wall_is_vertical(wall)
            level = int(wall.get("archgen_floor_level", 0))
            opening_id = str(d_item.get("id") or idx)
            wall_base = float(wall.get("archgen_wall_base_z", wall.location.z - wall.scale.z / 2.0))
            dz = max(dz, wall_base)

            # Create Boolean Cutter Box (oriented to slice through wall cleanly)
            cutter_h = dh + 0.10
            cutter_z = dz + (dh / 2.0)
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, cutter_z))
            cutter = bpy.context.active_object
            cutter.name = f"_boolean_cutter_door_{idx}"
            if is_vert:
                cutter.scale = (0.80, dw, cutter_h)
            else:
                cutter.scale = (dw, 0.80, cutter_h)

            # Apply the opening only to its canonical host wall.
            bool_mod = wall.modifiers.new(name=f"Bool_Door_{idx}", type='BOOLEAN')
            bool_mod.operation = 'DIFFERENCE'
            bool_mod.object = cutter
            bool_mod.solver = 'EXACT'

            cutter.display_type = 'WIRE'
            cutter.hide_render = True

            # Use deterministic geometry for wall-hosted doors. Imported door
            # hierarchies have inconsistent pivots and loose trim meshes, which
            # previously produced floating strips and distorted repeated doors.
            door_type = str(d_item.get("type", "")).lower()
            if door_type == "garage_door":
                door_asset = _create_garage_door_model(dx, dy, dz, dw, dh, is_vertical=is_vert)
            else:
                door_asset = _create_hinged_door_model(
                    dx, dy, dz, dw, dh,
                    is_vertical=is_vert,
                    door_type=door_type,
                    swing=str(d_item.get("swing", "inward_right")),
                )
            if door_asset:
                door_asset.name = f"Door_L{level}_{opening_id}"
                door_asset["archgen_opening_id"] = opening_id
                door_asset["archgen_opening_kind"] = "door"
                door_asset["archgen_opening_width"] = dw
                door_asset["archgen_opening_height"] = dh
                door_asset["archgen_opening_vertical"] = is_vert
                door_asset["archgen_opening_x"] = dx
                door_asset["archgen_opening_y"] = dy
                door_asset["archgen_opening_base_z"] = dz
                created_frames.append(door_asset)
            else:
                # Fallback: Insert Architectural Door Frame
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, dz + dh / 2.0))
                frame = bpy.context.active_object
                frame.name = f"DoorFrame_L{level}_{opening_id}"
                frame["archgen_opening_id"] = opening_id
                frame["archgen_opening_kind"] = "door"
                frame["archgen_opening_width"] = dw
                frame["archgen_opening_height"] = dh
                frame["archgen_opening_vertical"] = is_vert
                frame["archgen_opening_x"] = dx
                frame["archgen_opening_y"] = dy
                frame["archgen_opening_base_z"] = dz
                if is_vert:
                    frame.scale = (0.22, dw + 0.08, dh + 0.04)
                else:
                    frame.scale = (dw + 0.08, 0.22, dh + 0.04)

                if door_mat:
                    frame.data.materials.append(door_mat)

                # Hollow interior of frame
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, dz + (dh - 0.04) / 2.0))
                frame_cutter = bpy.context.active_object
                frame_cutter.name = f"_frame_cutter_{idx}"
                if is_vert:
                    frame_cutter.scale = (0.30, dw - 0.06, dh - 0.04)
                else:
                    frame_cutter.scale = (dw - 0.06, 0.30, dh - 0.04)

                mod = frame.modifiers.new(name="FrameHollow", type='BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object = frame_cutter
                mod.solver = 'EXACT'
                frame_cutter.hide_render = True
                frame_cutter.display_type = 'WIRE'

                created_frames.append(frame)
        except Exception as e:
            print(f"[WARN] Failed to process door {idx}: {e}")
            opening_errors.append(f"door '{d_item.get('id', idx)}': {e}")

    # 2. Process Windows
    for idx, w_item in enumerate(windows):
        try:
            wx, wy, wz, ww, wh = _safe_opening_coords(w_item, default_z=1.0)
            wall = target_wall(w_item, wx, wy)
            if wall is None:
                raise ValueError(f"window '{w_item.get('id')}' has no matching wall")
            is_vert = _wall_is_vertical(wall)
            level = int(wall.get("archgen_floor_level", 0))
            opening_id = str(w_item.get("id") or idx)
            wall_base = float(wall.get("archgen_wall_base_z", wall.location.z - wall.scale.z / 2.0))
            wall_top = wall_base + float(wall.get("archgen_wall_height", wall.scale.z))
            actual_z = min(max(wz + (wh / 2.0), wall_base + wh / 2.0), wall_top - wh / 2.0)
            actual_base_z = actual_z - wh / 2.0

            # Create Boolean Cutter Box
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
            cutter = bpy.context.active_object
            cutter.name = f"_boolean_cutter_win_{idx}"
            if is_vert:
                cutter.scale = (0.60, ww, wh)
            else:
                cutter.scale = (ww, 0.60, wh)

            bool_mod = wall.modifiers.new(name=f"Bool_Win_{idx}", type='BOOLEAN')
            bool_mod.operation = 'DIFFERENCE'
            bool_mod.object = cutter
            bool_mod.solver = 'EXACT'

            cutter.display_type = 'WIRE'
            cutter.hide_render = True

            # Try to place 3D window model
            win_asset = _try_import_window_model(wx, wy, actual_z, ww, wh, idx, is_vertical=is_vert)
            if win_asset:
                win_asset.name = f"Window_L{level}_{opening_id}"
                win_asset["archgen_opening_id"] = opening_id
                win_asset["archgen_opening_kind"] = "window"
                win_asset["archgen_opening_width"] = ww
                win_asset["archgen_opening_height"] = wh
                win_asset["archgen_opening_vertical"] = is_vert
                win_asset["archgen_opening_x"] = wx
                win_asset["archgen_opening_y"] = wy
                win_asset["archgen_opening_base_z"] = actual_base_z
                created_frames.append(win_asset)
            else:
                # Fallback: Insert Modern Aluminum Window Frame + Double Glazing
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
                win_frame = bpy.context.active_object
                win_frame.name = f"WindowFrame_L{level}_{opening_id}"
                win_frame["archgen_opening_id"] = opening_id
                win_frame["archgen_opening_kind"] = "window"
                win_frame["archgen_opening_width"] = ww
                win_frame["archgen_opening_height"] = wh
                win_frame["archgen_opening_vertical"] = is_vert
                win_frame["archgen_opening_x"] = wx
                win_frame["archgen_opening_y"] = wy
                win_frame["archgen_opening_base_z"] = actual_base_z
                if is_vert:
                    win_frame.scale = (0.22, ww + 0.06, wh + 0.06)
                else:
                    win_frame.scale = (ww + 0.06, 0.22, wh + 0.06)

                if metal_mat:
                    win_frame.data.materials.append(metal_mat)

                # Hollow window frame
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
                wcutter = bpy.context.active_object
                wcutter.name = f"_wframe_cutter_{idx}"
                if is_vert:
                    wcutter.scale = (0.30, ww - 0.08, wh - 0.08)
                else:
                    wcutter.scale = (ww - 0.08, 0.30, wh - 0.08)

                wmod = win_frame.modifiers.new(name="WinHollow", type='BOOLEAN')
                wmod.operation = 'DIFFERENCE'
                wmod.object = wcutter
                wmod.solver = 'EXACT'
                wcutter.hide_render = True
                wcutter.display_type = 'WIRE'

                created_frames.append(win_frame)

                # Insert Double-Glazed Glass Pane
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
                glass = bpy.context.active_object
                glass.name = f"WindowGlass_L{level}_{opening_id}"
                if is_vert:
                    glass.scale = (0.02, ww - 0.08, wh - 0.08)
                else:
                    glass.scale = (ww - 0.08, 0.02, wh - 0.08)

                if glass_mat:
                    glass.data.materials.append(glass_mat)
                # The pane is already in canonical world coordinates. Parenting
                # it to a non-applied, non-uniformly scaled frame can produce a
                # second transform during glTF export and stretch it across the
                # house, so keep it as an independent architectural mesh.
                created_frames.append(glass)
        except Exception as e:
            print(f"[WARN] Failed to process window {idx}: {e}")
            opening_errors.append(f"window '{w_item.get('id', idx)}': {e}")

    if opening_errors:
        raise RuntimeError("Opening generation failed: " + "; ".join(opening_errors))

    return created_frames


# ─── Lighting ─────────────────────────────────────────────────────────────────

def setup_lighting():
    """Adds balanced warm sunlight and soft fill lights without overexposure."""
    if bpy is None:
        return

    # Warm directional sun at 45 degree angle
    bpy.ops.object.light_add(type='SUN', location=(14, -14, 20))
    sun = bpy.context.active_object
    sun.name = "ArchGen_WarmSun"
    sun.data.energy = 1.6
    sun.data.color = (1.0, 0.98, 0.94)  # Warm white sunlight
    sun.rotation_euler = (math.radians(45), math.radians(20), math.radians(45))

    # Soft ambient fill light
    bpy.ops.object.light_add(type='SUN', location=(-12, 12, 16))
    fill = bpy.context.active_object
    fill.name = "ArchGen_SoftFill"
    fill.data.energy = 0.5
    fill.data.color = (0.85, 0.92, 1.0)  # Cool sky reflection
    fill.rotation_euler = (math.radians(-35), math.radians(-15), math.radians(225))


# ─── Multi-Floor Staircases, Intermediate Slabs, Roof & Site ──────────────────

def build_staircase(stair_def: Dict[str, Any], lower_elevation: float = 0.0, upper_elevation: float = 3.0) -> List[Any]:
    """Procedurally constructs 3D staircase mesh connecting lower to upper floor."""
    if bpy is None or not stair_def:
        return []
    pos = stair_def.get("position", {})
    dim = stair_def.get("dimensions", {})
    sx = float(pos.get("x", 0.0))
    sy = float(pos.get("y", 0.0))
    sw = float(dim.get("width", 1.1))
    sd = float(dim.get("depth", 2.8))
    sh = upper_elevation - lower_elevation
    steps_count = int(stair_def.get("steps", 16))
    riser_h = sh / steps_count
    tread_d = sd / steps_count

    wood_mat = create_pbr_material("mat_stair_tread", "wood")
    metal_mat = create_pbr_material("mat_stair_railing", "metal")
    created = []

    for step_i in range(steps_count):
        step_z = lower_elevation + (step_i * riser_h) + (riser_h / 2.0)
        step_y = sy + (step_i * tread_d) + (tread_d / 2.0)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(sx + sw / 2.0, step_y, step_z))
        step_obj = bpy.context.active_object
        step_obj.name = f"stair_step_{step_i+1}"
        step_obj.scale = (sw, tread_d, riser_h)
        if wood_mat:
            step_obj.data.materials.append(wood_mat)
        created.append(step_obj)

    # Handrail along outer side
    rail_z = lower_elevation + sh / 2.0 + 0.9
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(sx + sw - 0.05, sy + sd / 2.0, rail_z))
    rail_obj = bpy.context.active_object
    rail_obj.name = "stair_handrail"
    rail_obj.scale = (0.05, sd, 0.05)
    if metal_mat:
        rail_obj.data.materials.append(metal_mat)
    created.append(rail_obj)

    return created


def build_intermediate_slab(
    rooms: List[Dict[str, Any]],
    stair_def: Optional[Dict[str, Any]] = None,
    elevation: float = 3.0,
    slab_thickness: float = 0.22
) -> List[Any]:
    """Constructs upper floor slab with precise boolean cutout for staircase."""
    if bpy is None or not rooms:
        return []
    min_x = min(float(r.get("bounds", {}).get("x", 0)) for r in rooms)
    max_x = max(float(r.get("bounds", {}).get("x", 0)) + float(r.get("bounds", {}).get("width", 4)) for r in rooms)
    min_y = min(float(r.get("bounds", {}).get("y", 0)) for r in rooms)
    max_y = max(float(r.get("bounds", {}).get("y", 0)) + float(r.get("bounds", {}).get("depth", 4)) for r in rooms)
    w = max_x - min_x
    d = max_y - min_y
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    cz = elevation - slab_thickness / 2.0

    wood_mat = create_pbr_material("mat_intermediate_slab", "wood")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    slab = bpy.context.active_object
    slab.name = f"intermediate_slab_{int(elevation)}"
    slab.scale = (w, d, slab_thickness)
    if wood_mat:
        slab.data.materials.append(wood_mat)

    # Boolean cutout for staircase
    if stair_def:
        spos = stair_def.get("position", {})
        sdim = stair_def.get("dimensions", {})
        stx = float(spos.get("x", 0)) + float(sdim.get("width", 1.1)) / 2.0
        sty = float(spos.get("y", 0)) + float(sdim.get("depth", 2.8)) / 2.0
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(stx, sty, cz))
        cutter = bpy.context.active_object
        cutter.name = "_stair_opening_cutter"
        cutter.scale = (float(sdim.get("width", 1.1)) + 0.1, float(sdim.get("depth", 2.8)) + 0.1, slab_thickness * 2.0)
        mod = slab.modifiers.new(name="StairOpening", type='BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cutter
        mod.solver = 'FAST'
        cutter.hide_render = True
        cutter.display_type = 'WIRE'

    return [slab]


def build_roof_structure(
    bldg_w: float,
    bldg_d: float,
    cx: float,
    cy: float,
    top_elevation: float,
    roof_data: Dict[str, Any]
) -> List[Any]:
    """Procedurally builds roof structure matching building footprint with dedicated naming."""
    if bpy is None:
        return []
    roof_type = str(roof_data.get("type", "parapet")).lower()
    slab_mat = create_pbr_material("mat_roof_slab", "concrete")
    trim_mat = create_pbr_material("mat_roof_trim", "trim")
    created = []

    # Main horizontal roof ceiling slab
    slab_thickness = 0.20
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, top_elevation + slab_thickness / 2.0))
    roof_slab = bpy.context.active_object
    roof_slab.name = "Roof_Main_Structure"
    roof_slab.scale = (bldg_w + 0.4, bldg_d + 0.4, slab_thickness)
    if slab_mat:
        roof_slab.data.materials.append(slab_mat)
    apply_box_uv_mapping(roof_slab, tile_meters=1.5)
    created.append(roof_slab)

    if roof_type in ["parapet", "flat"]:
        # Parapet perimeter wall around the roof deck
        parapet_h = 0.90
        parapet_t = 0.18
        walls_cfg = [
            (cx, cy - bldg_d / 2.0, bldg_w + 0.4, parapet_t),
            (cx, cy + bldg_d / 2.0, bldg_w + 0.4, parapet_t),
            (cx - bldg_w / 2.0, cy, parapet_t, bldg_d + 0.4),
            (cx + bldg_w / 2.0, cy, parapet_t, bldg_d + 0.4),
        ]
        for i, (px, py, pw, pd) in enumerate(walls_cfg):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(px, py, top_elevation + slab_thickness + parapet_h / 2.0))
            pwall = bpy.context.active_object
            pwall.name = f"Roof_Parapet_Wall_{i+1}"
            pwall.scale = (pw, pd, parapet_h)
            if trim_mat:
                pwall.data.materials.append(trim_mat)
            # Keep parapets in world space. A child of the non-uniformly scaled
            # slab exported with the slab transform a second time in glTF,
            # producing the huge floating rectangle that followed Roof ON/OFF.
            apply_box_uv_mapping(pwall, tile_meters=1.5)
            created.append(pwall)
    elif roof_type == "gable":
        gable_h = 1.80
        bpy.ops.mesh.primitive_cone_add(
            vertices=4,
            radius1=(bldg_w + 0.8) / 1.414,
            depth=gable_h,
            location=(cx, cy, top_elevation + slab_thickness + gable_h / 2.0)
        )
        gable = bpy.context.active_object
        gable.name = "Roof_Gable_Structure"
        gable.rotation_euler = (0, 0, math.radians(45))
        if trim_mat:
            gable.data.materials.append(trim_mat)
        apply_box_uv_mapping(gable, tile_meters=1.5)
        created.append(gable)

    return created


def build_exterior_features(
    site_data: Dict[str, Any],
    exterior_data: Dict[str, Any],
    bldg_w: float,
    bldg_d: float,
    cx: float,
    cy: float
) -> List[Any]:
    """Constructs boundary walls, entrance gate, driveway, and landscaping."""
    if bpy is None:
        return []
    plot = site_data.get("plot", {})
    pw = float(plot.get("width", bldg_w + 6.0))
    pd = float(plot.get("depth", bldg_d + 8.0))
    sb = site_data.get("setbacks", {})
    sb_f = float(sb.get("front", 3.5))

    wall_mat = create_pbr_material("mat_boundary_wall", "concrete")
    gate_mat = create_pbr_material("mat_entrance_gate", "metal")
    drive_mat = create_pbr_material("mat_driveway_paving", "concrete")
    created = []

    boundary = exterior_data.get("boundary_wall", {})
    gate_cfg = exterior_data.get("gate", {})
    drive_cfg = exterior_data.get("driveway", {})
    entrance_path_cfg = exterior_data.get("entrance_path", {})
    bw_h = float(boundary.get("height", 1.8))
    bw_t = float(boundary.get("thickness", 0.15))
    plot_cx, plot_cy = pw / 2.0, pd / 2.0
    drive_w = float(drive_cfg.get("width", 3.8))
    drive_d = min(pd, max(0.0, float(drive_cfg.get("depth", sb_f))))
    drive_pos = drive_cfg.get("position", {})
    drive_x0 = max(0.0, min(pw - drive_w, float(drive_pos.get("x", plot_cx - drive_w / 2.0))))
    gate_w = min(float(gate_cfg.get("width", drive_w)), drive_w)
    gate_h = float(gate_cfg.get("height", bw_h))
    gate_x = drive_x0 + drive_w / 2.0

    if boundary.get("enabled", False):
        # The canonical plot origin is south-west (0, 0); boundary geometry must
        # never be centred around the building or it can cross the entire scene.
        b_segments = [
            (0.0, plot_cy, bw_t, pd),
            (pw, plot_cy, bw_t, pd),
            (plot_cx, pd, pw, bw_t),
        ]
        left_width = max(0.0, gate_x - gate_w / 2.0)
        right_start = gate_x + gate_w / 2.0
        right_width = max(0.0, pw - right_start)
        if left_width > 0.05:
            b_segments.append((left_width / 2.0, 0.0, left_width, bw_t))
        if right_width > 0.05:
            b_segments.append((right_start + right_width / 2.0, 0.0, right_width, bw_t))
        for idx, (bx, by, b_w, b_d) in enumerate(b_segments):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, by, bw_h / 2.0))
            bw_obj = bpy.context.active_object
            bw_obj.name = f"Exterior_Boundary_Wall_{idx+1}"
            bw_obj.scale = (b_w, b_d, bw_h)
            if wall_mat:
                bw_obj.data.materials.append(wall_mat)
            apply_box_uv_mapping(bw_obj, tile_meters=1.8)
            created.append(bw_obj)

    if gate_cfg:
        gate_obj = _try_import_gate_model(gate_x, 0.0, 0.0, gate_w, gate_h)
        if gate_obj is None:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(gate_x, 0.0, gate_h / 2.0))
            gate_obj = bpy.context.active_object
            gate_obj.name = "Exterior_Entrance_Gate"
            gate_obj.scale = (gate_w, 0.06, gate_h)
            if gate_mat:
                gate_obj.data.materials.append(gate_mat)
            apply_box_uv_mapping(gate_obj, tile_meters=1.2)
        created.append(gate_obj)

    if drive_cfg and drive_d > 0.05:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(gate_x, drive_d / 2.0, -0.01))
        drive_obj = bpy.context.active_object
        drive_obj.name = "Exterior_Driveway_Paving"
        drive_obj.scale = (drive_w, drive_d, 0.02)
        if drive_mat:
            drive_obj.data.materials.append(drive_mat)
        apply_box_uv_mapping(drive_obj, tile_meters=1.5)
        created.append(drive_obj)

    if entrance_path_cfg:
        start = entrance_path_cfg.get("start", {})
        end = entrance_path_cfg.get("end", {})
        start_x = float(start.get("x", gate_x))
        start_y = float(start.get("y", 0.0))
        end_x = float(end.get("x", start_x))
        end_y = float(end.get("y", sb_f))
        path_w = max(0.8, float(entrance_path_cfg.get("width", 1.2)))
        delta_x, delta_y = end_x - start_x, end_y - start_y
        path_length = math.hypot(delta_x, delta_y)
        if path_length > 0.05:
            bpy.ops.mesh.primitive_cube_add(
                size=1.0,
                location=((start_x + end_x) / 2.0, (start_y + end_y) / 2.0, 0.005),
                rotation=(0.0, 0.0, math.atan2(delta_y, delta_x)),
            )
            path_obj = bpy.context.active_object
            path_obj.name = "Exterior_Main_Entrance_Path"
            path_obj.scale = (path_length, path_w, 0.025)
            if drive_mat:
                path_obj.data.materials.append(drive_mat)
            apply_box_uv_mapping(path_obj, tile_meters=1.0)
            created.append(path_obj)

    return created


def validate_generated_scene(
    layout_data: Dict[str, Any], rooms: List[Dict[str, Any]], expected_ids: List[str]
) -> Dict[str, Any]:
    """Validate the actual Blender scene, including transformed asset bounds."""
    if bpy is None or mathutils is None:
        return {"status": "unavailable", "errors": ["Blender scene is unavailable"], "warnings": []}
    bpy.context.view_layer.update()
    errors, warnings = [], []
    room_map = {str(room.get("id")): room for room in rooms}
    validation_doors = list(layout_data.get("openings", {}).get("doors", []) or layout_data.get("doors", []))
    actual_roots: Dict[str, List[Any]] = {}
    for obj in bpy.context.scene.objects:
        instance_id = obj.get("archgen_instance_id")
        if instance_id is not None:
            actual_roots.setdefault(str(instance_id), []).append(obj)

    missing = [str(item_id) for item_id in expected_ids if str(item_id) not in actual_roots]
    duplicates = [item_id for item_id, values in actual_roots.items() if len(values) != 1]
    if missing:
        errors.append(f"Missing furniture instances: {missing}")
    if duplicates:
        errors.append(f"Duplicate furniture instances: {duplicates}")

    for item_id, roots in actual_roots.items():
        root = roots[0]
        if root.get("archgen_asset_load_failed", False):
            errors.append(f"Furniture '{item_id}' used a missing-asset placeholder: {root.get('archgen_asset_error', '')}")
        room_id = str(root.get("archgen_room_id", ""))
        room = room_map.get(room_id)
        meshes = [obj for obj in [root] + list(root.children_recursive) if obj.type == 'MESH']
        if not room or not meshes:
            errors.append(f"Furniture '{item_id}' has no valid room or mesh geometry.")
            continue
        corners = [obj.matrix_world @ mathutils.Vector(corner) for obj in meshes for corner in obj.bound_box]
        min_x, max_x = min(p.x for p in corners), max(p.x for p in corners)
        min_y, max_y = min(p.y for p in corners), max(p.y for p in corners)
        min_z = min(p.z for p in corners)
        bounds = room.get("bounds", {})
        rx, ry = float(bounds.get("x", 0.0)), float(bounds.get("y", 0.0))
        rw, rd = float(bounds.get("width", 0.0)), float(bounds.get("depth", 0.0))
        tolerance = 0.16
        if min_x < rx - tolerance or max_x > rx + rw + tolerance or min_y < ry - tolerance or max_y > ry + rd + tolerance:
            errors.append(
                f"Furniture '{item_id}' actual bounds [{min_x:.2f},{min_y:.2f}]..[{max_x:.2f},{max_y:.2f}] "
                f"leave room '{room_id}' [{rx:.2f},{ry:.2f}]..[{rx + rw:.2f},{ry + rd:.2f}]."
            )
        if str(room.get("type", "")).lower() != "garage":
            actual_footprint = (min_x, min_y, max_x, max_y)
            for zone in place_furniture._door_clearance_zones(room, validation_doors):
                if place_furniture._rectangles_overlap(actual_footprint, zone, 0.01):
                    errors.append(
                        f"Furniture '{item_id}' blocks a door approach in room '{room_id}': "
                        f"footprint={tuple(round(value, 2) for value in actual_footprint)}, "
                        f"clearance={tuple(round(value, 2) for value in zone)}."
                    )
                    break
        floor_z = float(bounds.get("z", 0.0))
        expected_clearance = float(root.get("archgen_floor_clearance", 0.0))
        expected_bottom = floor_z + expected_clearance
        if min_z < floor_z - 0.002 or abs(min_z - expected_bottom) > 0.004:
            errors.append(
                f"Furniture '{item_id}' is not seated on its finished floor: "
                f"bottom={min_z:.3f}, expected={expected_bottom:.3f}."
            )

    expected_inventory = layout_data.get("expected_inventory", {})
    for kind, key in (("door", "door_ids"), ("window", "window_ids")):
        expected_openings = [str(value) for value in expected_inventory.get(key, [])]
        actual_openings: Dict[str, List[Any]] = {}
        for obj in bpy.context.scene.objects:
            if str(obj.get("archgen_opening_kind", "")) == kind and obj.get("archgen_opening_id") is not None:
                actual_openings.setdefault(str(obj.get("archgen_opening_id")), []).append(obj)
        missing_openings = sorted(set(expected_openings) - set(actual_openings))
        duplicate_openings = sorted(value for value, objects in actual_openings.items() if len(objects) != 1)
        extra_openings = sorted(set(actual_openings) - set(expected_openings))
        if missing_openings or duplicate_openings or extra_openings:
            errors.append(
                f"{kind.title()} inventory mismatch: missing={missing_openings}, duplicates={duplicate_openings}, extra={extra_openings}."
            )
        for opening_id, roots in actual_openings.items():
            if len(roots) != 1:
                continue
            root = roots[0]
            meshes = [obj for obj in [root] + list(root.children_recursive) if obj.type == 'MESH']
            if not meshes:
                errors.append(f"{kind.title()} '{opening_id}' has no mesh geometry.")
                continue
            # Open door leaves intentionally swing perpendicular to the wall;
            # validate the jamb/header against the canonical opening and check
            # the leaf separately through the global site-bounds pass below.
            alignment_meshes = [
                obj for obj in meshes
                if not (kind == "door" and obj.get("archgen_open_door_leaf", False))
            ] or meshes
            points = [
                obj.matrix_world @ mathutils.Vector(corner)
                for obj in alignment_meshes
                for corner in obj.bound_box
            ]
            size_x = max(point.x for point in points) - min(point.x for point in points)
            size_y = max(point.y for point in points) - min(point.y for point in points)
            size_z = max(point.z for point in points) - min(point.z for point in points)
            expected_width = float(root.get("archgen_opening_width", 0.0))
            expected_height = float(root.get("archgen_opening_height", 0.0))
            vertical = bool(root.get("archgen_opening_vertical", False))
            along, through = (size_y, size_x) if vertical else (size_x, size_y)
            if along > expected_width + 0.25 or through > 0.65 or size_z > expected_height + 0.25:
                errors.append(
                    f"{kind.title()} '{opening_id}' geometry exceeds its canonical opening "
                    f"({along:.2f} x {through:.2f} x {size_z:.2f} m)."
                )
            center_x = (min(point.x for point in points) + max(point.x for point in points)) / 2.0
            center_y = (min(point.y for point in points) + max(point.y for point in points)) / 2.0
            min_z = min(point.z for point in points)
            expected_x = float(root.get("archgen_opening_x", center_x))
            expected_y = float(root.get("archgen_opening_y", center_y))
            expected_base_z = float(root.get("archgen_opening_base_z", min_z))
            if (
                abs(center_x - expected_x) > 0.08
                or abs(center_y - expected_y) > 0.08
                or abs(min_z - expected_base_z) > 0.08
            ):
                errors.append(
                    f"{kind.title()} '{opening_id}' is misaligned with its canonical opening "
                    f"(centre={center_x:.2f},{center_y:.2f}, base={min_z:.2f})."
                )

    expected_rooms = {str(room.get("id")) for room in rooms}
    floor_objects: Dict[str, List[Any]] = {}
    for obj in bpy.context.scene.objects:
        if obj.get("archgen_room_id") is not None and obj.name.lower().startswith("floor"):
            floor_objects.setdefault(str(obj.get("archgen_room_id")), []).append(obj)
    floor_rooms = set(floor_objects)
    if expected_rooms != floor_rooms:
        errors.append(f"Floor inventory mismatch: missing={sorted(expected_rooms - floor_rooms)}, extra={sorted(floor_rooms - expected_rooms)}")
    duplicate_floors = sorted(room_id for room_id, objects in floor_objects.items() if len(objects) != 1)
    if duplicate_floors:
        errors.append(f"Duplicate room floor surfaces: {duplicate_floors}")
    for room_id, objects in floor_objects.items():
        room = room_map.get(room_id)
        if not room or len(objects) != 1:
            continue
        obj = objects[0]
        points = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        bounds = room.get("bounds", {})
        expected = (
            float(bounds.get("x", 0.0)), float(bounds.get("y", 0.0)),
            float(bounds.get("x", 0.0)) + float(bounds.get("width", 0.0)),
            float(bounds.get("y", 0.0)) + float(bounds.get("depth", 0.0)),
            float(bounds.get("z", 0.0)),
        )
        actual = (min(p.x for p in points), min(p.y for p in points), max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))
        if any(abs(first - second) > 0.015 for first, second in zip(actual, expected)):
            errors.append(f"Floor '{room_id}' bounds/elevation do not match its canonical room polygon.")

    plot = layout_data.get("site", {}).get("plot", {})
    plot_w, plot_d = float(plot.get("width", 0.0)), float(plot.get("depth", 0.0))
    top = max((float(room.get("bounds", {}).get("z", 0.0)) + float(room.get("height", 3.0)) for room in rooms), default=3.0)
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or obj.name == "Lush_Garden_Ground" or obj.name.startswith("_"):
            continue
        points = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        if any(not math.isfinite(value) for point in points for value in point):
            errors.append(f"Object '{obj.name}' contains non-finite geometry.")
            continue
        if plot_w > 0 and plot_d > 0:
            if (min(p.x for p in points) < -2.0 or max(p.x for p in points) > plot_w + 2.0 or
                    min(p.y for p in points) < -2.0 or max(p.y for p in points) > plot_d + 2.0 or
                    min(p.z for p in points) < -1.0 or max(p.z for p in points) > top + 3.0):
                errors.append(f"Object '{obj.name}' is detached from the canonical site bounds.")

    report = {
        "status": "invalid" if errors else "valid",
        "errors": errors,
        "warnings": warnings,
        "furniture_expected": len(expected_ids),
        "furniture_actual": len(actual_roots),
        "rooms_expected": len(expected_rooms),
        "floors_actual": len(floor_rooms),
    }
    if errors:
        raise RuntimeError("Scene validation failed: " + "; ".join(errors))
    print(
        f"[ARCHGEN] Scene validation PASS: rooms={len(expected_rooms)}, "
        f"furniture={len(actual_roots)}, no detached geometry."
    )
    return report


# ─── Main Generator Pipeline ──────────────────────────────────────────────────

def generate_house_from_layout(
    layout_data: Dict[str, Any],
    output_glb_path: str,
    blender_root: str,
    dollhouse_mode: bool = False
) -> str:
    """Main hyperrealistic generator pipeline supporting multi-floor architecture."""
    print(f"[ARCHGEN] Generating Hyperrealistic 3D Architecture: {layout_data.get('project_name', 'House')}")

    validation = layout_data.get("generation_validation", {})
    critical = validation.get("critical_errors", []) if isinstance(validation, dict) else []
    if critical:
        raise ValueError("Generation blocked by architectural preflight: " + "; ".join(str(v) for v in critical))

    # 1. Clear default scene
    clear_scene()

    # 2. Extract architectural specs
    bldg = layout_data.get("building", {})
    wall_h = 1.45 if dollhouse_mode else float(bldg.get("wall_height", 2.8))
    wall_t = float(bldg.get("wall_thickness", 0.20))
    slab_t = float(bldg.get("slab_thickness", 0.22))
    rooms = layout_data.get("rooms", [])
    wall_network = layout_data.get("walls", [])
    openings = layout_data.get("openings", {})
    floors = layout_data.get("floors", [])
    roof_data = layout_data.get("roof", {})
    exterior_data = layout_data.get("exterior", {})
    site_data = layout_data.get("site", {})

    # Calculate building center and bounds
    if rooms:
        min_x = min(float(r.get("bounds", {}).get("x", 0)) for r in rooms)
        max_x = max(float(r.get("bounds", {}).get("x", 0)) + float(r.get("bounds", {}).get("width", 4)) for r in rooms)
        min_y = min(float(r.get("bounds", {}).get("y", 0)) for r in rooms)
        max_y = max(float(r.get("bounds", {}).get("y", 0)) + float(r.get("bounds", {}).get("depth", 4)) for r in rooms)
        bldg_w = max_x - min_x
        bldg_d = max_y - min_y
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
    else:
        bldg_w, bldg_d, cx, cy = 10.0, 14.0, 5.0, 7.0

    # 3. Foundation Podium & Patio Deck
    print("[ARCHGEN] Building architectural foundation & outdoor patio deck...")
    ground_rooms = [r for r in rooms if int(r.get("floor_level", 0)) == 0]
    build_foundation_and_patio(ground_rooms or rooms)

    # 4. Room Floor Slabs with PBR Materials
    print("[ARCHGEN] Building room floor slabs with PBR shaders...")
    build_floor_slab(rooms, slab_thickness=slab_t)

    # 5. Walls with Baseboard Skirting and Dollhouse Caps
    print(f"[ARCHGEN] Constructing architectural walls (height={wall_h}m)...")
    if wall_network:
        wall_objs = build_walls_from_network(wall_network, rooms, wall_height=wall_h, default_thickness=wall_t)
        auto_doors = []
    else:
        # Backward compatibility for stored legacy projects only.
        wall_objs, auto_doors = build_walls(rooms, wall_height=wall_h, wall_thickness=wall_t, add_baseboards=True)

    # 6. Door and Window Boolean Cutouts & Glazing
    print(f"[ARCHGEN] Carving door and window openings (input doors={len(openings.get('doors', []))}, auto partition doors={len(auto_doors)})...")
    all_doors = list(openings.get("doors", [])) + auto_doors
    combined_openings = {"doors": all_doors, "windows": openings.get("windows", [])}
    apply_openings(combined_openings, wall_objs, wall_height=wall_h)

    # 7. Multi-Floor Staircases & Upper Intermediate Slabs
    stair_def = None
    for fl in floors:
        for s in fl.get("stairs", []):
            stair_def = s
            break
        if stair_def:
            break

    if stair_def and len(floors) > 1:
        print("[ARCHGEN] Building true 3D staircase and upper intermediate floor slab...")
        build_staircase(stair_def, lower_elevation=0.0, upper_elevation=3.0)
        # Upper floors were already emitted from their canonical room polygons;
        # do not add a second bounding-rectangle slab over them.

    # 8. Populate Real 3D Furniture Assets
    print("[ARCHGEN] Populating rooms with catalogued 3D furniture models...")
    catalog = place_furniture.FurnitureCatalog(base_path=blender_root)
    furniture_doors = list(layout_data.get("openings", {}).get("doors", []) or layout_data.get("doors", []))
    total_furniture = 0
    for room in rooms:
        placed = place_furniture.populate_room_furniture(
            room,
            catalog,
            base_blender_dir=blender_root,
            door_openings=furniture_doors,
        )
        total_furniture += len(placed)
    expected_ids = list(layout_data.get("expected_inventory", {}).get("furniture_ids", []))
    actual_ids = {
        str(obj.get("archgen_instance_id")) for obj in bpy.context.scene.objects
        if obj.get("archgen_instance_id") is not None
    }
    missing_ids = [item_id for item_id in expected_ids if str(item_id) not in actual_ids]
    if total_furniture != len(expected_ids) or missing_ids:
        raise RuntimeError(
            f"Furniture inventory mismatch: expected={len(expected_ids)}, placed={total_furniture}, missing={missing_ids}"
        )
    print(f"[ARCHGEN] Verified furniture inventory: {total_furniture}/{len(expected_ids)} pieces.")

    # 9. Roof Generation
    if roof_data:
        top_elev = max(
            (float(r.get("bounds", {}).get("z", 0.0)) + float(r.get("height", wall_h)) for r in rooms),
            default=wall_h,
        )
        print(f"[ARCHGEN] Generating architectural roof ({roof_data.get('type', 'parapet')})...")
        build_roof_structure(bldg_w, bldg_d, cx, cy, top_elev, roof_data)

    # 10. Exterior Features (Boundary Wall, Gate, Driveway)
    if exterior_data:
        print("[ARCHGEN] Generating exterior features (gate, boundary, driveway)...")
        build_exterior_features(site_data, exterior_data, bldg_w, bldg_d, cx, cy)

    # Validate transformed meshes, not merely the input JSON or Blender exit code.
    validate_generated_scene(layout_data, rooms, expected_ids)

    # 11. Physical Lighting
    setup_lighting()

    # 12. Export to High-Quality GLB
    print(f"[ARCHGEN] Exporting scene to: {output_glb_path}")
    final_path = export_glb.export_scene_to_glb(output_glb_path)

    print("[ARCHGEN] Hyperrealistic 3D house generation completed successfully!")
    return final_path


def parse_cli_args():
    """Parses arguments passed after '--' in Blender headless execution."""
    parser = argparse.ArgumentParser(description="ArchGen Headless Hyperrealistic House Generator")
    parser.add_argument("--input", type=str, default="input/sample_house_layout.json",
                        help="Path to the house layout JSON input file.")
    parser.add_argument("--output", type=str, default="output/generated_house.glb",
                        help="Target output GLB file path.")
    parser.add_argument("--dollhouse", action="store_true",
                        help="Use 1.45m dollhouse cutaways instead of full-height 2.8m walls.")
    parser.add_argument("--full-height", action="store_true",
                        help="Use full 2.8m walls (default). Kept for backward compatibility.")

    if "--" in sys.argv:
        args_idx = sys.argv.index("--") + 1
        return parser.parse_args(sys.argv[args_idx:])
    return parser.parse_args([])


def main():
    args = parse_cli_args()
    input_path = args.input if os.path.isabs(args.input) else os.path.join(BLENDER_ROOT, args.input)
    output_path = args.output if os.path.isabs(args.output) else os.path.join(BLENDER_ROOT, args.output)

    if not os.path.exists(input_path):
        print(f"[ERROR] Input layout file does not exist: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        layout_data = json.load(f)

    generate_house_from_layout(
        layout_data=layout_data,
        output_glb_path=output_path,
        blender_root=BLENDER_ROOT,
        dollhouse_mode=bool(args.dollhouse)
    )


if __name__ == "__main__":
    main()
