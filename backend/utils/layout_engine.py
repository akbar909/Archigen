"""
layout_engine.py
================
Deterministic Architectural Layout Engine for ArchiGen.
Solves contiguous spatial layouts, room relationships, shared wall networks,
wall-hosted openings, staircase alignment, and furniture placement rules
for 2D CAD plans, Blender Headless 3D, and Three.js viewer.
"""

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


# ─── Coordinate Conversion Utilities ──────────────────────────────────────────

def json_to_svg_coords(x: float, y: float, plot_depth: float, scale: float = 40.0, margin: float = 2.0) -> Tuple[float, float]:
    """
    Converts architectural JSON coordinates (X = width from left, Y = depth from front/south)
    to 2D SVG canvas coordinates (origin top-left).
    """
    svg_x = (margin + x) * scale
    svg_y = (margin + (plot_depth - y)) * scale
    return round(svg_x, 2), round(svg_y, 2)


def json_to_blender_coords(x: float, y: float, z: float, origin_offset: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float, float]:
    """
    Converts architectural JSON coordinates to Blender world space:
    Blender: X = width, Y = depth, Z = elevation (up).
    """
    bx = x - origin_offset[0]
    by = y - origin_offset[1]
    bz = z
    return round(bx, 3), round(by, 3), round(bz, 3)


def json_to_threejs_coords(x: float, y: float, z: float, origin_offset: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float, float]:
    """
    Converts architectural JSON coordinates to Three.js coordinates:
    Three.js: X = width, Y = elevation (up), Z = depth.
    """
    tx = x - origin_offset[0]
    ty = z
    tz = y - origin_offset[1]
    return round(tx, 3), round(ty, 3), round(tz, 3)


# ─── Layout Generation Engine ─────────────────────────────────────────────────

