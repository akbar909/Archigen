"""Canonical architectural preflight shared by the 2D and 3D pipelines.

The layout engine owns geometry.  This module only normalizes identifiers and
transforms, performs deterministic safe repairs, and reports anything that
cannot be repaired without changing the requested design.
"""

from __future__ import annotations

import copy
import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from utils.architectural_vertical import repair_exterior_access, validate_vertical_circulation


EPS = 1e-6
WALL_MARGIN = 0.12
OPENING_GAP = 0.12
FURNITURE_GAP = 0.06


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _position(obj: Dict[str, Any]) -> Dict[str, float]:
    value = obj.get("position") if isinstance(obj.get("position"), dict) else {}
    return {
        "x": _number(value.get("x")),
        "y": _number(value.get("y")),
        "z": _number(value.get("z")),
    }


def _dimensions(obj: Dict[str, Any]) -> Dict[str, float]:
    value = obj.get("dimensions") if isinstance(obj.get("dimensions"), dict) else {}
    return {
        "width": max(EPS, _number(value.get("width"), 0.8)),
        "depth": max(EPS, _number(value.get("depth"), 0.8)),
        "height": max(EPS, _number(value.get("height"), 0.8)),
    }


def _room_box(room: Dict[str, Any]) -> Tuple[float, float, float, float]:
    pos, dim = _position(room), _dimensions(room)
    return pos["x"], pos["y"], pos["x"] + dim["width"], pos["y"] + dim["depth"]


def _rotated_footprint(item: Dict[str, Any]) -> Tuple[float, float]:
    dim = _dimensions(item)
    angle = math.radians(_number(item.get("rotation")) % 180.0)
    c, s = abs(math.cos(angle)), abs(math.sin(angle))
    return dim["width"] * c + dim["depth"] * s, dim["width"] * s + dim["depth"] * c


def _wall_side(value: Any) -> str:
    value = str(value or "").strip().lower().replace("wall", "").replace("_", " ")
    aliases = {
        "front": "south", "bottom": "south", "s": "south", "south": "south",
        "back": "north", "top": "north", "n": "north", "north": "north",
        "left": "west", "w": "west", "west": "west",
        "right": "east", "e": "east", "east": "east",
    }
    return aliases.get(value.strip(), "")


def _infer_side(room: Dict[str, Any], opening: Dict[str, Any]) -> str:
    explicit = _wall_side(opening.get("wall_side") or opening.get("wall") or opening.get("side"))
    if explicit:
        return explicit
    x0, y0, x1, y1 = _room_box(room)
    pos = _position(opening)
    return min(
        ((abs(pos["y"] - y0), "south"), (abs(pos["y"] - y1), "north"),
         (abs(pos["x"] - x0), "west"), (abs(pos["x"] - x1), "east")),
        key=lambda pair: pair[0],
    )[1]


def _wall_geometry(room: Dict[str, Any], side: str) -> Tuple[str, float, float, float]:
    x0, y0, x1, y1 = _room_box(room)
    if side == "south":
        return "h", y0, x0, x1
    if side == "north":
        return "h", y1, x0, x1
    if side == "west":
        return "v", x0, y0, y1
    return "v", x1, y0, y1


def _resolve_wall_id(
    walls: Iterable[Dict[str, Any]], room: Dict[str, Any], side: str, coordinate: float,
    intended_ids: Iterable[str] = (), preferred_id: str = "",
) -> str:
    axis, fixed, start, end = _wall_geometry(room, side)
    rid = room.get("id")
    best: Tuple[float, str] | None = None
    for wall in walls:
        connected = wall.get("connected_rooms") or wall.get("room_ids") or []
        if connected and rid not in connected:
            continue
        p1 = wall.get("start") or wall.get("from") or {}
        p2 = wall.get("end") or wall.get("to") or {}
        if not isinstance(p1, dict) or not isinstance(p2, dict):
            continue
        wx1, wy1 = _number(p1.get("x")), _number(p1.get("y"))
        wx2, wy2 = _number(p2.get("x")), _number(p2.get("y"))
        wall_axis = "h" if abs(wy2 - wy1) <= abs(wx2 - wx1) else "v"
        if wall_axis != axis:
            continue
        wall_fixed = (wy1 + wy2) / 2.0 if axis == "h" else (wx1 + wx2) / 2.0
        a, b = sorted((wx1, wx2)) if axis == "h" else sorted((wy1, wy2))
        overlap = min(end, b) - max(start, a)
        coordinate_penalty = max(a - coordinate, 0.0, coordinate - b)
        score = abs(wall_fixed - fixed) + coordinate_penalty + (100.0 if overlap <= EPS else 0.0)
        # Coincident segments at a T junction may have the same distance. Prefer
        # a real shared host satisfying the doorway's intended room connection.
        intended = set(str(value) for value in intended_ids)
        if intended and not intended.issubset(set(str(value) for value in connected)):
            score += 1.0
        if str(wall.get("id")) == str(preferred_id):
            score -= 0.000001
        if best is None or score < best[0]:
            best = (score, str(wall.get("id") or ""))
    return best[1] if best and best[0] < 0.08 and best[1] else f"{rid}:{side}"


def _opening_coordinate(opening: Dict[str, Any], room: Dict[str, Any], side: str) -> float:
    pos = _position(opening)
    axis, _, start, end = _wall_geometry(room, side)
    coord = pos["x"] if axis == "h" else pos["y"]
    if abs(coord) <= EPS and opening.get("offset") is not None:
        coord = start + _number(opening.get("offset"))
    return max(start, min(end, coord))


