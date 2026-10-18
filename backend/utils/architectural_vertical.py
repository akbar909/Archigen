"""Exterior access repair and multi-storey vertical-circulation validation."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


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
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


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
    canonical_path = {
        "start": {"x": round(gate_position["x"] + gate_width / 2.0, 2), "y": round(gate_position["y"], 2)},
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
    if len(floors) <= 1:
        return
    ordered = sorted(floors, key=lambda item: int(item.get("level", 0)))
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
                stair_position, stair_dimensions = _position(stair), _dimensions(stair)
                opening_position, opening_dimensions = _position(matching), _dimensions(matching)
                if (
                    abs(stair_position["x"] - opening_position["x"]) > 0.05
                    or abs(stair_position["y"] - opening_position["y"]) > 0.05
                    or opening_dimensions["width"] + EPS < stair_dimensions["width"]
                    or opening_dimensions["depth"] + EPS < stair_dimensions["depth"]
                ):
                    report["critical_errors"].append(
                        f"Slab opening '{matching.get('id')}' is not aligned with stair '{stair_id}'."
                    )
                if _number(stair.get("clear_width"), stair_dimensions["width"]) < 0.90:
                    report["critical_errors"].append(f"Stair '{stair_id}' is narrower than 0.90 m clear width.")
                if _number(stair.get("headroom"), 0.0) < 2.0:
                    report["critical_errors"].append(f"Stair '{stair_id}' has less than 2.00 m headroom.")
        elif stairs:
            report["critical_errors"].append(
                f"Top floor '{floor.get('id')}' contains a stair with no upper destination."
            )

        core = floor.get("stair_core")
        if not isinstance(core, dict):
            continue
        core_position, core_dimensions = _position(core), _dimensions(core)
        core_box = (
            core_position["x"], core_position["y"],
            core_position["x"] + core_dimensions["width"],
            core_position["y"] + core_dimensions["depth"],
        )
        for item in floor.get("furniture", []):
            position = _position(item)
            width, depth = _rotated_footprint(item)
            item_box = (
                position["x"] - width / 2.0, position["y"] - depth / 2.0,
                position["x"] + width / 2.0, position["y"] + depth / 2.0,
            )
            if _boxes_overlap(core_box, item_box, 0.12):
                report["critical_errors"].append(
                    f"Furniture '{item.get('id')}' blocks the stair core on floor '{floor.get('id')}'."
                )
