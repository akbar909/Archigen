"""Public dispatcher for deterministic architectural refinements."""

from utils.refinement_common import *
from utils.refinement_resize import *
from utils.refinement_validation import *
from utils.refinement_style import *
from utils.refinement_furniture import *

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

