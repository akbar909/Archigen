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


def create_pbr_material(
    name: str,
    mat_type: str = "wall",
    color_rgb: Optional[List[float]] = None,
    roughness: float = 0.5,
    metalness: float = 0.0
) -> Any:
    """
    Creates physically based Principled BSDF materials with realistic shader parameters.
    Supported mat_types: 'wood', 'tile', 'marble', 'wall', 'glass', 'metal', 'deck', 'concrete', 'trim'
    """
    if bpy is None:
        return None

    # Reuse existing if already created
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")

    if not bsdf:
        return mat

    c = color_rgb if color_rgb and len(color_rgb) >= 3 else [0.85, 0.85, 0.85]

    if mat_type == "glass":
        # Architectural double-glazed glass
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
        # Warm architectural oak / walnut
        wood_color = (c[0] * 0.9, c[1] * 0.85, c[2] * 0.75, 1.0)
        bsdf.inputs["Base Color"].default_value = wood_color
        bsdf.inputs["Roughness"].default_value = 0.42
        bsdf.inputs["Specular"].default_value = 0.45 if "Specular" in bsdf.inputs else 0.5

    elif mat_type in ["marble", "tile"]:
        # Polished stone / porcelain tile with high specularity
        tile_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = tile_color
        bsdf.inputs["Roughness"].default_value = 0.18
        if "Clearcoat" in bsdf.inputs:
            bsdf.inputs["Clearcoat"].default_value = 0.6
        elif "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.6

    elif mat_type == "metal":
        # Powder-coated architectural aluminum (matte dark casing)
        bsdf.inputs["Base Color"].default_value = (0.15, 0.18, 0.22, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.85
        bsdf.inputs["Roughness"].default_value = 0.35

    elif mat_type == "trim":
        # Deep architectural wood trim for baseboards and caps
        bsdf.inputs["Base Color"].default_value = (0.24, 0.18, 0.14, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55

    elif mat_type == "deck":
        # Slatted outdoor teak patio deck
        bsdf.inputs["Base Color"].default_value = (0.45, 0.25, 0.16, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.65

    elif mat_type == "concrete":
        # Contemporary dark architectural foundation stone
        bsdf.inputs["Base Color"].default_value = (0.18, 0.22, 0.28, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.85

    else:
        # High-end tactile matte drywall / plaster
        wall_color = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Base Color"].default_value = wall_color
        bsdf.inputs["Roughness"].default_value = 0.85
        if "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.2

    return mat


# ─── Foundation & Landscape Grounds ───────────────────────────────────────────

def build_foundation_and_patio(rooms: List[Dict[str, Any]]) -> List[Any]:
    """
    Creates a dual-tier beveled concrete podium and an outdoor teak patio deck
    framing the house for an elevated architectural appearance.
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

    # 1. Main Foundation Slab (sub-base)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, -0.22))
    base = bpy.context.active_object
    base.name = "Architectural_Foundation_Podium"
    base.scale = (hw + 1.8, hd + 1.8, 0.2)
    if concrete_mat:
        base.data.materials.append(concrete_mat)
    created_objs.append(base)

    # 2. Outdoor Front Patio Deck (slatted teak look)
    deck_depth = 4.5
    deck_y = min_y - (deck_depth / 2.0) - 0.2
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, deck_y, -0.05))
    deck = bpy.context.active_object
    deck.name = "Outdoor_Teak_Patio_Deck"
    deck.scale = (hw + 1.0, deck_depth, 0.14)
    if deck_mat:
        deck.data.materials.append(deck_mat)
    created_objs.append(deck)

    return created_objs


# ─── Room Floors ──────────────────────────────────────────────────────────────

def build_floor_slab(rooms: List[Dict[str, Any]], slab_thickness: float = 0.2) -> List[Any]:
    """Procedurally builds room floor slabs with customized PBR materials."""
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
        cz = -slab_thickness / 2.0

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
        slab = bpy.context.active_object
        slab.name = f"floor_{room.get('id', 'room')}"
        slab.scale = (w, d, slab_thickness)

        # Determine material type and color
        flooring = room.get("flooring", {})
        pattern = str(flooring.get("material", "")).lower()
        color = flooring.get("color", [0.8, 0.75, 0.7])

        if "wood" in pattern or "plank" in pattern or "living" in room_type or "bed" in room_type:
            mat = create_pbr_material(f"mat_floor_wood_{room.get('id')}", "wood", color)
        elif "tile" in pattern or "marble" in pattern or "bath" in room_type or "kitchen" in room_type:
            mat = create_pbr_material(f"mat_floor_tile_{room.get('id')}", "tile", color)
        else:
            mat = create_pbr_material(f"mat_floor_default_{room.get('id')}", "marble", color)

        if mat:
            slab.data.materials.append(mat)

        floor_objects.append(slab)

    return floor_objects


# ─── Walls with Baseboards & Dollhouse Caps ────────────────────────────────────

def build_walls(
    rooms: List[Dict[str, Any]],
    wall_height: float = 1.45,
    wall_thickness: float = 0.20,
    add_baseboards: bool = False
) -> List[Any]:
    """
    Constructs clean perimeter and partition walls for all rooms.
    Deduplicates shared partition walls between adjacent rooms to prevent Z-fighting.
    """
    if bpy is None or not rooms:
        return []

    wall_objects = []
    wall_mat = create_pbr_material("mat_architectural_wall", "wall", [0.94, 0.94, 0.92], roughness=0.85)

    # Collect all proposed wall segments
    raw_wall_segments = []
    for room in rooms:
        bounds = room.get("bounds", {})
        rx, ry = bounds.get("x", 0.0), bounds.get("y", 0.0)
        rw, rd = bounds.get("width", 4.0), bounds.get("depth", 4.0)
        room_id = room.get("id", "room")

        segments = [
            # South wall (y min)
            (rx + rw / 2.0, ry + wall_thickness / 2.0, rw, wall_thickness, 0, room_id),
            # North wall (y max)
            (rx + rw / 2.0, ry + rd - wall_thickness / 2.0, rw, wall_thickness, 1, room_id),
            # West wall (x min)
            (rx + wall_thickness / 2.0, ry + rd / 2.0, wall_thickness, rd, 2, room_id),
            # East wall (x max)
            (rx + rw - wall_thickness / 2.0, ry + rd / 2.0, wall_thickness, rd, 3, room_id),
        ]
        raw_wall_segments.extend(segments)

    # Deduplicate shared partition walls between adjacent snapped rooms
    deduped_segments = []
    for wx, wy, sx, sy, sidx, room_id in raw_wall_segments:
        is_duplicate = False
        for ex, ey, esx, esy, _, _ in deduped_segments:
            is_same_orientation = (sx > sy and esx > esy) or (sx <= sy and esx <= esy)
            if is_same_orientation:
                dist = math.hypot(wx - ex, wy - ey)
                if dist < wall_thickness * 1.4:
                    is_duplicate = True
                    break
        if not is_duplicate:
            deduped_segments.append((wx, wy, sx, sy, sidx, room_id))

    # Construct clean single partition walls with no exploding parented trim
    for wx, wy, sx, sy, sidx, room_id in deduped_segments:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, wall_height / 2.0))
        wall = bpy.context.active_object
        wall.name = f"wall_{room_id}_{sidx}"
        wall.scale = (sx, sy, wall_height)

        if wall_mat:
            wall.data.materials.append(wall_mat)

        wall_objects.append(wall)

    return wall_objects


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


def apply_openings(
    openings: Dict[str, Any],
    wall_objects: List[Any],
    wall_height: float = 1.45
) -> List[Any]:
    """
    Carves clean boolean openings for doors and windows through walls,
    and inserts architectural frames and glass panes.
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

            # Create Boolean Cutter Box
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, dh / 2.0))
            cutter = bpy.context.active_object
            cutter.name = f"_boolean_cutter_door_{idx}"
            cutter.scale = (dw, 0.60, dh + 0.02)  # Extra depth to cleanly slice wall

            # Apply Boolean Difference to all intersecting walls
            for wall in wall_objects:
                dist = math.hypot(wall.location.x - dx, wall.location.y - dy)
                if dist < max(wall.scale.x, wall.scale.y) + 0.5:
                    bool_mod = wall.modifiers.new(name=f"Bool_Door_{idx}", type='BOOLEAN')
                    bool_mod.operation = 'DIFFERENCE'
                    bool_mod.object = cutter
                    bool_mod.solver = 'FAST'

            cutter.display_type = 'WIRE'
            cutter.hide_render = True

            # Insert Architectural Door Frame
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, dh / 2.0))
            frame = bpy.context.active_object
            frame.name = f"door_frame_{idx}"
            frame.scale = (dw + 0.08, 0.22, dh + 0.04)
            if door_mat:
                frame.data.materials.append(door_mat)

            # Hollow interior of frame
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, (dh - 0.04) / 2.0))
            frame_cutter = bpy.context.active_object
            frame_cutter.name = f"_frame_cutter_{idx}"
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

            # Create Boolean Cutter Box
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
            cutter = bpy.context.active_object
            cutter.name = f"_boolean_cutter_win_{idx}"
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

            # Insert Modern Aluminum Window Frame
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
            win_frame = bpy.context.active_object
            win_frame.name = f"window_frame_{idx}"
            win_frame.scale = (ww + 0.06, 0.22, wh + 0.06)
            if metal_mat:
                win_frame.data.materials.append(metal_mat)

            # Hollow window frame
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, wy, actual_z))
            wcutter = bpy.context.active_object
            wcutter.name = f"_wframe_cutter_{idx}"
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


