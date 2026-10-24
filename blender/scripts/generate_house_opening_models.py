"""Door, window, and gate model construction helpers."""

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

from generate_house_materials import apply_box_uv_mapping, create_pbr_material

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


def _door_opens_toward_local_y(is_vertical: bool, wall_side: str, swing: str) -> float:
    """Return +1/-1 for the open leaf direction in canonical door-local space."""
    side_value = str(wall_side or "south").lower()
    swing_value = str(swing or "inward_right").lower()
    direction = 1.0 if (
        (not is_vertical and ("south" in side_value or "front" in side_value))
        or (is_vertical and ("east" in side_value or "right" in side_value))
    ) else -1.0
    return -direction if "outward" in swing_value else direction


def _select_door_model_path(door_dir: str, preferred_asset: Optional[str] = None) -> Optional[str]:
    """Select one stable house door, or an explicitly requested door asset."""
    candidates = []
    search_dirs = [
        os.path.join(BLENDER_ROOT, "assets", "architecture", "doors"),
        os.path.join(BLENDER_ROOT, "assets", "doors"),
    ]
    for s_dir in search_dirs:
        if os.path.isdir(s_dir):
            for root, _, names in os.walk(s_dir):
                for name in names:
                    if os.path.splitext(name)[1].lower() in {".glb", ".gltf"}:
                        candidates.append(os.path.join(root, name))

    requested = str(preferred_asset or "").strip().replace("\\", "/").lower()
    if requested:
        requested_name = os.path.basename(requested)
        requested_stem = os.path.splitext(requested_name)[0]
        for candidate in candidates:
            candidate_norm = candidate.replace("\\", "/").lower()
            candidate_name = os.path.basename(candidate_norm)
            if (
                candidate_norm.endswith(requested)
                or candidate_name == requested_name
                or os.path.splitext(candidate_name)[0] == requested_stem
            ):
                return candidate
        print(f"[WARN] Requested door asset '{preferred_asset}' was not found; using the house default.")
    for candidate in candidates:
        cand_lower = os.path.basename(candidate).lower()
        if "interior_door" in cand_lower or cand_lower == "door_standard.glb":
            return candidate
    return candidates[0] if candidates else None


