"""Room geometry resize refinements."""

from utils.refinement_common import *

def _room_width(room: Dict[str, Any]) -> float:
    dimensions = room.get("dimensions") if isinstance(room.get("dimensions"), dict) else {}
    return float(dimensions.get("width", room.get("width", 0.0)) or 0.0)


def _room_depth(room: Dict[str, Any]) -> float:
    dimensions = room.get("dimensions") if isinstance(room.get("dimensions"), dict) else {}
    return float(dimensions.get("depth", room.get("length", 0.0)) or 0.0)


def _minimum_width(room: Dict[str, Any]) -> float:
    if room.get('_editor_min_width') is not None:
        return float(room['_editor_min_width'])
    room_type = _type_group(room.get("type"))
    if room_type == "master_bedroom":
        key = "master_bedroom"
    else:
        key = room_type
    return float(MIN_ROOM_DIMENSIONS.get(key, (1.5, 1.5))[0])


def _edge_donors(
    rooms: List[Dict[str, Any]], target: Dict[str, Any], side: str, tolerance: float = 0.03
) -> List[Dict[str, Any]]:
    """Return rectangular neighbors that can safely yield space to ``target``.

    A donor may cover only part of the target edge (the remainder can be unused
    floor area), but it must not extend beyond the target edge. Shrinking such a
    room would otherwise leave a gap beside a different room outside the edited
    room's span.
    """
    tx = float(target.get("position", {}).get("x", 0.0))
    ty0 = float(target.get("position", {}).get("y", 0.0))
    ty1 = ty0 + _room_depth(target)
    boundary = tx if side == "west" else tx + _room_width(target)
    donors: List[Tuple[float, float, Dict[str, Any]]] = []
    for room in rooms:
        if room is target:
            continue
        rx = float(room.get("position", {}).get("x", 0.0))
        ry0 = float(room.get("position", {}).get("y", 0.0))
        ry1 = ry0 + _room_depth(room)
        donor_edge = rx + _room_width(room) if side == "west" else rx
        if abs(donor_edge - boundary) > tolerance:
            continue
        if ry0 < ty0 - tolerance or ry1 > ty1 + tolerance:
            continue
        start, end = max(ty0, ry0), min(ty1, ry1)
        if end - start > tolerance:
            donors.append((start, end, room))
    return [room for _start, _end, room in sorted(donors, key=lambda row: (row[0], row[1]))]


def _resize_side_capacity(donors: List[Dict[str, Any]]) -> float:
    if not donors:
        return 0.0
    return max(0.0, min(_room_width(room) - _minimum_width(room) for room in donors))


def _building_horizontal_bounds(design: Dict[str, Any], rooms: List[Dict[str, Any]]) -> Tuple[float, float]:
    building = design.get("building") if isinstance(design.get("building"), dict) else {}
    site = design.get("site") if isinstance(design.get("site"), dict) else {}
    setbacks = site.get("setbacks") if isinstance(site.get("setbacks"), dict) else {}
    natural_left = min(float(room.get("position", {}).get("x", 0.0)) for room in rooms)
    natural_right = max(
        float(room.get("position", {}).get("x", 0.0)) + _room_width(room) for room in rooms
    )
    left = float(setbacks.get("left", natural_left) or natural_left)
    width = float(building.get("width", natural_right - left) or (natural_right - left))
    return left, left + width


def _push_side_capacity(
    donors: List[Dict[str, Any]], side: str, building_bounds: Tuple[float, float]
) -> float:
    if not donors:
        return 0.0
    left, right = building_bounds
    if side == "west":
        return max(0.0, min(float(room.get("position", {}).get("x", 0.0)) - left for room in donors))
    return max(0.0, min(
        right - (float(room.get("position", {}).get("x", 0.0)) + _room_width(room))
        for room in donors
    ))


def _set_room_width(room: Dict[str, Any], width: float) -> None:
    room.setdefault("dimensions", {})["width"] = round(width, 4)
    room["width"] = round(width, 4)


