"""Deterministic edits applied to an existing canonical architectural version.

Small structural refinements must not be sent through whole-house generation:
doing so lets an LLM rewrite the plot, room dimensions, furniture, and unrelated
openings.  This module recognizes supported targeted operations and changes only
the addressed canonical object before running the shared architectural preflight.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.architectural_preflight import validate_and_repair_design


ROOM_ALIASES = {
    "master bedroom": "master_bedroom",
    "bed room": "bedroom",
    "bedroom": "bedroom",
    "wash room": "bathroom",
    "washroom": "bathroom",
    "bath room": "bathroom",
    "bathroom": "bathroom",
    "living room": "living_room",
    "living": "living_room",
    "lounge": "living_room",
    "kitchen": "kitchen",
    "dining room": "dining_room",
    "dining": "dining_room",
    "corridor": "corridor",
    "hallway": "corridor",
    "foyer": "foyer",
    "garage": "garage",
}


def _type_group(value: Any) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    if "bath" in text or "wash" in text or "toilet" in text:
        return "bathroom"
    if "bed" in text:
        return "master_bedroom" if "master" in text else "bedroom"
    if "living" in text or "lounge" in text:
        return "living_room"
    if "kitchen" in text:
        return "kitchen"
    if "dining" in text:
        return "dining_room"
    if "corridor" in text or "hallway" in text:
        return "corridor"
    return text


def _requested_room_type(prompt: str) -> Optional[str]:
    for alias in sorted(ROOM_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", prompt):
            return ROOM_ALIASES[alias]
    return None


def _is_window_removal(prompt: str) -> bool:
    normal = " ".join(prompt.lower().split())
    explicit = re.search(r"\b(?:remove|delete|omit|take\s+out)\b[^.;]{0,80}\bwindow\b", normal)
    # Common dictation/typing error observed in refinement prompts:
    # "room one window from bedroom" means "remove one window ...".
    remove_typo = re.search(r"\broom\s+(?:one|1|a)\s+window\s+from\b", normal)
    return bool(explicit or remove_typo)


def _nearest_room_side(room: Dict[str, Any], position: Dict[str, Any]) -> str:
    rpos = room.get("position", {})
    dim = room.get("dimensions", {})
    x0, y0 = float(rpos.get("x", 0.0)), float(rpos.get("y", 0.0))
    x1 = x0 + float(dim.get("width", room.get("width", 0.0)))
    y1 = y0 + float(dim.get("depth", room.get("length", 0.0)))
    x, y = float(position.get("x", 0.0)), float(position.get("y", position.get("z", 0.0)))
    return min(
        ((abs(y - y0), "south"), (abs(y - y1), "north"),
         (abs(x - x0), "west"), (abs(x - x1), "east")),
        key=lambda item: item[0],
    )[1]


def _target_window_side(prompt: str, floor: Dict[str, Any], room: Dict[str, Any]) -> Optional[str]:
    text = prompt.lower()
    if any(phrase in text for phrase in ("behind the bed", "behind bed", "back side of bed", "backside of bed", "headboard")):
        room_id = str(room.get("id"))
        bed = next((
            item for item in floor.get("furniture", [])
            if str(item.get("room_id") or item.get("roomId")) == room_id
            and "bed" in str(item.get("asset") or item.get("category") or item.get("type", "")).lower()
            and "night" not in str(item.get("asset") or item.get("category") or item.get("type", "")).lower()
        ), None)
        if bed:
            return _nearest_room_side(room, bed.get("position", {}))

    side_phrases = (
        ("back", "north"), ("rear", "north"), ("north", "north"),
        ("front", "south"), ("south", "south"),
        ("left", "west"), ("west", "west"),
        ("right", "east"), ("east", "east"),
    )
    for phrase, side in side_phrases:
        if re.search(rf"\b{phrase}\b(?:\s+side|\s+wall|\s+window)?", text):
            return side
    return None


def apply_targeted_refinement(
    base_design: Dict[str, Any], prompt: str
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Apply a supported targeted edit or report that full generation is needed."""
    report: Dict[str, Any] = {"handled": False, "changes": [], "errors": []}
    if not isinstance(base_design, dict) or not base_design.get("floors"):
        return None, report
    if not _is_window_removal(prompt):
        return None, report

    report["handled"] = True
    room_type = _requested_room_type(prompt)
    if not room_type:
        report["errors"].append("Specify which room the window should be removed from.")
        return None, report

    design = copy.deepcopy(base_design)
    removed = None
    for floor in design.get("floors", []):
        rooms = [room for room in floor.get("rooms", []) if _type_group(room.get("type")) == room_type]
        if room_type == "bedroom" and not rooms:
            rooms = [room for room in floor.get("rooms", []) if _type_group(room.get("type")) == "master_bedroom"]
        for room in rooms:
            room_id = str(room.get("id"))
            candidates = [
                window for window in floor.get("windows", [])
                if str(window.get("room_id") or window.get("roomId")) == room_id
            ]
            if not candidates:
                continue
            side = _target_window_side(prompt, floor, room)
            matching = [window for window in candidates if str(window.get("wall_side", "")).lower() == side] if side else candidates
            if not matching:
                report["errors"].append(
                    f"The {room.get('name', room_type)} has no window on the requested {side} side."
                )
                return None, report
            # Stable selection ensures repeating the same edit is deterministic.
            removed = sorted(matching, key=lambda item: str(item.get("id", "")))[0]
            floor["windows"] = [window for window in floor.get("windows", []) if window is not removed]
            report["changes"].append(
                f"Removed window '{removed.get('id')}' from room '{room_id}' ({side or 'unspecified'} side)."
            )
            break
        if removed:
            break

    if not removed:
        report["errors"].append(f"No window was found in the requested {room_type.replace('_', ' ')}.")
        return None, report

    # A new version must never inherit approval or a GLB belonging to its base.
    design.pop("glb_url", None)
    design.pop("approved_at", None)
    design["layout_approved"] = False
    design, validation = validate_and_repair_design(design, repair=True)
    if validation["critical_errors"]:
        report["errors"].extend(validation["critical_errors"])
        return None, report
    design["refinement"] = report
    return design, report

