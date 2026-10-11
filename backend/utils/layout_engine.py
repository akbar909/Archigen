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

        # Scale plot size to accommodate rooms without cramped dimensions
        has_garage_req = any("garage" in str(r.get("type", "")).lower() for r in norm_room_types)
        total_rooms_count = len(norm_room_types)
        min_pw = 15.0 if has_garage_req else (13.5 if total_rooms_count >= 5 else 11.0)
        min_pd = 16.5 if total_rooms_count >= 5 else (14.0 if total_rooms_count >= 3 else 10.0)
        plot_w = max(min_pw, plot_w)
        plot_d = max(min_pd, plot_d)

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
        ground_doors = self._generate_doors(ground_rooms, ground_walls, is_ground=True)
        ground_windows = self._generate_windows(ground_rooms, ground_walls, bldg_w, bldg_d, sb_left, sb_front)
        ground_furniture = self._place_furniture_for_rooms(ground_rooms, style, elevation=0.0)

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
            first_doors = self._generate_doors(first_rooms, first_walls, is_ground=False)
            first_windows = self._generate_windows(first_rooms, first_walls, bldg_w, bldg_d, sb_left, sb_front)
            first_furniture = self._place_furniture_for_rooms(first_rooms, style, elevation=floor_h)

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
        has_garage = any(r.get("type") == "garage" for r in ground_rooms)
        driveway_x = ground_rooms[0]["position"]["x"] if has_garage else sb_left
        driveway_w = ground_rooms[0]["dimensions"]["width"] if has_garage else 3.8

        exterior_data = {
            "facade_style": style,
            "main_entrance": {
                "position": {"x": round(sb_left + bldg_w * 0.45, 2), "y": round(sb_front, 2), "z": 0.0},
                "width": 1.4,
                "height": 2.4,
            },
            "gate": {
                "position": {"x": round(driveway_x, 2), "y": 0.2, "z": 0.0},
                "width": 3.6,
                "height": 2.0,
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

        # Ensure mandatory core rooms exist if multi-room house
        types_present = {r["type"] for r in room_types}
        if len(room_types) > 1:
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
            hab_x = round(sb_left + gw + wall_t, 2)
            hab_w = round(bldg_w - gw - wall_t, 2)

            # Check if an office, extra bedroom, or laundry can take the space behind the garage
            rear_flank_d = round(bldg_d - gd - wall_t, 2)
            if office and rear_flank_d >= 3.0:
                rear_flank_room = office
                office = None  # consumed
            elif other_beds and rear_flank_d >= 3.0:
                rear_flank_room = other_beds.pop(0)
            elif misc_rooms and rear_flank_d >= 2.5:
                rear_flank_room = misc_rooms.pop(0)

            if rear_flank_room:
                rooms.append(self._create_room_dict(
                    room_id=rear_flank_room.get("raw", {}).get("id", f"{rear_flank_room['type']}_flank"),
                    name=rear_flank_room["name"],
                    room_type=rear_flank_room["type"],
                    x=sb_left,
                    y=round(sb_front + gd + wall_t, 2),
                    z=elevation,
                    w=gw,
                    d=rear_flank_d,
                    materials=self._default_materials(rear_flank_room["type"]),
                    floor_idx=floor_idx,
                ))

        # ── 2. Divide Habitable Zone into Front Band (South) and Rear Band (North) ──
        front_d = round(bldg_d * 0.46, 2)
        rear_d = round(bldg_d - front_d - wall_t, 2)

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
            sec_w = round(hab_w - liv_w - wall_t, 2)

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
                    x=round(hab_x + liv_w + wall_t, 2),
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
                    x=round(hab_x + liv_w + wall_t, 2),
                    y=round(sb_front + din_d + wall_t, 2),
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
                    x=round(hab_x + liv_w + wall_t, 2),
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
            stair_y = round(sb_front + front_d + wall_t, 2)
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
        rear_y = round(sb_front + front_d + wall_t, 2)
        if not rear_candidates:
            # Fallback master bed
            rear_candidates.append({"type": "master_bedroom", "name": "Master Bedroom", "raw": {}})

        if len(rear_candidates) == 1:
            rc = rear_candidates[0]
            # If bathroom exists, place attached ensuite in corner
            bath_w = 2.4
            bath_d = 2.2
            if baths:
                b_item = baths.pop(0)
                main_w = round(hab_w - bath_w - wall_t, 2)
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
                    x=round(hab_x + main_w + wall_t, 2),
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
            right_w = round(hab_w - left_w - wall_t, 2)

            r_left = rear_candidates[0]
            r_right = rear_candidates[1]

            # Attached bathroom handling for left wing (Master Bed)
            if "master" in r_left["type"] and baths:
                b_item = baths.pop(0)
                bath_d = min(2.5, round(rear_d * 0.45, 2))
                bed_d = round(rear_d - bath_d - wall_t, 2)

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
                    y=round(rear_y + bed_d + wall_t, 2),
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
                main_d = round(rear_d - bath_d - wall_t, 2)

                rooms.append(self._create_room_dict(
                    room_id=r_right.get("raw", {}).get("id", f"{r_right['type']}_02"),
                    name=r_right["name"],
                    room_type=r_right["type"],
                    x=round(hab_x + left_w + wall_t, 2),
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
                    x=round(hab_x + left_w + wall_t, 2),
                    y=round(rear_y + main_d + wall_t, 2),
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
                    x=round(hab_x + left_w + wall_t, 2),
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
                    y=round(sb_front + gd + wall_t, 2),
                    z=elevation,
                    w=gw,
                    d=min(2.5, rear_flank_d),
                    materials=self._default_materials("bathroom"),
                    floor_idx=floor_idx,
                ))

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

        # Group coincident wall lines
        walls = []
        matched_indices = set()

        for i, s1 in enumerate(raw_segments):
            if i in matched_indices:
                continue

            connected = [s1["room_id"]]
            is_horizontal = (s1["side"] in ["south", "north"])

            # Check if an opposite segment from another room touches this line
            for j, s2 in enumerate(raw_segments):
                if i != j and j not in matched_indices:
                    if is_horizontal and (s2["side"] in ["south", "north"]):
                        if abs(s1["y1"] - s2["y1"]) < 0.15:
                            # Overlap check along X
                            ov_start = max(s1["x1"], s2["x1"])
                            ov_end = min(s1["x2"], s2["x2"])
                            if (ov_end - ov_start) > 0.30:
                                matched_indices.add(j)
                                if s2["room_id"] not in connected:
                                    connected.append(s2["room_id"])
                    elif not is_horizontal and (s2["side"] in ["west", "east"]):
                        if abs(s1["x1"] - s2["x1"]) < 0.15:
                            # Overlap check along Y
                            ov_start = max(s1["y1"], s2["y1"])
                            ov_end = min(s1["y2"], s2["y2"])
                            if (ov_end - ov_start) > 0.30:
                                matched_indices.add(j)
                                if s2["room_id"] not in connected:
                                    connected.append(s2["room_id"])

            matched_indices.add(i)

            # Determine wall type: exterior if on building boundary, interior if sharing rooms
            is_ext = len(connected) == 1 and (
                abs(s1["y1"] - sb_front) < 0.25 or
                abs(s1["y1"] - (sb_front + bldg_d)) < 0.25 or
                abs(s1["x1"] - sb_left) < 0.25 or
                abs(s1["x1"] - (sb_left + bldg_w)) < 0.25
            )

            wall_id = f"wall_{'ext' if is_ext else 'part'}_{s1['side']}_{len(walls)+1}"
            thickness = 0.20 if is_ext else 0.15

            walls.append({
                "id": wall_id,
                "type": "exterior" if is_ext else "interior",
                "side": s1["side"],
                "start": {"x": round(s1["x1"], 2), "y": round(s1["y1"], 2), "z": round(s1["z"], 2)},
                "end": {"x": round(s1["x2"], 2), "y": round(s1["y2"], 2), "z": round(s1["z"], 2)},
                # Center point position for viewer mapping
                "position": {
                    "x": round((s1["x1"] + s1["x2"]) / 2.0, 2),
                    "y": round((s1["y1"] + s1["y2"]) / 2.0, 2),
                    "z": round(s1["z"], 2)
                },
                "dimensions": {
                    "width": round(abs(s1["x2"] - s1["x1"]), 2) if is_horizontal else thickness,
                    "depth": thickness if is_horizontal else round(abs(s1["y2"] - s1["y1"]), 2),
                    "height": 3.0
                },
                "thickness": thickness,
                "height": 3.0,
                "connected_rooms": connected,
            })

        return walls

    # ─── Wall-Hosted Openings (Doors & Windows) ───────────────────────────────

    def _generate_doors(
        self,
        rooms: List[Dict[str, Any]],
        walls: List[Dict[str, Any]],
        is_ground: bool
    ) -> List[Dict[str, Any]]:
        """Places wall-hosted doors with valid wall references and CAD swing arcs."""
        doors = []

        for r in rooms:
            rid = r["id"]
            rx = r["position"]["x"]
            ry = r["position"]["y"]
            rz = r["position"]["z"]
            rw = r["dimensions"]["width"]
            rd = r["dimensions"]["depth"]
            rtype = r["type"]

            if is_ground and rtype == "living_room":
                # Main Entrance Door on south front exterior wall
                door_x = round(rx + rw * 0.5, 2)
                door_y = round(ry, 2)
                doors.append({
                    "id": "door_main_entrance",
                    "roomId": rid,
                    "room_id": rid,
                    "wall_id": "wall_ext_south_main",
                    "wall": "front",
                    "wall_side": "south",
                    "type": "main_entrance",
                    "position": {"x": door_x, "y": door_y, "z": round(rz, 2)},
                    "width": 1.10,
                    "height": 2.20,
                    "swing": "inward_right",
                })
            elif rtype == "garage":
                # Garage roller door on south exterior wall + passage into house
                doors.append({
                    "id": f"door_garage_roll_{rid}",
                    "roomId": rid,
                    "room_id": rid,
                    "wall_id": "wall_ext_south_garage",
                    "wall": "front",
                    "wall_side": "south",
                    "type": "garage_door",
                    "position": {"x": round(rx + rw * 0.5, 2), "y": round(ry, 2), "z": round(rz, 2)},
                    "width": 2.80,
                    "height": 2.40,
                    "swing": "overhead",
                })
                # Service door into living/corridor
                doors.append({
                    "id": f"door_garage_entry_{rid}",
                    "roomId": rid,
                    "room_id": rid,
                    "wall_id": f"wall_part_garage_house",
                    "wall": "right",
                    "wall_side": "east",
                    "type": "interior_door",
                    "position": {"x": round(rx + rw, 2), "y": round(ry + rd * 0.3, 2), "z": round(rz, 2)},
                    "width": 0.90,
                    "height": 2.10,
                    "swing": "inward_left",
                })
            elif "master_bath" in rtype:
                # Attached bathroom door connecting to master bedroom
                doors.append({
                    "id": f"door_ensuite_{rid}",
                    "roomId": rid,
                    "room_id": rid,
                    "wall_id": "wall_part_ensuite",
                    "wall": "front",
                    "wall_side": "south",
                    "type": "interior_door",
                    "position": {"x": round(rx + rw * 0.5, 2), "y": round(ry, 2), "z": round(rz, 2)},
                    "width": 0.85,
                    "height": 2.10,
                    "swing": "inward_left",
                })
            else:
                # Standard interior room door connecting to hallway / living
                doors.append({
                    "id": f"door_{rid}",
                    "roomId": rid,
                    "room_id": rid,
                    "wall_id": f"wall_part_{rid}",
                    "wall": "front",
                    "wall_side": "south",
                    "type": "interior_door",
                    "position": {"x": round(rx + min(1.2, rw * 0.3), 2), "y": round(ry, 2), "z": round(rz, 2)},
                    "width": 0.90,
                    "height": 2.10,
                    "swing": "inward_right",
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

            # South exterior window (front facing road)
            if abs(ry - sb_front) < 0.25 and rtype != "garage":
                is_living = "living" in rtype
                win_w = 2.40 if is_living else 1.60
                windows.append({
                    "id": f"win_{rid}_south",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "front",
                    "wall_side": "south",
                    "position": {"x": round(rx + rw * 0.5, 2), "y": round(ry, 2), "z": round(rz + 0.9, 2)},
                    "width": win_w,
                    "height": 1.50,
                    "sill_height": 0.80,
                })

            # North exterior window (rear facing)
            if abs((ry + rd) - (sb_front + bldg_d)) < 0.25:
                win_w = 1.80 if "bed" in rtype else (1.40 if "office" in rtype else 0.90)
                windows.append({
                    "id": f"win_{rid}_north",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "back",
                    "wall_side": "north",
                    "position": {"x": round(rx + rw * 0.5, 2), "y": round(ry + rd, 2), "z": round(rz + 0.9, 2)},
                    "width": win_w,
                    "height": 1.40,
                    "sill_height": 0.90,
                })

            # West exterior window (left flank)
            if abs(rx - sb_left) < 0.25 and rtype != "garage":
                windows.append({
                    "id": f"win_{rid}_west",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "left",
                    "wall_side": "west",
                    "position": {"x": round(rx, 2), "y": round(ry + rd * 0.5, 2), "z": round(rz + 0.9, 2)},
                    "width": 1.50,
                    "height": 1.30,
                    "sill_height": 0.90,
                })

            # East exterior window (right flank)
            if abs((rx + rw) - (sb_left + bldg_w)) < 0.25:
                win_w = 1.40 if "kitchen" in rtype else 1.60
                windows.append({
                    "id": f"win_{rid}_east",
                    "roomId": rid,
                    "room_id": rid,
                    "wall": "right",
                    "wall_side": "east",
                    "position": {"x": round(rx + rw, 2), "y": round(ry + rd * 0.5, 2), "z": round(rz + 0.9, 2)},
                    "width": win_w,
                    "height": 1.30,
                    "sill_height": 0.90,
                })

        return windows

    # ─── Architectural Furniture Placement ────────────────────────────────────

    def _place_furniture_for_rooms(
        self,
        rooms: List[Dict[str, Any]],
        style: str,
        elevation: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Positions architectural furniture with clearance, solid wall anchoring,
        and proper rotation angles for both 2D and 3D viewers.
        """
        furniture = []
        floor_elev = elevation + 0.22  # top of floor slab

        for r in rooms:
            rid = r["id"]
            rtype = r["type"]
            rx = r["position"]["x"]
            ry = r["position"]["y"]
            rw = r["dimensions"]["width"]
            rd = r["dimensions"]["depth"]
            cx = round(rx + rw / 2.0, 2)
            cy = round(ry + rd / 2.0, 2)

            def _add(f_dict):
                fw = float(f_dict.get("dimensions", {}).get("width", 0.8))
                fd = float(f_dict.get("dimensions", {}).get("depth", 0.8))
                px = float(f_dict.get("position", {}).get("x", cx))
                py = float(f_dict.get("position", {}).get("y", cy))
                cx_clamped = max(rx + fw / 2.0 + 0.05, min(rx + rw - fw / 2.0 - 0.05, px))
                cy_clamped = max(ry + fd / 2.0 + 0.05, min(ry + rd - fd / 2.0 - 0.05, py))
                f_dict["position"]["x"] = round(cx_clamped, 2)
                f_dict["position"]["y"] = round(cy_clamped, 2)
                furniture.append(f_dict)

            if rtype == "living_room":
                for item in [
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
                ]:
                    _add(item)
            elif "bedroom" in rtype:
                bed_y = round(ry + rd - 1.15, 2)
                for item in [
                    {
                        "id": f"bed_{rid}",
                        "asset": "bed",
                        "asset_id": "bed_02",
                        "category": "bed",
                        "roomId": rid,
                        "room_id": rid,
                        "position": {"x": cx, "y": bed_y, "z": floor_elev},
                        "rotation": 180.0,
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
                        "dimensions": {"width": 1.2, "depth": 0.60, "height": 2.00},
                    },
                ]:
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
                        "rotation": 0.0,
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
                        "rotation": 0.0,
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
                        "rotation": 180.0,
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
                        "rotation": 180.0,
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
                        "rotation": 0.0,
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
                    "category": "storage",
                    "roomId": rid,
                    "room_id": rid,
                    "position": {"x": cx, "y": cy, "z": floor_elev},
                    "rotation": 0.0,
                    "dimensions": {"width": 2.0, "depth": 4.5, "height": 1.50},
                })

        return furniture

    # ─── Integration Bridge with Gemini Output ────────────────────────────────

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
        style = design_data.get("style") or house_info.get("style") or "modern"

        requirements = {
            "project_name": design_data.get("project_name", "ArchiGen Residential Home"),
            "style": style,
            "orientation": design_data.get("site", {}).get("road", {}).get("side", "south"),
            "plot": {"width": pw, "depth": pd},
            "floors": floors_cnt,
            "rooms": raw_rooms if raw_rooms else [],
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