def _rebuild_floor_walls(design: Dict[str, Any], floor: Dict[str, Any]) -> None:
    building = design.get("building") if isinstance(design.get("building"), dict) else {}
    site = design.get("site") if isinstance(design.get("site"), dict) else {}
    setbacks = site.get("setbacks") if isinstance(site.get("setbacks"), dict) else {}
    rooms = floor.get("rooms", [])
    if not rooms:
        return
    min_x = min(float(room.get("position", {}).get("x", 0.0)) for room in rooms)
    min_y = min(float(room.get("position", {}).get("y", 0.0)) for room in rooms)
    max_x = max(float(room.get("position", {}).get("x", 0.0)) + _room_width(room) for room in rooms)
    max_y = max(float(room.get("position", {}).get("y", 0.0)) + _room_depth(room) for room in rooms)
    left = float(setbacks.get("left", min_x) or min_x)
    front = float(setbacks.get("front", min_y) or min_y)
    width = float(building.get("width", max_x - left) or (max_x - left))
    depth = float(building.get("depth", max_y - front) or (max_y - front))
    thickness = float(building.get("wall_thickness", 0.2) or 0.2)
    floor["walls"] = ArchitecturalLayoutEngine(unit="meters")._compute_floor_walls(
        rooms, thickness, left, front, width, depth,
    )


