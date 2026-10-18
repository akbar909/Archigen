"""Contiguous room placement and room metadata."""

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

class RoomPlacementMixin:
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

        # Repair narrow layout slivers before walls, openings, and furniture are
        # derived from these rectangles. This also keeps canonical dimensions
        # synchronized with the legacy width/length schema fields.
        self._repair_schema_minimum_room_spans(rooms)

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
                    new_width = round(b["dimensions"]["width"] * (scale ** 0.5), 2)
                    new_depth = round(b["dimensions"]["depth"] * (scale ** 0.5), 2)
                    # Do not turn a valid room into an invalid sub-1.5 m sliver.
                    if new_width >= 1.5 and new_depth >= 1.5:
                        b["dimensions"]["width"] = new_width
                        b["dimensions"]["depth"] = new_depth
                        b["width"] = new_width
                        b["length"] = new_depth

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

        pbr_material = {
            "floor": {"color": materials.get("floor", {}).get("color", "#CCCCCC"), "pattern": materials.get("floor", {}).get("pattern", "wood_planks")},
            "walls": {"color": materials.get("walls", {}).get("color", "#F0EDE8"), "pattern": materials.get("walls", {}).get("pattern", "plain")},
        }
        if isinstance(materials.get("accent_wall"), dict):
            pbr_material["accent_wall"] = dict(materials["accent_wall"])

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
            "pbr_material": pbr_material,
        }

    def _default_materials(self, room_type: str) -> Dict[str, Any]:
        if "living" in room_type:
            return {
                "floor": {"pattern": "wood_planks", "color": "#7A5C3D"},
                "walls": {"pattern": "plain", "color": "#F4F1EA"},
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



