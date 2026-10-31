"""Public dispatcher for deterministic architectural refinements."""

from utils.refinement_common import *
from utils.refinement_resize import *
from utils.refinement_validation import *
from utils.refinement_style import *
from utils.refinement_furniture import *


def apply_layout_refinement(base_design, prompt, selection=None):
    """Apply local editor instructions as one draft transaction, without persistence.

    Reuse the existing targeted refinement pipeline, including its geometric
    repairs. Unsupported instructions fail explicitly instead of replacing the
    floor plan with a newly generated house.
    """
    clauses = re.split(r"\s+(?:and|then)\s+(?=(?:slide|move|rotate|flip|make|increase|resize|set)\b)", prompt, flags=re.I)
    design = copy.deepcopy(base_design)
    changes = []
    for clause in clauses:
        if selection:
            from utils.editor_selection_refinement import apply_selection_refinement
            result, report = apply_selection_refinement(design, clause, selection)
        else:
            result, report = _apply_editor_opening_refinement(design, clause)
        if not report["handled"]:
            result, report = apply_targeted_refinement(design, clause)
        if not report.get("handled"):
            return None, {"handled": False, "errors": ["This edit is not supported. Specify a room resize, furniture transform, or a door/window move or flip."], "changes": []}
        if result is None or report.get("errors"):
            return None, report
        before_entities = {item.get("id"): item for floor in design.get("floors", [])
                           for key in ("rooms", "walls", "doors", "windows", "furniture", "stairs")
                           for item in floor.get(key, []) if isinstance(item, dict) and item.get("locked")}
        after_entities = {item.get("id"): item for floor in result.get("floors", [])
                          for key in ("rooms", "walls", "doors", "windows", "furniture", "stairs")
                          for item in floor.get(key, []) if isinstance(item, dict)}
        if any(after_entities.get(identifier) != item for identifier, item in before_entities.items()):
            return None, {"handled": True, "errors": ["This edit would change a locked element. Unlock it first."], "changes": []}
        design = result
        changes.extend(report.get("changes", []))
    return design, {"handled": True, "changes": changes, "errors": []}


