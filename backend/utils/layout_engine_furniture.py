"""Room-aware furniture placement."""

import copy
import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

from utils.architectural_schema_v3 import (
    MIN_ROOM_DIMENSIONS,
    VALID_ORIENTATIONS,
    VALID_ROOM_TYPES,
    VALID_STYLES,
    ft_to_m,
    m_to_ft,
)

class FurnitureMixin:
    def _place_furniture_for_rooms(
        self,
        rooms: List[Dict[str, Any]],
        style: str,
        elevation: float = 0.0,
        doors: Optional[List[Dict[str, Any]]] = None,
        stair_zones: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Positions architectural furniture with clearance, solid wall anchoring,
        and proper rotation angles for both 2D and 3D viewers.
        """
        furniture = []
        # Architectural Z is the finished-floor elevation.  The Blender slab is
        # generated below this plane, so furniture rests exactly at elevation.
        floor_elev = elevation

        for r in rooms:
            rid = r["id"]
            rtype = r["type"]
            rx = r["position"]["x"]
            ry = r["position"]["y"]
            rw = r["dimensions"]["width"]
            rd = r["dimensions"]["depth"]
            cx = round(rx + rw / 2.0, 2)
            cy = round(ry + rd / 2.0, 2)

            def _door_xy(door: Dict[str, Any]) -> Tuple[float, float, float]:
                pos = door.get("position", {})
                if isinstance(pos, dict):
                    return float(pos.get("x", 0.0)), float(pos.get("y", 0.0)), float(pos.get("z", floor_elev))
                if isinstance(pos, (list, tuple)):
                    return (
                        float(pos[0]) if len(pos) > 0 else 0.0,
                        float(pos[1]) if len(pos) > 1 else 0.0,
                        float(pos[2]) if len(pos) > 2 else floor_elev,
                    )
                return 0.0, 0.0, floor_elev

            def _nearest_side(x: float, y: float) -> str:
                distances = {
                    "south": abs(y - ry), "north": abs((ry + rd) - y),
                    "west": abs(x - rx), "east": abs((rx + rw) - x),
                }
                return min(distances, key=distances.get)

            door_zones: List[Tuple[float, float, float, float]] = []
            for door in doors or []:
                dx, dy, dz = _door_xy(door)
                if abs(dz - floor_elev) > 0.35:
                    continue
                connected = {
                    str(value) for value in (door.get("connected_room_ids") or door.get("connected_rooms") or [])
                }
                direct_room = door.get("room_id") or door.get("roomId")
                if direct_room is not None:
                    connected.add(str(direct_room))
                on_boundary = (
                    rx - 0.3 <= dx <= rx + rw + 0.3
                    and ry - 0.3 <= dy <= ry + rd + 0.3
                    and min(abs(dx - rx), abs(dx - (rx + rw)), abs(dy - ry), abs(dy - (ry + rd))) <= 0.35
                )
                if str(rid) not in connected and not on_boundary:
                    continue
                half_width = float(door.get("width", 0.9)) / 2.0 + 0.35
                side = _nearest_side(dx, dy)
                if side == "south":
                    zone = (dx - half_width, ry, dx + half_width, min(ry + rd, ry + 1.15))
                elif side == "north":
                    zone = (dx - half_width, max(ry, ry + rd - 1.15), dx + half_width, ry + rd)
                elif side == "west":
                    zone = (rx, dy - half_width, min(rx + rw, rx + 1.15), dy + half_width)
                else:
                    zone = (max(rx, rx + rw - 1.15), dy - half_width, rx + rw, dy + half_width)
                door_zones.append((max(rx, zone[0]), max(ry, zone[1]), min(rx + rw, zone[2]), min(ry + rd, zone[3])))

            # A stair is circulation, not furniture. Reserve its complete plan
            # footprint (plus a small landing clearance) on every connected
            # floor so beds, desks and cabinets cannot block either flight.
            circulation_zones: List[Tuple[float, float, float, float]] = list(door_zones)
            for stair in stair_zones or []:
                spos = stair.get("position", {})
                sdim = stair.get("dimensions", {})
                sx = float(spos.get("x", 0.0))
                sy = float(spos.get("y", 0.0))
                sw = float(sdim.get("width", 0.0))
                sd = float(sdim.get("depth", 0.0))
                margin = 0.20
                zone = (sx - margin, sy - margin, sx + sw + margin, sy + sd + margin)
                clipped = (
                    max(rx, zone[0]), max(ry, zone[1]),
                    min(rx + rw, zone[2]), min(ry + rd, zone[3]),
                )
                if clipped[0] < clipped[2] and clipped[1] < clipped[3]:
                    circulation_zones.append(clipped)

            def _add(f_dict):
                fw = float(f_dict.get("dimensions", {}).get("width", 0.8))
                fd = float(f_dict.get("dimensions", {}).get("depth", 0.8))
                rotation = float(f_dict.get("rotation", 0.0))
                angle = math.radians(rotation % 180.0)
                rotated_w = abs(math.cos(angle)) * fw + abs(math.sin(angle)) * fd
                rotated_d = abs(math.sin(angle)) * fw + abs(math.cos(angle)) * fd
                px = float(f_dict.get("position", {}).get("x", cx))
                py = float(f_dict.get("position", {}).get("y", cy))
                min_x, max_x = rx + rotated_w / 2.0 + 0.10, rx + rw - rotated_w / 2.0 - 0.10
                min_y, max_y = ry + rotated_d / 2.0 + 0.10, ry + rd - rotated_d / 2.0 - 0.10
                cx_clamped = max(min_x, min(max_x, px)) if min_x <= max_x else cx
                cy_clamped = max(min_y, min(max_y, py)) if min_y <= max_y else cy

                def footprint(x: float, y: float) -> Tuple[float, float, float, float]:
                    return (x - rotated_w / 2.0, y - rotated_d / 2.0, x + rotated_w / 2.0, y + rotated_d / 2.0)

                def blocked(rect: Tuple[float, float, float, float]) -> bool:
                    if str(f_dict.get("category", "")).lower() == "vehicle":
                        return False
                    return any(not (
                        rect[2] + 0.04 <= zone[0] or rect[0] - 0.04 >= zone[2]
                        or rect[3] + 0.04 <= zone[1] or rect[1] - 0.04 >= zone[3]
                    ) for zone in circulation_zones)

                if blocked(footprint(cx_clamped, cy_clamped)) and min_x <= max_x and min_y <= max_y:
                    candidates = []
                    candidate_x = min_x
                    while candidate_x <= max_x + 0.001:
                        candidate_y = min_y
                        while candidate_y <= max_y + 0.001:
                            candidates.append((candidate_x, candidate_y))
                            candidate_y += 0.25
                        candidate_x += 0.25
                    candidates.sort(key=lambda value: (value[0] - px) ** 2 + (value[1] - py) ** 2)
                    replacement = next((value for value in candidates if not blocked(footprint(*value))), None)
                    if replacement:
                        cx_clamped, cy_clamped = replacement
                f_dict["position"]["x"] = round(cx_clamped, 2)
                f_dict["position"]["y"] = round(cy_clamped, 2)
                furniture.append(f_dict)

            if rtype in {"living_room", "drawing_room"}:
                compact_living = rw * rd < 20.0
                living_items = [
                    {
                        "id": f"sofa_{rid}",
                        "asset": "sofa",
                        "asset_id": "sofa_01_4k",
                        "category": "sofa",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": round(cy - 0.5, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {
                            "width": 1.80 if compact_living else 2.20,
                            "depth": 0.85 if compact_living else 0.95,
                            "height": 0.82,
                        },
                    },
                    {
                        "id": f"coffee_table_{rid}",
                        "asset": "coffee_table",
                        "asset_id": "CoffeeTable_01",
                        "category": "coffee_table",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": round(cy + 0.35, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 1.1, "depth": 0.65, "height": 0.42},
                    },
                    {
                        "id": f"armchair_{rid}",
                        "asset": "armchair",
                        "asset_id": "ArmChair_01",
                        "category": "armchair",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(cx - 1.25, 2), "y": cy, "z": floor_elev},
                        "rotation": 45.0,
                        "dimensions": {"width": 0.88, "depth": 0.88, "height": 0.84},
                    },
                    {
                        "id": f"tv_cabinet_{rid}",
                        "asset": "tv_cabinet",
                        "asset_id": "modren_wooden_cabinet_01",
                        "category": "cabinet",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": round(ry + rd - 0.45, 2), "z": floor_elev},
                        "rotation": 180.0,
                        "anchor_wall": "north",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 1.8, "depth": 0.45, "height": 0.60},
                    },
                ]
                # Keep compact living rooms genuinely compact. Optional tables
                # and media storage previously forced requested 11 x 12 m homes
                # into a validation failure after circulation clearances were
                # applied. The sofa and chair remain; larger rooms get the full
                # furniture group.
                if compact_living:
                    living_items = [living_items[0]]
                for item in living_items:
                    _add(item)
            elif "bedroom" in rtype:
                bed_y = round(ry + rd - 1.15, 2)
                is_master_bedroom = rtype == "master_bedroom"
                bedroom_items = [
                    {
                        "id": f"bed_{rid}",
                        "asset": "bed",
                        "asset_id": "bed_02",
                        "category": "bed",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": bed_y, "z": floor_elev},
                        "rotation": 0.0,
                        "anchor_wall": "north",
                        "placement_hint": "wall_backed",
                        "dimensions": {
                            "width": 2.10 if is_master_bedroom else 1.40,
                            "depth": 2.15 if is_master_bedroom else 2.00,
                            "height": 1.10,
                        },
                    },
                    {
                        "id": f"nightstand_{rid}_1",
                        "asset": "nightstand",
                        "asset_id": "bedside_table_001",
                        "category": "nightstand",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(cx - 1.35, 2), "y": round(bed_y + 0.65, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.55},
                    },
                    {
                        "id": f"nightstand_{rid}_2",
                        "asset": "nightstand",
                        "asset_id": "bedside_table_001",
                        "category": "nightstand",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(cx + 1.35, 2), "y": round(bed_y + 0.65, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.55},
                    },
                    {
                        "id": f"wardrobe_{rid}",
                        "asset": "wardrobe",
                        "asset_id": "wardrobe_modern_01",
                        "category": "wardrobe",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + 0.65, 2), "y": round(ry + 0.8, 2), "z": floor_elev},
                        "rotation": 90.0,
                        "anchor_wall": "west",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 1.56, "depth": 0.65, "height": 2.06},
                    },
                ]
                # A compact parking-side bedroom cannot safely hold a double
                # bed, two nightstands, and a freestanding wardrobe while
                # preserving door circulation. Keep the essential sleep zone.
                if rw * rd < 14.0:
                    bedroom_items = bedroom_items[:3]
                for item in bedroom_items:
                    _add(item)
            elif rtype == "kitchen":
                # Wall fixtures are essential and are placed first. An island
                # requires a real working aisle around it; compact kitchens use
                # an open center instead of forcing an approval-blocking asset.
                kitchen_items = [
                    {
                        "id": f"fridge_{rid}",
                        "asset": "refrigerator",
                        "asset_id": "refrigerator_001",
                        "category": "refrigerator",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + 0.55, 2), "y": round(ry + 0.55, 2), "z": floor_elev},
                        "rotation": 180.0,
                        "anchor_wall": "south",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 0.90, "depth": 0.80, "height": 1.82},
                    },
                    {
                        "id": f"sink_{rid}",
                        "asset": "kitchen_sink",
                        "asset_id": "sink_001",
                        "category": "sink",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + rw - 0.55, 2), "y": round(ry + 0.55, 2), "z": floor_elev},
                        "rotation": 180.0,
                        "anchor_wall": "south",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 0.80, "depth": 0.55, "height": 0.88},
                    },
                ]
                island_rotation = None
                # A fixed island needs working aisles on every side in addition
                # to the refrigerator/sink door arcs.  Do not treat merely
                # fitting its rectangle as an architecturally usable kitchen.
                if rw >= 3.80 and rd >= 3.80:
                    island_rotation = 0.0
                if island_rotation is not None:
                    kitchen_items.append({
                        "id": f"island_{rid}",
                        "asset": "kitchen_island",
                        "asset_id": "kitchen_island_001",
                        "category": "kitchen_island",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": cy, "z": floor_elev},
                        "rotation": island_rotation,
                        "dimensions": {"width": 1.8, "depth": 0.90, "height": 0.92},
                    })
                for item in kitchen_items:
                    _add(item)
            elif "bath" in rtype:
                bath_items = [
                    {
                        "id": f"toilet_{rid}",
                        "asset": "toilet",
                        "asset_id": "toilet_001",
                        "category": "toilet",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + 0.45, 2), "y": round(ry + rd - 0.45, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "anchor_wall": "north",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 0.45, "depth": 0.65, "height": 0.80},
                    },
                    {
                        "id": f"vanity_{rid}",
                        "asset": "bathroom_sink",
                        "asset_id": "sink_001",
                        "category": "sink",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + rw - 0.45, 2), "y": round(ry + rd - 0.45, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "anchor_wall": "north",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 0.70, "depth": 0.48, "height": 0.85},
                    },
                ]
                # Only add shower / tub if the room has sufficient depth and width without blocking door
                if (rw * rd) >= 4.5 and rw >= 2.2 and rd >= 2.0:
                    bath_items.append({
                        "id": f"shower_{rid}",
                        "asset": "shower",
                        "asset_id": "shower_001",
                        "category": "shower",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + rw - 0.55, 2), "y": round(ry + 0.55, 2), "z": floor_elev},
                        "rotation": 180.0,
                        "anchor_wall": "south",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 0.90, "depth": 0.90, "height": 2.00},
                    })
                for item in bath_items:
                    _add(item)
            elif rtype == "dining_room":
                # Orient the dining group along the room's long axis and keep
                # chair footprints beyond the tabletop edge. The previous
                # 0.55 m offset physically intersected the 0.85 m-deep table.
                table_rotation = 0.0 if rw >= rd else 90.0
                chair_offset = 0.85 / 2.0 + 0.45 / 2.0 + 0.10
                if table_rotation == 0.0:
                    chair_specs = [
                        (cx - 0.50, cy - chair_offset, 0.0),
                        (cx + 0.50, cy - chair_offset, 0.0),
                        (cx - 0.50, cy + chair_offset, 180.0),
                        (cx + 0.50, cy + chair_offset, 180.0),
                    ]
                else:
                    chair_specs = [
                        (cx - chair_offset, cy - 0.50, 270.0),
                        (cx - chair_offset, cy + 0.50, 270.0),
                        (cx + chair_offset, cy - 0.50, 90.0),
                        (cx + chair_offset, cy + 0.50, 90.0),
                    ]
                dining_items = [
                    {
                        "id": f"table_{rid}",
                        "asset": "dining_table",
                        "asset_id": "dining_table_001",
                        "category": "dining_table",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": cy, "z": floor_elev},
                        "rotation": table_rotation,
                        "dimensions": {"width": 1.60, "depth": 0.85, "height": 0.76},
                    },
                ]
                for index, (chair_x, chair_y, chair_rotation) in enumerate(chair_specs, 1):
                    dining_items.append({
                        "id": f"chair_{rid}_{index}",
                        "asset": "dining_chair",
                        "asset_id": "dining_chair_001",
                        "category": "dining_chair",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(chair_x, 2), "y": round(chair_y, 2), "z": floor_elev},
                        "rotation": chair_rotation,
                        "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.85},
                    })
                for item in dining_items:
                    _add(item)
            elif rtype == "home_office":
                for item in [
                    {
                        "id": f"desk_{rid}",
                        "asset": "desk",
                        "asset_id": "desk_001",
                        "category": "desk",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": round(cy + 0.2, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 1.40, "depth": 0.70, "height": 0.75},
                    },
                    {
                        "id": f"chair_{rid}",
                        "asset": "chair",
                        "asset_id": "chair_001",
                        "category": "chair",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": round(cy - 0.40, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 0.55, "depth": 0.55, "height": 0.95},
                    },
                    {
                        "id": f"bookshelf_{rid}",
                        "asset": "wardrobe",
                        "asset_id": "modren_wooden_cabinet_01",
                        "category": "cabinet",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + 0.55, 2), "y": round(ry + rd - 0.35, 2), "z": floor_elev},
                        "rotation": 180.0,
                        "anchor_wall": "north",
                        "placement_hint": "wall_backed",
                        "dimensions": {"width": 1.10, "depth": 0.38, "height": 1.85},
                    },
                ]:
                    _add(item)
            elif rtype == "garage":
                _add({
                    "id": f"car_parking_{rid}",
                    "asset": "coffee_table",
                    "asset_id": "car_clearance_marker",
                    "category": "vehicle",
                    "roomId": rid,
                    "room_id": rid,
                    "position": {"x": cx, "y": cy, "z": floor_elev},
                    "rotation": 0.0,
                    "dimensions": {"width": 1.80, "depth": 4.50, "height": 1.50},
                })

        return furniture