def _set_opening_position(opening: Dict[str, Any], room: Dict[str, Any], side: str, center: float) -> None:
    axis, fixed, start, _ = _wall_geometry(room, side)
    base_z = _position(room)["z"]
    sill = _number(opening.get("sill_height"), 0.9 if opening.get("kind") == "window" else 0.0)
    opening["position"] = {
        "x": center if axis == "h" else fixed,
        "y": fixed if axis == "h" else center,
        "z": base_z + sill,
    }
    opening["offset"] = center - start


def _minimum_opening_width(opening: Dict[str, Any]) -> float:
    """Return a conservative usable minimum while preserving every opening."""
    if opening.get("kind") == "window":
        return 0.60
    opening_type = str(opening.get("type", "")).lower()
    if opening_type == "garage_door":
        return 2.20
    if opening_type == "main_entrance":
        return 0.90
    return 0.75


def _shrink_openings_to_wall(
    entries: List[Tuple[Dict[str, Any], Dict[str, Any], str, float]],
    wall_id: str,
    available_width: float,
    report: Dict[str, List[str]],
) -> bool:
    """Reduce oversized openings deterministically before declaring a conflict."""
    required = sum(_number(entry[0].get("width")) for entry in entries)
    excess = required - max(0.0, available_width)
    if excess <= EPS:
        return True

    # Prefer resizing windows; preserve entrance and circulation door widths.
    adjustable = sorted(
        entries,
        key=lambda row: (0 if row[0].get("kind") == "window" else 1, str(row[0].get("id", ""))),
    )
    total_reducible = sum(
        max(0.0, _number(opening.get("width")) - _minimum_opening_width(opening))
        for opening, *_ in adjustable
    )
    if total_reducible + EPS < excess:
        return False

    remaining = excess
    for opening, *_ in adjustable:
        current = _number(opening.get("width"))
        minimum = _minimum_opening_width(opening)
        reduction = min(max(0.0, current - minimum), remaining)
        if reduction <= EPS:
            continue
        opening["width"] = round(current - reduction, 4)
        remaining -= reduction
        report["repairs"].append(
            f"Reduced opening '{opening['id']}' to {opening['width']:.2f} m to share wall '{wall_id}'."
        )
        if remaining <= EPS:
            return True
    return remaining <= EPS


