"""Door and window opening application."""

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

from generate_house_materials import create_pbr_material
from generate_house_opening_models import (
    _create_garage_door_model,
    _create_hinged_door_model,
    _is_opening_vertical,
    _safe_opening_coords,
    _try_import_door_model,
    _try_import_window_model,
    _wall_half_extents,
    _wall_is_vertical,
)

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
        requested_level = item.get("floor_level")
        if requested_level is None:
            position = item.get("position", {})
            if isinstance(position, dict):
                requested_level = int(round(float(position.get("z", 0.0)) / max(wall_height, 0.1)))
            elif isinstance(position, (list, tuple)) and len(position) > 2:
                requested_level = int(round(float(position[2]) / max(wall_height, 0.1)))
        requested_level = int(requested_level) if requested_level is not None else None

        def on_requested_floor(candidate):
            return requested_level is None or int(candidate.get("archgen_floor_level", 0)) == requested_level

        if wall_id:
            for candidate in wall_objects:
                if str(candidate.get("archgen_wall_id", "")) == wall_id and on_requested_floor(candidate):
                    return candidate
        vertical = _is_opening_vertical(ox, oy, item.get("wall_side") or item.get("wall"), wall_objects)
        compatible = [
            wall for wall in wall_objects
            if _wall_is_vertical(wall) == vertical and on_requested_floor(wall)
        ]
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

            # Use downloaded room-door models when available, matching the
            # window asset flow. Keep procedural geometry as a safe fallback
            # for missing/invalid assets and for special garage doors.
            door_type = str(d_item.get("type", "")).lower()
            if door_type == "garage_door":
                door_asset = _create_garage_door_model(dx, dy, dz, dw, dh, is_vertical=is_vert)
            else:
                door_asset = _try_import_door_model(
                    dx, dy, dz, dw, dh, idx,
                    is_vertical=is_vert,
                    swing=str(d_item.get("swing", "inward_right")),
                    wall_side=str(d_item.get("wall_side") or d_item.get("wall") or "south"),
                    preferred_asset=(
                        d_item.get("door_asset") or d_item.get("asset_id")
                        or d_item.get("model_file") or d_item.get("asset")
                    ),
                )
                if door_asset is None:
                    door_asset = _create_hinged_door_model(
                        dx, dy, dz, dw, dh,
                        is_vertical=is_vert,
                        door_type=door_type,
                        swing=str(d_item.get("swing", "inward_right")),
                        wall_side=str(d_item.get("wall_side") or d_item.get("wall") or "south"),
                    )
            if door_asset:
                door_asset.name = f"Door_L{level}_{opening_id}"
                door_asset["archgen_opening_id"] = opening_id
                door_asset["archgen_opening_kind"] = "door"
                door_asset["archgen_door_type"] = door_type
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
                frame["archgen_door_type"] = door_type
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
