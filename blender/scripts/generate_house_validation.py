"""Validation of generated Blender scene geometry."""

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
        opening_defs = {
            str(item.get("id")): item
            for item in layout_data.get("openings", {}).get(f"{kind}s", [])
            if isinstance(item, dict) and item.get("id") is not None
        }
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

            # Verify the visible 3D leaf opens toward the same side described
            # by the canonical swing used by the 2D CAD symbol.
            if kind == "door":
                definition = opening_defs.get(opening_id, {})
                swing_value = str(definition.get("swing", "inward_right")).lower()
                door_type = str(definition.get("type", "")).lower()
                leaf_meshes = [obj for obj in meshes if obj.get("archgen_open_door_leaf", False)]
                if leaf_meshes and swing_value != "overhead" and door_type != "garage_door":
                    leaf_points = [
                        obj.matrix_world @ mathutils.Vector(corner)
                        for obj in leaf_meshes
                        for corner in obj.bound_box
                    ]
                    leaf_x = (min(point.x for point in leaf_points) + max(point.x for point in leaf_points)) / 2.0
                    leaf_y = (min(point.y for point in leaf_points) + max(point.y for point in leaf_points)) / 2.0
                    side = str(definition.get("wall_side") or definition.get("wall") or "south").lower()
                    outward = "outward" in swing_value
                    if side in {"south", "front"}:
                        signed_distance = leaf_y - expected_y
                    elif side in {"north", "back"}:
                        signed_distance = expected_y - leaf_y
                    elif side in {"west", "left"}:
                        signed_distance = leaf_x - expected_x
                    else:
                        signed_distance = expected_x - leaf_x
                    if outward:
                        signed_distance *= -1.0
                    if signed_distance < 0.05:
                        errors.append(
                            f"Door '{opening_id}' leaf opens opposite to its canonical '{swing_value}' direction."
                        )

    expected_stairs = {
        str(stair.get("id")): stair
        for floor in layout_data.get("floors", [])
        for stair in floor.get("stairs", [])
        if isinstance(stair, dict) and stair.get("id")
    }
    actual_stair_parts: Dict[str, List[Any]] = {}
    for obj in bpy.context.scene.objects:
        stair_id = obj.get("archgen_stair_id")
        if stair_id is not None:
            actual_stair_parts.setdefault(str(stair_id), []).append(obj)
    missing_stairs = sorted(set(expected_stairs) - set(actual_stair_parts))
    extra_stairs = sorted(set(actual_stair_parts) - set(expected_stairs))
    if missing_stairs or extra_stairs:
        errors.append(f"Stair inventory mismatch: missing={missing_stairs}, extra={extra_stairs}.")
    for stair_id, definition in expected_stairs.items():
        parts = actual_stair_parts.get(stair_id, [])
        expected_treads = max(16, int(definition.get("steps", 18)))
        if expected_treads % 2:
            expected_treads += 1
        treads = [obj for obj in parts if obj.get("archgen_stair_component") == "tread"]
        landings = [obj for obj in parts if obj.get("archgen_stair_component") == "landing"]
        handrails = [obj for obj in parts if obj.get("archgen_stair_component") == "handrail"]
        if len(treads) != expected_treads or len(landings) != 1 or len(handrails) < 2:
            errors.append(
                f"Stair '{stair_id}' is incomplete: treads={len(treads)}/{expected_treads}, "
                f"landings={len(landings)}/1, handrails={len(handrails)}/2."
            )

    expected_stair_openings = {
        str(opening.get("id"))
        for floor in layout_data.get("floors", [])
        for opening in floor.get("stair_openings", [])
        if isinstance(opening, dict) and opening.get("id")
    }
    actual_stair_openings = {
        str(obj.get("archgen_stair_opening_id"))
        for obj in bpy.context.scene.objects
        if obj.get("archgen_stair_opening", False) and obj.get("archgen_stair_opening_id")
    }
    missing_stair_openings = sorted(expected_stair_openings - actual_stair_openings)
    if missing_stair_openings:
        errors.append(f"Missing upper-slab stair openings: {missing_stair_openings}.")

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
                errors.append(
                    f"Object '{obj.name}' is detached from the canonical site bounds: "
                    f"x={min(p.x for p in points):.2f}..{max(p.x for p in points):.2f}, "
                    f"y={min(p.y for p in points):.2f}..{max(p.y for p in points):.2f}, "
                    f"z={min(p.z for p in points):.2f}..{max(p.z for p in points):.2f}."
                )

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

