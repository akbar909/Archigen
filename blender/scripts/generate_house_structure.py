"""Foundation, slabs, and wall construction."""

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

from generate_house_materials import apply_box_uv_mapping, create_pbr_material, hex_to_rgb

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

def build_floor_slab(
    rooms: List[Dict[str, Any]],
    slab_thickness: float = 0.2,
    stair_openings: Optional[List[Dict[str, Any]]] = None,
) -> List[Any]:
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

        # Upper slabs must have a real opening over the stair flight.  Apply a
        # cutter to every room slab intersected by that floor's vertical core;
        # this also works when the opening crosses a room boundary.
        room_level = int(room.get("floor_level", 0))
        for opening_index, opening in enumerate(stair_openings or []):
            opening_level = int(opening.get("floor_level", room_level))
            if opening_level != room_level:
                continue
            opos = opening.get("position", {})
            odim = opening.get("dimensions", {})
            ox = float(opos.get("x", 0.0))
            oy = float(opos.get("y", 0.0))
            ow = float(odim.get("width", odim.get("w", 0.0)))
            od = float(odim.get("depth", odim.get("d", 0.0)))
            if ow <= 0.0 or od <= 0.0:
                continue
            ix0, iy0 = max(x, ox), max(y, oy)
            ix1, iy1 = min(x + w, ox + ow), min(y + d, oy + od)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            bpy.ops.mesh.primitive_cube_add(
                size=1.0,
                location=((ix0 + ix1) / 2.0, (iy0 + iy1) / 2.0, cz),
            )
            cutter = bpy.context.active_object
            cutter.name = f"_StairOpening_L{room_level}_{opening_index}_{room.get('id', 'room')}"
            cutter.scale = (ix1 - ix0 + 0.04, iy1 - iy0 + 0.04, slab_thickness * 3.0)
            cutter["archgen_floor_level"] = room_level
            cutter["archgen_stair_opening"] = True
            cutter["archgen_stair_opening_id"] = str(opening.get("id") or f"stair_opening_{opening_index}")
            cutter["archgen_serves_stair_id"] = str(opening.get("serves_stair_id") or "")
            modifier = slab.modifiers.new(name=f"StairOpening_{opening_index}", type='BOOLEAN')
            modifier.operation = 'DIFFERENCE'
            modifier.object = cutter
            modifier.solver = 'EXACT'
            cutter.hide_render = True
            cutter.display_type = 'WIRE'

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


def _normalized_wall_config(value: Any) -> Dict[str, Any]:
    """Return a small, renderer-safe wall style dictionary."""
    if isinstance(value, str) and value.strip():
        return {"pattern": value.strip().lower(), "color": [0.93, 0.91, 0.88]}
    if not isinstance(value, dict):
        return {}
    nested = value.get("walls") or value.get("wall")
    if isinstance(nested, dict):
        value = nested
    pattern = str(value.get("pattern") or value.get("material") or value.get("style") or "").strip().lower()
    color = value.get("color")
    if isinstance(color, str):
        color = hex_to_rgb(color)
    if not isinstance(color, (list, tuple)) or len(color) < 3:
        color = [0.93, 0.91, 0.88]
    return {"pattern": pattern or "plain", "color": list(color[:3])}


def _select_house_wall_config(
    rooms: List[Dict[str, Any]], configured: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Choose one default wall finish for the complete house."""
    explicit = _normalized_wall_config(configured)
    if explicit:
        return explicit

    configs = []
    pattern_counts: Dict[str, int] = {}
    for room in rooms:
        cfg = _normalized_wall_config(room.get("walls", {}))
        if not cfg:
            continue
        configs.append(cfg)
        pattern = cfg["pattern"]
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    if not configs:
        return {"pattern": "plain", "color": [0.93, 0.91, 0.88]}

    # max() keeps the first-seen pattern when counts tie, making selection
    # deterministic without allowing each room to restyle its own walls.
    winning_pattern = max(pattern_counts, key=pattern_counts.get)
    return next(cfg for cfg in configs if cfg["pattern"] == winning_pattern)


def _wall_material_from_config(config: Dict[str, Any], name: str) -> Any:
    cfg = _normalized_wall_config(config)
    pattern, color = cfg.get("pattern", "plain"), cfg.get("color")
    if "brick" in pattern:
        return create_pbr_material(name, "wall_brick", color)
    if any(token in pattern for token in ("wood", "slat", "panel")):
        return create_pbr_material(name, "wall_wood", color)
    if "paint" in pattern:
        return create_pbr_material(name, "wall_painted", color)
    return create_pbr_material(name, "wall", color, roughness=0.82)


def _wall_specific_override(wall_data: Dict[str, Any]) -> Dict[str, Any]:
    """Read an intentional per-wall override without using room defaults."""
    for key in ("material_override", "wall_material", "style_override"):
        cfg = _normalized_wall_config(wall_data.get(key))
        if cfg:
            return cfg
    return {}


def build_walls_from_network(
    walls: List[Dict[str, Any]], rooms: List[Dict[str, Any]], wall_height: float = 2.8,
    default_thickness: float = 0.20, default_wall_config: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """Build the approved wall network exactly once; never infer it from rooms."""
    if bpy is None:
        return []
    house_wall_cfg = _select_house_wall_config(rooms, default_wall_config)
    default_mat = _wall_material_from_config(house_wall_cfg, "mat_house_wall_shared")
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

        override = _wall_specific_override(wall_data)
        material = (
            _wall_material_from_config(override, f"mat_wall_override_{wall_id}")
            if override else default_mat
        )
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
    add_baseboards: bool = False,
    default_wall_config: Optional[Dict[str, Any]] = None,
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
    house_wall_cfg = _select_house_wall_config(rooms, default_wall_config)
    wall_mat = _wall_material_from_config(house_wall_cfg, "mat_house_wall_shared")

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

        if wall_mat:
            wall.data.materials.append(wall_mat)

        apply_box_uv_mapping(wall, tile_meters=1.8)
        wall_objects.append(wall)

    return wall_objects, auto_doors