def _repair_openings(
    floor: Dict[str, Any], rooms: Dict[str, Dict[str, Any]], report: Dict[str, List[str]]
) -> None:
    walls = floor.get("walls") if isinstance(floor.get("walls"), list) else []
    walls_by_id = {str(wall.get("id")): wall for wall in walls if isinstance(wall, dict) and wall.get("id")}
    grouped: Dict[str, List[Tuple[Dict[str, Any], Dict[str, Any], str, float]]] = defaultdict(list)
    seen: set[str] = set()
    for kind in ("doors", "windows"):
        items = floor.get(kind) if isinstance(floor.get(kind), list) else []
        for index, opening in enumerate(items):
            if not isinstance(opening, dict):
                report["critical_errors"].append(f"Floor {floor.get('id')}: invalid {kind[:-1]} entry")
                continue
            opening["kind"] = kind[:-1]
            oid = str(opening.get("id") or f"{kind[:-1]}_{floor.get('id', 'floor')}_{index + 1:02d}")
            if oid in seen:
                oid = f"{oid}_{index + 1}"
                report["repairs"].append(f"Renamed duplicate opening to '{oid}'.")
            seen.add(oid)
            opening["id"] = oid
            rid = opening.get("room_id") or opening.get("roomId")
            room = rooms.get(str(rid))
            if not room:
                report["critical_errors"].append(f"Opening '{oid}' references missing room '{rid}'.")
                continue
            opening["room_id"] = room["id"]
            opening["roomId"] = room["id"]
            side = _infer_side(room, opening)
            opening["wall_side"] = side
            center = _opening_coordinate(opening, room, side)
            intended = opening.get("connected_room_ids") or [value for value in (rid, opening.get("connected_room_id")) if value]
            wall_id = _resolve_wall_id(walls, room, side, center, intended, str(opening.get("wall_id") or ""))
            # Preserve useful diagnostics if no wall can fulfil an interior
            # connection; never turn a disconnected door into an exterior exit.
            if wall_id not in walls_by_id:
                wall_id = _resolve_wall_id(walls, room, side, center)
            opening["wall_id"] = wall_id
            width = max(0.45, _number(opening.get("width"), 0.9 if kind == "doors" else 1.2))
            _, _, start, end = _wall_geometry(room, side)
            host_wall = walls_by_id.get(wall_id)
            if not host_wall:
                report["critical_errors"].append(
                    f"Opening '{oid}' has no canonical host wall for room '{room['id']}' on its {side} side."
                )
            elif kind == "doors" and str(opening.get("type", "")).lower() not in ("main_entrance", "garage_door"):
                intended = [str(value) for value in opening.get("connected_room_ids", [])]
                hosted = [str(value) for value in (host_wall.get("connected_rooms") or host_wall.get("room_ids") or [])]
                if len(intended) >= 2 and not set(intended[:2]).issubset(set(hosted)):
                    report["critical_errors"].append(
                        f"Door '{oid}' intends to connect {intended[:2]} but its wall '{wall_id}' connects {hosted}."
                    )
            if host_wall:
                hosted = list(host_wall.get("connected_rooms") or host_wall.get("room_ids") or [])
                if len(intended) <= 1 or set(intended).issubset(set(hosted)):
                    opening["connected_room_ids"] = hosted
                    opening["connected_rooms"] = hosted
                    opening["connected_room_id"] = next((value for value in hosted if value != room["id"]), None)
                wall_start, wall_end = host_wall.get("start", {}), host_wall.get("end", {})
                if side in ("south", "north"):
                    start, end = sorted((_number(wall_start.get("x")), _number(wall_end.get("x"))))
                else:
                    start, end = sorted((_number(wall_start.get("y")), _number(wall_end.get("y"))))
            maximum = max(0.45, end - start - 2 * WALL_MARGIN)
            if width > maximum:
                width = maximum
                report["repairs"].append(f"Reduced opening '{oid}' to fit wall '{wall_id}'.")
            opening["width"] = width
            opening["height"] = max(0.5, _number(opening.get("height"), 2.1 if kind == "doors" else 1.2))
            if kind == "windows":
                opening["sill_height"] = max(0.0, _number(opening.get("sill_height"), 0.9))
            if kind == "doors" and not opening.get("client_edited_2d") and str(opening.get("type", "")).lower() not in ("main_entrance", "garage_door"):
                # Interior doors are placed near a wall end, preserving the
                # larger uninterrupted wall area for circulation/furniture.
                corner_center = start + WALL_MARGIN + width / 2.0 + 0.10
                center = min(center, corner_center)
            grouped[wall_id].append((opening, room, side, center))

    for wall_id, entries in grouped.items():
        entries.sort(key=lambda row: (row[3], row[0]["id"]))
        _, _, start, end = _wall_geometry(entries[0][1], entries[0][2])
        host_wall = walls_by_id.get(wall_id)
        if host_wall:
            wall_start, wall_end = host_wall.get("start", {}), host_wall.get("end", {})
            if entries[0][2] in ("south", "north"):
                start, end = sorted((_number(wall_start.get("x")), _number(wall_end.get("x"))))
            else:
                start, end = sorted((_number(wall_start.get("y")), _number(wall_end.get("y"))))
        available_width = (
            (end - start)
            - 2 * WALL_MARGIN
            - max(0, len(entries) - 1) * OPENING_GAP
        )
        if not _shrink_openings_to_wall(entries, wall_id, available_width, report):
            report["critical_errors"].append(
                f"Openings on wall '{wall_id}' require more wall length than is available."
            )
            continue
        cursor = start + WALL_MARGIN
        placements: List[Tuple[Dict[str, Any], Dict[str, Any], str, float]] = []
        for opening, room, side, desired in entries:
            half = opening["width"] / 2.0
            center = max(desired, cursor + half, start + WALL_MARGIN + half)
            placements.append((opening, room, side, center))
            cursor = center + half + OPENING_GAP
        overflow = cursor - OPENING_GAP - (end - WALL_MARGIN)
        if overflow > EPS:
            cursor = start + WALL_MARGIN
            placements = []
            for opening, room, side, _ in entries:
                half = opening["width"] / 2.0
                center = cursor + half
                placements.append((opening, room, side, center))
                cursor = center + half + OPENING_GAP
            if cursor - OPENING_GAP > end - WALL_MARGIN + EPS:
                report["critical_errors"].append(
                    f"Openings on wall '{wall_id}' require more wall length than is available."
                )
                continue
        for opening, room, side, center in placements:
            old = _opening_coordinate(opening, room, side)
            _set_opening_position(opening, room, side, center)
            opening["offset"] = center - start
            if abs(old - center) > 0.01:
                report["repairs"].append(f"Moved opening '{opening['id']}' to prevent overlap.")


def _boxes_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], gap: float) -> bool:
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def _candidate_centers(room: Dict[str, Any], fw: float, fd: float, desired: Tuple[float, float]):
    x0, y0, x1, y1 = _room_box(room)
    min_x, max_x = x0 + WALL_MARGIN + fw / 2, x1 - WALL_MARGIN - fw / 2
    min_y, max_y = y0 + WALL_MARGIN + fd / 2, y1 - WALL_MARGIN - fd / 2
    if min_x > max_x or min_y > max_y:
        return []
    clamped = (max(min_x, min(max_x, desired[0])), max(min_y, min(max_y, desired[1])))
    values = [
        clamped,
        (min_x, min_y), (min_x, max_y), (max_x, min_y), (max_x, max_y),
        (clamped[0], min_y), (clamped[0], max_y),
        (min_x, clamped[1]), (max_x, clamped[1]),
    ]
    step = max(0.18, min(fw, fd) / 3.0)
    y = min_y
    while y <= max_y + EPS:
        x = min_x
        while x <= max_x + EPS:
            values.append((x, y))
            x += step
        y += step
    unique = {(round(x, 4), round(y, 4)) for x, y in values}
    return sorted(unique, key=lambda p: ((p[0] - desired[0]) ** 2 + (p[1] - desired[1]) ** 2, p[1], p[0]))


