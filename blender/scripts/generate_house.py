"""
Hyperrealistic ArchGen headless 3D architectural house generator.

The implementation is divided by responsibility; this module preserves the
original command-line and import interface.
"""

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Blender's ``--python`` execution does not reliably add the script directory
# to ``sys.path`` before imports are evaluated.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from generate_house_runtime import (
    BLENDER_ROOT,
    SCRIPT_DIR,
    bpy,
    export_glb,
    import_asset,
    mathutils,
    place_furniture,
)

from generate_house_materials import clear_scene
from generate_house_opening_models import _select_door_model_path
from generate_house_openings import apply_openings
from generate_house_structure import (
    _select_house_wall_config,
    _wall_specific_override,
    build_floor_slab,
    build_foundation_and_patio,
    build_walls,
    build_walls_from_network,
)
from generate_house_validation import validate_generated_scene
from generate_house_vertical import (
    build_exterior_features,
    build_intermediate_slab,
    build_roof_structure,
    build_staircase,
    setup_lighting,
)

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
    default_wall_config = (
        bldg.get("default_wall") or bldg.get("wall_style")
        or layout_data.get("default_wall")
    )
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
    stair_openings = []
    for floor_index, floor in enumerate(floors):
        level = int(floor.get("level", floor_index))
        for opening in floor.get("stair_openings", []):
            adapted_opening = dict(opening)
            adapted_opening["floor_level"] = level
            stair_openings.append(adapted_opening)
    build_floor_slab(rooms, slab_thickness=slab_t, stair_openings=stair_openings)

    # 5. Walls with Baseboard Skirting and Dollhouse Caps
    print(f"[ARCHGEN] Constructing architectural walls (height={wall_h}m)...")
    if wall_network:
        wall_objs = build_walls_from_network(
            wall_network, rooms, wall_height=wall_h, default_thickness=wall_t,
            default_wall_config=default_wall_config,
        )
        auto_doors = []
    else:
        # Backward compatibility for stored legacy projects only.
        wall_objs, auto_doors = build_walls(
            rooms, wall_height=wall_h, wall_thickness=wall_t, add_baseboards=True,
            default_wall_config=default_wall_config,
        )

    # 6. Door and Window Boolean Cutouts & Glazing
    print(f"[ARCHGEN] Carving door and window openings (input doors={len(openings.get('doors', []))}, auto partition doors={len(auto_doors)})...")
    all_doors = list(openings.get("doors", [])) + auto_doors
    combined_openings = {"doors": all_doors, "windows": openings.get("windows", [])}
    apply_openings(combined_openings, wall_objs, wall_height=wall_h)

    # 7. Multi-Floor Staircases & Upper Intermediate Slabs
    if len(floors) > 1:
        print("[ARCHGEN] Building aligned stair flights for every adjacent floor pair...")
        default_floor_height = float(bldg.get("floor_height", wall_h))
        for floor_index, floor in enumerate(floors):
            lower_elevation = float(floor.get("elevation", floor_index * default_floor_height))
            upper_elevation = lower_elevation + float(floor.get("floor_height", default_floor_height))
            for stair_def in floor.get("stairs", []):
                build_staircase(
                    stair_def,
                    lower_elevation=lower_elevation,
                    upper_elevation=upper_elevation,
                )
        # Upper room slabs already exist; build_floor_slab carved their
        # canonical stair openings, so no duplicate bounding slab is needed.

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
