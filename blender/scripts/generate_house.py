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
        mat.blend_method = 'BLEND'
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
    Creates a dual-tier beveled concrete podium, an outdoor teak patio deck,
    and lush surrounding grass grounds framing the house with distinct Z levels.
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
    deck_mat = create_pbr_material("mat_patio_deck", "deck")
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

    # 2. Outdoor Front Patio Deck (top at 0.00)
    deck_depth = 4.5
    deck_y = min_y - (deck_depth / 2.0) - 0.2
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, deck_y, -0.06))
    deck = bpy.context.active_object
    deck.name = "Outdoor_Teak_Patio_Deck"
    deck.scale = (hw + 1.0, deck_depth, 0.12)
    if deck_mat:
        deck.data.materials.append(deck_mat)
    apply_box_uv_mapping(deck, tile_meters=1.5)
    created_objs.append(deck)

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
        # Floor slab top at +0.01 to ensure zero Z-fighting with foundation
        cz = -slab_thickness / 2.0 + 0.01

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
        slab = bpy.context.active_object
        slab.name = f"floor_{room.get('id', 'room')}"
        slab.scale = (w, d, slab_thickness)

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
        if "z" in pos:
            y = float(pos.get("z", 0.0))
            z = float(pos.get("y", default_z))
        else:
            y = float(pos.get("y", 0.0))
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
        half_sx = wall.scale.x / 2.0
        half_sy = wall.scale.y / 2.0
        dx = max(wall.location.x - half_sx - ox, 0.0, ox - (wall.location.x + half_sx))
        dy = max(wall.location.y - half_sy - oy, 0.0, oy - (wall.location.y + half_sy))
        dist = math.hypot(dx, dy)
        if dist < min_dist:
            min_dist = dist
            closest_wall = wall

    if closest_wall:
        # If wall length along Y is greater than along X, it is a vertical wall
        return closest_wall.scale.y > closest_wall.scale.x
    return False


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

                door_obj.location = (dx, dy, 0.0)
                if is_vertical:
                    door_obj.rotation_euler = (0.0, 0.0, math.radians(90))
                    door_obj.scale = (wall_t / cur_d, dw / cur_w, target_h / cur_h)
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
                    win_obj.scale = (wall_t / cur_d, ww / cur_w, wh / cur_h)
                else:
                    win_obj.rotation_euler = (0.0, 0.0, 0.0)
                    win_obj.scale = (ww / cur_w, wall_t / cur_d, wh / cur_h)
                return win_obj
            except Exception as e:
                print(f"[WARN] Could not load window model {p}: {e}")
    return None


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

    # 1. Process Doors
    for idx, d_item in enumerate(doors):
        try:
            dx, dy, _, dw, raw_dh = _safe_opening_coords(d_item, default_z=0.0)
            dh = min(raw_dh, wall_height)
            is_vert = _is_opening_vertical(dx, dy, d_item.get("wall"), wall_objects)

            # Create Boolean Cutter Box (oriented to slice through wall cleanly)
            cutter_h = dh + 0.10
            cutter_z = (dh / 2.0)
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, cutter_z))
            cutter = bpy.context.active_object
            cutter.name = f"_boolean_cutter_door_{idx}"
            if is_vert:
                cutter.scale = (0.80, dw, cutter_h)
            else:
                cutter.scale = (dw, 0.80, cutter_h)

            # Apply Boolean Difference to all intersecting walls
            for wall in wall_objects:
                dist = math.hypot(wall.location.x - dx, wall.location.y - dy)
                if dist < max(wall.scale.x, wall.scale.y) + 0.8:
                    bool_mod = wall.modifiers.new(name=f"Bool_Door_{idx}", type='BOOLEAN')
                    bool_mod.operation = 'DIFFERENCE'
                    bool_mod.object = cutter
                    bool_mod.solver = 'FAST'

            cutter.display_type = 'WIRE'
            cutter.hide_render = True

            # Try to place 3D door model
            door_asset = _try_import_door_model(dx, dy, 0.0, dw, dh, idx, is_vertical=is_vert)
            if door_asset:
                created_frames.append(door_asset)
            else:
                # Fallback: Insert Architectural Door Frame
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, dh / 2.0))
                frame = bpy.context.active_object
                frame.name = f"door_frame_{idx}"
                if is_vert:
                    frame.scale = (0.22, dw + 0.08, dh + 0.04)
                else:
                    frame.scale = (dw + 0.08, 0.22, dh + 0.04)

                if door_mat:
                    frame.data.materials.append(door_mat)

                # Hollow interior of frame
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, (dh - 0.04) / 2.0))
                frame_cutter = bpy.context.active_object
                frame_cutter.name = f"_frame_cutter_{idx}"
                if is_vert:
                    frame_cutter.scale = (0.30, dw - 0.06, dh - 0.04)
                else:
                    frame_cutter.scale = (dw - 0.06, 0.30, dh - 0.04)

                mod = frame.modifiers.new(name="FrameHollow", type='BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object = frame_cutter
                mod.solver = 'FAST'
                frame_cutter.hide_render = True
                frame_cutter.display_type = 'WIRE'

                created_frames.append(frame)
        except Exception as e:
            print(f"[WARN] Failed to process door {idx}: {e}")

    # 2. Process Windows
    for idx, w_item in enumerate(windows):
        try:
            wx, wy, wz, ww, wh = _safe_opening_coords(w_item, default_z=1.0)
            actual_z = min(wz + (wh / 2.0), wall_height - (wh / 2.0))
            is_vert = _is_opening_vertical(wx, wy, w_item.get("wall"), wall_objects)

            # Create Boolean Cutter Box
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
            cutter = bpy.context.active_object
            cutter.name = f"_boolean_cutter_win_{idx}"
            if is_vert:
                cutter.scale = (0.60, ww, wh)
            else:
                cutter.scale = (ww, 0.60, wh)

            for wall in wall_objects:
                dist = math.hypot(wall.location.x - wx, wall.location.y - wy)
                if dist < max(wall.scale.x, wall.scale.y) + 0.5:
                    bool_mod = wall.modifiers.new(name=f"Bool_Win_{idx}", type='BOOLEAN')
                    bool_mod.operation = 'DIFFERENCE'
                    bool_mod.object = cutter
                    bool_mod.solver = 'FAST'

            cutter.display_type = 'WIRE'
            cutter.hide_render = True

            # Try to place 3D window model
            win_asset = _try_import_window_model(wx, wy, actual_z, ww, wh, idx, is_vertical=is_vert)
            if win_asset:
                created_frames.append(win_asset)
            else:
                # Fallback: Insert Modern Aluminum Window Frame + Double Glazing
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
                win_frame = bpy.context.active_object
                win_frame.name = f"window_frame_{idx}"
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
                wmod.solver = 'FAST'
                wcutter.hide_render = True
                wcutter.display_type = 'WIRE'

                created_frames.append(win_frame)

                # Insert Double-Glazed Glass Pane
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
                glass = bpy.context.active_object
                glass.name = f"window_glass_{idx}"
                if is_vert:
                    glass.scale = (0.02, ww - 0.08, wh - 0.08)
                else:
                    glass.scale = (ww - 0.08, 0.02, wh - 0.08)

                if glass_mat:
                    glass.data.materials.append(glass_mat)
                glass.parent = win_frame
                created_frames.append(glass)
        except Exception as e:
            print(f"[WARN] Failed to process window {idx}: {e}")

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
            pwall.parent = roof_slab
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
        gable.parent = roof_slab
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

    bw_h = 1.80
    bw_t = 0.15
    px_center = cx
    py_center = cy - (sb_f / 2.0)

    # Left, Right, Rear boundary walls
    b_segments = [
        (px_center - pw / 2.0, py_center, bw_t, pd),
        (px_center + pw / 2.0, py_center, bw_t, pd),
        (px_center, py_center + pd / 2.0, pw, bw_t),
    ]
    for idx, (bx, by, b_w, b_d) in enumerate(b_segments):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, by, bw_h / 2.0))
        bw_obj = bpy.context.active_object
        bw_obj.name = f"Exterior_Boundary_Wall_{idx+1}"
        bw_obj.scale = (b_w, b_d, bw_h)
        if wall_mat:
            bw_obj.data.materials.append(wall_mat)
        created.append(bw_obj)

    # Front Gate
    gate_w = 3.6
    gate_h = 1.80
    gate_y = py_center - pd / 2.0
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(px_center - 1.5, gate_y, gate_h / 2.0))
    gate_obj = bpy.context.active_object
    gate_obj.name = "Exterior_Entrance_Gate"
    gate_obj.scale = (gate_w, 0.06, gate_h)
    if gate_mat:
        gate_obj.data.materials.append(gate_mat)
    created.append(gate_obj)

    # Driveway Paving
    drive_w = 3.8
    drive_d = max(sb_f + 1.0, 4.0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(px_center - 1.5, gate_y + drive_d / 2.0, 0.01))
    drive_obj = bpy.context.active_object
    drive_obj.name = "Exterior_Driveway_Paving"
    drive_obj.scale = (drive_w, drive_d, 0.02)
    if drive_mat:
        drive_obj.data.materials.append(drive_mat)
    created.append(drive_obj)

    return created


