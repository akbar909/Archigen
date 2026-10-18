"""Lighting, stairs, roof, and exterior site features."""

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
from generate_house_opening_models import _try_import_gate_model

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
    """Build a code-compliant U-shaped stair inside its reserved vertical core."""
    if bpy is None or not stair_def:
        return []
    pos = stair_def.get("position", {})
    dim = stair_def.get("dimensions", {})
    sx = float(pos.get("x", 0.0))
    sy = float(pos.get("y", 0.0))
    sw = float(dim.get("width", 2.2))
    sd = float(dim.get("depth", 3.4))
    sh = upper_elevation - lower_elevation
    steps_count = max(16, int(stair_def.get("steps", 18)))
    if steps_count % 2:
        steps_count += 1
    steps_per_flight = steps_count // 2
    riser_h = sh / steps_count
    landing_d = min(max(float(stair_def.get("landing_depth", 0.9)), 0.85), sd * 0.35)
    run_d = sd - landing_d
    tread_d = run_d / steps_per_flight
    central_gap = 0.16
    flight_w = (sw - central_gap) / 2.0
    lower_level = int(stair_def.get("floor_level", round(lower_elevation / max(sh, 0.1))))
    upper_level = lower_level + 1
    name_prefix = f"Stair_L{lower_level}_L{upper_level}"

    wood_mat = create_pbr_material("mat_stair_tread", "wood")
    metal_mat = create_pbr_material("mat_stair_railing", "metal")
    created = []

    def tag(obj, component):
        obj["archgen_floor_level"] = lower_level
        obj["archgen_upper_floor_level"] = upper_level
        obj["archgen_stair_id"] = str(stair_def.get("id", name_prefix))
        obj["archgen_stair_component"] = component

    def add_tread(name, x, y, z, width, depth):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, z))
        obj = bpy.context.active_object
        obj.name = name
        obj.scale = (width, depth, min(0.16, riser_h * 0.85))
        tag(obj, "tread")
        if wood_mat:
            obj.data.materials.append(wood_mat)
        created.append(obj)

    # Lower flight climbs north on the left; upper flight turns at the landing
    # and climbs south on the right. This fits a realistic 1 m clear width.
    for index in range(steps_per_flight):
        tread_z = lower_elevation + (index + 1) * riser_h
        tread_y = sy + (index + 0.5) * tread_d
        add_tread(
            f"{name_prefix}_LowerTread_{index + 1:02d}",
            sx + flight_w / 2.0, tread_y, tread_z,
            flight_w, tread_d + 0.025,
        )

    landing_z = lower_elevation + sh / 2.0
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(sx + sw / 2.0, sy + run_d + landing_d / 2.0, landing_z),
    )
    landing = bpy.context.active_object
    landing.name = f"{name_prefix}_Landing"
    landing.scale = (sw, landing_d, 0.18)
    tag(landing, "landing")
    if wood_mat:
        landing.data.materials.append(wood_mat)
    created.append(landing)

    for index in range(steps_per_flight):
        tread_z = landing_z + (index + 1) * riser_h
        tread_y = sy + run_d - (index + 0.5) * tread_d
        add_tread(
            f"{name_prefix}_UpperTread_{index + 1:02d}",
            sx + flight_w + central_gap + flight_w / 2.0,
            tread_y, tread_z, flight_w, tread_d + 0.025,
        )

    def add_sloped_rail(name, x, y0, y1, z0, z1):
        length_plan = abs(y1 - y0)
        length = math.hypot(length_plan, z1 - z0)
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(x, (y0 + y1) / 2.0, (z0 + z1) / 2.0),
        )
        rail = bpy.context.active_object
        rail.name = name
        rail.scale = (0.045, length, 0.045)
        rail.rotation_euler[0] = math.atan2(z1 - z0, y1 - y0)
        tag(rail, "handrail")
        if metal_mat:
            rail.data.materials.append(metal_mat)
        created.append(rail)

    rail_h = 0.90
    add_sloped_rail(
        f"{name_prefix}_LowerHandrail", sx + 0.04,
        sy, sy + run_d,
        lower_elevation + rail_h, landing_z + rail_h,
    )
    add_sloped_rail(
        f"{name_prefix}_UpperHandrail", sx + sw - 0.04,
        sy + run_d, sy,
        landing_z + rail_h, upper_elevation + rail_h,
    )

    # Landing guard at the turning edge closes the fall hazard between flights.
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(sx + sw / 2.0, sy + sd - 0.04, landing_z + rail_h),
    )
    landing_rail = bpy.context.active_object
    landing_rail.name = f"{name_prefix}_LandingGuard"
    landing_rail.scale = (sw, 0.045, 0.045)
    tag(landing_rail, "guardrail")
    if metal_mat:
        landing_rail.data.materials.append(metal_mat)
    created.append(landing_rail)

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
            # Keep the path surface above the exterior foundation (-0.02 m)
            # but just below the room's finished floor (0.0 m). This prevents
            # diagonal path corners from painting over the entrance room floor.
            bpy.ops.mesh.primitive_cube_add(
                size=1.0,
                location=((start_x + end_x) / 2.0, (start_y + end_y) / 2.0, -0.012),
                rotation=(0.0, 0.0, math.atan2(delta_y, delta_x)),
            )
            path_obj = bpy.context.active_object
            path_obj.name = "Exterior_Main_Entrance_Path"
            path_obj.scale = (path_length, path_w, 0.02)
            if drive_mat:
                path_obj.data.materials.append(drive_mat)
            apply_box_uv_mapping(path_obj, tile_meters=1.0)
            created.append(path_obj)

    return created