def _wall_candidate_centers(
    room: Dict[str, Any], fw: float, fd: float, desired: Tuple[float, float], side: str
):
    """Generate safe positions constrained to the requested backing wall."""
    x0, y0, x1, y1 = _room_box(room)
    min_x, max_x = x0 + WALL_MARGIN + fw / 2, x1 - WALL_MARGIN - fw / 2
    min_y, max_y = y0 + WALL_MARGIN + fd / 2, y1 - WALL_MARGIN - fd / 2
    if min_x > max_x or min_y > max_y:
        return []

    if side in {"west", "east"}:
        fixed = min_x if side == "west" else max_x
        preferred = max(min_y, min(max_y, desired[1]))
        values = [(fixed, preferred), (fixed, min_y), (fixed, max_y)]
        step = max(0.18, min(fw, fd) / 3.0)
        cursor = min_y
        while cursor <= max_y + EPS:
            values.append((fixed, cursor))
            cursor += step
    else:
        fixed = min_y if side == "south" else max_y
        preferred = max(min_x, min(max_x, desired[0]))
        values = [(preferred, fixed), (min_x, fixed), (max_x, fixed)]
        step = max(0.18, min(fw, fd) / 3.0)
        cursor = min_x
        while cursor <= max_x + EPS:
            values.append((cursor, fixed))
            cursor += step

    unique = {(round(x, 4), round(y, 4)) for x, y in values}
    return sorted(
        unique,
        key=lambda p: ((p[0] - desired[0]) ** 2 + (p[1] - desired[1]) ** 2, p[1], p[0]),
    )


def _door_clearance_boxes(
    floor: Dict[str, Any], rid: str, rooms: Dict[str, Dict[str, Any]]
) -> List[Tuple[float, float, float, float]]:
    result = []
    room = rooms.get(str(rid))
    if not room:
        return result
    x0, y0, x1, y1 = _room_box(room)
    for door in floor.get("doors", []):
        if str(door.get("type", "")).lower() == "garage_door" or str(door.get("swing", "")).lower() == "overhead":
            # Vehicles intentionally occupy the approach area of an overhead
            # garage opening; treating it as a pedestrian swing is incorrect.
            continue
        pos, width = _position(door), _number(door.get("width"), 0.9)
        connected = {
            str(value) for value in (door.get("connected_room_ids") or door.get("connected_rooms") or [])
        }
        direct_room = door.get("room_id") or door.get("roomId")
        if direct_room is not None:
            connected.add(str(direct_room))
        on_boundary = (
            x0 - 0.3 <= pos["x"] <= x1 + 0.3
            and y0 - 0.3 <= pos["y"] <= y1 + 0.3
            and min(abs(pos["x"] - x0), abs(pos["x"] - x1), abs(pos["y"] - y0), abs(pos["y"] - y1)) <= 0.35
        )
        if str(rid) not in connected and not on_boundary:
            continue
        # wall_side is defined relative to the door's primary room. Infer the
        # side again for this room so both sides of a shared door stay clear.
        side = min(
            ((abs(pos["y"] - y0), "south"), (abs(pos["y"] - y1), "north"),
             (abs(pos["x"] - x0), "west"), (abs(pos["x"] - x1), "east")),
            key=lambda pair: pair[0],
        )[1]
        half_width = width / 2.0 + 0.35
        depth = 1.15
        if side == "south": zone = (pos["x"] - half_width, y0, pos["x"] + half_width, min(y1, y0 + depth))
        elif side == "north": zone = (pos["x"] - half_width, max(y0, y1 - depth), pos["x"] + half_width, y1)
        elif side == "west": zone = (x0, pos["y"] - half_width, min(x1, x0 + depth), pos["y"] + half_width)
        else: zone = (max(x0, x1 - depth), pos["y"] - half_width, x1, pos["y"] + half_width)
        result.append((max(x0, zone[0]), max(y0, zone[1]), min(x1, zone[2]), min(y1, zone[3])))
    return result


def _window_clearance_boxes(
    floor: Dict[str, Any], rid: str, rooms: Dict[str, Dict[str, Any]]
) -> List[Tuple[float, float, float, float]]:
    """Keep tall/headboard-backed furniture off glazed wall openings."""
    result = []
    room = rooms.get(str(rid))
    if not room:
        return result
    x0, y0, x1, y1 = _room_box(room)
    for window in floor.get("windows", []):
        direct_room = str(window.get("room_id") or window.get("roomId") or "")
        if direct_room != str(rid):
            continue
        pos, width = _position(window), _number(window.get("width"), 1.2)
        side = min(
            ((abs(pos["y"] - y0), "south"), (abs(pos["y"] - y1), "north"),
             (abs(pos["x"] - x0), "west"), (abs(pos["x"] - x1), "east")),
            key=lambda pair: pair[0],
        )[1]
        half_width = width / 2.0 + 0.12
        depth = 0.45
        if side == "south": zone = (pos["x"] - half_width, y0, pos["x"] + half_width, min(y1, y0 + depth))
        elif side == "north": zone = (pos["x"] - half_width, max(y0, y1 - depth), pos["x"] + half_width, y1)
        elif side == "west": zone = (x0, pos["y"] - half_width, min(x1, x0 + depth), pos["y"] + half_width)
        else: zone = (max(x0, x1 - depth), pos["y"] - half_width, x1, pos["y"] + half_width)
        result.append((max(x0, zone[0]), max(y0, zone[1]), min(x1, zone[2]), min(y1, zone[3])))
    return result


def _stair_clearance_boxes(
    floor: Dict[str, Any], rid: str, rooms: Dict[str, Dict[str, Any]]
) -> List[Tuple[float, float, float, float]]:
    """Return the stair/landing footprint clipped to the furniture's room."""
    room = rooms.get(str(rid))
    core = floor.get("stair_core")
    if not room or not isinstance(core, dict):
        return []
    rx0, ry0, rx1, ry1 = _room_box(room)
    position, dimensions = _position(core), _dimensions(core)
    margin = 0.12
    core_box = (
        position["x"] - margin,
        position["y"] - margin,
        position["x"] + dimensions["width"] + margin,
        position["y"] + dimensions["depth"] + margin,
    )
    clipped = (
        max(rx0, core_box[0]), max(ry0, core_box[1]),
        min(rx1, core_box[2]), min(ry1, core_box[3]),
    )
    return [clipped] if clipped[0] < clipped[2] and clipped[1] < clipped[3] else []