def _apply_editor_opening_refinement(base_design, prompt):
    report = {"handled": False, "changes": [], "errors": []}
    kind_match = re.search(r"\b(door|window)\b", prompt, re.I)
    named_kinds = {kind for floor in base_design.get("floors", []) for kind in ("door", "window")
                   for item in floor.get(kind + "s", []) if item.get("id") and str(item["id"]).lower() in prompt.lower()}
    if not (kind_match or len(named_kinds) == 1) or not re.search(r"\b(move|slide|shift|flip|hinge|sill)\b", prompt, re.I):
        return None, report
    report["handled"] = True
    kind = kind_match.group(1).lower() if kind_match else next(iter(named_kinds))
    design = copy.deepcopy(base_design)
    target_type = _requested_room_type(prompt)
    candidates = []
    for floor in design.get("floors", []):
        for opening in floor.get(kind + "s", []):
            room = next((r for r in floor.get("rooms", []) if r.get("id") == (opening.get("room_id") or opening.get("roomId"))), None)
            named = str(opening.get("id", "")).lower() in prompt.lower() if opening.get("id") else False
            if named or room and (not target_type or _type_group(room.get("type")) == target_type):
                candidates.append((floor, opening))
    named = [pair for pair in candidates if str(pair[1]["id"]).lower() in prompt.lower()]
    candidates = named or candidates
    if len(candidates) != 1:
        report["errors"].append("Specify one opening by its identifier or a room with a single matching opening.")
        return None, report
    floor, opening = candidates[0]
    if opening.get("locked"):
        report["errors"].append("Unlock this opening before editing it.")
        return None, report
    if kind == "door" and re.search(r"\b(flip|hinge)\b", prompt, re.I):
        if re.search(r"\bhinge\b", prompt, re.I):
            opening["hinge_side"] = "right" if opening.get("hinge_side", "left") == "left" else "left"
        else:
            opening["swing_direction"] = "outward" if opening.get("swing_direction", "inward") == "inward" else "inward"
    else:
        amount = re.search(r"(\d+(?:\.\d+)?)\s*(feet|foot|ft|inches|in|meters?|metres?|m|cm|mm)\b", prompt, re.I)
        if not amount:
            report["errors"].append("Specify the distance and unit, for example 'slide door_01 1 ft right'.")
            return None, report
        unit = amount.group(2).lower()
        value = float(amount.group(1)) * ({"feet": .3048, "foot": .3048, "ft": .3048, "inches": .0254, "in": .0254, "cm": .01, "mm": .001}.get(unit, 1))
        if kind == "window" and re.search(r"\bsill\b", prompt, re.I):
            if value + float(opening.get("height", 1.4)) > float(floor.get("floor_height", 3)):
                report["errors"].append("The sill and window height exceed the floor height.")
                return None, report
            opening["sill_height"] = round(value, 4)
            opening.setdefault("position", {})["z"] = float(floor.get("elevation", 0)) + value
        else:
            wall = next((w for w in floor.get("walls", []) if w.get("id") == opening.get("wall_id")), None)
            if not wall:
                report["errors"].append("This opening must be hosted on a wall first.")
                return None, report
            start, end = wall["start"], wall["end"]
            length = ((end["x"] - start["x"]) ** 2 + (end["y"] - start["y"]) ** 2) ** .5
            if length <= .001:
                report["errors"].append("The host wall has zero length.")
                return None, report
            position = opening["position"]
            offset = ((position["x"] - start["x"]) * (end["x"] - start["x"]) + (position["y"] - start["y"]) * (end["y"] - start["y"])) / length
            negative = bool(re.search(r"\b(left|south|west|backward)\b", prompt, re.I))
            positive = bool(re.search(r"\b(right|north|east|forward)\b", prompt, re.I))
            if not negative and not positive:
                report["errors"].append("Specify a direction along the wall: left/right or south/north.")
                return None, report
            offset += -value if negative else value
            margin = float(opening.get("width", .85)) / 2 + .1
            if not margin <= offset <= length - margin:
                report["errors"].append("The move would exceed the wall or its jamb clearance.")
                return None, report
            opening["wall_offset"] = opening["offset"] = round(offset, 4)
            opening["t"] = offset / length
            position["x"] = round(start["x"] + (end["x"] - start["x"]) * offset / length, 4)
            position["y"] = round(start["y"] + (end["y"] - start["y"]) * offset / length, 4)
    report["changes"].append(f"Edited {kind} '{opening['id']}'.")
    if kind == "door":
        opening["swing"] = f"{opening.get('swing_direction', 'inward')}_{opening.get('hinge_side', 'right')}"
    return _finalize_refinement(design, report)

def apply_targeted_refinement(
    base_design: Dict[str, Any], prompt: str, requested_style: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Apply a supported targeted edit or report that full generation is needed."""
    report: Dict[str, Any] = {"handled": False, "changes": [], "errors": []}
    if not isinstance(base_design, dict) or not base_design.get("floors"):
        return None, report
    design, room_program_report = apply_room_program_refinement(base_design, prompt, report)
    if room_program_report["handled"]:
        return design, room_program_report
    resize_intent = _parse_room_resize_intent(prompt)
    if resize_intent:
        return _apply_room_resize(base_design, resize_intent, report)
    if _is_validation_repair_request(prompt, base_design):
        return _apply_validation_repair(base_design, prompt, report)
    if _is_style_only_refinement(prompt):
        return _apply_style_refinement(base_design, prompt, requested_style, report)
    # Naming an existing furniture asset means this is a local edit request.
    # Never silently fall through to whole-house generation merely because the
    # user's adjustment verb was not in our vocabulary. Window removal is
    # checked separately because prompts such as "window behind the bed" name
    # furniture only to identify an opening location.
    furniture_targeted = _design_has_furniture_target(base_design, prompt)
    if not _is_window_removal(prompt) and (
        _has_furniture_transform_intent(prompt) or furniture_targeted
    ):
        design, furniture_report = _apply_furniture_transform_refinement(base_design, prompt, report)
        if furniture_report["handled"]:
            return design, furniture_report
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

    return _finalize_refinement(design, report)