def _try_import_door_model(
    dx: float,
    dy: float,
    dz: float,
    dw: float,
    dh: float,
    idx: int,
    is_vertical: bool = False,
    swing: str = "inward_right",
    wall_side: str = "south",
    preferred_asset: Optional[str] = None,
) -> Optional[Any]:
    """Import the one default door, unless this opening names an override."""
    door_dir = os.path.join(BLENDER_ROOT, "assets", "architecture", "doors")
    requested = str(preferred_asset or "").strip().replace("\\", "/").lower()
    selected = _select_door_model_path(door_dir, preferred_asset)
    door_candidates = [selected] if selected else []

    for p in door_candidates:
        if os.path.isfile(p):
            try:
                imported = import_asset.load_model(p, name_prefix=f"door_asset_{idx}")
                cur_w, cur_d, cur_h = import_asset.get_bounding_dimensions(imported)
                cur_w = max(cur_w, 0.001)
                cur_d = max(cur_d, 0.001)
                cur_h = max(cur_h, 0.001)
                target_h = min(dh, 2.3)
                wall_t = 0.20

                placement = bpy.data.objects.new(f"Imported_Door_Placement_{idx}", None)
                bpy.context.scene.collection.objects.link(placement)
                placement.location = (dx, dy, dz)
                placement.rotation_euler = (0.0, 0.0, math.radians(90.0) if is_vertical else 0.0)
                imported.parent = placement
                imported.location = (0.0, 0.0, 0.0)

                # Some downloaded doors are authored Y-up while glTF normally
                # uses Z-up after import. Detect both and normalize to the same
                # local X=width, Y=wall-depth, Z=height convention.
                if cur_d > cur_h * 1.5 and cur_d > cur_w * 1.15:
                    imported.rotation_euler = (math.radians(90.0), 0.0, 0.0)
                    imported.scale = (dw / cur_w, target_h / cur_d, wall_t / cur_h)
                    source_up_axis = "Y"
                else:
                    imported.rotation_euler = (0.0, 0.0, 0.0)
                    imported.scale = (dw / cur_w, wall_t / cur_d, target_h / cur_h)
                    source_up_axis = "Z"
                bpy.context.view_layer.update()

                meshes = [obj for obj in imported.children_recursive if obj.type == "MESH"]
                if not meshes:
                    raise RuntimeError("Door asset has no mesh geometry")

                # Recenter and seat the normalized asset in placement-local
                # coordinates, independent of the source pivot and up axis.
                placement_inv = placement.matrix_world.inverted()
                local_points = [
                    placement_inv @ obj.matrix_world @ mathutils.Vector(corner)
                    for obj in meshes
                    for corner in obj.bound_box
                ]
                center_x = (min(point.x for point in local_points) + max(point.x for point in local_points)) / 2.0
                center_y = (min(point.y for point in local_points) + max(point.y for point in local_points)) / 2.0
                min_z = min(point.z for point in local_points)
                imported.location += mathutils.Vector((-center_x, -center_y, -min_z))
                bpy.context.view_layer.update()

                fixed_tokens = ("frame", "jamb", "trim", "casing", "doorway", "threshold")
                fixed_meshes = []
                leaf_meshes = []
                for mesh in meshes:
                    source_name = str(mesh.get("archgen_source_object_name") or mesh.data.name or mesh.name).lower()
                    if any(token in source_name for token in fixed_tokens):
                        fixed_meshes.append(mesh)
                    else:
                        leaf_meshes.append(mesh)
                if not leaf_meshes:
                    leaf_meshes = list(meshes)
                    fixed_meshes = []

                frame_width = min(0.09, max(0.055, dw * 0.08))
                if not fixed_meshes:
                    frame_mat = create_pbr_material("mat_imported_door_frame", "wood", [0.42, 0.28, 0.16])
                    for name, location, dimensions in (
                        ("ImportedDoorFrame_Left", (-dw / 2.0 + frame_width / 2.0, 0.0, target_h / 2.0), (frame_width, 0.16, target_h)),
                        ("ImportedDoorFrame_Right", (dw / 2.0 - frame_width / 2.0, 0.0, target_h / 2.0), (frame_width, 0.16, target_h)),
                        ("ImportedDoorFrame_Header", (0.0, 0.0, target_h - frame_width / 2.0), (dw, 0.16, frame_width)),
                    ):
                        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
                        frame_part = bpy.context.active_object
                        frame_part.name = name
                        frame_part.parent = placement
                        frame_part.location = location
                        frame_part.scale = dimensions
                        if frame_mat:
                            frame_part.data.materials.append(frame_mat)
                        fixed_meshes.append(frame_part)

                swing_value = str(swing or "inward_right").lower()
                hinge_on_right = "right" in swing_value
                hinge_x = (dw / 2.0 - frame_width) if hinge_on_right else (-dw / 2.0 + frame_width)
                hinge = bpy.data.objects.new(f"Imported_Door_Hinge_{idx}", None)
                bpy.context.scene.collection.objects.link(hinge)
                hinge.parent = placement
                hinge.location = (hinge_x, 0.0, 0.0)
                # Evaluate the parented hinge before preserving child world
                # transforms; otherwise Blender still sees its stale origin and
                # the first rotation can throw the leaf several metres away.
                bpy.context.view_layer.update()
                for leaf in leaf_meshes:
                    world_matrix = leaf.matrix_world.copy()
                    leaf.parent = hinge
                    leaf.matrix_world = world_matrix
                    leaf["archgen_open_door_leaf"] = True
                direction = _door_opens_toward_local_y(is_vertical, wall_side, swing_value)
                base_angle = -82.0 if hinge_on_right else 82.0
                hinge.rotation_euler = (0.0, 0.0, math.radians(base_angle * direction))
                bpy.context.view_layer.update()

                placement["archgen_imported_door"] = True
                placement["archgen_source_file"] = os.path.basename(p)
                placement["archgen_source_up_axis"] = source_up_axis
                placement["archgen_door_swing"] = swing_value
                print(
                    f"[ARCHGEN] Loaded room door {os.path.basename(p)} "
                    f"(selection={'explicit' if requested else 'house-default'}, up={source_up_axis}, swing={swing_value})"
                )
                return placement
            except Exception as e:
                print(f"[WARN] Could not load door model {p}: {e}")
    return None