def _is_optional_furniture(item: Dict[str, Any]) -> bool:
    if str(item.get("category", "")).strip().lower() == "vehicle":
        return False
    value = " ".join(
        str(item.get(key, "")).lower()
        for key in ("category", "asset", "asset_id", "type", "id")
    )
    return any(token in value for token in (
        "coffee_table", "coffee table", "side_table", "side table",
        "nightstand", "bedside", "armchair", "decor", "ottoman",
        "tv_cabinet", "console", "bookshelf", "dining_chair",
        "dining chair", "kitchen_island", "kitchen island",
        "shower",
    ))


def _allows_integrated_overlap(item: Dict[str, Any], other: Dict[str, Any]) -> bool:
    """Allow fixtures designed to be embedded in compatible cabinetry."""
    item_name = " ".join(str(item.get(key, "")).lower() for key in ("asset", "asset_id", "category", "type"))
    other_name = " ".join(str(other.get(key, "")).lower() for key in ("asset", "asset_id", "category", "type"))
    fixture_tokens = ("kitchen_sink", "kitchen sink", "cooktop", "hob")
    support_tokens = ("kitchen_island", "kitchen island", "kitchen_cabinet", "counter", "cabinet")
    return (
        any(token in item_name for token in fixture_tokens)
        and any(token in other_name for token in support_tokens)
    ) or (
        any(token in other_name for token in fixture_tokens)
        and any(token in item_name for token in support_tokens)
    )


