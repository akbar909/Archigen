"""
import_asset.py
================
Utility module to import 3D furniture models into Blender scenes,
normalize origins to base/floor level, compute bounding dimensions,
and assign necessary custom metadata properties for ArchGen.

Designed for Headless Blender execution (bpy).
Primary runtime format: GLB/glTF.
"""

import os
import sys
import math
from typing import Optional, Tuple, Dict, Any

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None
    mathutils = None


def ensure_bpy():
    """Verify that Blender Python environment (bpy) is available."""
    if bpy is None:
        raise RuntimeError("This script must be executed inside Blender's Python environment.")


def load_model(file_path: str, name_prefix: Optional[str] = None) -> Any:
    """
    Imports a 3D model (GLB, glTF, OBJ, FBX) into the active Blender scene.
    
    Args:
        file_path: Absolute or relative path to the 3D model.
        name_prefix: Optional prefix to rename imported root object.

    Returns:
        The imported root Blender Object or collection.
    """
    ensure_bpy()

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Model file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    
    # Store objects present before import to identify new objects
    existing_objects = set(bpy.context.scene.objects)

    if ext in [".glb", ".gltf"]:
        bpy.ops.import_scene.gltf(filepath=file_path)
    elif ext == ".obj":
        # Blender 3.x+ / 4.x wave_front obj importer
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=file_path)
        else:
            bpy.ops.import_scene.obj(filepath=file_path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=file_path)
    else:
        raise ValueError(f"Unsupported 3D model format '{ext}'. Recommended format is .glb / .gltf.")

    # Identify newly imported objects
    new_objects = [obj for obj in bpy.context.scene.objects if obj not in existing_objects]

    if not new_objects:
        raise RuntimeError(f"No objects were imported from {file_path}")

    # Primary imported object (or parent if hierarchy exists)
    root_obj = None
    for obj in new_objects:
        if obj.parent is None:
            root_obj = obj
            break

    if root_obj is None:
        root_obj = new_objects[0]

    if name_prefix:
        root_obj.name = f"{name_prefix}_{root_obj.name}"

    # Perform automated origin centering to bottom (floor contact point)
    adjust_origin_to_bottom(root_obj)

    return root_obj


def adjust_origin_to_bottom(obj: Any) -> None:
    """
    Adjusts the object's origin (pivot point) to the bottom-center of its bounding box.
    This ensures that setting Z=0 places the furniture directly on the floor.
    """
    ensure_bpy()
    mesh_objs = [o for o in [obj] + list(obj.children_recursive) if o.type == 'MESH']
    if not mesh_objs:
        return

    # If single mesh object
    if len(mesh_objs) == 1 and obj.type == 'MESH':
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        matrix = obj.matrix_world
        bbox_corners = [matrix @ mathutils.Vector(corner) for corner in obj.bound_box]
        min_z = min(corner.z for corner in bbox_corners)
        center_x = sum(corner.x for corner in bbox_corners) / 8.0
        center_y = sum(corner.y for corner in bbox_corners) / 8.0

        bpy.context.scene.cursor.location = mathutils.Vector((center_x, center_y, min_z))
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        return

    # Multi-mesh or hierarchy: compute global minimum Z across all descendant meshes
    all_corners = []
    for m in mesh_objs:
        for corner in m.bound_box:
            all_corners.append(m.matrix_world @ mathutils.Vector(corner))

    if not all_corners:
        return

    min_z = min(pt.z for pt in all_corners)
    center_x = sum(pt.x for pt in all_corners) / len(all_corners)
    center_y = sum(pt.y for pt in all_corners) / len(all_corners)

    bpy.context.scene.cursor.location = mathutils.Vector((center_x, center_y, min_z))
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    except Exception:
        pass


def get_bounding_dimensions(obj: Any) -> Tuple[float, float, float]:
    """
    Calculates the world-space bounding box dimensions (width_x, depth_y, height_z) in meters,
    correctly traversing all child meshes in the hierarchy.
    """
    ensure_bpy()
    mesh_objs = [o for o in [obj] + list(obj.children_recursive) if o.type == 'MESH']
    if not mesh_objs:
        return (max(obj.dimensions.x, 0.001), max(obj.dimensions.y, 0.001), max(obj.dimensions.z, 0.001))

    min_coords = [float("inf"), float("inf"), float("inf")]
    max_coords = [float("-inf"), float("-inf"), float("-inf")]
    for o in mesh_objs:
        for corner in o.bound_box:
            world_corner = o.matrix_world @ mathutils.Vector(corner)
            for i in range(3):
                min_coords[i] = min(min_coords[i], world_corner[i])
                max_coords[i] = max(max_coords[i], world_corner[i])

    wx = max(max_coords[0] - min_coords[0], 0.001)
    wy = max(max_coords[1] - min_coords[1], 0.001)
    wz = max(max_coords[2] - min_coords[2], 0.001)
    return (wx, wy, wz)


def attach_metadata_properties(obj: Any, metadata: Dict[str, Any]) -> None:
    """
    Stores custom properties on the Blender object to retain asset metadata.
    """
    ensure_bpy()
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            obj[f"archgen_{key}"] = value


# CLI Entrypoint for standalone testing
if __name__ == "__main__":
    print("ArchGen Asset Importer Utility loaded successfully.")