def _try_import_window_model(
    wx: float, wy: float, wz: float, ww: float, wh: float, idx: int, is_vertical: bool = False
) -> Optional[Any]:
    """Attempts to import a real 3D window GLB model into the opening cutout, rotated and scaled to match wall."""
    win_dirs = [
        os.path.join(BLENDER_ROOT, "assets", "architecture", "windows"),
        os.path.join(BLENDER_ROOT, "assets", "windows"),
    ]
    win_candidates = []
    for wd in win_dirs:
        if os.path.isdir(wd):
            for root, _, files in os.walk(wd):
                for f in sorted(files):
                    if f.lower().endswith((".glb", ".gltf")):
                        win_candidates.append(os.path.join(root, f))

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
    """Build or import a 3D sectional garage shutter instead of procedural cubes."""
    garage_model_candidates = [
        os.path.join(BLENDER_ROOT, "assets", "architecture", "doors", "exterior", "roller_garager_door_01.glb"),
        os.path.join(BLENDER_ROOT, "assets", "architecture", "doors", "exterior", "roller_garage_door_01.glb"),
        os.path.join(BLENDER_ROOT, "assets", "doors", "roller_garager_door_01.glb"),
    ]
    for g_path in garage_model_candidates:
        if os.path.isfile(g_path) and import_asset is not None:
            try:
                door_obj = import_asset.load_model(g_path, name_prefix="Garage_Rollup_Door")
                cur_w, cur_d, cur_h = import_asset.get_bounding_dimensions(door_obj)
                cur_w = max(cur_w, 0.001)
                cur_d = max(cur_d, 0.001)
                cur_h = max(cur_h, 0.001)
                door_obj.location = (dx, dy, dz)
                if is_vertical:
                    door_obj.rotation_euler = (0.0, 0.0, math.radians(90.0))
                    door_obj.scale = (0.20 / cur_d, dw / cur_w, dh / cur_h)
                else:
                    door_obj.rotation_euler = (0.0, 0.0, 0.0)
                    door_obj.scale = (dw / cur_w, 0.20 / cur_d, dh / cur_h)
                return door_obj
            except Exception as e:
                print(f"[WARN] Failed to load 3D garage door model {g_path}: {e}")

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
    wall_side: str = "south",
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
    swing_value = str(swing or "inward_right").lower()
    side_value = str(wall_side or "south").lower()
    hinge_on_right = "right" in swing_value
    hinge_x = (dw / 2.0 - frame_width) if hinge_on_right else (-dw / 2.0 + frame_width)
    leaf_width = max(0.45, dw - frame_width * 2.0)
    leaf_height = max(0.8, dh - frame_width)
    hinge = bpy.data.objects.new("DoorLeaf_Hinge", None)
    bpy.context.scene.collection.objects.link(hinge)
    hinge.parent = root
    hinge.location = (hinge_x, 0.0, 0.0)
    opens_toward_local_y = _door_opens_toward_local_y(is_vertical, side_value, swing_value)
    base_angle = -82.0 if hinge_on_right else 82.0
    hinge.rotation_euler = (0.0, 0.0, math.radians(base_angle * opens_toward_local_y))
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

