"""Wall network, door, and window generation."""

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

class OpeningsMixin:
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

        def private_ensuite_owner(room_id: str) -> Optional[str]:
            room = room_map[room_id]
            if str(room.get("access", "")).lower() != "ensuite_only":
                return None
            owner = str(room.get("ensuite_for_room_id", ""))
            return owner or None

        # Attached bathrooms are hard instance-level relationships, not type
        # preferences. Each must share a wall and open only to its owner room.
        # Failing here is safer than emitting a bathroom bank or pass-through
        # ensuite that happens to make the generic circulation graph connected.
        for ensuite in (room for room in rooms if private_ensuite_owner(str(room["id"]))):
            ensuite_id = str(ensuite["id"])
            owner_id = private_ensuite_owner(ensuite_id)
            if owner_id not in room_map:
                raise ValueError(
                    f"Ensuite '{ensuite_id}' references missing bedroom '{owner_id}'."
                )
            pair = tuple(sorted((ensuite_id, owner_id)))
            if pair not in shared:
                raise ValueError(
                    f"Ensuite '{ensuite_id}' must share a wall with its bedroom '{owner_id}'."
                )
            select_pair(ensuite_id, owner_id)

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

        # Build one intentional circulation tree instead of selecting a door
        # independently for every room. Independent selection produced cycles
        # and placed two or three doors in compact bedrooms/garages, leaving no
        # viable furniture wall. Explicit user connections are retained first.
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

        circulation_groups = {"stair_lobby", "hallway", "corridor", "foyer"}

        def edge_score(pair: Tuple[str, str]) -> Tuple[float, str, str]:
            first, second = pair
            left, right = type_group(room_map[first]), type_group(room_map[second])
            groups = {left, right}
            if groups & circulation_groups:
                functional_penalty = 0.0
            elif groups == {"bedroom", "bathroom"}:
                functional_penalty = 1.0
            elif groups == {"bathroom", "kitchen"}:
                # A bathroom should open to its bedroom or circulation space,
                # never through the kitchen when another shared-wall route is
                # available.
                functional_penalty = 9.0
            elif groups <= {"living_room", "drawing_room", "dining_room", "kitchen"}:
                functional_penalty = 1.5
            elif "garage" in groups:
                functional_penalty = 6.0
            elif "bedroom" in groups:
                functional_penalty = 4.0
            else:
                functional_penalty = 3.0
            longest_wall = max(wall_length(wall) for wall in shared[pair])
            return functional_penalty - min(longest_wall, 6.0) * 0.01, first, second

        def edge_allowed(pair: Tuple[str, str]) -> bool:
            first, second = pair
            first_owner = private_ensuite_owner(first)
            second_owner = private_ensuite_owner(second)
            if first_owner and second != first_owner:
                return False
            if second_owner and first != second_owner:
                return False
            # Bathrooms are destination rooms, never circulation between one
            # another. This is a hard architectural rule for generated plans.
            return not (
                type_group(room_map[first]) == "bathroom"
                and type_group(room_map[second]) == "bathroom"
            )

        # Powder rooms and stores are destinations, never corridors. Their one
        # public door is enough; private ensuite links are handled separately.
        terminal_types = {"bathroom", "storage_room"}
        public_degree = {rid: 0 for rid in room_map}
        for first, second in selected:
            if private_ensuite_owner(first) == second or private_ensuite_owner(second) == first:
                continue
            public_degree[first] += 1
            public_degree[second] += 1

        def terminal_capacity_available(pair: Tuple[str, str]) -> bool:
            return all(
                type_group(room_map[room_id]) not in terminal_types
                or public_degree[room_id] < 1
                for room_id in pair
            )

        for first, second in sorted(
            (pair for pair in shared if edge_allowed(pair)), key=edge_score
        ):
            if find(first) != find(second) and terminal_capacity_available((first, second)):
                select_pair(first, second)
                union(first, second)
                public_degree[first] += 1
                public_degree[second] += 1

        disconnected = {find(room_id) for room_id in room_map}
        if len(disconnected) > 1:
            raise ValueError(
                "The packed floor cannot provide direct circulation to every room "
                "without using a bathroom or storage room as a passage."
            )

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