def _repair_furniture(
    floor: Dict[str, Any], rooms: Dict[str, Dict[str, Any]], report: Dict[str, List[str]]
) -> None:
    occupied: Dict[str, List[Tuple[Tuple[float, float, float, float], Dict[str, Any]]]] = defaultdict(list)
    seen: set[str] = set()
    valid_items: List[Dict[str, Any]] = []
    preserve_source_order = bool(floor.pop("_preserve_furniture_order", False))
    source_items = list(enumerate(floor.get("furniture", [])))
    # Reserve circulation-safe positions for essential fixtures first. Optional
    # chairs/tables can then fill the remaining space or be omitted cleanly.
    if not preserve_source_order:
        def placement_priority(item: Dict[str, Any]) -> int:
            """Place constrained wall storage before movable room furniture.

            A wardrobe has only four narrow wall runs available, while a bed can
            use the remaining wall and move along it.  Placing the bed first can
            consume the only wardrobe run even in an otherwise adequate room.
            """
            if _is_optional_furniture(item):
                return 4
            category = str(item.get("category", "")).strip().lower()
            if category in {"wardrobe", "closet", "cabinet"}:
                return 0
            if category in {"bed"}:
                return 2
            return 1

        source_items.sort(key=lambda pair: (
            placement_priority(pair[1]) if isinstance(pair[1], dict) else 3,
            pair[0],
        ))
    for index, item in source_items:
        if not isinstance(item, dict):
            report["critical_errors"].append(f"Floor {floor.get('id')}: invalid furniture entry")
            continue
        fid = str(item.get("id") or f"furniture_{floor.get('id', 'floor')}_{index + 1:03d}")
        if fid in seen:
            fid = f"{fid}_{index + 1}"
            report["repairs"].append(f"Renamed duplicate furniture item to '{fid}'.")
        seen.add(fid)
        item["id"] = fid
        rid = str(item.get("room_id") or item.get("roomId") or "")
        room = rooms.get(rid)
        if not room:
            report["critical_errors"].append(f"Furniture '{fid}' references missing room '{rid}'.")
            valid_items.append(item)
            continue
        item["room_id"] = rid
        item["roomId"] = rid
        item["rotation"] = _number(item.get("rotation")) % 360.0
        item["dimensions"] = _dimensions(item)
        pos = _position(item)
        if item.get("support_id"):
            # Resolve against repaired tables after all floor furniture is placed.
            # A clock resting on a table must not reserve another floor footprint.
            valid_items.append(item)
            continue
        ceiling_mounted = item.get("ceiling_mounted") is True
        if ceiling_mounted:
            clearance = max(0.0, _number(item.get("ceiling_clearance"), 0.06))
            item["ceiling_clearance"] = clearance
            pos["z"] = _position(room)["z"] + _dimensions(room)["height"] - item["dimensions"]["height"] - clearance
        else:
            pos["z"] = _position(room)["z"]
        door_clearances = _door_clearance_boxes(floor, rid, rooms)
        window_clearances = _window_clearance_boxes(floor, rid, rooms)
        stair_clearances = _stair_clearance_boxes(floor, rid, rooms)
        chosen = None
        anchor_side = _wall_side(item.get("anchor_wall"))
        lock_to_wall = str(item.get("placement_hint", "")).lower() in {
            "wall", "wall_backed", "wall_exact",
        }
        original_rotation = item["rotation"]
        placement_options = [(original_rotation, anchor_side)]
        window_fallback = None
        # A transform committed by the interactive 3D editor is intentional.
        # Do not run it through the automatic room-packing search again: doing
        # so made a moved car/bed jump back to an older candidate on save.
        # Keep collision reporting, but make the user's in-room position the
        # authoritative candidate for this item.
        client_edited = item.get("client_edited_3d") is True or ceiling_mounted
        if client_edited:
            fw, fd = _rotated_footprint(item)
            room_x0, room_y0, room_x1, room_y1 = _room_box(room)
            wall_mounted = item.get("wall_mounted") is True
            cx = pos["x"] if wall_mounted else min(max(pos["x"], room_x0 + fw / 2), room_x1 - fw / 2)
            cy = pos["y"] if wall_mounted else min(max(pos["y"], room_y0 + fd / 2), room_y1 - fd / 2)
            if abs(cx - pos["x"]) > 0.01 or abs(cy - pos["y"]) > 0.01:
                report["warnings"].append(
                    f"Clamped user-edited furniture '{fid}' to the boundary of room '{rid}'."
                )
            # Wall décor occupies the wall plane, not the walking floor. Keep a
            # tiny reservation so it cannot push beds/chairs away during save.
            box = (
                (cx - 0.01, cy - 0.01, cx + 0.01, cy + 0.01)
                if wall_mounted else
                (cx - fw / 2, cy - fd / 2, cx + fw / 2, cy + fd / 2)
            )
            if not ceiling_mounted and any(
                _boxes_overlap(box, other_box, FURNITURE_GAP)
                and not _allows_integrated_overlap(item, other_item)
                for other_box, other_item in occupied[rid]
            ):
                report["warnings"].append(
                    f"User-edited furniture '{fid}' overlaps another item in room '{rid}'."
                )
            chosen = (cx, cy, box, original_rotation, anchor_side)
        rotatable_categories = {
            "dining_table", "kitchen_island", "kitchen_counter", "desk", "table", "sofa",
        }
        if lock_to_wall and anchor_side and str(item.get("placement_hint", "")).lower() != "wall_exact":
            side_angle = {"north": 0.0, "west": 90.0, "south": 180.0, "east": 270.0}
            base_angle = side_angle[anchor_side]
            for alternate_side in ("north", "east", "south", "west"):
                if alternate_side == anchor_side:
                    continue
                alternate_rotation = (
                    original_rotation + side_angle[alternate_side] - base_angle
                ) % 360.0
                placement_options.append((alternate_rotation, alternate_side))
        elif not lock_to_wall and str(item.get("category", "")).lower() in rotatable_categories:
            perpendicular = (original_rotation + 90.0) % 360.0
            if perpendicular != original_rotation:
                placement_options.append((perpendicular, anchor_side))

        for rotation, candidate_side in ([] if client_edited else placement_options):
            item["rotation"] = rotation
            fw, fd = _rotated_footprint(item)
            candidates = (
                _wall_candidate_centers(room, fw, fd, (pos["x"], pos["y"]), candidate_side)
                if candidate_side and lock_to_wall else
                _candidate_centers(room, fw, fd, (pos["x"], pos["y"]))
            )
            for cx, cy in candidates:
                box = (cx - fw / 2, cy - fd / 2, cx + fw / 2, cy + fd / 2)
                furniture_collision = any(
                    _boxes_overlap(box, other_box, FURNITURE_GAP)
                    and not _allows_integrated_overlap(item, other_item)
                    for other_box, other_item in occupied[rid]
                )
                door_collision = any(_boxes_overlap(box, other, FURNITURE_GAP) for other in door_clearances)
                category = str(item.get("category", "")).strip().lower()
                window_collision = (
                    category in {"bed", "wardrobe", "closet", "bookshelf"}
                    and any(_boxes_overlap(box, other, 0.02) for other in window_clearances)
                )
                stair_collision = any(_boxes_overlap(box, other, FURNITURE_GAP) for other in stair_clearances)
                if (
                    window_collision and not furniture_collision
                    and not door_collision and not stair_collision
                    and window_fallback is None
                ):
                    window_fallback = (cx, cy, box, rotation, candidate_side)
                if not furniture_collision and not door_collision and not window_collision and not stair_collision:
                    chosen = (cx, cy, box, rotation, candidate_side)
                    break
            if chosen is not None:
                break
        if chosen is None and window_fallback is not None:
            chosen = window_fallback
            report["warnings"].append(
                f"Furniture '{fid}' overlaps a window wall because no other collision-free wall is available."
            )
        if chosen is None:
            item["rotation"] = original_rotation
            if _is_optional_furniture(item):
                report["repairs"].append(
                    f"Removed optional furniture '{fid}' because it cannot fit without blocking circulation."
                )
                continue
            report["critical_errors"].append(
                f"Furniture '{fid}' cannot fit safely inside room '{rid}' without a collision."
            )
            valid_items.append(item)
            continue
        cx, cy, box, chosen_rotation, chosen_side = chosen
        if abs(chosen_rotation - original_rotation) > 0.01:
            report["repairs"].append(
                f"Rotated furniture '{fid}' to {chosen_rotation:.0f} degrees to fit room '{rid}'."
            )
        item["rotation"] = chosen_rotation
        if chosen_side and chosen_side != anchor_side:
            item["anchor_wall"] = chosen_side
            report["repairs"].append(
                f"Moved furniture '{fid}' to the {chosen_side} wall to preserve door clearance."
            )
        if abs(cx - pos["x"]) > 0.01 or abs(cy - pos["y"]) > 0.01:
            report["repairs"].append(f"Moved furniture '{fid}' inside room '{rid}'.")
        item["position"] = {"x": cx, "y": cy, "z": pos["z"]}
        if not ceiling_mounted:
            occupied[rid].append((box, item))
        valid_items.append(item)
    by_id = {str(item["id"]): item for item in valid_items}
    for item in valid_items:
        if not item.get("support_id"):
            continue
        support = by_id.get(str(item["support_id"]))
        rid = item["room_id"]
        category = str((support or {}).get("category", ""))
        valid = support and support.get("room_id") == rid and not support.get("support_id") and any(
            token in category for token in ("table", "desk", "nightstand", "console"))
        if valid:
            dims, sd = _dimensions(item), _dimensions(support)
            angle = math.radians(_number(item.get("rotation")) - _number(support.get("rotation")))
            width = abs(math.cos(angle)) * dims["width"] + abs(math.sin(angle)) * dims["depth"]
            depth = abs(math.sin(angle)) * dims["width"] + abs(math.cos(angle)) * dims["depth"]
            valid = width + 0.02 <= sd["width"] and depth + 0.02 <= sd["depth"]
        if not valid:
            item.pop("support_id", None)
            item["position"] = {**_position(item), "z": _position(rooms[rid])["z"]}
            report["warnings"].append(f"Tabletop support for '{item['id']}' is unavailable; placed on floor.")
            continue
        p, sp = _position(item), _position(support)
        origin = item.get("support_origin") or sp
        old = math.radians(_number(item.get("support_rotation", support.get("rotation"))))
        dx, dy = p["x"] - _number(origin.get("x")), p["y"] - _number(origin.get("y"))
        lx, ly = (sd["width"] - width) / 2 - 0.01, (sd["depth"] - depth) / 2 - 0.01
        x = max(-lx, min(lx, math.cos(old) * dx + math.sin(old) * dy))
        y = max(-ly, min(ly, -math.sin(old) * dx + math.cos(old) * dy))
        turn = math.radians(_number(support.get("rotation")))
        item["position"] = {"x": sp["x"] + math.cos(turn) * x - math.sin(turn) * y,
                            "y": sp["y"] + math.sin(turn) * x + math.cos(turn) * y,
                            "z": sp["z"] + sd["height"] + 0.002}
        item["support_origin"] = dict(sp)
        item["support_rotation"] = _number(support.get("rotation"))
    floor["furniture"] = valid_items


