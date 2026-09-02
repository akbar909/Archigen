"""
generate_house.py
=================
Main entry point for ArchGen procedural 3D house generation in Blender.

This script parses architectural layout JSON data, procedurally builds:
- Foundation / Slabs
- Exterior and interior walls
- Door and window openings
- Room floors with designated materials
- Furniture asset placement via catalog lookup
- Final optimized GLB export for Three.js

Usage:
  blender --background --python blender/scripts/generate_house.py -- \\
          --input blender/input/sample_house_layout.json \\
          --output blender/output/generated_house.glb
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None
    mathutils = None

# Ensure sibling scripts can be imported
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

    # Purge orphaned data blocks
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def create_material(name: str, color_rgb: List[float], roughness: float = 0.5) -> Any:
    """Creates a basic Principled BSDF PBR material."""
    if bpy is None:
        return None
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        # Base Color (RGBA)
        rgba = (color_rgb[0], color_rgb[1], color_rgb[2], 1.0) if len(color_rgb) >= 3 else (0.8, 0.8, 0.8, 1.0)
        bsdf.inputs["Base Color"].default_value = rgba
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build_floor_slab(rooms: List[Dict[str, Any]], slab_thickness: float = 0.2) -> Any:
    """
    Procedurally creates floor meshes for each room with assigned materials.
    """
    if bpy is None:
        return None

    floor_objects = []
    for room in rooms:
        bounds = room.get("bounds", {})
        x = bounds.get("x", 0.0)
        y = bounds.get("y", 0.0)
        w = bounds.get("width", 4.0)
        d = bounds.get("depth", 4.0)

        # Center point for cube
        cx = x + (w / 2.0)
        cy = y + (d / 2.0)
        cz = -slab_thickness / 2.0

        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(cx, cy, cz)
        )
        slab = bpy.context.active_object
        slab.name = f"floor_{room.get('id', 'room')}"
        slab.scale = (w, d, slab_thickness)

        # Apply material
        flooring_info = room.get("flooring", {})
        color = flooring_info.get("color", [0.75, 0.75, 0.75])
        mat_name = f"mat_{flooring_info.get('material', 'default_floor')}"
        mat = create_material(mat_name, color, roughness=0.4)
        if mat and slab.data.materials:
            slab.data.materials[0] = mat
        elif mat:
            slab.data.materials.append(mat)

        floor_objects.append(slab)

    return floor_objects


def build_walls(
    rooms: List[Dict[str, Any]],
    wall_height: float = 2.8,
    wall_thickness: float = 0.2
) -> Any:
    """
    Builds exterior and perimeter walls around rooms.
    TODO: Add boolean modifier cutouts for door and window openings.
    """
    if bpy is None:
        return []

    wall_objects = []
    wall_mat = create_material("mat_wall_white", [0.95, 0.95, 0.95], roughness=0.8)

    for room in rooms:
        bounds = room.get("bounds", {})
        rx = bounds.get("x", 0.0)
        ry = bounds.get("y", 0.0)
        rw = bounds.get("width", 4.0)
        rd = bounds.get("depth", 4.0)

        # Build 4 perimeter wall segments per room
        wall_segments = [
            # South wall (y min)
            (rx + rw / 2.0, ry + wall_thickness / 2.0, rw, wall_thickness),
            # North wall (y max)
            (rx + rw / 2.0, ry + rd - wall_thickness / 2.0, rw, wall_thickness),
            # West wall (x min)
            (rx + wall_thickness / 2.0, ry + rd / 2.0, wall_thickness, rd),
            # East wall (x max)
            (rx + rw - wall_thickness / 2.0, ry + rd / 2.0, wall_thickness, rd),
        ]

        for idx, (wx, wy, sx, sy) in enumerate(wall_segments):
            bpy.ops.mesh.primitive_cube_add(
                size=1.0,
                location=(wx, wy, wall_height / 2.0)
            )
            wall = bpy.context.active_object
            wall.name = f"wall_{room.get('id', 'room')}_{idx}"
            wall.scale = (sx, sy, wall_height)

            if wall_mat:
                wall.data.materials.append(wall_mat)

            wall_objects.append(wall)

    # TODO: Add door & window boolean cutouts from layout_data["openings"]
    return wall_objects


def setup_lighting():
    """Adds default sunlight and ambient fill for Three.js rendering."""
    if bpy is None:
        return
    # Add Sun light
    bpy.ops.object.light_add(type='SUN', location=(10, -10, 15))
    sun = bpy.context.active_object
    sun.name = "ArchGen_SunLight"
    sun.data.energy = 2.5
    sun.rotation_euler = (0.785, 0.35, 0.785)


def generate_house_from_layout(layout_data: Dict[str, Any], output_glb_path: str, blender_root: str) -> str:
    """
    Main generator pipeline execution function.
    """
    print(f"[ARCHGEN] Starting generation for: {layout_data.get('project_name', 'House')}")

    # 1. Clear default scene
    clear_scene()

    # 2. Extract architectural specs
    bldg = layout_data.get("building", {})
    wall_h = bldg.get("wall_height", 2.8)
    wall_t = bldg.get("wall_thickness", 0.2)
    slab_t = bldg.get("slab_thickness", 0.25)
    rooms = layout_data.get("rooms", [])

    # 3. Procedural Structure
    print("[ARCHGEN] Building floor slabs...")
    build_floor_slab(rooms, slab_thickness=slab_t)

    print("[ARCHGEN] Building walls...")
    build_walls(rooms, wall_height=wall_h, wall_thickness=wall_t)

    # 4. Setup Lighting
    setup_lighting()

    # 5. Populate Furniture
    print("[ARCHGEN] Loading furniture catalog and populating rooms...")
    catalog = place_furniture.FurnitureCatalog(base_path=blender_root)
    total_furniture = 0
    for room in rooms:
        placed = place_furniture.populate_room_furniture(room, catalog, base_blender_dir=blender_root)
        total_furniture += len(placed)
    print(f"[ARCHGEN] Placed {total_furniture} furniture objects.")

    # 6. Export to GLB
    print(f"[ARCHGEN] Exporting final scene to: {output_glb_path}")
    final_path = export_glb.export_scene_to_glb(output_glb_path)

    print("[ARCHGEN] House generation completed successfully!")
    return final_path


def parse_cli_args():
    """Parses arguments passed after '--' in Blender headless execution."""
    parser = argparse.ArgumentParser(description="ArchGen Headless 3D House Generator")
    parser.add_argument("--input", type=str, default="input/sample_house_layout.json",
                        help="Path to the house layout JSON input file.")
    parser.add_argument("--output", type=str, default="output/generated_house.glb",
                        help="Target output GLB file path.")
    
    # Blender passes all args to python; arguments after '--' belong to this script
    if "--" in sys.argv:
        args_idx = sys.argv.index("--") + 1
        return parser.parse_args(sys.argv[args_idx:])
    return parser.parse_args([])


def main():
    args = parse_cli_args()
    
    # Resolve paths relative to blender root if not absolute
    input_path = args.input if os.path.isabs(args.input) else os.path.join(BLENDER_ROOT, args.input)
    output_path = args.output if os.path.isabs(args.output) else os.path.join(BLENDER_ROOT, args.output)

    if not os.path.exists(input_path):
        print(f"[ERROR] Input layout file does not exist: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        layout_data = json.load(f)

    generate_house_from_layout(layout_data, output_path, BLENDER_ROOT)


if __name__ == "__main__":
    main()