def _apply_room_resize(
    base_design: Dict[str, Any], intent: Dict[str, Any], report: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Expand one room by moving shared walls and borrowing safe donor space."""
    report["handled"] = True
    report["kind"] = "room_resize"
    requested_type = intent["room_type"]
    matches: List[Tuple[int, Dict[str, Any]]] = []
    for floor_index, floor in enumerate(base_design.get("floors", [])):
        if intent.get('floor_id') and str(floor.get('id')) != str(intent['floor_id']):
            continue
        for room in floor.get("rooms", []):
            matches_target = str(room.get('id')) == str(intent['room_id']) if intent.get('room_id') else _room_type_matches(requested_type, room.get("type"))
            if matches_target:
                matches.append((floor_index, room))
    if not matches:
        report["errors"].append(f"No {requested_type.replace('_', ' ')} exists in this layout.")
        return None, report
    if len(matches) > 1:
        report["errors"].append(
            f"More than one {requested_type.replace('_', ' ')} exists. Specify its name or identifier."
        )
        return None, report

    floor_index, target = matches[0]
    rooms = base_design["floors"][floor_index].get("rooms", [])
    current = _room_width(target)
    amount = intent.get("amount")
    if intent.get("mode") == "to" and amount is not None:
        desired = float(amount)
    elif intent.get("mode") == "by" and amount is not None:
        desired = current + float(amount)
    else:
        # With no number, reach the accepted minimum or provide a visible 0.5 m
        # increase when the room is already at/above that minimum.
        desired = max(current + 0.5, _minimum_width(target))
    if desired <= current + 0.01:
        report["errors"].append(
            f"The requested width ({desired:.2f} m) is not greater than the current width ({current:.2f} m)."
        )
        return None, report

    west_donors = _edge_donors(rooms, target, "west")
    east_donors = _edge_donors(rooms, target, "east")
    building_bounds = _building_horizontal_bounds(base_design, rooms)
    west_shrink_capacity = _resize_side_capacity(west_donors)
    east_shrink_capacity = _resize_side_capacity(east_donors)
    west_push_capacity = _push_side_capacity(west_donors, "west", building_bounds)
    east_push_capacity = _push_side_capacity(east_donors, "east", building_bounds)
    west_capacity = max(west_shrink_capacity, west_push_capacity)
    east_capacity = max(east_shrink_capacity, east_push_capacity)
    if intent.get("direction") == "west":
        east_capacity, east_donors = 0.0, []
    elif intent.get("direction") == "east":
        west_capacity, west_donors = 0.0, []

    requested_growth = desired - current
    exact_amount = intent.get("mode") in {"to", "by"}
    available = west_capacity + east_capacity
    maximum_growth = requested_growth if available + 0.001 >= requested_growth else available
    if maximum_growth < 0.10 or (exact_amount and maximum_growth + 0.001 < requested_growth):
        report["errors"].append(
            f"The room needs {requested_growth:.2f} m more width, but adjacent rooms can safely provide "
            f"only {available:.2f} m without falling below their minimum widths."
        )
        return None, report

    growth_values = {round(maximum_growth, 4)}
    if not exact_amount:
        # If the ideal increase cannot validate because a partial-height neighbor
        # blocks one side, still honor an unquantified "make it wider" request
        # with the largest safe increase available on the other side.
        growth_values.update({round(min(west_capacity, requested_growth), 4),
                              round(min(east_capacity, requested_growth), 4)})
        cursor = 0.10
        while cursor <= maximum_growth + 0.001:
            growth_values.add(round(cursor, 4))
            cursor += 0.10

    allocations = []
    for growth in sorted((value for value in growth_values if value >= 0.10), reverse=True):
        low_west = max(0.0, growth - east_capacity)
        high_west = min(west_capacity, growth)
        west_values = {round(low_west, 4), round(high_west, 4)}
        cursor = low_west
        while cursor <= high_west + 0.001:
            west_values.add(round(cursor, 4))
            cursor += 0.10
        allocations.extend((west, growth - west) for west in west_values)
    allocations.sort(key=lambda pair: (
        -(pair[0] + pair[1]),
        int(pair[0] > 0.001) + int(pair[1] > 0.001),
        len(west_donors) * pair[0] + len(east_donors) * pair[1],
        -max(pair),
    ))

    valid_trials: List[Tuple[float, Dict[str, Any], Dict[str, Any], float, float]] = []
    failure_messages: List[str] = []
    target_id = str(target.get("id"))
    west_ids = {str(room.get("id")) for room in west_donors}
    east_ids = {str(room.get("id")) for room in east_donors}
    for west_growth, east_growth in allocations:
        west_modes = ["none"] if west_growth <= 0.001 else []
        east_modes = ["none"] if east_growth <= 0.001 else []
        if west_growth <= west_push_capacity + 0.001:
            west_modes.append("push")
        if west_growth <= west_shrink_capacity + 0.001:
            west_modes.append("shrink")
        if east_growth <= east_push_capacity + 0.001:
            east_modes.append("push")
        if east_growth <= east_shrink_capacity + 0.001:
            east_modes.append("shrink")
        for west_mode, east_mode in itertools.product(west_modes, east_modes):
            trial = copy.deepcopy(base_design)
            floor = trial["floors"][floor_index]
            room_map = {str(room.get("id")): room for room in floor.get("rooms", [])}
            trial_target = room_map[target_id]
            old_x = float(trial_target.get("position", {}).get("x", 0.0))
            trial_target.setdefault("position", {})["x"] = round(old_x - west_growth, 4)
            _set_room_width(trial_target, current + west_growth + east_growth)
            for donor_id in west_ids:
                donor = room_map[donor_id]
                if west_mode == "push":
                    donor.setdefault("position", {})["x"] = round(
                        float(donor.get("position", {}).get("x", 0.0)) - west_growth, 4
                    )
                else:
                    _set_room_width(donor, _room_width(donor) - west_growth)
            for donor_id in east_ids:
                donor = room_map[donor_id]
                donor.setdefault("position", {})["x"] = round(
                    float(donor.get("position", {}).get("x", 0.0)) + east_growth, 4
                )
                if east_mode == "shrink":
                    _set_room_width(donor, _room_width(donor) - east_growth)

            _rebuild_floor_walls(trial, floor)
            candidate, validation = validate_and_repair_design(trial, repair=True)
            if validation.get("critical_errors"):
                failure_messages.extend(str(message) for message in validation["critical_errors"])
                continue
            # Prefer the largest safe growth, preserving donor dimensions when
            # translation into unused building area is possible.
            score = (
                -100.0 * (west_growth + east_growth)
                + (len(west_ids) if west_growth > 0.001 else 0)
                + (len(east_ids) if east_growth > 0.001 else 0)
                + 0.25 * int(west_mode == "shrink")
                + 0.25 * int(east_mode == "shrink")
                + 0.01 * len(validation.get("repairs", []))
            )
            valid_trials.append((score, candidate, validation, west_growth, east_growth))

    if not valid_trials:
        detail = failure_messages[0] if failure_messages else "No collision-free wall movement was found."
        report["errors"].append(f"The room width could not be increased safely: {detail}")
        return None, report

    _score, design, validation, west_growth, east_growth = min(valid_trials, key=lambda row: row[0])
    final_width = current + west_growth + east_growth
    changed_neighbors = sorted(
        (west_ids if west_growth > 0.001 else set()) | (east_ids if east_growth > 0.001 else set())
    )
    report["changes"].append(
        f"Increased room '{target_id}' width from {current:.2f} m to {final_width:.2f} m by moving "
        f"shared wall geometry; adjusted adjacent rooms {changed_neighbors}."
    )
    actual_growth = west_growth + east_growth
    if actual_growth + 0.001 < requested_growth:
        report["changes"].append(
            f"Used the maximum safe increase ({actual_growth:.2f} m) available from adjacent rooms."
        )
    report["validation"] = validation
    design.pop("glb_url", None)
    design.pop("approved_at", None)
    design["layout_approved"] = False
    design["refinement"] = report
    return design, report

__all__ = [name for name in globals() if not name.startswith('__')]