def _validate_floor_geometry(
    floor: Dict[str, Any], rooms: Dict[str, Dict[str, Any]], design: Dict[str, Any], report: Dict[str, Any]
) -> None:
    """Validate room polygons and door topology after deterministic repairs."""
    room_values = list(rooms.values())
    plot = design.get("site", {}).get("plot", {})
    plot_w, plot_d = _number(plot.get("width")), _number(plot.get("depth"))
    for index, room in enumerate(room_values):
        x0, y0, x1, y1 = _room_box(room)
        if x1 - x0 <= EPS or y1 - y0 <= EPS:
            report["critical_errors"].append(f"Room '{room['id']}' has an invalid boundary.")
        if plot_w > EPS and plot_d > EPS and (x0 < -EPS or y0 < -EPS or x1 > plot_w + EPS or y1 > plot_d + EPS):
            report["critical_errors"].append(
                f"Room '{room['id']}' extends outside the {plot_w:.2f} x {plot_d:.2f} m plot."
            )
        for other in room_values[index + 1:]:
            ox0, oy0, ox1, oy1 = _room_box(other)
            overlap_x = min(x1, ox1) - max(x0, ox0)
            overlap_y = min(y1, oy1) - max(y0, oy0)
            if overlap_x > EPS and overlap_y > EPS:
                report["critical_errors"].append(
                    f"Rooms '{room['id']}' and '{other['id']}' overlap by {overlap_x:.2f} x {overlap_y:.2f} m."
                )

    if len(room_values) <= 1:
        return
    graph = {str(room["id"]): set() for room in room_values}
    entrance_room = None
    walls_by_id = {str(wall.get("id")): wall for wall in floor.get("walls", []) if isinstance(wall, dict)}
    interior_door_pairs: List[Tuple[str, str]] = []
    for door in floor.get("doors", []):
        dtype = str(door.get("type", "")).lower()
        rid = str(door.get("room_id") or door.get("roomId") or "")
        if dtype == "main_entrance":
            entrance_room = rid
        if dtype in ("main_entrance", "garage_door"):
            continue
        connected = [str(value) for value in door.get("connected_room_ids", []) if str(value) in graph]
        if len(connected) < 2:
            wall = walls_by_id.get(str(door.get("wall_id")), {})
            connected = [str(value) for value in wall.get("connected_rooms", []) if str(value) in graph]
        if len(connected) >= 2:
            for first in connected:
                graph[first].update(value for value in connected if value != first)
            interior_door_pairs.append((connected[0], connected[1]))

    def is_bathroom(room_id: str) -> bool:
        return "bath" in str(rooms.get(room_id, {}).get("type", "")).lower()

    for first, second in interior_door_pairs:
        if is_bathroom(first) and is_bathroom(second):
            report["critical_errors"].append(
                f"Bathrooms '{first}' and '{second}' must not connect directly."
            )

    for room in room_values:
        if str(room.get("access", "")).lower() != "ensuite_only":
            continue
        ensuite_id = str(room["id"])
        owner_id = str(room.get("ensuite_for_room_id", ""))
        if owner_id not in graph:
            report["critical_errors"].append(
                f"Ensuite '{ensuite_id}' references missing bedroom '{owner_id}'."
            )
            continue
        direct_count = sum(
            1 for first, second in interior_door_pairs
            if {first, second} == {ensuite_id, owner_id}
        )
        if direct_count != 1:
            report["critical_errors"].append(
                f"Ensuite '{ensuite_id}' requires exactly one direct door to bedroom '{owner_id}'."
            )
        other_access = graph[ensuite_id] - {owner_id}
        if other_access:
            report["critical_errors"].append(
                f"Ensuite '{ensuite_id}' must be private to bedroom '{owner_id}', not connected to {sorted(other_access)}."
            )
        owner = rooms[owner_id]
        if str(owner.get("ensuite_id", "")) != ensuite_id:
            report["critical_errors"].append(
                f"Bedroom '{owner_id}' and ensuite '{ensuite_id}' have inconsistent ownership metadata."
            )

    start = entrance_room if entrance_room in graph else next(iter(graph))
    visited, pending = set(), [start]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph[current] - visited)
    missing = sorted(set(graph) - visited)
    if missing:
        report["critical_errors"].append(
            f"Floor '{floor.get('id')}' has rooms unreachable through doors: {missing}."
        )


