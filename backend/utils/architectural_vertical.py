"""Exterior access repair and multi-storey vertical-circulation validation."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from utils.stair_geometry import stair_approach_box, stair_metrics


EPS = 1e-6


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _position(obj: Dict[str, Any]) -> Dict[str, float]:
    value = obj.get("position") if isinstance(obj.get("position"), dict) else {}
    return {key: _number(value.get(key)) for key in ("x", "y", "z")}


def _dimensions(obj: Dict[str, Any]) -> Dict[str, float]:
    value = obj.get("dimensions") if isinstance(obj.get("dimensions"), dict) else {}
    return {
        "width": max(EPS, _number(value.get("width"), 0.8)),
        "depth": max(EPS, _number(value.get("depth"), 0.8)),
        "height": max(EPS, _number(value.get("height"), 0.8)),
    }


def _rotated_footprint(item: Dict[str, Any]) -> Tuple[float, float]:
    dimensions = _dimensions(item)
    angle = math.radians(_number(item.get("rotation")) % 180.0)
    cosine, sine = abs(math.cos(angle)), abs(math.sin(angle))
    return (
        dimensions["width"] * cosine + dimensions["depth"] * sine,
        dimensions["width"] * sine + dimensions["depth"] * cosine,
    )


def _boxes_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], gap: float) -> bool:
    return not (a[2] + gap <= b[0] + EPS or b[2] + gap <= a[0] + EPS or a[3] + gap <= b[1] + EPS or b[3] + gap <= a[1] + EPS)


def _box(item):
    position, dimensions = _position(item), _dimensions(item)
    return (position["x"], position["y"], position["x"] + dimensions["width"], position["y"] + dimensions["depth"])


def _rectangle(box):
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _contains(outer, inner, tolerance=0.001):
    return (outer[0] <= inner[0] + tolerance and outer[1] <= inner[1] + tolerance
            and outer[2] + tolerance >= inner[2] and outer[3] + tolerance >= inner[3])


def _polygons_overlap(first, second):
    for polygon in (first, second):
        for index, a in enumerate(polygon):
            b = polygon[(index + 1) % len(polygon)]
            axis = (-(b[1] - a[1]), b[0] - a[0])
            if abs(axis[0]) + abs(axis[1]) < EPS:
                continue
            projections = [[x * axis[0] + y * axis[1] for x, y in shape] for shape in (first, second)]
            if max(projections[0]) <= min(projections[1]) + EPS or max(projections[1]) <= min(projections[0]) + EPS:
                return False
    return True


def _furniture_polygon(item):
    position, dimensions = _position(item), _dimensions(item)
    angle = math.radians(_number(item.get("rotation")))
    cosine, sine = math.cos(angle), math.sin(angle)
    return [(position["x"] + x * cosine - y * sine, position["y"] + x * sine + y * cosine)
            for x, y in ((-dimensions["width"] / 2, -dimensions["depth"] / 2),
                         (dimensions["width"] / 2, -dimensions["depth"] / 2),
                         (dimensions["width"] / 2, dimensions["depth"] / 2),
                         (-dimensions["width"] / 2, dimensions["depth"] / 2))]


def _door_sectors(door):
    """The same hinge/quarter-circle geometry used by the 2D CAD symbols."""
    if any(token in str(door.get("type", "")) for token in ("sliding", "garage")):
        return []
    width = _number(door.get("width"), 0.85)
    side = door.get("wall_side", "south")
    vertical = side in ("west", "east")
    if "double" in str(door.get("type", "")):
        result = []
        for sign in (-1, 1):
            position = _position(door)
            position["x" if not vertical else "y"] += sign * width / 4
            result.extend(_door_sectors({**door, "type": "single", "width": width / 2,
                                         "hinge_side": "left" if sign < 0 else "right", "position": position}))
        return result
    tangent = (0, 1) if vertical else (1, 0)
    normal = {"south": (0, 1), "north": (0, -1), "west": (1, 0), "east": (-1, 0)}.get(side, (0, 1))
    right = door.get("hinge_side") == "right"
    outward = door.get("swing_direction") == "outward"
    position = _position(door)
    hinge = (position["x"] + tangent[0] * width / 2 * (1 if right else -1),
             position["y"] + tangent[1] * width / 2 * (1 if right else -1))
    closed = tuple(value * (-1 if right else 1) for value in tangent)
    opened = tuple(value * (-1 if outward else 1) for value in normal)
    sector = [hinge]
    for index in range(25):
        angle = index / 24 * math.pi / 2
        sector.append((hinge[0] + width * (closed[0] * math.cos(angle) + opened[0] * math.sin(angle)),
                       hinge[1] + width * (closed[1] * math.cos(angle) + opened[1] * math.sin(angle))))
    return [sector]


def _door_approach_boxes(floor, door):
    """Reserve a door-width, 1.15 m deep route on both sides of a doorway.

    Furniture placement also offers a lateral comfort margin. A structural
    collision uses the actual aperture width, so a stair beside a clear
    doorway is not rejected merely for occupying that optional side margin.
    """
    if "garage" in str(door.get("type", "")) or door.get("swing") == "overhead":
        return []
    position = door.get("position")
    if not isinstance(position, dict):
        return []
    x, y = _number(position.get("x")), _number(position.get("y"))
    connected = {str(value) for value in (door.get("connected_room_ids") or door.get("connected_rooms") or [])}
    connected.update(str(value) for value in (door.get("room_id"), door.get("roomId"), door.get("connected_room_id")) if value)
    half, depth = _number(door.get("width"), .9) / 2, 1.15
    result = []
    for room in floor.get("rooms", []):
        if not isinstance(room, dict):
            continue
        elevation = _number((room.get("position") or {}).get("z"), _number(floor.get("elevation")))
        if abs(_number(position.get("z"), elevation) - elevation) > .35:
            continue
        x0, y0, x1, y1 = _box(room)
        distance, side = min(((abs(y - y0), "south"), (abs(y - y1), "north"),
                              (abs(x - x0), "west"), (abs(x - x1), "east")), key=lambda item: item[0])
        on_boundary = x0 - .3 <= x <= x1 + .3 and y0 - .3 <= y <= y1 + .3 and distance <= .35
        if str(room.get("id")) not in connected and not on_boundary:
            continue
        if side == "south":
            zone = x - half, y0, x + half, min(y1, y0 + depth)
        elif side == "north":
            zone = x - half, max(y0, y1 - depth), x + half, y1
        elif side == "west":
            zone = x0, y - half, min(x1, x0 + depth), y + half
        else:
            zone = max(x0, x1 - depth), y - half, x1, y + half
        zone = max(x0, zone[0]), max(y0, zone[1]), min(x1, zone[2]), min(y1, zone[3])
        if zone[2] > zone[0] + EPS and zone[3] > zone[1] + EPS:
            result.append(zone)
    return result


def _wall_crosses_box(wall, box):
    """Clip the whole wall segment against the interior, rather than its midpoint."""
    start, end = wall.get("start") or wall.get("from"), wall.get("end") or wall.get("to")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return False
    low, high = 0.0, 1.0
    for axis, lower, upper in (("x", box[0] + .02, box[2] - .02), ("y", box[1] + .02, box[3] - .02)):
        origin, delta = _number(start.get(axis)), _number(end.get(axis)) - _number(start.get(axis))
        if abs(delta) < EPS:
            if not lower < origin < upper:
                return False
        else:
            first, second = sorted(((lower - origin) / delta, (upper - origin) / delta))
            low, high = max(low, first), min(high, second)
            if low >= high - EPS:
                return False
    return low < high - EPS


def repair_exterior_access(
    design: Dict[str, Any], doors: List[Dict[str, Any]], report: Dict[str, Any]
) -> None:
    """Keep the site gate, entrance route, and wall-hosted main door connected."""
    main_door = next(
        (door for door in doors if str(door.get("type", "")).lower() == "main_entrance"),
        None,
    )
    exterior = design.get("exterior")
    if not main_door or not isinstance(exterior, dict):
        return
    door_position = _position(main_door)
    canonical_entrance = {
        "door_id": main_door.get("id"),
        "position": door_position,
        "width": round(_number(main_door.get("width"), 1.10), 2),
        "height": round(_number(main_door.get("height"), 2.20), 2),
    }
    if exterior.get("main_entrance") != canonical_entrance:
        exterior["main_entrance"] = canonical_entrance
        report["repairs"].append("Aligned the exterior entrance marker with the main entrance door.")
    gate = exterior.get("gate")
    if not isinstance(gate, dict):
        return
    gate.setdefault("asset", "architecture/doors/exterior/Gate.glb")
    gate_position = _position(gate)
    gate_width = max(0.8, _number(gate.get("width"), 3.6))
    vertical_gate = gate.get("axis") == "y" or gate.get("side") in {"east", "west"}
    canonical_path = {
        "start": {
            "x": round(gate_position["x"] + (0 if vertical_gate else gate_width / 2.0), 2),
            "y": round(gate_position["y"] + (gate_width / 2.0 if vertical_gate else 0), 2),
        },
        "end": {"x": round(door_position["x"], 2), "y": round(door_position["y"], 2)},
        "width": 1.2,
    }
    if exterior.get("entrance_path") != canonical_path:
        exterior["entrance_path"] = canonical_path
        report["repairs"].append("Connected the main gate to the main entrance with an access path.")


def validate_vertical_circulation(
    floors: List[Dict[str, Any]], design: Dict[str, Any], report: Dict[str, Any]
) -> None:
    """Validate adjacent storey connections, slab openings, and stair clearance."""
    ordered = sorted(floors, key=lambda item: int(item.get("level", 0)))
    public_types = {"stair_lobby", "hallway", "corridor", "foyer", "living_room", "dining_room"}

    def validate_zone(floor, box, label, *, approach=False):
        rooms = [room for room in floor.get("rooms", []) if isinstance(room, dict)]
        hosts = [room for room in rooms if _contains(_box(room), box)]
        if not hosts:
            report["critical_errors"].append(f"{label} is not contained in a usable room or stair lobby on floor '{floor.get('id')}'.")
        elif not any(room.get("type") in public_types for room in hosts):
            report["critical_errors"].append(f"{label} occupies a private or service room on floor '{floor.get('id')}'; provide shared stair access.")
        polygon = _rectangle(box)
        for item in floor.get("furniture", []):
            if not isinstance(item, dict) or item.get("ceiling_mounted") or item.get("wall_mounted"):
                continue
            if any(token in str(item.get("category", "")) for token in ("rug", "carpet")):
                continue
            if _polygons_overlap(polygon, _furniture_polygon(item)):
                report["critical_errors"].append(f"Furniture '{item.get('id')}' blocks {label.lower()} on floor '{floor.get('id')}'.")
        for door in floor.get("doors", []):
            if any(_polygons_overlap(polygon, sector) for sector in _door_sectors(door)):
                report["critical_errors"].append(f"Door '{door.get('id')}' swings into {label.lower()} on floor '{floor.get('id')}'.")
            if not approach and any(_boxes_overlap(box, zone, 0) for zone in _door_approach_boxes(floor, door)):
                report["critical_errors"].append(f"{label} blocks the approach to door '{door.get('id')}' on floor '{floor.get('id')}'.")
        # Approach strips can end at an access doorway, but no solid wall may
        # pass through the stair or its upper-floor void.
        if not approach:
            for wall in floor.get("walls", []):
                if _wall_crosses_box(wall, box):
                    report["critical_errors"].append(f"Wall '{wall.get('id')}' crosses {label.lower()} on floor '{floor.get('id')}'.")

    for index, floor in enumerate(ordered):
        stairs = [item for item in floor.get("stairs", []) if isinstance(item, dict)]
        if index < len(ordered) - 1:
            if not stairs:
                report["critical_errors"].append(f"Floor '{floor.get('id')}' has no stair to the next storey.")
                continue
            if len(stairs) > 1:
                report["warnings"].append(
                    f"Floor '{floor.get('id')}' contains multiple stair flights; only aligned adjacent connections are validated."
                )
            upper = ordered[index + 1]
            openings = [item for item in upper.get("stair_openings", []) if isinstance(item, dict)]
            for stair in stairs:
                stair_id = str(stair.get("id") or "")
                rise = _number(upper.get("elevation")) - _number(floor.get("elevation"))
                metrics = stair_metrics(stair, rise)
                report["critical_errors"].extend(f"Stair '{stair_id}' {error}" for error in metrics["errors"])
                if abs(_dimensions(stair)["height"] - rise) > 0.05:
                    report["critical_errors"].append(f"Stair '{stair_id}' height does not match its floor-to-floor rise.")
                if abs(_position(stair)["z"] - _number(floor.get("elevation"))) > 0.05:
                    report["critical_errors"].append(f"Stair '{stair_id}' does not start at its lower floor elevation.")
                validate_zone(floor, _box(stair), f"Stair '{stair_id}'")
                if _number(stair.get("access_depth")) > 0:
                    validate_zone(floor, stair_approach_box(stair), f"Stair '{stair_id}' approach", approach=True)
                connects = stair.get("connects", {})
                if connects.get("lower_floor") != floor.get("id") or connects.get("upper_floor") != upper.get("id"):
                    report["critical_errors"].append(
                        f"Stair '{stair_id}' does not connect adjacent floors '{floor.get('id')}' and '{upper.get('id')}'."
                    )
                matching = next(
                    (opening for opening in openings if str(opening.get("serves_stair_id") or "") == stair_id),
                    None,
                )
                if not matching:
                    report["critical_errors"].append(
                        f"Upper floor '{upper.get('id')}' has no slab opening for stair '{stair_id}'."
                    )
                    continue
                validate_zone(upper, _box(matching), f"Stair opening '{matching.get('id')}'")
                if _number(stair.get("access_depth")) > 0:
                    validate_zone(upper, stair_approach_box(stair, upper=True), f"Stair '{stair_id}' upper approach", approach=True)
                stair_position, stair_dimensions = _position(stair), _dimensions(stair)
                opening_position, opening_dimensions = _position(matching), _dimensions(matching)
                if (
                    abs(stair_position["x"] - opening_position["x"]) > 0.05
                    or abs(stair_position["y"] - opening_position["y"]) > 0.05
                    or opening_dimensions["width"] + EPS < stair_dimensions["width"]
                    or opening_dimensions["depth"] + EPS < stair_dimensions["depth"]
                    or not _contains(_box(matching), _box(stair), tolerance=.001)
                    or abs(opening_position["z"] - _number(upper.get("elevation"))) > .05
                ):
                    report["critical_errors"].append(
                        f"Slab opening '{matching.get('id')}' is not aligned with stair '{stair_id}'."
                    )
                if _number(stair.get("headroom"), 0.0) < 2.0:
                    report["critical_errors"].append(f"Stair '{stair_id}' has less than 2.00 m headroom.")
        elif stairs:
            report["critical_errors"].append(
                f"Top floor '{floor.get('id')}' contains a stair with no upper destination."
            )