class ArchitecturalLayoutEngine:
    """
    Deterministically arranges rooms, stairs, openings, roof, and exterior features
    from architectural requirements while satisfying geometric constraints.
    """

    def __init__(self, unit: str = "ft"):
        self.unit = unit.lower()
        self.is_feet = self.unit in ["ft", "feet"]

    def _to_meters(self, val: float) -> float:
        return ft_to_m(val) if self.is_feet else float(val)

    def generate_layout(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a complete Architectural JSON v3.0 document from high-level requirements.
        """
        proj_name = requirements.get("project_name", "ArchiGen Residential Home")
        style = str(requirements.get("style", "modern")).lower()
        if style not in VALID_STYLES:
            style = "modern"

        orientation = str(requirements.get("orientation", "south")).lower()
        if orientation not in VALID_ORIENTATIONS:
            orientation = "south"

        floors_count = int(requirements.get("floors", 1))
        floors_count = max(1, min(3, floors_count))

        # 1. Site and Plot
        raw_plot = requirements.get("plot", {})
        raw_pw = float(raw_plot.get("width", 36.0 if self.is_feet else 12.0))
        raw_pd = float(raw_plot.get("depth", 54.0 if self.is_feet else 18.0))

        plot_w = round(self._to_meters(raw_pw) if raw_pw > 20 and not self.is_feet else (ft_to_m(raw_pw) if self.is_feet else raw_pw), 2)
        plot_d = round(self._to_meters(raw_pd) if raw_pd > 20 and not self.is_feet else (ft_to_m(raw_pd) if self.is_feet else raw_pd), 2)

        # 2. Extract Requested Rooms
        req_room_inputs = requirements.get("rooms", [])
        norm_room_types = self._normalize_requested_rooms(req_room_inputs, requirements, floors_count)

        # The requested plot is a hard boundary, not a suggestion.  Previous
        # code silently enlarged smaller valid plots (an 11 x 12 m request
        # became 11 x 14 m), so both the scale and resulting room geometry no
        # longer matched the user's approved plan.
        if plot_w < 6.0 or plot_d < 6.0:
            raise ValueError(
                f"Plot {plot_w:.2f} x {plot_d:.2f} m is too small for a safe residential layout."
            )

        # Standard residential setbacks
        sb_front = round(min(plot_d * 0.18, 3.5), 2)
        sb_back = round(min(plot_d * 0.12, 2.5), 2)
        sb_left = round(min(plot_w * 0.10, 1.5), 2)
        sb_right = round(min(plot_w * 0.10, 1.5), 2)

        bldg_w = round(plot_w - sb_left - sb_right, 2)
        bldg_d = round(plot_d - sb_front - sb_back, 2)
        wall_t = 0.20
        slab_t = 0.22
        floor_h = 3.0

        # 3. Generate Ground Floor Layout
        ground_types, upper_types = self._split_rooms_by_floor(norm_room_types, floors_count)

        ground_rooms, stair_def = self._layout_floor_rooms(
            room_types=ground_types,
            bldg_w=bldg_w,
            bldg_d=bldg_d,
            sb_left=sb_left,
            sb_front=sb_front,
            floor_idx=0,
            has_stairs=floors_count > 1,
            style=style,
            wall_t=wall_t,
        )

        ground_walls = self._compute_floor_walls(ground_rooms, wall_t, sb_left, sb_front, bldg_w, bldg_d)
        connection_preferences = requirements.get("connection_preferences", [])
        ground_doors = self._generate_doors(
            ground_rooms, ground_walls, is_ground=True,
            connection_preferences=connection_preferences,
        )
        ground_windows = self._generate_windows(ground_rooms, ground_walls, bldg_w, bldg_d, sb_left, sb_front)
        ground_furniture = self._place_furniture_for_rooms(
            ground_rooms, style, elevation=0.0, doors=ground_doors,
        )

        floors_data = [
            {
                "id": "ground_floor",
                "level": 0,
                "elevation": 0.0,
                "floor_height": floor_h,
                "rooms": ground_rooms,
                "walls": ground_walls,
                "doors": ground_doors,
                "windows": ground_windows,
                "stairs": [stair_def] if stair_def else [],
                "furniture": ground_furniture,
                "ceiling": {"type": "cove_recessed", "height": floor_h - 0.12},
            }
        ]

        # 4. Generate Upper Floor if requested
        if floors_count > 1:
            first_rooms, _ = self._layout_floor_rooms(
                room_types=upper_types,
                bldg_w=bldg_w,
                bldg_d=bldg_d,
                sb_left=sb_left,
                sb_front=sb_front,
                floor_idx=1,
                has_stairs=True,
                style=style,
                wall_t=wall_t,
                stair_ref=stair_def,
            )
            first_walls = self._compute_floor_walls(first_rooms, wall_t, sb_left, sb_front, bldg_w, bldg_d)
            first_doors = self._generate_doors(
                first_rooms, first_walls, is_ground=False,
                connection_preferences=connection_preferences,
            )
            first_windows = self._generate_windows(first_rooms, first_walls, bldg_w, bldg_d, sb_left, sb_front)
            first_furniture = self._place_furniture_for_rooms(
                first_rooms, style, elevation=floor_h, doors=first_doors,
            )

            floors_data.append({
                "id": "first_floor",
                "level": 1,
                "elevation": floor_h,
                "floor_height": floor_h,
                "rooms": first_rooms,
                "walls": first_walls,
                "doors": first_doors,
                "windows": first_windows,
                "stairs": [
                    {
                        **stair_def,
                        "position": {**stair_def["position"], "z": floor_h},
                        "dimensions": dict(stair_def["dimensions"]),
                    }
                ] if stair_def else [],
                "furniture": first_furniture,
                "ceiling": {"type": "flat", "height": floor_h - 0.10},
            })

        # 5. Roof Structure
        roof_type = requirements.get("roof_type", "parapet" if style in ["modern", "minimalist"] else "gable")
        top_elevation = floor_h * floors_count
        roof_data = {
            "type": roof_type,
            "elevation": top_elevation,
            "height": 0.9 if roof_type == "parapet" else 1.8,
            "overhang": 0.35,
            "material": "concrete_slab" if roof_type == "parapet" else "dark_shingle",
        }

        # 6. Exterior Features
        road_side = orientation
        garage_room = next((r for r in ground_rooms if r.get("type") == "garage"), None)
        driveway_x = garage_room["position"]["x"] if garage_room else sb_left
        driveway_w = garage_room["dimensions"]["width"] if garage_room else 3.8
        main_door = next((d for d in ground_doors if d.get("type") == "main_entrance"), None)
        entrance_position = dict(
            (main_door or {}).get("position")
            or {"x": round(sb_left + bldg_w * 0.45, 2), "y": round(sb_front, 2), "z": 0.0}
        )
        entrance_width = float((main_door or {}).get("width", 1.10))
        entrance_height = float((main_door or {}).get("height", 2.20))
        gate_width = min(3.6, float(driveway_w))
        gate_center_x = float(driveway_x) + gate_width / 2.0

        exterior_data = {
            "facade_style": style,
            "main_entrance": {
                "door_id": (main_door or {}).get("id"),
                "position": entrance_position,
                "width": round(entrance_width, 2),
                "height": round(entrance_height, 2),
            },
            "gate": {
                "position": {"x": round(driveway_x, 2), "y": 0.0, "z": 0.0},
                "width": round(gate_width, 2),
                "height": 2.0,
                "asset": "architecture/doors/exterior/Gate.glb",
            },
            "entrance_path": {
                "start": {"x": round(gate_center_x, 2), "y": 0.0},
                "end": {
                    "x": round(float(entrance_position.get("x", gate_center_x)), 2),
                    "y": round(float(entrance_position.get("y", sb_front)), 2),
                },
                "width": 1.2,
            },
            "boundary_wall": {
                "enabled": True,
                "height": 2.1,
                "thickness": 0.15,
            },
            "driveway": {
                "position": {"x": round(driveway_x, 2), "y": 0.0, "z": 0.0},
                "width": round(driveway_w, 2),
                "depth": sb_front,
            },
            "landscape": {
                "lawn_enabled": True,
                "patio_depth": 2.4,
            },
        }

        # Collect top-level rooms, doors, windows, furniture for backward compatibility
        top_rooms = []
        top_doors = []
        top_windows = []
        top_furniture = []
        for fl in floors_data:
            top_rooms.extend(fl.get("rooms", []))
            top_doors.extend(fl.get("doors", []))
            top_windows.extend(fl.get("windows", []))
            top_furniture.extend(fl.get("furniture", []))

        doc = {
            "schema_version": "3.0",
            "version": "2.0",  # backward compat
            "project": {
                "name": proj_name,
                "unit": "meters",
                "display_unit": self.unit,
                "style": style,
                "orientation": orientation,
            },
            "site": {
                "plot": {"width": plot_w, "depth": plot_d},
                "road": {"side": road_side, "width": 6.0},
                "setbacks": {
                    "front": sb_front,
                    "back": sb_back,
                    "left": sb_left,
                    "right": sb_right,
                },
            },
            "building": {
                "width": bldg_w,
                "depth": bldg_d,
                "wall_thickness": wall_t,
                "slab_thickness": slab_t,
                "floors": floors_count,
            },
            "floors": floors_data,
            # Top-level exports ensuring Three.js and legacy routes work seamlessly
            "rooms": top_rooms,
            "doors": top_doors,
            "windows": top_windows,
            "furniture": top_furniture,
            "roof": roof_data,
            "exterior": exterior_data,
            "validation": {
                "status": "valid",
                "errors": [],
                "warnings": [],
            },
        }

        return doc

    def _normalize_requested_rooms(
        self,
        raw_rooms: Any,
        requirements: Dict[str, Any],
        floors_count: int
    ) -> List[Dict[str, Any]]:
        """Extracts and normalizes all requested rooms with standard types and metadata."""
        room_types = []

        if isinstance(raw_rooms, list) and raw_rooms:
            for item in raw_rooms:
                if isinstance(item, dict):
                    rtype = str(item.get("type", item.get("name", "Room"))).lower()
                    rname = str(item.get("name", item.get("type", "Room")))
                else:
                    rtype = str(item).lower()
                    rname = str(item).title()

                clean_type = self._classify_room_type(rtype)
                room_types.append({"type": clean_type, "name": rname, "raw": item if isinstance(item, dict) else {}})
        else:
            # Infer from requirements counts
            num_beds = int(requirements.get("bedrooms", 2 if floors_count == 1 else 3))
            num_baths = int(requirements.get("bathrooms", 2))
            has_living = requirements.get("has_living", True)
            has_kitchen = requirements.get("has_kitchen", True)
            has_dining = requirements.get("has_dining", True)
            has_garage = bool(requirements.get("garage", False))
            has_office = bool(requirements.get("office", False))

            if has_garage:
                room_types.append({"type": "garage", "name": "Garage", "raw": {}})
            if has_living:
                room_types.append({"type": "living_room", "name": "Living Room", "raw": {}})
            if has_dining:
                room_types.append({"type": "dining_room", "name": "Dining Room", "raw": {}})
            if has_kitchen:
                room_types.append({"type": "kitchen", "name": "Kitchen", "raw": {}})
            if has_office:
                room_types.append({"type": "home_office", "name": "Office / Study", "raw": {}})

            room_types.append({"type": "master_bedroom", "name": "Master Bedroom", "raw": {}})
            for i in range(1, num_beds):
                room_types.append({"type": "bedroom", "name": f"Bedroom {i+1}", "raw": {}})

            room_types.append({"type": "master_bathroom", "name": "Master Ensuite", "raw": {}})
            for i in range(1, num_baths):
                room_types.append({"type": "bathroom", "name": f"Bathroom {i+1}", "raw": {}})

        # Older layouts automatically gained living/kitchen/bathroom spaces.
        # Explicit full-design prompts use a strict room program instead: the
        # user's categories and counts are the contract.
        types_present = {r["type"] for r in room_types}
        has_living_or_kitchen_intent = any(t in types_present for t in ["living_room", "kitchen", "dining_room"])
        strict_room_program = bool(requirements.get("strict_room_program", False))
        if not strict_room_program and (len(room_types) >= 3 or (len(room_types) >= 2 and has_living_or_kitchen_intent)):
            if "living_room" not in types_present:
                room_types.insert(0, {"type": "living_room", "name": "Living Room", "raw": {}})
            if "kitchen" not in types_present:
                room_types.append({"type": "kitchen", "name": "Kitchen", "raw": {}})
            if "bathroom" not in types_present and "master_bathroom" not in types_present:
                room_types.append({"type": "bathroom", "name": "Bathroom", "raw": {}})

        return room_types

    def _classify_room_type(self, s: str) -> str:
        s = s.lower().replace(" ", "_")
        if "garage" in s:
            return "garage"
        if "master" in s and "bed" in s:
            return "master_bedroom"
        if "master" in s and ("bath" in s or "wash" in s or "toilet" in s):
            return "master_bathroom"
        if "bed" in s or "guest" in s:
            return "bedroom"
        if "bath" in s or "wash" in s or "toilet" in s or "powder" in s:
            return "bathroom"
        if "kitchen" in s or "kitch" in s:
            return "kitchen"
        if "dining" in s:
            return "dining_room"
        if "office" in s or "study" in s or "work" in s:
            return "home_office"
        if "living" in s or "lounge" in s or "great" in s or "drawing" in s:
            return "living_room"
        if "foyer" in s or "entry" in s:
            return "foyer"
        if "laundry" in s or "utility" in s:
            return "laundry"
        return "living_room" if "room" in s else s

    def _split_rooms_by_floor(self, room_types: List[Dict[str, Any]], floors_count: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Separates room types logically across ground and upper floors."""
        if floors_count <= 1:
            return room_types, []

        ground = []
        upper = []

        # Ground floor preferred: Garage, Living, Dining, Kitchen, Powder Bath, 1 Bedroom/Office
        # Upper floor preferred: Master Suite, other Bedrooms, Family Bath, Office
        for r in room_types:
            rtype = r["type"]
            # Check if user specified floor explicitly
            raw_floor = r.get("raw", {}).get("floor")
            if raw_floor is not None:
                if int(raw_floor) == 0:
                    ground.append(r)
                else:
                    upper.append(r)
                continue

            if rtype in ["garage", "living_room", "dining_room", "kitchen"]:
                ground.append(r)
            elif rtype == "master_bedroom" or rtype == "master_bathroom":
                upper.append(r)
            elif rtype == "home_office":
                if len(ground) < 4:
                    ground.append(r)
                else:
                    upper.append(r)
            elif rtype == "bedroom":
                if sum(1 for x in ground if "bed" in x["type"]) == 0 and len(room_types) > 4:
                    ground.append(r)  # 1 guest bedroom on ground
                else:
                    upper.append(r)
            elif rtype == "bathroom":
                if sum(1 for x in ground if "bath" in x["type"]) == 0:
                    ground.append(r)
                else:
                    upper.append(r)
            else:
                if len(ground) <= len(upper):
                    ground.append(r)
                else:
                    upper.append(r)

        if not ground:
            ground = room_types[:len(room_types)//2]
            upper = room_types[len(room_types)//2:]

        return ground, upper

    # ─── Dynamic Contiguous Spatial Placement ─────────────────────────────────

    def _layout_floor_rooms(
        self,
        room_types: List[Dict[str, Any]],
        bldg_w: float,
        bldg_d: float,
        sb_left: float,
        sb_front: float,
        floor_idx: int,
        has_stairs: bool,
        style: str,
        wall_t: float,
        stair_ref: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Dynamically partitions the building footprint into cohesive, contiguous rooms
        sharing common partition walls edge-to-edge. No floating islands or gaps.
        """
        elevation = floor_idx * 3.0
        rooms = []
        stair_def = stair_ref

        # Categorize rooms to be placed on this floor
        garage = next((r for r in room_types if r["type"] == "garage"), None)
        living = next((r for r in room_types if r["type"] == "living_room"), None)
        dining = next((r for r in room_types if r["type"] == "dining_room"), None)
        kitchen = next((r for r in room_types if r["type"] == "kitchen"), None)
        office = next((r for r in room_types if r["type"] == "home_office"), None)
        master_bed = next((r for r in room_types if r["type"] == "master_bedroom"), None)
        other_beds = [r for r in room_types if r["type"] == "bedroom"]
        baths = [r for r in room_types if "bath" in r["type"]]
        misc_rooms = [r for r in room_types if r not in ([garage, living, dining, kitchen, office, master_bed] + other_beds + baths)]

        # The primary bedroom belongs in the main habitable wing.
        # If no explicit master bedroom is labeled, promote the first
        # bedroom to master so it anchors the rear suite rather than being
        # demoted to a narrow utility/garage flank.
        if not master_bed and other_beds:
            master_bed = other_beds.pop(0)

        # ── 1. Vehicular Flank: Garage (if present on ground floor) ──
        hab_x = sb_left
        hab_w = bldg_w
        rear_flank_room = None

        if garage and floor_idx == 0:
            gw = min(4.2, max(3.4, round(bldg_w * 0.30, 2)))
            gd = min(6.0, max(5.0, round(bldg_d * 0.50, 2)))
            rooms.append(self._create_room_dict(
                room_id=garage.get("raw", {}).get("id", "garage_01"),
                name=garage["name"],
                room_type="garage",
                x=sb_left,
                y=sb_front,
                z=elevation,
                w=gw,
                d=gd,
                materials={"floor": {"pattern": "concrete", "color": "#808080"}, "walls": {"pattern": "plain", "color": "#D3D3D3"}},
                floor_idx=floor_idx,
            ))
            # Habitable building zone is shifted to the right of the garage
            hab_x = round(sb_left + gw, 2)
            hab_w = round(bldg_w - gw, 2)

            # Check if an office, extra bedroom, laundry, or bathroom can take the space behind the garage.
            # IMPORTANT: The primary bedroom is already master_bed and is reserved for the main rear wing.
            rear_flank_d = round(bldg_d - gd, 2)
            if office and rear_flank_d >= 3.0:
                rear_flank_room = office
                office = None  # consumed
            elif other_beds and rear_flank_d >= 3.0:
                # Secondary bedroom in flank behind garage
                rear_flank_room = other_beds.pop(0)
            elif misc_rooms and rear_flank_d >= 2.5:
                rear_flank_room = misc_rooms.pop(0)
            elif not living and not dining and baths and rear_flank_d >= 2.2:
                # When there is no living/dining room, kitchen takes front habitable wing
                # and master bedroom takes the rear habitable wing.
                # The bathroom takes the garage flank so that the bedroom retains the grand rear wing!
                rear_flank_room = baths.pop(0)
            elif kitchen and living and rear_flank_d >= 3.0:
                # Kitchen behind garage with direct service access, leaving front habitable zone for living room
                rear_flank_room = kitchen
                kitchen = None
            elif baths and len(baths) > 1 and rear_flank_d >= 2.2:
                # Common/powder bath in garage flank
                rear_flank_room = baths.pop()

            if rear_flank_room:
                rooms.append(self._create_room_dict(
                    room_id=rear_flank_room.get("raw", {}).get("id", f"{rear_flank_room['type']}_flank"),
                    name=rear_flank_room["name"],
                    room_type=rear_flank_room["type"],
                    x=sb_left,
                    y=round(sb_front + gd, 2),
                    z=elevation,
                    w=gw,
                    d=rear_flank_d,
                    materials=self._default_materials(rear_flank_room["type"]),
                    floor_idx=floor_idx,
                ))

        # ── 1b. Small House Spatial Arrangement (<= 2 rooms on this floor) ──
        if len(room_types) == 1 and not garage:
            single_r = room_types[0]
            rooms.append(self._create_room_dict(
                room_id=single_r.get("raw", {}).get("id", f"{single_r['type']}_01"),
                name=single_r["name"],
                room_type=single_r["type"],
                x=hab_x,
                y=sb_front,
                z=elevation,
                w=hab_w,
                d=bldg_d,
                materials=self._default_materials(single_r["type"]),
                floor_idx=floor_idx,
            ))
            return rooms, stair_def

        if len(room_types) == 2 and not garage and not any(r["type"] in ["living_room", "dining_room"] for r in room_types):
            main_r = next((r for r in room_types if "bed" in r["type"] or "office" in r["type"]), room_types[0])
            sec_r = next((r for r in room_types if r != main_r), room_types[1])

            # Main room (bedroom) takes ~68% of building width, secondary room (bathroom) takes ~32%
            main_w = round(hab_w * 0.68, 2)
            sec_w = round(hab_w - main_w, 2)

            rooms.append(self._create_room_dict(
                room_id=main_r.get("raw", {}).get("id", f"{main_r['type']}_01"),
                name=main_r["name"],
                room_type=main_r["type"],
                x=hab_x,
                y=sb_front,
                z=elevation,
                w=main_w,
                d=bldg_d,
                materials=self._default_materials(main_r["type"]),
                floor_idx=floor_idx,
            ))

            rooms.append(self._create_room_dict(
                room_id=sec_r.get("raw", {}).get("id", f"{sec_r['type']}_01"),
                name=sec_r["name"],
                room_type=sec_r["type"],
                x=round(hab_x + main_w, 2),
                y=sb_front,
                z=elevation,
                w=sec_w,
                d=bldg_d,
                materials=self._default_materials(sec_r["type"]),
                floor_idx=floor_idx,
            ))
            return rooms, stair_def

        # ── 2. Divide Habitable Zone into Front Band (South) and Rear Band (North) ──
        has_front_intent = bool(living or dining or kitchen)
        front_d = round(bldg_d * 0.46, 2) if has_front_intent else 0.0
        rear_d = round(bldg_d - front_d, 2)

        # ── A. Front Zone Placement (Living, Dining, Kitchen) ──
        front_rooms_list = []
        if living:
            front_rooms_list.append(living)
        if dining:
            front_rooms_list.append(dining)
        elif kitchen and not dining:
            front_rooms_list.append(kitchen)
            kitchen = None

        if len(front_rooms_list) == 1:
            r = front_rooms_list[0]
            rooms.append(self._create_room_dict(
                room_id=r.get("raw", {}).get("id", "living_01"),
                name=r["name"],
                room_type=r["type"],
                x=hab_x,
                y=sb_front,
                z=elevation,
                w=hab_w,
                d=front_d,
                materials=self._default_materials(r["type"]),
                floor_idx=floor_idx,
            ))
        elif len(front_rooms_list) >= 2:
            # Living takes 58% of width, Dining/Secondary takes 42%
            liv = front_rooms_list[0]
            sec = front_rooms_list[1]
            liv_w = round(hab_w * 0.58, 2)
            sec_w = round(hab_w - liv_w, 2)

            rooms.append(self._create_room_dict(
                room_id=liv.get("raw", {}).get("id", "living_01"),
                name=liv["name"],
                room_type=liv["type"],
                x=hab_x,
                y=sb_front,
                z=elevation,
                w=liv_w,
                d=front_d,
                materials=self._default_materials(liv["type"]),
                floor_idx=floor_idx,
            ))

            # If kitchen is also needed, split the secondary wing vertically (Dining front, Kitchen behind)
            if kitchen:
                din_d = round(front_d * 0.55, 2)
                kit_d = round(front_d * 0.45, 2)
                rooms.append(self._create_room_dict(
                    room_id=sec.get("raw", {}).get("id", "dining_01"),
                    name=sec["name"],
                    room_type=sec["type"],
                    x=round(hab_x + liv_w, 2),
                    y=sb_front,
                    z=elevation,
                    w=sec_w,
                    d=din_d,
                    materials=self._default_materials(sec["type"]),
                    floor_idx=floor_idx,
                ))
                rooms.append(self._create_room_dict(
                    room_id=kitchen.get("raw", {}).get("id", "kitchen_01"),
                    name=kitchen["name"],
                    room_type="kitchen",
                    x=round(hab_x + liv_w, 2),
                    y=round(sb_front + din_d, 2),
                    z=elevation,
                    w=sec_w,
                    d=kit_d,
                    materials=self._default_materials("kitchen"),
                    floor_idx=floor_idx,
                ))
                kitchen = None  # consumed
            else:
                rooms.append(self._create_room_dict(
                    room_id=sec.get("raw", {}).get("id", "dining_01"),
                    name=sec["name"],
                    room_type=sec["type"],
                    x=round(hab_x + liv_w, 2),
                    y=sb_front,
                    z=elevation,
                    w=sec_w,
                    d=front_d,
                    materials=self._default_materials(sec["type"]),
                    floor_idx=floor_idx,
                ))

        # ── B. Rear Zone Placement (Bedrooms, Bathrooms, Office, Kitchen if remaining) ──
        rear_candidates = []
        if master_bed:
            rear_candidates.append(master_bed)
        if other_beds:
            rear_candidates.extend(other_beds)
        if office:
            rear_candidates.append(office)
        if kitchen:
            rear_candidates.append(kitchen)
        if misc_rooms:
            rear_candidates.extend(misc_rooms)

        # Place staircase in rear/central circulation if multi-floor
        if has_stairs and not stair_def:
            stair_w = 1.10
            stair_d = 2.80
            stair_x = round(hab_x + hab_w * 0.48, 2)
            stair_y = round(sb_front + front_d, 2)
            stair_def = {
                "id": "stair_01",
                "position": {"x": stair_x, "y": stair_y, "z": 0.0},
                "dimensions": {"width": stair_w, "depth": stair_d, "height": 3.0},
                "direction": "north",
                "steps": 16,
                "riser": 0.187,
                "tread": 0.28,
                "connects": {"lower_floor": "ground_floor", "upper_floor": "first_floor"},
            }

        # Divide rear band into left wing and right wing
        rear_y = round(sb_front + front_d, 2)
        if not rear_candidates:
            # Never invent a bedroom. If the requested program only has a
            # remaining bathroom, let it occupy this rear zone; otherwise the
            # already placed front/flank rooms complete the floor.
            if baths:
                rear_candidates.append(baths.pop(0))
            else:
                return rooms, stair_def

        # ── Realistic bathroom size caps (meters) ─────────────────────────
        # Bathrooms must never inherit an oversized zone.  Architectural
        # norms: standard bath ≤ 3.5 × 3.0 m, master bath ≤ 4.0 × 3.5 m.
        MAX_BATH_DIMS = {
            "bathroom":        {"w": 3.5, "d": 3.0},
            "master_bathroom": {"w": 4.0, "d": 3.5},
            "powder_room":     {"w": 2.0, "d": 1.8},
        }

        def _cap_bath(room_type: str, w: float, d: float):
            """Clamp bathroom dimensions to realistic architectural maximums."""
            caps = MAX_BATH_DIMS.get(room_type)
            if caps:
                w = min(w, caps["w"])
                d = min(d, caps["d"])
            return round(w, 2), round(d, 2)

        if len(rear_candidates) == 1:
            rc = rear_candidates[0]
            is_bath_only = "bath" in rc["type"]

            if is_bath_only and not baths:
                # A bathroom is the sole rear room — cap it and give the
                # remaining width back to any bedroom already placed in the
                # garage flank (expand it), or leave a gap that the
                # foundation covers.
                capped_w, capped_d = _cap_bath(rc["type"], hab_w, rear_d)
                rooms.append(self._create_room_dict(
                    room_id=rc.get("raw", {}).get("id", f"{rc['type']}_01"),
                    name=rc["name"],
                    room_type=rc["type"],
                    x=hab_x,
                    y=rear_y,
                    z=elevation,
                    w=capped_w,
                    d=capped_d,
                    materials=self._default_materials(rc["type"]),
                    floor_idx=floor_idx,
                ))
            elif baths:
                # If bathroom exists, place attached ensuite in corner
                b_item = baths.pop(0)
                bath_w = min(2.8, max(2.2, round(hab_w * 0.35, 2)))
                bath_d = rear_d  # fill full depth of the corner column to ensure continuous shared partition
                main_w = round(hab_w - bath_w, 2)
                rooms.append(self._create_room_dict(
                    room_id=rc.get("raw", {}).get("id", f"{rc['type']}_01"),
                    name=rc["name"],
                    room_type=rc["type"],
                    x=hab_x,
                    y=rear_y,
                    z=elevation,
                    w=main_w,
                    d=rear_d,
                    materials=self._default_materials(rc["type"]),
                    floor_idx=floor_idx,
                ))
                rooms.append(self._create_room_dict(
                    room_id=b_item.get("raw", {}).get("id", f"{b_item['type']}_01"),
                    name=b_item["name"],
                    room_type=b_item["type"],
                    x=round(hab_x + main_w, 2),
                    y=rear_y,
                    z=elevation,
                    w=bath_w,
                    d=bath_d,
                    materials=self._default_materials(b_item["type"]),
                    floor_idx=floor_idx,
                ))
            else:
                rooms.append(self._create_room_dict(
                    room_id=rc.get("raw", {}).get("id", f"{rc['type']}_01"),
                    name=rc["name"],
                    room_type=rc["type"],
                    x=hab_x,
                    y=rear_y,
                    z=elevation,
                    w=hab_w,
                    d=rear_d,
                    materials=self._default_materials(rc["type"]),
                    floor_idx=floor_idx,
                ))
        else:
            # Multiple rear rooms: split width into 2 wings (Left Wing & Right Wing)
            left_w = round(hab_w * 0.52, 2)
            right_w = round(hab_w - left_w, 2)

            r_left = rear_candidates[0]
            r_right = rear_candidates[1]

            # Attached bathroom handling for left wing (Master Bed)
            if "master" in r_left["type"] and baths:
                b_item = baths.pop(0)
                bath_d = min(2.5, round(rear_d * 0.45, 2))
                # Cap bathroom dimensions to realistic maximums
                _, bath_d = _cap_bath(b_item["type"], left_w, bath_d)
                bed_d = round(rear_d - bath_d, 2)

                rooms.append(self._create_room_dict(
                    room_id=r_left.get("raw", {}).get("id", "master_bed_01"),
                    name=r_left["name"],
                    room_type=r_left["type"],
                    x=hab_x,
                    y=rear_y,
                    z=elevation,
                    w=left_w,
                    d=bed_d,
                    materials=self._default_materials(r_left["type"]),
                    floor_idx=floor_idx,
                ))
                rooms.append(self._create_room_dict(
                    room_id=b_item.get("raw", {}).get("id", "master_bath_01"),
                    name=b_item["name"],
                    room_type=b_item["type"],
                    x=hab_x,
                    y=round(rear_y + bed_d, 2),
                    z=elevation,
                    w=left_w,
                    d=bath_d,
                    materials=self._default_materials(b_item["type"]),
                    floor_idx=floor_idx,
                ))
            else:
                rooms.append(self._create_room_dict(
                    room_id=r_left.get("raw", {}).get("id", f"{r_left['type']}_01"),
                    name=r_left["name"],
                    room_type=r_left["type"],
                    x=hab_x,
                    y=rear_y,
                    z=elevation,
                    w=left_w,
                    d=rear_d,
                    materials=self._default_materials(r_left["type"]),
                    floor_idx=floor_idx,
                ))

            # Right Wing: Place r_right (Office / Bed 2) and Common Bathroom
            if baths:
                b_common = baths.pop(0)
                bath_d = min(2.4, round(rear_d * 0.45, 2))
                # Cap bathroom dimensions to realistic maximums
                _, bath_d = _cap_bath(b_common["type"], right_w, bath_d)
                main_d = round(rear_d - bath_d, 2)

                rooms.append(self._create_room_dict(
                    room_id=r_right.get("raw", {}).get("id", f"{r_right['type']}_02"),
                    name=r_right["name"],
                    room_type=r_right["type"],
                    x=round(hab_x + left_w, 2),
                    y=rear_y,
                    z=elevation,
                    w=right_w,
                    d=main_d,
                    materials=self._default_materials(r_right["type"]),
                    floor_idx=floor_idx,
                ))
                rooms.append(self._create_room_dict(
                    room_id=b_common.get("raw", {}).get("id", f"{b_common['type']}_02"),
                    name=b_common["name"],
                    room_type=b_common["type"],
                    x=round(hab_x + left_w, 2),
                    y=round(rear_y + main_d, 2),
                    z=elevation,
                    w=right_w,
                    d=bath_d,
                    materials=self._default_materials(b_common["type"]),
                    floor_idx=floor_idx,
                ))
            else:
                rooms.append(self._create_room_dict(
                    room_id=r_right.get("raw", {}).get("id", f"{r_right['type']}_02"),
                    name=r_right["name"],
                    room_type=r_right["type"],
                    x=round(hab_x + left_w, 2),
                    y=rear_y,
                    z=elevation,
                    w=right_w,
                    d=rear_d,
                    materials=self._default_materials(r_right["type"]),
                    floor_idx=floor_idx,
                ))

        # Any extra bathroom placement
        while baths:
            b_rem = baths.pop(0)
            if garage and floor_idx == 0 and not rear_flank_room and rear_flank_d >= 2.2:
                rear_flank_room = b_rem
                rooms.append(self._create_room_dict(
                    room_id=b_rem.get("raw", {}).get("id", f"{b_rem['type']}_flank"),
                    name=b_rem["name"],
                    room_type="bathroom",
                    x=sb_left,
                    y=round(sb_front + gd, 2),
                    z=elevation,
                    w=gw,
                    d=rear_flank_d,
                    materials=self._default_materials("bathroom"),
                    floor_idx=floor_idx,
                ))

        # Architectural sanity check: A bathroom must NEVER be larger than any bedroom on the floor
        all_beds = [r for r in rooms if "bed" in r["type"]]
        all_baths = [r for r in rooms if "bath" in r["type"]]
        if all_beds and all_baths:
            min_bed_area = min(r["dimensions"]["width"] * r["dimensions"]["depth"] for r in all_beds)
            for b in all_baths:
                b_area = b["dimensions"]["width"] * b["dimensions"]["depth"]
                if b_area > min_bed_area:
                    # Bathroom cannot exceed bedroom: clamp its dimensions
                    scale = (min_bed_area * 0.7) / b_area
                    b["dimensions"]["width"] = round(b["dimensions"]["width"] * (scale ** 0.5), 2)
                    b["dimensions"]["depth"] = round(b["dimensions"]["depth"] * (scale ** 0.5), 2)

        return rooms, stair_def

    def _create_room_dict(
        self,
        room_id: str,
        name: str,
        room_type: str,
        x: float,
        y: float,
        z: float,
        w: float,
        d: float,
        materials: Dict[str, Any],
        floor_idx: int,
    ) -> Dict[str, Any]:
        """Creates unified room dictionary with both Schema v3 and backward-compatible fields."""
        rx = round(x, 2)
        ry = round(y, 2)
        rz = round(z, 2)
        rw = round(w, 2)
        rd = round(d, 2)

        return {
            "id": room_id,
            "name": name,
            "type": room_type,
            "position": {"x": rx, "y": ry, "z": rz},
            "dimensions": {"width": rw, "depth": rd, "height": 3.0},
            # Backward-compatibility fields for Three.js legacy components
            "width": rw,
            "length": rd,
            "height": 3.0,
            "floor": floor_idx,
            "materials": materials,
            "pbr_material": {
                "floor": {"color": materials.get("floor", {}).get("color", "#CCCCCC"), "pattern": materials.get("floor", {}).get("pattern", "wood_planks")},
                "walls": {"color": materials.get("walls", {}).get("color", "#F0EDE8"), "pattern": materials.get("walls", {}).get("pattern", "plain")},
                "accent_wall": materials.get("accent_wall", {"side": "back", "color": "#7C5335", "pattern": "wood_panel"}),
            },
        }

    def _default_materials(self, room_type: str) -> Dict[str, Any]:
        if "living" in room_type:
            return {
                "floor": {"pattern": "wood_planks", "color": "#7A5C3D"},
                "walls": {"pattern": "plain", "color": "#F4F1EA"},
                "accent_wall": {"side": "back", "pattern": "wood_panel", "color": "#5C4033"},
            }
        if "dining" in room_type:
            return {
                "floor": {"pattern": "marble_tile", "color": "#E5E5E5"},
                "walls": {"pattern": "plain", "color": "#F4F1EA"},
            }
        if "kitchen" in room_type:
            return {
                "floor": {"pattern": "marble_tile", "color": "#DCDCDC"},
                "walls": {"pattern": "plain", "color": "#FAFAFA"},
            }
        if "bed" in room_type:
            return {
                "floor": {"pattern": "wood_planks", "color": "#8C6D4F"},
                "walls": {"pattern": "plain", "color": "#F8F6F0"},
                "accent_wall": {"side": "back", "pattern": "wood_panel", "color": "#4A3525"},
            }
        if "bath" in room_type:
            return {
                "floor": {"pattern": "marble_tile", "color": "#CCCCCC"},
                "walls": {"pattern": "plain", "color": "#FFFFFF"},
            }
        if "office" in room_type:
            return {
                "floor": {"pattern": "wood_planks", "color": "#6E4D25"},
                "walls": {"pattern": "plain", "color": "#F4F1EA"},
            }
        return {
            "floor": {"pattern": "wood_planks", "color": "#7A5C3D"},
            "walls": {"pattern": "plain", "color": "#F4F1EA"},
        }

    # ─── Shared Wall Network ──────────────────────────────────────────────────

    def _compute_floor_walls(
        self,
        rooms: List[Dict[str, Any]],
        wall_t: float,
        sb_left: float,
        sb_front: float,
        bldg_w: float,
        bldg_d: float
    ) -> List[Dict[str, Any]]:
        """
        Extracts unique, clean shared architectural walls.
        Merges coincident partition boundaries and marks exterior vs. interior walls.
        """
        raw_segments = []
        for r in rooms:
            rid = r["id"]
            rx = r["position"]["x"]
            ry = r["position"]["y"]
            rz = r["position"]["z"]
            rw = r["dimensions"]["width"]
            rd = r["dimensions"]["depth"]

            # 4 boundaries of the room
            raw_segments.append({"side": "south", "room_id": rid, "x1": rx, "y1": ry, "x2": rx + rw, "y2": ry, "z": rz})
            raw_segments.append({"side": "north", "room_id": rid, "x1": rx, "y1": ry + rd, "x2": rx + rw, "y2": ry + rd, "z": rz})
            raw_segments.append({"side": "west", "room_id": rid, "x1": rx, "y1": ry, "x2": rx, "y2": ry + rd, "z": rz})
            raw_segments.append({"side": "east", "room_id": rid, "x1": rx + rw, "y1": ry, "x2": rx + rw, "y2": ry + rd, "z": rz})

        # Split every collinear run at every room endpoint.  This avoids the old
        # behaviour where a partially overlapping room edge consumed the whole
        # neighbouring wall and produced gaps or duplicate partitions.
        line_groups: Dict[Tuple[str, float, float], List[Dict[str, Any]]] = {}
        for segment in raw_segments:
            horizontal = segment["side"] in ("south", "north")
            axis = "h" if horizontal else "v"
            fixed = segment["y1"] if horizontal else segment["x1"]
            key = (axis, round(fixed, 4), round(segment["z"], 4))
            line_groups.setdefault(key, []).append(segment)

        atomic = []
        for (axis, fixed, z), segments in sorted(line_groups.items()):
            points = sorted({
                round(value, 4)
                for segment in segments
                for value in ((segment["x1"], segment["x2"]) if axis == "h" else (segment["y1"], segment["y2"]))
            })
            for start, end in zip(points, points[1:]):
                if end - start <= 0.01:
                    continue
                middle = (start + end) / 2.0
                covering = []
                for segment in segments:
                    a, b = ((segment["x1"], segment["x2"]) if axis == "h" else (segment["y1"], segment["y2"]))
                    if min(a, b) - 0.01 <= middle <= max(a, b) + 0.01:
                        covering.append(segment)
                if not covering:
                    continue
                connected = sorted({segment["room_id"] for segment in covering})
                side = covering[0]["side"]
                on_boundary = (
                    (axis == "h" and (abs(fixed - sb_front) < 0.05 or abs(fixed - (sb_front + bldg_d)) < 0.05)) or
                    (axis == "v" and (abs(fixed - sb_left) < 0.05 or abs(fixed - (sb_left + bldg_w)) < 0.05))
                )
                is_ext = len(connected) == 1 and on_boundary
                signature = (axis, fixed, z, tuple(connected), is_ext, side)
                if atomic and atomic[-1]["signature"] == signature and abs(atomic[-1]["end"] - start) < 0.01:
                    atomic[-1]["end"] = end
                else:
                    atomic.append({
                        "axis": axis, "fixed": fixed, "z": z, "start": start, "end": end,
                        "connected": connected, "is_ext": is_ext, "side": side, "signature": signature,
                    })

        walls = []
        for index, item in enumerate(atomic, 1):
            horizontal = item["axis"] == "h"
            x1, y1 = (item["start"], item["fixed"]) if horizontal else (item["fixed"], item["start"])
            x2, y2 = (item["end"], item["fixed"]) if horizontal else (item["fixed"], item["end"])
            thickness = wall_t if item["is_ext"] else min(wall_t, 0.15)
            walls.append({
                "id": f"wall_{'ext' if item['is_ext'] else 'part'}_{index:03d}",
                "type": "exterior" if item["is_ext"] else "interior",
                "side": item["side"],
                "start": {"x": round(x1, 2), "y": round(y1, 2), "z": round(item["z"], 2)},
                "end": {"x": round(x2, 2), "y": round(y2, 2), "z": round(item["z"], 2)},
                "position": {"x": round((x1 + x2) / 2.0, 2), "y": round((y1 + y2) / 2.0, 2), "z": round(item["z"], 2)},
                "dimensions": {
                    "width": round(item["end"] - item["start"], 2) if horizontal else thickness,
                    "depth": thickness if horizontal else round(item["end"] - item["start"], 2),
                    "height": 3.0,
                },
                "thickness": thickness,
                "height": 3.0,
                "connected_rooms": item["connected"],
            })
        return walls

    # ─── Wall-Hosted Openings (Doors & Windows) ───────────────────────────────

    def _generate_doors(
        self,
        rooms: List[Dict[str, Any]],
        walls: List[Dict[str, Any]],
        is_ground: bool,
        connection_preferences: Optional[List[List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Create openings only on real shared wall segments.

        Door relationships are selected by room function (and explicit prompt
        preferences), then the exact canonical wall id is recorded.  This avoids
        the old behaviour that placed a bathroom door against the first room in
        list order or invented a wall id that did not exist in Blender.
        """
        if not rooms:
            return []

        doors: List[Dict[str, Any]] = []
        room_map = {str(room["id"]): room for room in rooms}

        def type_group(room: Dict[str, Any]) -> str:
            value = str(room.get("type", "")).lower()
            if "bath" in value or "wash" in value: return "bathroom"
            if "bed" in value: return "bedroom"
            if "living" in value or "lounge" in value: return "living_room"
            if "kitchen" in value: return "kitchen"
            if "dining" in value: return "dining_room"
            if "corridor" in value or "hallway" in value: return "corridor"
            if "foyer" in value or "entry" in value: return "foyer"
            if "garage" in value: return "garage"
            return value

        def wall_length(wall: Dict[str, Any]) -> float:
            start, end = wall.get("start", {}), wall.get("end", {})
            return math.hypot(float(end.get("x", 0)) - float(start.get("x", 0)),
                              float(end.get("y", 0)) - float(start.get("y", 0)))

        shared: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        exterior: Dict[str, List[Dict[str, Any]]] = {}
        for wall in walls:
            connected = [str(value) for value in wall.get("connected_rooms", []) if str(value) in room_map]
            if len(connected) >= 2:
                # A narrow incidental contact is not a usable doorway. Treating
                # it as circulation used to squeeze a door into a 0.58 m wall.
                if wall_length(wall) < 1.05:
                    continue
                for index, first in enumerate(connected):
                    for second in connected[index + 1:]:
                        shared.setdefault(tuple(sorted((first, second))), []).append(wall)
            elif len(connected) == 1:
                exterior.setdefault(connected[0], []).append(wall)

        def side_for(room: Dict[str, Any], wall: Dict[str, Any]) -> str:
            pos, dim = room["position"], room["dimensions"]
            x0, y0 = float(pos["x"]), float(pos["y"])
            x1, y1 = x0 + float(dim["width"]), y0 + float(dim["depth"])
            start, end = wall.get("start", {}), wall.get("end", {})
            wx = (float(start.get("x", 0)) + float(end.get("x", 0))) / 2.0
            wy = (float(start.get("y", 0)) + float(end.get("y", 0))) / 2.0
            return min(((abs(wy - y0), "south"), (abs(wy - y1), "north"),
                        (abs(wx - x0), "west"), (abs(wx - x1), "east")), key=lambda value: value[0])[1]

        def opening_on_wall(wall: Dict[str, Any], room: Dict[str, Any], width: float) -> Tuple[str, Dict[str, float]]:
            start, end = wall.get("start", {}), wall.get("end", {})
            x1, y1 = float(start.get("x", 0)), float(start.get("y", 0))
            x2, y2 = float(end.get("x", 0)), float(end.get("y", 0))
            side = side_for(room, wall)
            margin = min(0.35, max(0.12, (wall_length(wall) - width) / 4.0))
            if abs(x2 - x1) >= abs(y2 - y1):
                lo, hi = sorted((x1, x2))
                center = min(max(lo + margin + width / 2.0, (lo + hi) / 2.0), hi - margin - width / 2.0)
                position = {"x": round(center, 2), "y": round((y1 + y2) / 2.0, 2), "z": round(float(room["position"].get("z", 0)), 2)}
            else:
                lo, hi = sorted((y1, y2))
                center = min(max(lo + margin + width / 2.0, (lo + hi) / 2.0), hi - margin - width / 2.0)
                position = {"x": round((x1 + x2) / 2.0, 2), "y": round(center, 2), "z": round(float(room["position"].get("z", 0)), 2)}
            return side, position

        # Main entrance belongs to a real exterior segment of the living/foyer.
        entry = next((room for room in rooms if type_group(room) == "foyer"), None)
        entry = entry or next((room for room in rooms if type_group(room) == "living_room"), None)
        entry = entry or next((room for room in rooms if type_group(room) == "kitchen"), None)
        entry = entry or next((room for room in rooms if type_group(room) != "garage"), rooms[0])
        if is_ground and exterior.get(str(entry["id"])):
            candidates = exterior[str(entry["id"])]
            south = [wall for wall in candidates if side_for(entry, wall) == "south"]
            host = max(south or candidates, key=wall_length)
            width = min(1.10, max(0.75, wall_length(host) - 0.40))
            side, position = opening_on_wall(host, entry, width)
            doors.append({
                "id": "door_main_entrance", "roomId": entry["id"], "room_id": entry["id"],
                "connected_room_ids": [entry["id"], "exterior"], "wall_id": host["id"],
                "wall": {"south": "front", "north": "back", "west": "left", "east": "right"}[side],
                "wall_side": side, "type": "main_entrance", "position": position,
                "width": width, "height": 2.20, "swing": "inward_right",
            })

        # Garage vehicle openings are exterior; pedestrian access is selected
        # below through the same shared-wall graph as every other room.
        for garage in (room for room in rooms if type_group(room) == "garage"):
            candidates = exterior.get(str(garage["id"]), [])
            if candidates:
                south = [wall for wall in candidates if side_for(garage, wall) == "south"]
                host = max(south or candidates, key=wall_length)
                width = min(2.80, max(1.80, wall_length(host) - 0.40))
                side, position = opening_on_wall(host, garage, width)
                doors.append({
                    "id": f"door_garage_roll_{garage['id']}", "roomId": garage["id"], "room_id": garage["id"],
                    "connected_room_ids": [garage["id"], "exterior"], "wall_id": host["id"],
                    "wall": {"south": "front", "north": "back", "west": "left", "east": "right"}[side],
                    "wall_side": side, "type": "garage_door", "position": position,
                    "width": width, "height": 2.40, "swing": "overhead",
                })

        adjacency = {rid: [] for rid in room_map}
        for pair, pair_walls in shared.items():
            adjacency[pair[0]].append((pair[1], pair_walls))
            adjacency[pair[1]].append((pair[0], pair_walls))

        selected: List[Tuple[str, str]] = []
        selected_set = set()

        def select_pair(first: str, second: str) -> bool:
            pair = tuple(sorted((first, second)))
            if first == second or pair not in shared or pair in selected_set:
                return False
            selected.append(pair)
            selected_set.add(pair)
            return True

        # Explicit prompt edits win whenever those spaces share a partition.
        for preference in connection_preferences or []:
            if not isinstance(preference, (list, tuple)) or len(preference) != 2:
                continue
            left = [room for room in rooms if type_group(room) == str(preference[0])]
            right = [room for room in rooms if type_group(room) == str(preference[1])]
            for first in left:
                match = next((second for second in right if tuple(sorted((str(first["id"]), str(second["id"])))) in shared), None)
                if match:
                    select_pair(str(first["id"]), str(match["id"]))

        priorities = {
            "bathroom": ["bedroom", "corridor", "foyer", "living_room", "dining_room", "kitchen"],
            "bedroom": ["corridor", "living_room", "foyer", "dining_room", "kitchen"],
            "kitchen": ["living_room", "dining_room", "corridor", "foyer"],
            "dining_room": ["living_room", "kitchen", "corridor", "foyer"],
            "garage": ["corridor", "foyer", "living_room", "kitchen"],
            "corridor": ["foyer", "living_room"],
            "foyer": ["living_room", "corridor"],
        }
        for room in rooms:
            rid, group = str(room["id"]), type_group(room)
            if rid == str(entry["id"]):
                continue
            neighbors = adjacency.get(rid, [])
            ranked = sorted(neighbors, key=lambda value: (
                priorities.get(group, ["corridor", "living_room"]).index(type_group(room_map[value[0]]))
                if type_group(room_map[value[0]]) in priorities.get(group, ["corridor", "living_room"]) else 99,
                value[0],
            ))
            if ranked:
                select_pair(rid, ranked[0][0])

        # Ensure every room is reachable from the entrance, adding the smallest
        # number of additional shared-wall doors needed to join components.
        parent = {rid: rid for rid in room_map}
        def find(value: str) -> str:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value
        def union(first: str, second: str) -> None:
            a, b = find(first), find(second)
            if a != b: parent[b] = a
        for first, second in selected:
            union(first, second)
        for first, second in sorted(shared):
            if find(first) != find(second):
                select_pair(first, second)
                union(first, second)

        for index, (first, second) in enumerate(selected, 1):
            host = max(shared[(first, second)], key=wall_length)
            room = room_map[first]
            width = min(0.85 if type_group(room) == "bathroom" or type_group(room_map[second]) == "bathroom" else 0.90,
                        max(0.65, wall_length(host) - 0.40))
            side, position = opening_on_wall(host, room, width)
            doors.append({
                "id": f"door_{first}_{second}", "roomId": first, "room_id": first,
                "connected_room_ids": [first, second], "wall_id": host["id"],
                "wall": {"south": "front", "north": "back", "west": "left", "east": "right"}[side],
                "wall_side": side, "type": "interior_door", "position": position,
                "width": width, "height": 2.10, "swing": "inward_right",
            })

        return doors

    def _generate_windows(
        self,
        rooms: List[Dict[str, Any]],
        walls: List[Dict[str, Any]],
        bldg_w: float,
        bldg_d: float,
        sb_left: float,
        sb_front: float
    ) -> List[Dict[str, Any]]:
        """Places exterior windows only along perimeter building walls."""
        windows = []

        for r in rooms:
            rid = r["id"]
            rx = r["position"]["x"]
            ry = r["position"]["y"]
            rz = r["position"]["z"]
            rw = r["dimensions"]["width"]
            rd = r["dimensions"]["depth"]
            rtype = r["type"]
            is_bath = "bath" in rtype

            # South exterior window (front facing road)
            if abs(ry - sb_front) < 0.25 and rtype != "garage":
                is_living = "living" in rtype
                win_w = 2.40 if is_living else (1.00 if is_bath else 1.60)
                # Offset if room front wall has the main entrance door
                has_front_door = (rtype == "living_room") or (r == rooms[0])
                win_x = round(rx + rw * 0.25, 2) if has_front_door else round(rx + rw * 0.5, 2)
                windows.append({
                    "id": f"win_{rid}_south",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "front",
                    "wall_side": "south",
                    "position": {"x": win_x, "y": round(ry, 2), "z": round(rz + (1.2 if is_bath else 0.9), 2)},
                    "width": win_w,
                    "height": 0.90 if is_bath else 1.50,
                    "sill_height": 1.30 if is_bath else 0.80,
                })

            # North exterior window (rear facing)
            if abs((ry + rd) - (sb_front + bldg_d)) < 0.25:
                win_w = 1.00 if is_bath else (1.80 if "bed" in rtype else (1.40 if "office" in rtype else 0.90))
                windows.append({
                    "id": f"win_{rid}_north",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "back",
                    "wall_side": "north",
                    "position": {"x": round(rx + rw * 0.5, 2), "y": round(ry + rd, 2), "z": round(rz + (1.2 if is_bath else 0.9), 2)},
                    "width": win_w,
                    "height": 0.90 if is_bath else 1.40,
                    "sill_height": 1.30 if is_bath else 0.90,
                })

            # West exterior window (left flank)
            if abs(rx - sb_left) < 0.25 and rtype != "garage":
                win_w = 1.00 if is_bath else 1.50
                windows.append({
                    "id": f"win_{rid}_west",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "left",
                    "wall_side": "west",
                    "position": {"x": round(rx, 2), "y": round(ry + rd * 0.5, 2), "z": round(rz + (1.2 if is_bath else 0.9), 2)},
                    "width": win_w,
                    "height": 0.90 if is_bath else 1.30,
                    "sill_height": 1.30 if is_bath else 0.90,
                })

            # East exterior window (right flank)
            if abs((rx + rw) - (sb_left + bldg_w)) < 0.25:
                win_w = 1.00 if is_bath else (1.40 if "kitchen" in rtype else 1.60)
                windows.append({
                    "id": f"win_{rid}_east",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "right",
                    "wall_side": "east",
                    "position": {"x": round(rx + rw, 2), "y": round(ry + rd * 0.5, 2), "z": round(rz + (1.2 if is_bath else 0.9), 2)},
                    "width": win_w,
                    "height": 0.90 if is_bath else 1.30,
                    "sill_height": 1.30 if is_bath else 0.90,
                })

        return windows

    # ─── Architectural Furniture Placement ────────────────────────────────────

    def _place_furniture_for_rooms(
        self,
        rooms: List[Dict[str, Any]],
        style: str,
        elevation: float = 0.0,
        doors: Optional[List[Dict[str, Any]]] = None,
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
                    ) for zone in door_zones)

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

            if rtype == "living_room":
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
                        "dimensions": {"width": 2.2, "depth": 0.95, "height": 0.82},
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
                        "dimensions": {"width": 1.8, "depth": 0.45, "height": 0.60},
                    },
                ]
                # Keep compact living rooms genuinely compact. Optional tables
                # and media storage previously forced requested 11 x 12 m homes
                # into a validation failure after circulation clearances were
                # applied. The sofa and chair remain; larger rooms get the full
                # furniture group.
                if rw * rd < 20.0:
                    living_items = [living_items[0]]
                for item in living_items:
                    _add(item)
            elif "bedroom" in rtype:
                bed_y = round(ry + rd - 1.15, 2)
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
                        "dimensions": {"width": 2.1, "depth": 2.15, "height": 1.10},
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
                        "asset_id": "modren_wooden_cabinet_01",
                        "category": "wardrobe",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(rx + 0.65, 2), "y": round(ry + 0.8, 2), "z": floor_elev},
                        "rotation": 90.0,
                        "anchor_wall": "west",
                        "dimensions": {"width": 1.2, "depth": 0.60, "height": 2.00},
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
                for item in [
                    {
                        "id": f"island_{rid}",
                        "asset": "kitchen_island",
                        "asset_id": "kitchen_island_001",
                        "category": "kitchen_counter",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": cy, "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 1.8, "depth": 0.90, "height": 0.92},
                    },
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
                        "dimensions": {"width": 0.80, "depth": 0.55, "height": 0.88},
                    },
                ]:
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
                        "dimensions": {"width": 0.90, "depth": 0.90, "height": 2.00},
                    })
                for item in bath_items:
                    _add(item)
            elif rtype == "dining_room":
                for item in [
                    {
                        "id": f"table_{rid}",
                        "asset": "dining_table",
                        "asset_id": "dining_table_001",
                        "category": "dining_table",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": cy, "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 1.60, "depth": 0.85, "height": 0.76},
                    },
                    {
                        "id": f"chair_{rid}_1",
                        "asset": "dining_chair",
                        "asset_id": "dining_chair_001",
                        "category": "chair",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(cx - 0.50, 2), "y": round(cy - 0.55, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.85},
                    },
                    {
                        "id": f"chair_{rid}_2",
                        "asset": "dining_chair",
                        "asset_id": "dining_chair_001",
                        "category": "chair",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(cx + 0.50, 2), "y": round(cy - 0.55, 2), "z": floor_elev},
                        "rotation": 0.0,
                        "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.85},
                    },
                    {
                        "id": f"chair_{rid}_3",
                        "asset": "dining_chair",
                        "asset_id": "dining_chair_001",
                        "category": "chair",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(cx - 0.50, 2), "y": round(cy + 0.55, 2), "z": floor_elev},
                        "rotation": 180.0,
                        "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.85},
                    },
                    {
                        "id": f"chair_{rid}_4",
                        "asset": "dining_chair",
                        "asset_id": "dining_chair_001",
                        "category": "chair",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": round(cx + 0.50, 2), "y": round(cy + 0.55, 2), "z": floor_elev},
                        "rotation": 180.0,
                        "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.85},
                    },
                ]:
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
                    "dimensions": {"width": 2.0, "depth": 4.5, "height": 1.50},
                })

        return furniture

    # ─── Integration Bridge with Gemini Output ────────────────────────────────

    def _rooms_for_explicit_program(
        self,
        raw_rooms: List[Dict[str, Any]],
        constraints: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Reconcile Gemini rooms to the exact deterministic prompt inventory."""
        requested_counts = constraints.get("room_counts", {})
        bedroom_types = {"bedroom", "master_bedroom", "guest_room"}
        bathroom_types = {"bathroom", "master_bathroom"}

        def family(room_type: str) -> str:
            normalized = self._classify_room_type(room_type)
            if normalized in bedroom_types:
                return "bedroom"
            if normalized in bathroom_types:
                return "bathroom"
            return normalized

        available = [room for room in raw_rooms if isinstance(room, dict)]
        selected: List[Dict[str, Any]] = []
        used_indices = set()
        labels = {
            "bedroom": "Bedroom",
            "master_bedroom": "Master Bedroom",
            "guest_room": "Guest Room",
            "bathroom": "Bathroom",
            "kitchen": "Kitchen",
            "living_room": "Living Room",
            "dining_room": "Dining Room",
            "garage": "Garage",
            "home_office": "Home Office",
        }

        for requested_type, raw_count in requested_counts.items():
            count = max(0, int(raw_count))
            output_type = requested_type
            if requested_type == "bedroom":
                output_type = constraints.get("bedroom_type", "bedroom")

            candidates = [
                (index, room)
                for index, room in enumerate(available)
                if index not in used_indices
                and family(str(room.get("type", room.get("name", "")))) == requested_type
            ]
            # Prefer the exact requested bedroom kind. An unsolicited master
            # bedroom must not become a second sleeping room.
            candidates.sort(key=lambda value: (
                self._classify_room_type(str(value[1].get("type", ""))) != output_type,
                value[0],
            ))

            for ordinal in range(1, count + 1):
                if candidates:
                    source_index, source = candidates.pop(0)
                    used_indices.add(source_index)
                    room = dict(source)
                else:
                    room = {}

                label = labels.get(output_type, output_type.replace("_", " ").title())
                room["id"] = str(room.get("id") or f"requested_{output_type}_{ordinal:02d}")
                room["type"] = output_type
                room["name"] = label if count == 1 else f"{label} {ordinal}"
                selected.append(room)

        return selected

    def solve_or_refine_design(self, design_data: Dict[str, Any], prompt: str = "") -> Dict[str, Any]:
        """
        Takes raw Gemini design output (with arbitrary/missing coordinates) and
        produces a mathematically validated, contiguous architectural CAD model.
        """
        from utils.gemini_layout import infer_layout_constraints

        constraints = infer_layout_constraints(prompt)

        # Extract plot dimensions or use standard architectural envelope
        plot_info = design_data.get("site", {}).get("plot", {})
        house_info = design_data.get("house", {})
        pw = float(plot_info.get("width") or house_info.get("width") or 14.0)
        pd = float(plot_info.get("depth") or house_info.get("length") or 18.0)

        floors_cnt = int(house_info.get("floors") or (len(design_data.get("floors", [])) or constraints.get("floors_count", 1)))

        # Build room requirement list
        raw_rooms = design_data.get("rooms", [])
        strict_room_program = bool(
            constraints.get("replace_room_program")
            and constraints.get("room_counts")
        )
        if strict_room_program:
            raw_rooms = self._rooms_for_explicit_program(raw_rooms, constraints)
        style = design_data.get("style") or house_info.get("style") or "modern"

        requirements = {
            "project_name": design_data.get("project_name", "ArchiGen Residential Home"),
            "style": style,
            "orientation": design_data.get("site", {}).get("road", {}).get("side", "south"),
            "plot": {"width": pw, "depth": pd},
            "floors": floors_cnt,
            "rooms": raw_rooms if raw_rooms else [],
            "connection_preferences": constraints.get("connections", []),
            "strict_room_program": strict_room_program,
        }

        # If rooms list was empty, populate from constraints
        if not requirements["rooms"]:
            for rtype, count in constraints.get("room_counts", {}).items():
                for _ in range(count):
                    requirements["rooms"].append({"type": rtype, "name": rtype.replace("_", " ").title()})

        # Run deterministic constraint engine
        solved_doc = self.generate_layout(requirements)

        # Merge custom PBR materials from Gemini where matching
        gemini_rooms_by_type = {}
        for gr in raw_rooms:
            gt = str(gr.get("type", "")).lower()
            if gt not in gemini_rooms_by_type:
                gemini_rooms_by_type[gt] = gr

        for fl in solved_doc.get("floors", []):
            for r in fl.get("rooms", []):
                rt = str(r.get("type", "")).lower()
                matching_gr = gemini_rooms_by_type.get(rt)
                if matching_gr and "materials" in matching_gr:
                    r["materials"] = matching_gr["materials"]
                if matching_gr and "pbr_material" in matching_gr:
                    r["pbr_material"] = matching_gr["pbr_material"]

        return solved_doc
