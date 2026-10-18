"""Targeted furniture transforms and opening-location helpers."""

from utils.refinement_common import *
from utils.refinement_style import *

def _has_furniture_transform_intent(prompt: str) -> bool:
    """Recognize a transform request without assuming any asset category."""
    normal = " ".join(prompt.lower().split())
    return bool(re.search(
        r"\b(?:fix|correct|adjust|set|put|shift|relocate|align|center|centre|middle|"
        r"rotate|turn|move|place|position|face|facing|direction|orientation|wrong|opposite|"
        r"resize|scale|larger|smaller|remove|delete|replace|swap)\b",
        normal,
    ))


def _normalized_phrase(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _furniture_aliases(item: Dict[str, Any]) -> List[str]:
    """Build searchable names from the actual design instead of a fixed asset list."""
    aliases = set()
    for key in ("id", "asset", "asset_id", "category", "type", "name"):
        phrase = _normalized_phrase(item.get(key))
        if phrase:
            aliases.add(phrase)
            # IDs commonly end with room IDs or numeric variants. Their first
            # one or two words still provide a useful human-facing asset name.
            words = phrase.split()
            if words:
                aliases.add(words[0])
            if len(words) > 1 and not words[1].isdigit():
                aliases.add(" ".join(words[:2]))
    expanded = set(aliases)
    for canonical, synonyms in FURNITURE_SYNONYMS.items():
        if canonical in aliases or any(canonical in alias for alias in aliases):
            expanded.update(synonyms)
    return sorted((alias for alias in expanded if len(alias) >= 2), key=len, reverse=True)


def _furniture_match_score(item: Dict[str, Any], prompt: str) -> int:
    normalized_prompt = _normalized_phrase(prompt)
    score = 0
    for alias in _furniture_aliases(item):
        if re.search(rf"\b{re.escape(alias)}\b", normalized_prompt):
            score = max(score, len(alias))
    return score


def _normalized_wall_side(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower().replace("_", " ").replace("wall", "").strip()
    aliases = {
        "north": "north", "back": "north", "rear": "north", "top": "north",
        "south": "south", "front": "south", "bottom": "south",
        "west": "west", "left": "west",
        "east": "east", "right": "east",
    }
    return aliases.get(text)


def _requested_asset_wall(prompt: str) -> Optional[str]:
    """Return an explicitly requested backing wall."""
    text = " ".join(prompt.lower().split())
    side_words = (
        ("north", "north"), ("back", "north"), ("rear", "north"),
        ("south", "south"), ("front", "south"),
        ("west", "west"), ("left", "west"),
        ("east", "east"), ("right", "east"),
    )
    for word, side in side_words:
        if re.search(rf"\b(?:against|along|on|at|to)\s+(?:the\s+)?{word}(?:\s+wall)?\b", text):
            return side
    return None


def _requested_facing_side(prompt: str) -> Optional[str]:
    text = " ".join(prompt.lower().split())
    aliases = (
        ("north", "north"), ("back", "north"), ("rear", "north"),
        ("south", "south"), ("front", "south"),
        ("west", "west"), ("left", "west"),
        ("east", "east"), ("right", "east"),
    )
    for word, side in aliases:
        if re.search(rf"\b(?:face|facing|toward|towards)\s+(?:the\s+)?{word}\b", text):
            return side
    return None


def _requested_rotation_delta(prompt: str) -> Optional[Tuple[float, bool]]:
    """Return (degrees, absolute) for explicit numeric rotation instructions."""
    text = " ".join(prompt.lower().split())
    match = re.search(
        r"\b(?:rotate|turn|rotation)\b[^.;]{0,45}?\b(?:(to|by)\s+)?(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg)?\b",
        text,
    )
    if not match:
        return None
    return float(match.group(2)), match.group(1) == "to"


def _snap_item_to_wall(item: Dict[str, Any], room: Dict[str, Any], side: str) -> None:
    """Put a wall-backed item's back on the wall while preserving its along-wall position."""
    room_pos = room.get("position", {})
    room_dim = room.get("dimensions", {})
    item_pos = item.get("position", {}) if isinstance(item.get("position"), dict) else {}
    item_dim = item.get("dimensions", {}) if isinstance(item.get("dimensions"), dict) else {}
    x0 = float(room_pos.get("x", 0.0))
    y0 = float(room_pos.get("y", room_pos.get("z", 0.0)))
    x1 = x0 + float(room_dim.get("width", room.get("width", 0.0)))
    y1 = y0 + float(room_dim.get("depth", room.get("length", 0.0)))
    width = float(item_dim.get("width", 0.8))
    depth = float(item_dim.get("depth", 0.8))
    rotation = WALL_ROTATIONS[side]
    footprint_width, footprint_depth = (width, depth) if side in {"north", "south"} else (depth, width)

    min_x = x0 + WALL_MARGIN + footprint_width / 2.0
    max_x = x1 - WALL_MARGIN - footprint_width / 2.0
    min_y = y0 + WALL_MARGIN + footprint_depth / 2.0
    max_y = y1 - WALL_MARGIN - footprint_depth / 2.0
    x = max(min_x, min(max_x, float(item_pos.get("x", (x0 + x1) / 2.0))))
    y = max(min_y, min(max_y, float(item_pos.get("y", item_pos.get("z", (y0 + y1) / 2.0)))))
    if side == "west":
        x = min_x
    elif side == "east":
        x = max_x
    elif side == "south":
        y = min_y
    else:
        y = max_y

    item["anchor_wall"] = side
    item["rotation"] = rotation
    item["placement_hint"] = "wall"
    item["position"] = {
        "x": round(x, 4),
        "y": round(y, 4),
        "z": float(item_pos.get("z", room_pos.get("z", 0.0))),
    }


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


def _finalize_refinement(
    design: Dict[str, Any], report: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Invalidate stale 3D output and run the same preflight used by generation."""
    design.pop("glb_url", None)
    design.pop("approved_at", None)
    design["layout_approved"] = False
    design, validation = validate_and_repair_design(design, repair=True)
    if validation["critical_errors"]:
        report["errors"].extend(validation["critical_errors"])
        return None, report
    design["refinement"] = report
    return design, report


def _apply_single_furniture_transform_refinement(
    base_design: Dict[str, Any], prompt: str, report: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Transform one named furniture asset without regenerating the house."""
    design = copy.deepcopy(base_design)
    requested_room_type = _requested_room_type(prompt)
    scored: List[Tuple[int, Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []

    for floor in design.get("floors", []):
        room_map = {str(room.get("id")): room for room in floor.get("rooms", [])}
        for item in floor.get("furniture", []):
            room = room_map.get(str(item.get("room_id") or item.get("roomId") or ""))
            if not room:
                continue
            actual_type = _type_group(room.get("type"))
            if requested_room_type:
                accepted = {requested_room_type}
                if requested_room_type == "bedroom":
                    accepted.add("master_bedroom")
                if actual_type not in accepted:
                    continue
            score = _furniture_match_score(item, prompt)
            if score:
                scored.append((score, floor, room, item))

    # The prompt may concern a door, window, room, or broad redesign. If no
    # actual furniture name matches, allow another handler to process it.
    if not scored:
        return None, report

    report["handled"] = True
    best_score = max(entry[0] for entry in scored)
    matches = [entry for entry in scored if entry[0] == best_score]
    if len(matches) > 1:
        label = _normalized_phrase(matches[0][3].get("category") or matches[0][3].get("asset") or "asset")
        report["errors"].append(
            f"More than one matching {label} was found. Specify its room, name, or identifier."
        )
        return None, report

    _score, _floor, room, item = matches[0]
    explicit_wall = _requested_asset_wall(prompt)
    facing_side = _requested_facing_side(prompt)
    numeric_rotation = _requested_rotation_delta(prompt)
    current_wall = _normalized_wall_side(item.get("anchor_wall"))
    old_position = copy.deepcopy(item.get("position", {}))
    old_rotation = float(item.get("rotation", item.get("rotation_y", 0.0)) or 0.0) % 360.0
    action = ""
    prioritize_exact_position = False

    if explicit_wall:
        _snap_item_to_wall(item, room, explicit_wall)
        action = f"placed against the {explicit_wall} wall and faced into the room"
    elif facing_side:
        if current_wall:
            backing_wall = OPPOSITE_SIDE[facing_side]
            _snap_item_to_wall(item, room, backing_wall)
            action = f"faced {facing_side} from the {backing_wall} wall"
        else:
            item.pop("anchor_wall", None)
            item["rotation"] = FACING_ROTATIONS[facing_side]
            action = f"faced {facing_side}"
    elif numeric_rotation:
        degrees, absolute = numeric_rotation
        new_rotation = (degrees if absolute else old_rotation + degrees) % 360.0
        cardinal = int(round(new_rotation / 90.0) * 90) % 360
        if current_wall and abs(new_rotation - cardinal) < 0.001:
            backing_wall = ROTATION_WALLS[cardinal]
            _snap_item_to_wall(item, room, backing_wall)
            action = f"rotated to {new_rotation:g} degrees and moved to the matching {backing_wall} wall"
        else:
            item.pop("anchor_wall", None)
            item["rotation"] = new_rotation
            action = f"rotated to {new_rotation:g} degrees"
    elif re.search(r"\b(?:opposite|other\s+way|reverse)\b", prompt.lower()):
        if current_wall:
            backing_wall = OPPOSITE_SIDE[current_wall]
            _snap_item_to_wall(item, room, backing_wall)
            action = f"reversed onto the {backing_wall} wall"
        else:
            item["rotation"] = (old_rotation + 180.0) % 360.0
            action = "turned in the opposite direction"
    elif re.search(r"\b(?:fix|correct|adjust|direction|orientation|wrong)\b", prompt.lower()):
        if current_wall:
            _snap_item_to_wall(item, room, current_wall)
            action = f"aligned with the {current_wall} wall and faced into the room"
        else:
            item["rotation"] = (old_rotation + 180.0) % 360.0
            action = "turned in the opposite direction"
    elif re.search(r"\b(?:center|centre|middle)\b", prompt.lower()):
        room_pos, room_dim = room.get("position", {}), room.get("dimensions", {})
        item.pop("anchor_wall", None)
        item["position"] = {
            "x": float(room_pos.get("x", 0.0)) + float(room_dim.get("width", 0.0)) / 2.0,
            "y": float(room_pos.get("y", 0.0)) + float(room_dim.get("depth", 0.0)) / 2.0,
            "z": float(old_position.get("z", room_pos.get("z", 0.0))),
        }
        action = "moved to the room center"
        prioritize_exact_position = True
    else:
        report["errors"].append(
            f"Specify how '{item.get('id')}' should move or rotate, for example: "
            "'rotate 90 degrees', 'face north', or 'move to the left wall'."
        )
        return None, report

    new_rotation = float(item.get("rotation", item.get("rotation_y", 0.0)) or 0.0) % 360.0
    report["changes"].append(
        f"Updated asset '{item.get('id')}' in room '{room.get('id')}': {action}; "
        f"rotation {old_rotation:g} degrees -> {new_rotation:g} degrees, "
        f"position {old_position} -> {item.get('position', {})}."
    )
    # Direction-only edits treat the saved furniture as fixed context. Exact
    # placement edits get priority so the requested position is honored safely.
    floor_items = list(_floor.get("furniture", []))
    other_items = [other for other in floor_items if other is not item]
    # An explicit center request is positional, not merely directional. Give
    # that exact target first choice and let preflight minimally relocate a
    # conflicting loose table/chair instead of moving the requested asset away.
    _floor["furniture"] = [item] + other_items if prioritize_exact_position else other_items + [item]
    return _finalize_refinement(design, report)


def _design_has_furniture_target(design: Dict[str, Any], text: str) -> bool:
    return any(
        _furniture_match_score(item, text) > 0
        for floor in design.get("floors", [])
        for item in floor.get("furniture", [])
        if isinstance(item, dict)
    )


def _split_furniture_edit_clauses(design: Dict[str, Any], prompt: str) -> List[str]:
    """Split only where a new named asset starts; keep modifiers with their asset."""
    raw_parts = [
        part.strip()
        for part in re.split(r"\s*(?:\r?\n+|;|,|\band\b)\s*", prompt, flags=re.IGNORECASE)
        if part.strip()
    ]
    clauses: List[str] = []
    for part in raw_parts:
        if _design_has_furniture_target(design, part):
            clauses.append(part)
        elif clauses:
            clauses[-1] = f"{clauses[-1]} and {part}"
    return clauses


def _apply_furniture_transform_refinement(
    base_design: Dict[str, Any], prompt: str, report: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Apply one or more named asset transforms as one atomic refinement."""
    clauses = _split_furniture_edit_clauses(base_design, prompt)
    if not clauses:
        return None, report

    working = base_design
    for clause in clauses:
        clause_report: Dict[str, Any] = {"handled": False, "changes": [], "errors": []}
        updated, clause_report = _apply_single_furniture_transform_refinement(
            working, clause, clause_report,
        )
        if not clause_report["handled"]:
            continue
        report["handled"] = True
        report["changes"].extend(clause_report["changes"])
        report["errors"].extend(clause_report["errors"])
        if clause_report["errors"] or updated is None:
            # Atomic behavior: if one requested edit is unsafe, save none of them.
            return None, report
        working = updated

    if not report["handled"]:
        return None, report
    working["refinement"] = report
    return working, report

__all__ = [name for name in globals() if not name.startswith('__')]