def validate_and_repair_design(design: Dict[str, Any], repair: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return a canonical design and a generation-gating validation report."""
    doc = copy.deepcopy(design) if repair else design
    report: Dict[str, Any] = {"critical_errors": [], "warnings": [], "repairs": []}
    floors = doc.get("floors") if isinstance(doc.get("floors"), list) else []
    if not floors:
        report["critical_errors"].append("The design has no canonical floors.")
    all_rooms: List[Dict[str, Any]] = []
    all_doors: List[Dict[str, Any]] = []
    all_windows: List[Dict[str, Any]] = []
    all_furniture: List[Dict[str, Any]] = []
    global_room_ids: set[str] = set()
    floor_height = max(2.4, _number(doc.get("building", {}).get("floor_height"), 3.0))
    deleted_furniture_ids = {str(value) for value in doc.get("deleted_furniture_ids", [])}
    for floor_index, floor in enumerate(floors):
        floor.setdefault("id", f"floor_{floor_index + 1}")
        floor.setdefault("level", floor_index)
        floor.setdefault("elevation", round(int(floor["level"]) * floor_height, 3))
        floor.setdefault("floor_height", floor_height)
        floor_elevation = _number(floor.get("elevation"), floor_index * floor_height)
        rooms_list = floor.get("rooms") if isinstance(floor.get("rooms"), list) else []
        rooms: Dict[str, Dict[str, Any]] = {}
        renamed_room_ids: Dict[str, str] = {}
        for room_index, room in enumerate(rooms_list):
            if not isinstance(room, dict):
                report["critical_errors"].append(f"Floor '{floor['id']}' contains an invalid room.")
                continue
            rid = str(room.get("id") or f"room_{floor_index + 1}_{room_index + 1:02d}")
            if rid in global_room_ids:
                new_id = f"{rid}_f{floor_index + 1}_{room_index + 1}"
                report["repairs"].append(f"Renamed duplicate room '{rid}' to '{new_id}'.")
                renamed_room_ids[rid] = new_id
                rid = new_id
            global_room_ids.add(rid)
            room["id"] = rid
            room["position"] = _position(room)
            if abs(room["position"]["z"] - floor_elevation) > EPS:
                room["position"]["z"] = floor_elevation
                report["repairs"].append(
                    f"Aligned room '{rid}' to floor elevation {floor_elevation:.2f} m."
                )
            room["dimensions"] = _dimensions(room)
            room["floor_id"] = floor["id"]
            room["floor_level"] = floor["level"]
            rooms[rid] = room
        floor["rooms"] = list(rooms.values())
        floor.setdefault("walls", [])
        floor.setdefault("doors", [])
        floor.setdefault("windows", [])
        floor.setdefault("furniture", [])
        floor["furniture"] = [item for item in floor["furniture"]
                              if not isinstance(item, dict) or str(item.get("id")) not in deleted_furniture_ids]
        floor.setdefault("stairs", [])
        floor.setdefault("stair_openings", [])
        if renamed_room_ids:
            for wall in floor["walls"]:
                if isinstance(wall, dict):
                    wall["connected_rooms"] = [
                        renamed_room_ids.get(str(value), str(value))
                        for value in wall.get("connected_rooms", [])
                    ]
            for collection_name in ("doors", "windows", "furniture"):
                for item in floor[collection_name]:
                    if not isinstance(item, dict):
                        continue
                    for key in ("room_id", "roomId"):
                        value = item.get(key)
                        if value is not None:
                            item[key] = renamed_room_ids.get(str(value), str(value))
                    if isinstance(item.get("connected_room_ids"), list):
                        item["connected_room_ids"] = [
                            renamed_room_ids.get(str(value), str(value))
                            for value in item["connected_room_ids"]
                        ]
        _repair_openings(floor, rooms, report)
        _repair_furniture(floor, rooms, report)
        _validate_floor_geometry(floor, rooms, doc, report)
        room_furniture: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in floor["furniture"]:
            room_furniture[str(item.get("room_id"))].append(item)
        for room in floor["rooms"]:
            room["furniture"] = room_furniture.get(room["id"], [])
        all_rooms.extend(floor["rooms"])
        all_doors.extend(floor["doors"])
        all_windows.extend(floor["windows"])
        all_furniture.extend(floor["furniture"])

    validate_vertical_circulation(floors, doc, report)
    doc["rooms"] = all_rooms
    doc["doors"] = all_doors
    doc["windows"] = all_windows
    doc["furniture"] = all_furniture
    repair_exterior_access(doc, all_doors, report)
    report["inventory"] = {
        "rooms": len(all_rooms), "doors": len(all_doors), "windows": len(all_windows),
        "furniture_expected": len(all_furniture),
    }
    report["errors"] = report["critical_errors"]
    report["status"] = "invalid" if report["critical_errors"] else "valid"
    doc["generation_validation"] = report
    return doc, report
