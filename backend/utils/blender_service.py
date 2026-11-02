"""
blender_service.py
==================
Client service responsible for communicating with the Headless Blender worker.
Transforms Gemini architectural layout JSON into Blender-compatible specifications,
invokes generation, and retrieves the exported .glb model URL.
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import requests

from config import (
    BLENDER_ENABLED,
    BLENDER_SERVICE_URL,
    BLENDER_TIMEOUT_SECONDS,
)
from utils.s3_storage import resolve_s3_url_to_presigned
from utils.blender_failures import worker_failure_reason

logger = logging.getLogger(__name__)


def _material_info(value: Any) -> Dict[str, Any]:
    """Normalize legacy string finishes and current structured finish records."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        return {"pattern": value}
    return {}


def hex_to_rgb(hex_str: str) -> List[float]:
    """Converts hex color string to normalized RGB list [r, g, b]."""
    hex_str = str(hex_str).lstrip("#")
    if len(hex_str) == 6:
        try:
            return [
                round(int(hex_str[0:2], 16) / 255.0, 3),
                round(int(hex_str[2:4], 16) / 255.0, 3),
                round(int(hex_str[4:6], 16) / 255.0, 3),
            ]
        except ValueError:
            pass
    return [0.8, 0.8, 0.8]


def _aligned_wall_item(item: Dict[str, Any], room: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve reviewed axes without mutating an older saved version."""
    if not item.get('wall_mounted') or not item.get('s3_key'):
        return item
    from utils.asset_catalog import _entry
    asset = _entry(item['s3_key'], 'saved')
    mounting = (asset or {}).get('mounting', {})
    if not mounting.get('orientation_verified'):
        return item
    result = {**item, 'canonical_yaw_offset_deg': asset['canonical_yaw_offset_deg'],
              'canonical_pitch_offset_deg': asset['canonical_pitch_offset_deg']}
    rp = room.get('position', room.get('bounds', {}))
    rd = room.get('dimensions', room.get('bounds', {}))
    anchor = item.get('wall_anchor') or {}
    face = item.get('wall_face')
    if not face and 'x' in anchor and 'y' in anchor:
        outside = {
            'left': float(rp.get('x', 0)) - anchor['x'],
            'right': anchor['x'] - float(rp.get('x', 0)) - float(rd.get('width', 4)),
            'back': float(rp.get('y', 0)) - anchor['y'],
            'front': anchor['y'] - float(rp.get('y', 0)) - float(rd.get('depth', 4)),
        }.get(item.get('wall_side'), 0)
        face = 'exterior' if outside > .03 else 'interior'
    result['wall_face'] = face or 'interior'
    if item.get('room_id') != 'exterior_ground':
        side=item.get('wall_side')
        normal=dict(item.get('wall_normal') or {})
        expected={'front':(0,1),'back':(0,-1),'left':(1,0),'right':(-1,0)}.get(side)
        if expected and face == 'exterior':
            expected = (-expected[0], -expected[1])
        if expected and normal.get('x',0)*expected[0]+normal.get('z',0)*expected[1]<0:
            normal.update(x=-normal.get('x',0),z=-normal.get('z',0))
            result['wall_normal']=normal
    version = int(mounting.get('orientation_version', 0))
    dimensions = dict(item.get('dimensions', {}))
    if version > int(item.get('wall_orientation_version', 0)):
        height = float(dimensions.get('height') or asset['dimensions']['height'])
        factor = height / asset['dimensions']['height']
        dimensions = {key: value * factor for key, value in asset['dimensions'].items()}
        result['dimensions'] = dimensions
        pos = dict(item.get('position', {}))
        rp = room.get('position', room.get('bounds', {}))
        rd = room.get('dimensions', room.get('bounds', {}))
        offset = dimensions['depth'] / 2 + 0.12
        side = item.get('wall_side')
        if side == 'left': pos['x'] = float(rp.get('x', 0)) + offset
        if side == 'right': pos['x'] = float(rp.get('x', 0)) + float(rd.get('width', 4)) - offset
        if side == 'back': pos['y'] = float(rp.get('y', 0)) + offset
        if side == 'front': pos['y'] = float(rp.get('y', 0)) + float(rd.get('depth', 4)) - offset
        result['position'] = pos
    if 'x' in anchor and 'y' in anchor:
        normal = result.get('wall_normal') or {}
        nx, nz = float(normal.get('x', 0)), float(normal.get('z', 0))
        length = (nx * nx + nz * nz) ** .5
        if length > .01:
            nx, nz = nx / length, nz / length
            pos = dict(result.get('position', {}))
            offset = float(dimensions.get('depth', .08)) / 2 + .012
            distance = (float(pos.get('x', 0)) - anchor['x']) * nx - (float(pos.get('y', 0)) - anchor['y']) * nz
            pos['x'] = float(pos.get('x', 0)) + nx * (offset - distance)
            pos['y'] = float(pos.get('y', 0)) - nz * (offset - distance)
            result['position'] = pos
    result['wall_orientation_version'] = version
    return result


def _canonical_blender_layout(
    design_data: Dict[str, Any], house_id: str, style: str
) -> Dict[str, Any]:
    """Losslessly adapt architectural v3 coordinates to Blender (X, Y, Z)."""
    building = design_data.get("building", {})
    adapted_rooms: List[Dict[str, Any]] = []
    walls: List[Dict[str, Any]] = []
    doors: List[Dict[str, Any]] = []
    windows: List[Dict[str, Any]] = []
    expected_furniture: List[str] = []
    seen_furniture: set[str] = set()

    for floor_index, floor in enumerate(design_data.get("floors", [])):
        floor_id = floor.get("id") or f"floor_{floor_index + 1}"
        level = int(floor.get("level", floor_index))
        for wall in floor.get("walls", []):
            if not isinstance(wall, dict):
                continue
            adapted = dict(wall)
            face_overrides = design_data.get("wall_face_overrides", {}).get(str(wall.get("id")), {})
            if face_overrides:
                adapted["material_overrides"] = {**wall.get("material_overrides", {}), **face_overrides}
            adapted["floor_id"] = floor_id
            adapted["floor_level"] = level
            walls.append(adapted)

        for collection, target in (("doors", doors), ("windows", windows)):
            for opening in floor.get(collection, []):
                if not isinstance(opening, dict):
                    continue
                pos = opening.get("position", {})
                dim = opening.get("dimensions", {})
                adapted = dict(opening)
                adapted["position"] = [
                    round(float(pos.get("x", 0.0)), 3),
                    round(float(pos.get("y", 0.0)), 3),
                    round(float(pos.get("z", 0.0)), 3),
                ]
                adapted["width"] = float(opening.get("width", dim.get("width", dim.get("w", 0.9))))
                adapted["height"] = float(opening.get("height", dim.get("height", dim.get("h", 2.1))))
                adapted["floor_id"] = floor_id
                adapted["floor_level"] = level
                target.append(adapted)

        floor_items = {
            str(item.get("id")): item for item in floor.get("furniture", [])
            if isinstance(item, dict) and item.get("id")
        }
        suppressed = {str(fid) for item in floor_items.values() for fid in item.get('suppressed_furniture_ids', [])}
        suppressed.update(str(fid) for fid in design_data.get('deleted_furniture_ids', []))
        floor_items = {fid: item for fid, item in floor_items.items() if fid not in suppressed}
        for room_index, room in enumerate(floor.get("rooms", [])):
            room_id = room.get("id") or f"room_{floor_index + 1}_{room_index + 1}"
            pos = room.get("position", {})
            dim = room.get("dimensions", {})
            bx, by, bz = float(pos.get("x", 0.0)), float(pos.get("y", 0.0)), float(pos.get("z", level * 3.0))
            bw, bd = float(dim.get("width", 1.0)), float(dim.get("depth", 1.0))
            materials = room.get("materials", {})
            pbr = room.get("pbr_material", {})
            floor_info = _material_info(materials.get("floor", pbr.get("floor", {})))
            wall_info = _material_info(materials.get("walls", materials.get("wall", pbr.get("walls", pbr.get("wall", {})))))

            ids = [
                fid for fid, item in floor_items.items()
                if str(item.get("room_id") or item.get("roomId")) == str(room_id)
            ]
            furniture_reqs = []
            for fid in ids:
                if fid in seen_furniture:
                    continue
                seen_furniture.add(fid)
                item = _aligned_wall_item(floor_items[fid], room)
                fpos, fdim = item.get("position", {}), item.get("dimensions", {})
                category = str(item.get("category") or item.get("asset") or item.get("type") or "furniture").lower()
                furniture_reqs.append({
                    "id": fid,
                    "instance_id": fid,
                    "category": category,
                    "preferred_id": item.get("asset_id") or item.get("asset") or item.get("model_id"),
                    "placement_hint": ("wall_exact" if item.get('wall_mounted') else "user_exact")
                        if item.get('client_edited_3d') else item.get("placement_hint", "exact"),
                    "anchor_wall": item.get("anchor_wall"),
                    "wall_mounted": bool(item.get("wall_mounted", False)),
                    "wall_side": item.get("wall_side"),
                    "wall_face": item.get("wall_face"),
                    "wall_normal": item.get("wall_normal"),
                    "wall_anchor": item.get("wall_anchor"),
                    "wall_orientation_version": item.get("wall_orientation_version", 0),
                    "ceiling_mounted": bool(item.get("ceiling_mounted", False)),
                    "ceiling_clearance": max(0.0, float(item.get("ceiling_clearance", 0.06))),
                    "canonical_yaw_offset_deg": item.get("canonical_yaw_offset_deg"),
                    "canonical_pitch_offset_deg": item.get("canonical_pitch_offset_deg"),
                    "mount_height": max(0.0, float(item.get("mount_height", 0.0) or 0.0)),
                    "position": [
                        round(float(fpos.get("x", bx + bw / 2.0)), 3),
                        round(float(fpos.get("y", by + bd / 2.0)), 3),
                        round(float(fpos.get("z", bz)), 3),
                    ],
                    "rotation_deg": float(item.get("rotation", item.get("rotation_y", 0.0))),
                    "flip_x": bool(item.get("flip_x", False)),
                    "flip_y": bool(item.get("flip_y", False)),
                    "dimensions": {
                        "width": float(fdim.get("width", 0.8)),
                        "depth": float(fdim.get("depth", 0.8)),
                        "height": float(fdim.get("height", 0.8)),
                    },
                    "room_id": room_id,
                })
                expected_furniture.append(fid)

            adapted_rooms.append({
                "id": room_id,
                "name": room.get("name") or room.get("type") or f"Room {room_index + 1}",
                "type": str(room.get("type") or "room").lower().replace(" ", "_"),
                "style": style,
                "floor_id": floor_id,
                "floor_level": level,
                "bounds": {"x": round(bx, 3), "y": round(by, 3), "z": round(bz, 3), "width": round(bw, 3), "depth": round(bd, 3)},
                "height": float(dim.get("height", building.get("floor_height", 3.0))),
                "flooring": {"material": floor_info.get("pattern", "wood_planks"), "color": hex_to_rgb(floor_info.get("color", "#CCCCCC"))},
                "walls": {"pattern": wall_info.get("pattern", "plaster"), "color": hex_to_rgb(wall_info.get("color", "#F0EDE8"))},
                "furniture_requirements": furniture_reqs,
            })

    # Layered outdoor assets are kept outside the architectural furniture
    # inventory so ordinary saves never repack them. An explicit Finalize GLB
    # merges them through the first ground-floor room's export collection.
    exterior_assets = design_data.get("exterior", {}).get("assets", [])
    ground_export_room = next(
        (room for room in adapted_rooms if int(room.get("floor_level", 0)) == 0),
        adapted_rooms[0] if adapted_rooms else None,
    )
    if ground_export_room and isinstance(exterior_assets, list):
        for item in exterior_assets:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            fid = str(item["id"])
            if fid in seen_furniture:
                continue
            seen_furniture.add(fid)
            position = item.get("position", {})
            dimensions = item.get("dimensions", {})
            ground_export_room["furniture_requirements"].append({
                "id": fid,
                "instance_id": fid,
                "category": str(item.get("category") or item.get("asset") or "outdoor").lower(),
                "preferred_id": item.get("asset_id") or item.get("model_id") or item.get("asset"),
                "placement_hint": "wall_exact" if item.get("wall_mounted") else "user_exact",
                "anchor_wall": item.get("anchor_wall"),
                "wall_mounted": bool(item.get("wall_mounted")),
                "wall_side": item.get("wall_side"),
                "wall_face": item.get("wall_face"),
                "wall_normal": item.get("wall_normal"),
                "wall_anchor": item.get("wall_anchor"),
                "canonical_yaw_offset_deg": item.get("canonical_yaw_offset_deg"),
                "canonical_pitch_offset_deg": item.get("canonical_pitch_offset_deg"),
                "mount_height": float(item.get("mount_height", 0.0) or 0.0),
                "position": [
                    round(float(position.get("x", 0.0)), 3),
                    round(float(position.get("y", 0.0)), 3),
                    round(float(position.get("z", 0.0)), 3),
                ],
                "rotation_deg": float(item.get("rotation", item.get("rotation_y", 0.0))),
                "flip_x": bool(item.get("flip_x", False)),
                "flip_y": bool(item.get("flip_y", False)),
                "dimensions": {
                    "width": float(dimensions.get("width", 1.0)),
                    "depth": float(dimensions.get("depth", 1.0)),
                    "height": float(dimensions.get("height", 1.0)),
                },
                "room_id": "exterior_ground",
            })
            expected_furniture.append(fid)

    return {
        "house_id": house_id,
        "project_name": f"ArchiGen {style.capitalize()} House",
        "unit": "meters",
        "coordinate_system": {"horizontal": ["x", "y"], "vertical": "z", "origin": "plot_south_west"},
        "building": {
            "wall_height": float(building.get("floor_height", 3.0)),
            "floor_height": float(building.get("floor_height", 3.0)),
            "wall_thickness": float(building.get("wall_thickness", 0.2)),
            "slab_thickness": float(building.get("slab_thickness", 0.22)),
            "floors": len(design_data.get("floors", [])) or 1,
        },
        "floors": design_data.get("floors", []),
        "rooms": adapted_rooms,
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "openings": {"doors": doors, "windows": windows},
        "roof": design_data.get("roof", {}),
        "exterior": design_data.get("exterior", {}),
        "site": design_data.get("site", {}),
        "generation_validation": design_data.get("generation_validation", design_data.get("validation", {})),
        "expected_inventory": {
            "furniture_ids": expected_furniture,
            "furniture_count": len(expected_furniture),
            "door_ids": [str(item.get("id")) for item in doors if item.get("id")],
            "window_ids": [str(item.get("id")) for item in windows if item.get("id")],
        },
    }


def adapt_gemini_to_blender_layout(
    design_data: Dict[str, Any],
    project_id: Optional[str] = None,
    version_num: int = 1,
) -> Dict[str, Any]:
    """
    Translates Gemini's room/furniture output into the standardized schema
    expected by blender/scripts/generate_house.py.
    """
    house_id = f"proj_{project_id or 'anon'}_v{version_num}_{uuid.uuid4().hex[:6]}"
    project = design_data.get("project") if isinstance(design_data.get("project"), dict) else {}
    house = design_data.get("house") if isinstance(design_data.get("house"), dict) else {}
    style = design_data.get("style") or project.get("style") or house.get("style") or "modern"

    # Architectural v3 floors are authoritative.  Keep the legacy adapter only
    # for stored pre-v3 projects which do not yet contain canonical floors.
    if isinstance(design_data.get("floors"), list) and design_data.get("floors"):
        return _canonical_blender_layout(design_data, house_id, style)

    raw_rooms = design_data.get("rooms", [])
    adapted_rooms = []
    collected_doors = []
    collected_windows = []

    for idx, r in enumerate(raw_rooms):
        room_id = r.get("id") or f"room_{idx + 1}"
        room_type = (r.get("type") or "Living Room").lower().replace(" ", "_")
        w = float(r.get("width") or 6.0)
        d = float(r.get("length") or r.get("depth") or 6.0)

        # Handle bounds or position format accurately
        pos = r.get("position", {})
        bounds = r.get("bounds", {})
        bw = float(r.get("dimensions", {}).get("width", r.get("width", w)))
        bd = float(r.get("dimensions", {}).get("depth", r.get("length", d)))

        if bounds:
            bx = float(bounds.get("x", 0.0))
            by = float(bounds.get("y", 0.0))
            bw = float(bounds.get("width", bw))
            bd = float(bounds.get("depth", bd))
        else:
            bx = float(pos.get("x", 0.0))
            by = float(pos.get("y", pos.get("z", 0.0)))

        # Flooring and Wall material extraction
        materials = r.get("materials", {})
        pbr = r.get("pbr_material", {})
        floor_info = _material_info(materials.get("floor", pbr.get("floor", {})))
        floor_color = hex_to_rgb(floor_info.get("color", "#CCCCCC"))
        floor_pattern = floor_info.get("pattern", "wood_planks")

        wall_info = _material_info(materials.get("wall", pbr.get("wall", {})))
        wall_color = hex_to_rgb(wall_info.get("color", "#F0EDE8"))
        wall_pattern = wall_info.get("pattern", "plaster")

        # Furniture extraction: combine room-level (old) + top-level filtered by roomId (new)
        furniture_reqs = []
        room_furniture = list(r.get("furniture", []))

        # Also gather top-level furniture assigned to this room
        top_level_furniture = design_data.get("furniture", [])
        if isinstance(top_level_furniture, list):
            for tf in top_level_furniture:
                if isinstance(tf, dict) and tf.get("roomId") == room_id:
                    room_furniture.append(tf)

        for f in room_furniture:
            # Support both old format ("type") and new format ("asset")
            cat = str(f.get("category") or f.get("asset") or f.get("type", "sofa")).lower()
            fpos = f.get("position", {})
            fx = float(fpos.get("x", 0.0)) if isinstance(fpos, dict) else 0.0
            fy_val = float(fpos.get("y", 0.0)) if isinstance(fpos, dict) else 0.0
            fz_val = float(fpos.get("z", 0.0)) if isinstance(fpos, dict) else 0.0
            elev = float(fpos.get("elevation", 0.0)) if isinstance(fpos, dict) else 0.0
            rot = float(f.get("rotation", f.get("rotation_y", 0.0)))

            # If fx is already an absolute scene position within the room bounds:
            if (bx - 0.5) <= fx <= (bx + bw + 0.5):
                abs_x = fx
                abs_y = fy_val if (by - 0.5) <= fy_val <= (by + bd + 0.5) else (fz_val if (by - 0.5) <= fz_val <= (by + bd + 0.5) else (by + bd / 2.0))
            else:
                # Relative to room origin
                abs_x = bx + (bw / 2.0) + fx
                abs_y = by + (bd / 2.0) + (fy_val if fy_val != 0 else fz_val)

            # Target elevation: finished floor slab top (0.22m for ground floor, 3.22m for upper)
            room_elev = float(r.get("position", {}).get("z", 0.0))
            target_z = elev if elev > 0.05 else (fz_val if fz_val > 0.05 and abs(fz_val - abs_y) > 0.5 else room_elev + 0.22)
            if target_z < 0.20:
                target_z = 0.22

            furniture_reqs.append({
                "category": cat,
                "preferred_id": f.get("asset_id") or f.get("preferred_id") or f.get("id"),
                "placement_hint": "center",
                "anchor_wall": f.get("anchor_wall"),
                "wall_mounted": bool(f.get("wall_mounted", False)),
                "wall_side": f.get("wall_side"),
                "wall_face": f.get("wall_face"),
                "wall_normal": f.get("wall_normal"),
                "wall_anchor": f.get("wall_anchor"),
                "mount_height": max(0.0, float(f.get("mount_height", 0.0) or 0.0)),
                "position": [round(abs_x, 2), round(abs_y, 2), round(target_z, 2)],
                "rotation_deg": rot,
            })

        # Smart adaptive furniture cap: 3 for small rooms (<6m²), 6 for large rooms (>=16m²), 4 for standard rooms
        room_area = bw * bd
        max_furn = 3 if room_area < 6.0 else (6 if room_area >= 16.0 else 4)
        if len(furniture_reqs) > max_furn:
            priority_cats = {"bed", "sofa", "dining_table", "kitchen_island", "kitchen_cabinet", "bathtub", "toilet", "desk"}
            furniture_reqs.sort(key=lambda item: 0 if item["category"] in priority_cats else 1)
            furniture_reqs = furniture_reqs[:max_furn]

        # Doors inside room
        for d_item in r.get("doors", []):
            dpos = d_item.get("position", {})
            if isinstance(dpos, dict):
                raw_dx = float(dpos.get("x", 0.0))
                raw_dy = float(dpos.get("y", dpos.get("z", 0.0)))
            elif isinstance(dpos, (list, tuple)):
                raw_dx = float(dpos[0]) if len(dpos) > 0 else 0.0
                raw_dy = float(dpos[1]) if len(dpos) > 1 else 0.0
            else:
                raw_dx, raw_dy = 0.0, 0.0

            if (bx - 0.5) <= raw_dx <= (bx + bw + 0.5):
                abs_dx = raw_dx
                abs_dy = raw_dy
            else:
                abs_dx = bx + (bw / 2.0) + raw_dx
                abs_dy = by + (bd / 2.0) + raw_dy

            dim = d_item.get("dimensions", {})
            collected_doors.append({
                "id": d_item.get("id") or f"door_{len(collected_doors)+1}",
                "type": "interior_door",
                "position": [round(abs_dx, 2), round(abs_dy, 2), 0.0],
                "width": float(dim.get("w", d_item.get("width", 0.9))),
                "height": float(dim.get("h", d_item.get("height", 2.1))),
                "wall": d_item.get("wall", "front"),
            })

        # Windows inside room
        for w_item in r.get("windows", []):
            wpos = w_item.get("position", {})
            if isinstance(wpos, dict):
                raw_wx = float(wpos.get("x", 0.0))
                raw_wy = float(wpos.get("y", wpos.get("z", 0.0)))
            elif isinstance(wpos, (list, tuple)):
                raw_wx = float(wpos[0]) if len(wpos) > 0 else 0.0
                raw_wy = float(wpos[1]) if len(wpos) > 1 else 0.0
            else:
                raw_wx, raw_wy = 0.0, 0.0

            if (bx - 0.5) <= raw_wx <= (bx + bw + 0.5):
                abs_wx = raw_wx
                abs_wy = raw_wy
            else:
                abs_wx = bx + (bw / 2.0) + raw_wx
                abs_wy = by + (bd / 2.0) + raw_wy

            dim = w_item.get("dimensions", {})
            collected_windows.append({
                "id": w_item.get("id") or f"win_{len(collected_windows)+1}",
                "position": [round(abs_wx, 2), round(abs_wy, 2), 1.0],
                "width": float(dim.get("w", w_item.get("width", 1.5))),
                "height": float(dim.get("h", w_item.get("height", 1.4))),
                "wall": w_item.get("wall", "front"),
            })

        adapted_rooms.append({
            "id": room_id,
            "name": r.get("name") or r.get("type") or f"Room {idx+1}",
            "type": room_type,
            "style": style,
            "bounds": {
                "x": round(bx, 2),
                "y": round(by, 2),
                "width": round(bw, 2),
                "depth": round(bd, 2),
            },
            "flooring": {
                "material": floor_pattern,
                "color": floor_color,
            },
            "walls": {
                "pattern": wall_pattern,
                "color": wall_color,
            },
            "furniture_requirements": furniture_reqs,
        })

    # Add top-level doors/windows if not already captured from rooms
    seen_door_ids = {d["id"] for d in collected_doors if "id" in d}
    for d_item in design_data.get("doors", []):
        if isinstance(d_item, dict):
            d_id = d_item.get("id")
            if d_id and d_id in seen_door_ids:
                continue
            pos = d_item.get("position", {})
            dim = d_item.get("dimensions", {})
            if isinstance(pos, dict):
                dx = float(pos.get("x", 0.0))
                if "y" in pos and "z" in pos:
                    if float(pos.get("z", 0.0)) <= 0.5 and float(pos.get("y", 0.0)) > 0.5:
                        dy = float(pos.get("y", 0.0))
                        delev = float(pos.get("z", 0.0))
                    else:
                        dy = float(pos.get("z", 0.0))
                        delev = float(pos.get("y", 0.0))
                elif "y" in pos:
                    dy = float(pos.get("y", 0.0))
                    delev = 0.0
                else:
                    dy = float(pos.get("z", 0.0))
                    delev = 0.0
            elif isinstance(pos, (list, tuple)):
                dx = float(pos[0]) if len(pos) > 0 else 0.0
                dy = float(pos[1]) if len(pos) > 1 else 0.0
                delev = float(pos[2]) if len(pos) > 2 else 0.0
            else:
                dx, dy, delev = 0.0, 0.0, 0.0
            collected_doors.append({
                "id": d_id or f"door_{len(collected_doors)+1}",
                "type": "door",
                "position": [round(dx, 2), round(dy, 2), round(delev, 2)],
                "width": float(dim.get("w", d_item.get("width", 0.95))),
                "height": float(dim.get("h", d_item.get("height", 2.1))),
                "wall": d_item.get("wall", "front"),
            })
            if d_id:
                seen_door_ids.add(d_id)

    seen_win_ids = {w["id"] for w in collected_windows if "id" in w}
    for w_item in design_data.get("windows", []):
        if isinstance(w_item, dict):
            w_id = w_item.get("id")
            if w_id and w_id in seen_win_ids:
                continue
            pos = w_item.get("position", {})
            dim = w_item.get("dimensions", {})
            if isinstance(pos, dict):
                wx = float(pos.get("x", 0.0))
                if "y" in pos and "z" in pos:
                    if float(pos.get("z", 0.0)) <= 1.5 and float(pos.get("y", 0.0)) > 1.5:
                        wy = float(pos.get("y", 0.0))
                        welev = float(pos.get("z", 1.0))
                    else:
                        wy = float(pos.get("z", 0.0))
                        welev = float(pos.get("y", 1.0))
                elif "y" in pos:
                    wy = float(pos.get("y", 0.0))
                    welev = 1.0
                else:
                    wy = float(pos.get("z", 0.0))
                    welev = 1.0
            elif isinstance(pos, (list, tuple)):
                wx = float(pos[0]) if len(pos) > 0 else 0.0
                wy = float(pos[1]) if len(pos) > 1 else 0.0
                welev = float(pos[2]) if len(pos) > 2 else 1.0
            else:
                wx, wy, welev = 0.0, 0.0, 1.0
            collected_windows.append({
                "id": w_id or f"win_{len(collected_windows)+1}",
                "position": [round(wx, 2), round(wy, 2), round(welev, 2)],
                "width": float(dim.get("w", w_item.get("width", 1.4))),
                "height": float(dim.get("h", w_item.get("height", 1.2))),
                "wall": w_item.get("wall", "front"),
            })
            if w_id:
                seen_win_ids.add(w_id)

    return {
        "house_id": house_id,
        "project_name": f"ArchGen {style.capitalize()} House",
        "unit": "meters",
        "building": {
            "wall_height": 2.8,
            "wall_thickness": 0.2,
            "slab_thickness": 0.25,
            "floors": len(design_data.get("floors", [])) or 1,
        },
        "floors": design_data.get("floors", []),
        "roof": design_data.get("roof", {}),
        "exterior": design_data.get("exterior", {}),
        "site": design_data.get("site", {}),
        "rooms": adapted_rooms,
        "doors": collected_doors,
        "windows": collected_windows,
        "openings": {
            "doors": collected_doors,
            "windows": collected_windows,
        },
    }


class BlenderGenerationError(RuntimeError):
    """An actionable generation failure safe to return with a job status."""


def generate_3d_house_model(
    design_data: Dict[str, Any],
    project_id: Optional[str] = None,
    version_num: int = 1,
    raise_on_error: bool = False,
) -> Optional[str]:
    """
    Sends layout to Blender worker microservice to procedurally build the 3D model.
    Returns the GLB download URL or None if generation is disabled or fails.
    """
    if not BLENDER_ENABLED:
        logger.info("[BLENDER] 3D Generation is disabled in config (BLENDER_ENABLED=False).")
        if raise_on_error:
            raise BlenderGenerationError('3D generation is disabled in the backend configuration.')
        return None

    try:
        adapted_layout = adapt_gemini_to_blender_layout(design_data, project_id, version_num)
        endpoint = f"{BLENDER_SERVICE_URL.rstrip('/')}/generate"

        logger.info(f"[BLENDER] Invoking Blender worker at {endpoint} for house {adapted_layout['house_id']}...")
        response = requests.post(
            endpoint,
            json={"layout": adapted_layout},
            headers={"Content-Type": "application/json"},
            timeout=BLENDER_TIMEOUT_SECONDS,
        )

        if response.status_code == 200:
            result = response.json()
            raw_glb_url = result.get("glb_url")
            if not raw_glb_url:
                raise BlenderGenerationError('The Blender worker completed without returning a 3D model.')
            glb_url = resolve_s3_url_to_presigned(raw_glb_url) or raw_glb_url
            logger.info(f"[BLENDER] Generation succeeded! GLB URL: {glb_url}")
            return glb_url
        else:
            logger.warning(
                f"[BLENDER] Worker responded with HTTP {response.status_code}: {response.text[:300]}"
            )
            try:
                payload = response.json()
                reason = worker_failure_reason(payload)
                if isinstance(payload, dict):
                    for stream in ('details', 'stderr', 'stdout'):
                        if payload.get(stream):
                            logger.warning('[BLENDER] Worker %s:\n%s', stream, str(payload[stream])[-12000:])
            except (ValueError, AttributeError):
                reason = 'The worker returned an invalid response.'
            raise BlenderGenerationError(f'Blender worker error ({response.status_code}): {reason}')

    except requests.exceptions.ConnectionError:
        logger.warning(
            f"[BLENDER] Could not connect to Blender worker at {BLENDER_SERVICE_URL}. "
            "Ensure worker_server.py is running or EC2 instance is online."
        )
        if raise_on_error:
            raise BlenderGenerationError('Cannot reach the Blender worker. Check that the worker service is running.') from None
        return None
    except requests.exceptions.Timeout:
        logger.warning(f"[BLENDER] Request timed out after {BLENDER_TIMEOUT_SECONDS}s.")
        if raise_on_error:
            raise BlenderGenerationError(f'The Blender worker did not finish within {BLENDER_TIMEOUT_SECONDS} seconds. Check its logs before retrying.') from None
        return None
    except BlenderGenerationError:
        if raise_on_error:
            raise
        return None
    except Exception as e:
        logger.error(f"[BLENDER] Unexpected error during 3D generation: {e}")
        if raise_on_error:
            raise BlenderGenerationError('The 3D build failed unexpectedly. Check the backend logs for details.') from None
        return None