# ─── Main Generator Pipeline ──────────────────────────────────────────────────

def generate_house_from_layout(
    layout_data: Dict[str, Any],
    output_glb_path: str,
    blender_root: str,
    dollhouse_mode: bool = False
) -> str:
    """Main hyperrealistic generator pipeline supporting multi-floor architecture."""
    print(f"[ARCHGEN] Generating Hyperrealistic 3D Architecture: {layout_data.get('project_name', 'House')}")

    # 1. Clear default scene
    clear_scene()

    # 2. Extract architectural specs
    bldg = layout_data.get("building", {})
    wall_h = 1.45 if dollhouse_mode else float(bldg.get("wall_height", 2.8))
    wall_t = float(bldg.get("wall_thickness", 0.20))
    slab_t = float(bldg.get("slab_thickness", 0.22))
    rooms = layout_data.get("rooms", [])
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
    build_foundation_and_patio(rooms)

    # 4. Room Floor Slabs with PBR Materials
    print("[ARCHGEN] Building room floor slabs with PBR shaders...")
    build_floor_slab(rooms, slab_thickness=slab_t)

    # 5. Walls with Baseboard Skirting and Dollhouse Caps
    print(f"[ARCHGEN] Constructing architectural walls (height={wall_h}m)...")
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
        upper_rooms = [r for r in rooms if r.get("bounds", {}).get("z", 0.0) >= 2.5]
        if upper_rooms:
            build_intermediate_slab(upper_rooms, stair_def=stair_def, elevation=3.0, slab_thickness=slab_t)

    # 8. Populate Real 3D Furniture Assets
    print("[ARCHGEN] Populating rooms with catalogued 3D furniture models...")
    catalog = place_furniture.FurnitureCatalog(base_path=blender_root)
    total_furniture = 0
    for room in rooms:
        placed = place_furniture.populate_room_furniture(room, catalog, base_blender_dir=blender_root)
        total_furniture += len(placed)
    print(f"[ARCHGEN] Successfully placed {total_furniture} furniture pieces.")

    # 9. Roof Generation
    if roof_data:
        top_elev = (len(floors) or 1) * 3.0
        print(f"[ARCHGEN] Generating architectural roof ({roof_data.get('type', 'parapet')})...")
        build_roof_structure(bldg_w, bldg_d, cx, cy, top_elev, roof_data)

    # 10. Exterior Features (Boundary Wall, Gate, Driveway)
    if exterior_data:
        print("[ARCHGEN] Generating exterior features (gate, boundary, driveway)...")
        build_exterior_features(site_data, exterior_data, bldg_w, bldg_d, cx, cy)

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