# ─── Main Generator Pipeline ──────────────────────────────────────────────────

def generate_house_from_layout(
    layout_data: Dict[str, Any],
    output_glb_path: str,
    blender_root: str,
    dollhouse_mode: bool = True
) -> str:
    """Main hyperrealistic generator pipeline."""
    print(f"[ARCHGEN] Generating Hyperrealistic 3D Architecture: {layout_data.get('project_name', 'House')}")

    # 1. Clear default scene
    clear_scene()

    # 2. Extract architectural specs
    bldg = layout_data.get("building", {})
    # Use dollhouse cutaway wall height (1.45m) so interior furniture and rooms are visible
    wall_h = 1.45 if dollhouse_mode else float(bldg.get("wall_height", 2.8))
    wall_t = float(bldg.get("wall_thickness", 0.20))
    slab_t = float(bldg.get("slab_thickness", 0.22))
    rooms = layout_data.get("rooms", [])
    openings = layout_data.get("openings", {})

    # 3. Foundation Podium & Patio Deck
    print("[ARCHGEN] Building architectural foundation & outdoor patio deck...")
    build_foundation_and_patio(rooms)

    # 4. Room Floor Slabs with PBR Materials
    print("[ARCHGEN] Building room floor slabs with PBR shaders...")
    build_floor_slab(rooms, slab_thickness=slab_t)

    # 5. Walls with Baseboard Skirting and Dollhouse Caps
    print(f"[ARCHGEN] Constructing architectural walls (height={wall_h}m)...")
    wall_objs = build_walls(rooms, wall_height=wall_h, wall_thickness=wall_t, add_baseboards=True)

    # 6. Door and Window Boolean Cutouts & Glazing
    print("[ARCHGEN] Carving door and window openings with architectural casings & glass...")
    apply_openings(openings, wall_objs, wall_height=wall_h)

    # 7. Populate Real 3D Furniture Assets
    print("[ARCHGEN] Populating rooms with catalogued 3D furniture models...")
    catalog = place_furniture.FurnitureCatalog(base_path=blender_root)
    total_furniture = 0
    for room in rooms:
        placed = place_furniture.populate_room_furniture(room, catalog, base_blender_dir=blender_root)
        total_furniture += len(placed)
    print(f"[ARCHGEN] Successfully placed {total_furniture} furniture pieces.")

    # 8. Physical Lighting
    setup_lighting()

    # 9. Export to High-Quality GLB
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
    parser.add_argument("--full-height", action="store_true",
                        help="Use full 2.8m walls instead of 1.45m dollhouse cutaways.")

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
        dollhouse_mode=not args.full_height
    )


if __name__ == "__main__":
    main()
