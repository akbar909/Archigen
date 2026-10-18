"""Furniture-conflict validation repairs with locked geometry."""

from utils.refinement_common import *

def _layout_geometry_view(design: Dict[str, Any]) -> Dict[str, Any]:
    """Return only fields a validation repair is forbidden to change."""
    room_keys = ("id", "name", "type", "position", "dimensions", "width", "length", "height", "floor")
    opening_keys = (
        "id", "type", "room_id", "roomId", "wall_id", "wall_side", "wall", "position",
        "offset", "width", "height", "sill_height", "swing", "hinge_side", "connected_room_ids",
    )

    def selected(value: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
        return {key: copy.deepcopy(value.get(key)) for key in keys if key in value}

    floors = []
    for floor in design.get("floors", []):
        floors.append({
            "id": floor.get("id"),
            "level": floor.get("level"),
            "elevation": floor.get("elevation"),
            "floor_height": floor.get("floor_height"),
            "rooms": [selected(room, room_keys) for room in floor.get("rooms", [])],
            "walls": copy.deepcopy(floor.get("walls", [])),
            "doors": [selected(door, opening_keys) for door in floor.get("doors", [])],
            "windows": [selected(window, opening_keys) for window in floor.get("windows", [])],
            "stairs": copy.deepcopy(floor.get("stairs", [])),
        })
    return {
        "site": copy.deepcopy(design.get("site")),
        "building": copy.deepcopy(design.get("building")),
        "roof": copy.deepcopy(design.get("roof")),
        "exterior": copy.deepcopy(design.get("exterior")),
        "floors": floors,
    }


def _furniture_category(item: Dict[str, Any]) -> str:
    explicit = str(item.get("category") or item.get("asset") or item.get("type") or "")
    explicit = explicit.lower().strip().replace("-", "_").replace(" ", "_")
    if explicit in COMPACT_FURNITURE_DIMENSIONS:
        return explicit
    text = " ".join(
        str(item.get(key, "")).lower().replace("-", "_")
        for key in ("category", "asset", "asset_id", "type", "id")
    )
    for category in sorted(COMPACT_FURNITURE_DIMENSIONS, key=len, reverse=True):
        if category in text:
            return category
    return explicit


def _compact_conflicting_items(design: Dict[str, Any], item_ids: set[str]) -> bool:
    changed = False
    for floor in design.get("floors", []):
        for item in floor.get("furniture", []):
            if str(item.get("id")) not in item_ids:
                continue
            compact = COMPACT_FURNITURE_DIMENSIONS.get(_furniture_category(item))
            dimensions = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else {}
            if not compact or not dimensions:
                continue
            for axis, minimum in compact.items():
                current = float(dimensions.get(axis, minimum))
                replacement = min(current, minimum)
                if replacement < current - 0.001:
                    dimensions[axis] = replacement
                    changed = True
    return changed


def _furniture_change_score(before: Dict[str, Any], after: Dict[str, Any], target_ids: set[str]) -> float:
    before_items = {
        str(item.get("id")): item
        for floor in before.get("floors", []) for item in floor.get("furniture", [])
    }
    score = 0.0
    after_ids = {
        str(item.get("id"))
        for floor in after.get("floors", []) for item in floor.get("furniture", [])
    }
    # Removing an optional item is a last resort after movement, rotation, and
    # compact variants.  A large penalty guarantees that any complete-furniture
    # solution wins even when it moves farther.
    score += 20.0 * len(set(before_items) - after_ids)
    for floor in after.get("floors", []):
        for item in floor.get("furniture", []):
            fid = str(item.get("id"))
            old = before_items.get(fid, {})
            old_pos, new_pos = old.get("position", {}), item.get("position", {})
            score += abs(float(new_pos.get("x", 0)) - float(old_pos.get("x", 0)))
            score += abs(float(new_pos.get("y", 0)) - float(old_pos.get("y", 0)))
            if float(item.get("rotation", 0)) % 360 != float(old.get("rotation", 0)) % 360:
                score += 0.35
            if item.get("dimensions") != old.get("dimensions"):
                score += 1.5 if fid in target_ids else 5.0
    return score


def _apply_validation_repair(
    base_design: Dict[str, Any], prompt: str, report: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Repair active furniture conflicts while treating all layout geometry as immutable."""
    requested_type = _requested_room_type(prompt)
    _checked, validation = validate_and_repair_design(base_design, repair=True)
    conflict_rows = []
    for message in validation.get("critical_errors", []):
        match = FURNITURE_CONFLICT_RE.search(str(message))
        if match:
            conflict_rows.append((match.group("item"), match.group("room"), str(message)))

    room_lookup = {
        str(room.get("id")): room
        for floor in base_design.get("floors", []) for room in floor.get("rooms", [])
    }
    relevant = [
        row for row in conflict_rows
        if row[1] in room_lookup and _room_type_matches(requested_type, room_lookup[row[1]].get("type"))
    ]
    report["handled"] = True
    report["kind"] = "validation_repair"
    if not relevant:
        room_label = requested_type.replace("_", " ") if requested_type else "requested area"
        report["errors"].append(
            f"No active furniture-fit conflict was found for the {room_label}."
        )
        return None, report

    target_ids = {item_id for item_id, _room_id, _message in relevant}
    target_room_ids = {room_id for _item_id, room_id, _message in relevant}
    locked_geometry = _layout_geometry_view(base_design)
    trials: List[Tuple[float, Dict[str, Any], Dict[str, Any]]] = []

    # Search furniture processing orders because the validator places items
    # greedily.  Large/conflicting objects get first choice, then the smaller
    # furniture is fitted around them.  Cap permutations to keep runtime bounded.
    room_orders: Dict[str, List[Tuple[str, ...]]] = {}
    for room_id in target_room_ids:
        items = [
            item for floor in base_design.get("floors", []) for item in floor.get("furniture", [])
            if str(item.get("room_id") or item.get("roomId")) == room_id
        ]
        ids = [str(item.get("id")) for item in items]
        prioritized = tuple(sorted(
            ids,
            key=lambda fid: (0 if fid in target_ids else 1, ids.index(fid)),
        ))
        orders = [prioritized]
        if len(ids) <= 6:
            orders.extend(order for order in itertools.permutations(ids) if order != prioritized)
        room_orders[room_id] = orders[:120]

    order_products = list(itertools.product(
        *(room_orders[room_id] for room_id in sorted(room_orders))
    ))
    target_rotations = {}
    for floor in base_design.get("floors", []):
        for item in floor.get("furniture", []):
            fid = str(item.get("id"))
            if fid in target_ids:
                current = float(item.get("rotation", 0.0)) % 360.0
                target_rotations[fid] = (current, (current + 90.0) % 360.0)
    rotation_products = list(itertools.product(
        *(target_rotations[fid] for fid in sorted(target_rotations))
    )) or [tuple()]

    optional_ids = []
    for floor in base_design.get("floors", []):
        for item in floor.get("furniture", []):
            room_id = str(item.get("room_id") or item.get("roomId"))
            if (
                room_id in target_room_ids
                and str(item.get("id")) not in target_ids
                and _furniture_category(item) in OPTIONAL_FURNITURE_CATEGORIES
            ):
                optional_ids.append(str(item.get("id")))
    # Keep all objects first. If impossible, remove the fewest optional objects,
    # in stable order, never essential furniture or fixtures.
    removal_choices: List[Tuple[str, ...]] = [tuple()]
    for count in range(1, min(2, len(optional_ids)) + 1):
        removal_choices.extend(itertools.combinations(sorted(optional_ids), count))

    for removed_ids_tuple in removal_choices:
        removed_ids = set(removed_ids_tuple)
        for order_choice in order_products:
            order_by_room = dict(zip(sorted(room_orders), order_choice))
            for compact_targets in (False, True):
                for rotation_choice in rotation_products:
                    trial = copy.deepcopy(base_design)
                    if compact_targets and not _compact_conflicting_items(trial, target_ids):
                        continue
                    rotations_by_id = dict(zip(sorted(target_rotations), rotation_choice))
                    for floor in trial.get("floors", []):
                        original_items = [
                            item for item in floor.get("furniture", [])
                            if str(item.get("id")) not in removed_ids
                        ]
                        for item in original_items:
                            fid = str(item.get("id"))
                            if fid in rotations_by_id:
                                item["rotation"] = rotations_by_id[fid]
                        target_room_items = {
                            room_id: {
                                str(item.get("id")): item for item in original_items
                                if str(item.get("room_id") or item.get("roomId")) == room_id
                            }
                            for room_id in target_room_ids
                        }
                        unaffected = [
                            item for item in original_items
                            if str(item.get("room_id") or item.get("roomId")) not in target_room_ids
                        ]
                        reordered = list(unaffected)
                        for room_id in sorted(target_room_ids):
                            indexed = target_room_items[room_id]
                            reordered.extend(
                                indexed[fid] for fid in order_by_room[room_id] if fid in indexed
                            )
                        floor["furniture"] = reordered

                    candidate, candidate_validation = validate_and_repair_design(trial, repair=True)
                    if candidate_validation.get("critical_errors"):
                        continue
                    if _layout_geometry_view(candidate) != locked_geometry:
                        continue
                    score = _furniture_change_score(base_design, candidate, target_ids)
                    trials.append((score, candidate, candidate_validation))
        # Choices are ordered by removal count. Once this choice yields valid
        # candidates, later choices would remove the same or more furniture.
        if trials:
            break

    if not trials:
        report["errors"].append(
            "The furniture conflict cannot be resolved without changing locked layout geometry "
            "or removing essential furniture. Permit a room-layout change to continue."
        )
        return None, report

    _score, design, candidate_validation = min(trials, key=lambda value: value[0])
    before_items = {
        str(item.get("id")): item
        for floor in base_design.get("floors", []) for item in floor.get("furniture", [])
    }
    after_ids = {
        str(item.get("id"))
        for floor in design.get("floors", []) for item in floor.get("furniture", [])
    }
    for removed_id in sorted(set(before_items) - after_ids):
        removed = before_items[removed_id]
        report["changes"].append(
            f"Removed optional furniture '{removed_id}' from room "
            f"'{removed.get('room_id') or removed.get('roomId')}' because no collision-free "
            "arrangement could retain it."
        )
    for floor in design.get("floors", []):
        for item in floor.get("furniture", []):
            fid = str(item.get("id"))
            old = before_items.get(fid)
            if old and (
                item.get("position") != old.get("position")
                or item.get("rotation") != old.get("rotation")
                or item.get("dimensions") != old.get("dimensions")
            ):
                report["changes"].append(
                    f"Adjusted furniture '{fid}' in room '{item.get('room_id') or item.get('roomId')}' "
                    "to resolve the validation conflict."
                )
    report["validation"] = candidate_validation
    design.pop("glb_url", None)
    design.pop("approved_at", None)
    design["layout_approved"] = False
    design["refinement"] = report
    return design, report

__all__ = [name for name in globals() if not name.startswith('__')]
