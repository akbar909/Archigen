"""Top-level layout generation and floor-program distribution."""

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

class LayoutGenerationMixin:
    def generate_layout(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a complete Architectural JSON v3.0 document from high-level requirements.
        """
        proj_name = requirements.get("project_name", "ArchiGen Residential Home")
        style = str(requirements.get("style", "modern")).lower()
        if style == "minimal":
            style = "minimalist"
        if style not in VALID_STYLES:
            style = "modern"

        orientation = str(requirements.get("orientation", "south")).lower()
        if orientation not in VALID_ORIENTATIONS:
            orientation = "south"

        floors_count = int(requirements.get("floors", 1))
        if floors_count < 1 or floors_count > 4:
            raise ValueError(
                f"Requested {floors_count} floors, but this residential generator supports 1 to 4 floors."
            )

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

        # Use explicit wizard setbacks when supplied; otherwise use safe
        # residential defaults. Structured constraints are canonical metres.
        requested_setbacks = requirements.get("setbacks")
        requested_setbacks = requested_setbacks if isinstance(requested_setbacks, dict) else {}
        sb_front = round(float(requested_setbacks.get("front", min(plot_d * 0.18, 3.5))), 2)
        sb_back = round(float(requested_setbacks.get("back", min(plot_d * 0.12, 2.5))), 2)
        sb_left = round(float(requested_setbacks.get("left", min(plot_w * 0.10, 1.5))), 2)
        sb_right = round(float(requested_setbacks.get("right", min(plot_w * 0.10, 1.5))), 2)

        bldg_w = round(plot_w - sb_left - sb_right, 2)
        bldg_d = round(plot_d - sb_front - sb_back, 2)
        max_coverage = requirements.get("max_coverage")
        if max_coverage not in (None, ""):
            allowed_area = plot_w * plot_d * float(max_coverage) / 100.0
            if bldg_w > 0 and bldg_w * bldg_d > allowed_area:
                bldg_d = round(allowed_area / bldg_w, 2)
                sb_back = round(plot_d - sb_front - bldg_d, 2)
        if bldg_w < 3.0 or bldg_d < 3.0:
            raise ValueError(
                "The selected setbacks and maximum coverage leave too little buildable area."
            )
        wall_t = 0.20
        slab_t = 0.22
        floor_h = 3.0

        # 3. Generate every requested floor. Room allocation, aligned vertical
        # circulation, openings, and furniture all use the same floor list so a
        # three/four-storey request cannot silently collapse to two storeys.
        room_groups = self._split_rooms_across_floors(norm_room_types, floors_count)
        rooms_by_level: List[List[Dict[str, Any]]] = []
        for level, room_group in enumerate(room_groups):
            level_rooms, _ = self._layout_floor_rooms(
                room_types=room_group,
                bldg_w=bldg_w,
                bldg_d=bldg_d,
                sb_left=sb_left,
                sb_front=sb_front,
                floor_idx=level,
                has_stairs=False,
                style=style,
                wall_t=wall_t,
            )
            self._namespace_floor_room_ids(level_rooms, level)
            rooms_by_level.append(level_rooms)

        stair_core = self._find_aligned_stair_core(
            rooms_by_level, sb_left, sb_front, bldg_w, bldg_d, floor_h,
        ) if floors_count > 1 else None
        connection_preferences = requirements.get("connection_preferences", [])
        floors_data = []
        for level, level_rooms in enumerate(rooms_by_level):
            floor_id = self._floor_id(level)
            elevation = round(level * floor_h, 3)
            walls = self._compute_floor_walls(
                level_rooms, wall_t, sb_left, sb_front, bldg_w, bldg_d,
            )
            self._namespace_floor_wall_ids(walls, level)
            doors = self._generate_doors(
                level_rooms, walls, is_ground=level == 0,
                connection_preferences=connection_preferences,
            )
            windows = self._generate_windows(
                level_rooms, walls, bldg_w, bldg_d, sb_left, sb_front,
            )
            self._namespace_floor_opening_ids(doors, windows, level)

            stairs = []
            if stair_core and level < floors_count - 1:
                stairs.append(self._stair_between_levels(stair_core, level, floor_h))
            stair_openings = []
            if stair_core and level > 0:
                stair_openings.append({
                    "id": f"stair_opening_l{level}",
                    "position": {
                        "x": stair_core["position"]["x"],
                        "y": stair_core["position"]["y"],
                        "z": elevation,
                    },
                    "dimensions": dict(stair_core["opening_dimensions"]),
                    "serves_stair_id": f"stair_l{level - 1}_l{level}",
                })
            furniture = self._place_furniture_for_rooms(
                level_rooms, style, elevation=elevation, doors=doors,
                stair_zones=[stair_core] if stair_core else None,
            )
            floors_data.append({
                "id": floor_id,
                "level": level,
                "elevation": elevation,
                "floor_height": floor_h,
                "rooms": level_rooms,
                "walls": walls,
                "doors": doors,
                "windows": windows,
                "stairs": stairs,
                "stair_openings": stair_openings,
                "stair_core": copy.deepcopy(stair_core) if stair_core else None,
                "furniture": furniture,
                "ceiling": {
                    "type": "cove_recessed" if level == 0 else "flat",
                    "height": floor_h - (0.12 if level == 0 else 0.10),
                },
            })

        ground_rooms = rooms_by_level[0]
        ground_doors = floors_data[0]["doors"]

        # 5. Roof Structure
        roof_type = requirements.get("roof_type") or ("parapet" if style in ["modern", "minimalist"] else "gable")
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
                "floor_height": floor_h,
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
        if "stair_lobby" in s or "stair lobby" in s:
            return "stair_lobby"
        if "drawing" in s:
            return "drawing_room"
        if "prayer" in s:
            return "prayer_room"
        if "storage" in s or "store_room" in s:
            return "storage_room"
        if "servant" in s:
            return "servant_room"
        if "balcony" in s:
            return "balcony"
        if "terrace" in s:
            return "terrace"
        if "garden" in s:
            return "garden"
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

    @staticmethod
    def _floor_id(level: int) -> str:
        labels = {0: "ground_floor", 1: "first_floor", 2: "second_floor", 3: "third_floor"}
        return labels.get(level, f"floor_{level}")

    def _split_rooms_across_floors(
        self, room_types: List[Dict[str, Any]], floors_count: int
    ) -> List[List[Dict[str, Any]]]:
        """Zone the requested program across every storey without inventing rooms."""
        if floors_count <= 1:
            return [list(room_types)]
        if len(room_types) < floors_count:
            raise ValueError(
                f"A {floors_count}-floor home needs at least one requested space per floor; "
                f"only {len(room_types)} spaces were provided."
            )

        buckets: List[List[Dict[str, Any]]] = [[] for _ in range(floors_count)]
        unassigned: List[Dict[str, Any]] = []

        def explicit_level(value: Any) -> Optional[int]:
            if value is None:
                return None
            text = str(value).strip().lower().replace("_", " ")
            aliases = {
                "ground": 0, "ground floor": 0, "first": 1, "first floor": 1,
                "second": 2, "second floor": 2, "third": 3, "third floor": 3,
            }
            if text in aliases:
                return min(aliases[text], floors_count - 1)
            try:
                return max(0, min(floors_count - 1, int(float(text))))
            except (TypeError, ValueError):
                return None

        for room in room_types:
            level = explicit_level(room.get("raw", {}).get("floor"))
            if level is None:
                unassigned.append(room)
            else:
                buckets[level].append(room)

        public_types = {"garage", "living_room", "dining_room", "kitchen", "foyer", "laundry"}
        public = [room for room in unassigned if room["type"] in public_types]
        private = [room for room in unassigned if room["type"] not in public_types]
        buckets[0].extend(public)

        upper_levels = list(range(1, floors_count))
        upper_cursor = 0
        ground_has_bed = any("bed" in room["type"] for room in buckets[0])
        ground_has_bath = any("bath" in room["type"] for room in buckets[0])
        for room in private:
            room_type = room["type"]
            if room_type == "bathroom" and (ground_has_bed or not ground_has_bath):
                buckets[0].append(room)
                ground_has_bath = True
                continue
            if room_type == "home_office" and len(buckets[0]) < 4:
                buckets[0].append(room)
                continue
            level = upper_levels[upper_cursor % len(upper_levels)]
            buckets[level].append(room)
            upper_cursor += 1

        # Every requested storey must be usable. Move a non-garage room from the
        # fullest level when automatic zoning left a level empty.
        for level in range(floors_count):
            if buckets[level]:
                continue
            donors = sorted(range(floors_count), key=lambda idx: len(buckets[idx]), reverse=True)
            moved = None
            for donor_level in donors:
                if len(buckets[donor_level]) <= 1:
                    continue
                moved = next(
                    (
                        room for room in reversed(buckets[donor_level])
                        if room["type"] != "garage"
                        and not room.get("raw", {}).get("strict_floor")
                    ),
                    None,
                )
                if moved:
                    buckets[donor_level].remove(moved)
                    buckets[level].append(moved)
                    break
            if not moved:
                raise ValueError(
                    f"Floor level {level} has no requested room. Add a room to that floor "
                    "instead of moving a room that was explicitly assigned elsewhere."
                )
        return buckets

    def _split_rooms_by_floor(
        self, room_types: List[Dict[str, Any]], floors_count: int
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Backward-compatible two-bucket view used by older callers."""
        groups = self._split_rooms_across_floors(room_types, floors_count)
        return groups[0], [room for group in groups[1:] for room in group]

    @staticmethod
    def _namespace_floor_room_ids(rooms: List[Dict[str, Any]], level: int) -> None:
        seen: Dict[str, int] = {}
        id_map: Dict[str, str] = {}
        for room in rooms:
            original = str(room.get("id") or room.get("type") or "room")
            base = original
            if level > 0 and not base.endswith(f"_l{level}"):
                base = f"{base}_l{level}"
            seen[base] = seen.get(base, 0) + 1
            namespaced = base if seen[base] == 1 else f"{base}_{seen[base]:02d}"
            room["id"] = namespaced
            id_map[original] = namespaced

        # Relationship endpoints must follow the canonical floor-scoped IDs.
        # Otherwise upper-floor ensuite ownership points at pre-normalized room
        # IDs and silently becomes unverifiable.
        for room in rooms:
            for key in ("ensuite_id", "ensuite_for_room_id"):
                endpoint = str(room.get(key, ""))
                if endpoint in id_map:
                    room[key] = id_map[endpoint]

    @staticmethod
    def _namespace_floor_wall_ids(walls: List[Dict[str, Any]], level: int) -> None:
        for wall in walls:
            wall["id"] = f"wall_l{level}_{str(wall.get('id') or 'wall').removeprefix('wall_')}"
            wall["floor_level"] = level

    @staticmethod
    def _namespace_floor_opening_ids(
        doors: List[Dict[str, Any]], windows: List[Dict[str, Any]], level: int
    ) -> None:
        for kind, values in (("door", doors), ("window", windows)):
            for index, opening in enumerate(values, 1):
                base = str(opening.get("id") or f"{kind}_{index:02d}")
                opening["id"] = f"{kind}_l{level}_{base.removeprefix(kind + '_')}"
                opening["floor_level"] = level

    def _find_aligned_stair_core(
        self,
        rooms_by_level: List[List[Dict[str, Any]]],
        sb_left: float,
        sb_front: float,
        bldg_w: float,
        bldg_d: float,
        floor_height: float,
    ) -> Dict[str, Any]:
        """Find one clear vertical core contained inside a room on every floor."""
        stair_w, stair_d, margin = 2.20, 3.40, 0.22
        candidates: List[Tuple[float, float, float]] = []
        x = sb_left + margin
        while x + stair_w + margin <= sb_left + bldg_w + 0.001:
            y = sb_front + margin
            while y + stair_d + margin <= sb_front + bldg_d + 0.001:
                containing = []
                for rooms in rooms_by_level:
                    host = next((room for room in rooms if (
                        float(room["position"]["x"]) + margin <= x
                        and float(room["position"]["y"]) + margin <= y
                        and x + stair_w <= float(room["position"]["x"]) + float(room["dimensions"]["width"]) - margin
                        and y + stair_d <= float(room["position"]["y"]) + float(room["dimensions"]["depth"]) - margin
                    )), None)
                    if not host:
                        containing = []
                        break
                    containing.append(host)
                if containing:
                    penalties = {
                        "hallway": 0, "corridor": 0, "foyer": 0, "stair_lobby": 0, "living_room": 1,
                        "dining_room": 2, "home_office": 3, "bedroom": 7,
                        "master_bedroom": 8, "kitchen": 9, "bathroom": 12, "garage": 12,
                    }
                    use_penalty = sum(penalties.get(str(room.get("type")), 5) for room in containing)
                    center_penalty = abs((x + stair_w / 2) - (sb_left + bldg_w / 2))
                    center_penalty += abs((y + stair_d / 2) - (sb_front + bldg_d / 2))
                    candidates.append((use_penalty * 10 + center_penalty, round(x, 2), round(y, 2)))
                y += 0.20
            x += 0.20
        if not candidates:
            raise ValueError(
                "The requested floors cannot share a safe 2.20 x 3.40 m stair core. "
                "Increase the plot, reduce room count, or use fewer floors."
            )
        _score, stair_x, stair_y = min(candidates)
        return {
            "position": {"x": stair_x, "y": stair_y, "z": 0.0},
            "dimensions": {"width": stair_w, "depth": stair_d, "height": floor_height},
            "opening_dimensions": {"width": stair_w + 0.16, "depth": stair_d + 0.16},
            "configuration": "u_shaped",
            "steps": 18,
            "riser": round(floor_height / 18.0, 4),
            "tread": 0.27,
            "clear_width": 1.0,
            "landing_depth": 0.90,
            "headroom": 2.10,
        }

    def _stair_between_levels(
        self, stair_core: Dict[str, Any], lower_level: int, floor_height: float
    ) -> Dict[str, Any]:
        stair = copy.deepcopy(stair_core)
        upper_level = lower_level + 1
        stair["id"] = f"stair_l{lower_level}_l{upper_level}"
        stair["position"]["z"] = round(lower_level * floor_height, 3)
        stair["floor_level"] = lower_level
        stair["connects"] = {
            "lower_floor": self._floor_id(lower_level),
            "upper_floor": self._floor_id(upper_level),
        }
        return stair

    # ─── Dynamic Contiguous Spatial Placement ─────────────────────────────────
