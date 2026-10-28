"""Helpers for deterministic architectural snapshot versioning."""

from __future__ import annotations

import copy
from typing import Any


ENTITY_GROUPS = ("rooms", "walls", "doors", "windows", "furniture")
TRANSIENT_DESIGN_KEYS = {"approved_at", "glb_url", "layout_approved", "model_url"}


def prepare_design_snapshot(design: dict[str, Any]) -> dict[str, Any]:
    """Return an independent, editable snapshot without stale synthesis state."""
    snapshot = copy.deepcopy(design)
    snapshot["layout_approved"] = False
    for key in TRANSIENT_DESIGN_KEYS - {"layout_approved"}:
        snapshot.pop(key, None)
    return snapshot


def _entity_key(entity: dict[str, Any], index: int, context: str) -> str:
    identity = entity.get("id") or entity.get("name") or entity.get("type") or index
    return f"{context}:{identity}"


def _collect_entities(design: dict[str, Any] | None, group: str) -> dict[str, dict[str, Any]]:
    if not isinstance(design, dict):
        return {}

    entities: dict[str, dict[str, Any]] = {}

    def add_items(items: Any, context: str) -> None:
        if not isinstance(items, list):
            return
        for index, item in enumerate(items):
            if isinstance(item, dict):
                entities[_entity_key(item, index, context)] = item

    floors = design.get("floors")
    has_floor_entities = False
    if isinstance(floors, list):
        for floor_index, floor in enumerate(floors):
            if not isinstance(floor, dict):
                continue
            floor_id = floor.get("id") or floor.get("level") or floor_index
            if isinstance(floor.get(group), list) and floor.get(group):
                has_floor_entities = True
            add_items(floor.get(group), f"floor:{floor_id}")

            if group == "furniture":
                rooms = floor.get("rooms")
                if isinstance(rooms, list):
                    for room_index, room in enumerate(rooms):
                        if not isinstance(room, dict):
                            continue
                        room_id = room.get("id") or room.get("name") or room_index
                        if isinstance(room.get("furniture"), list) and room.get("furniture"):
                            has_floor_entities = True
                        add_items(room.get("furniture"), f"floor:{floor_id}:room:{room_id}")

    if not has_floor_entities:
        add_items(design.get(group), "root")

    if group == "furniture" and not has_floor_entities:
        rooms = design.get("rooms")
        if isinstance(rooms, list):
            for room_index, room in enumerate(rooms):
                if not isinstance(room, dict):
                    continue
                room_id = room.get("id") or room.get("name") or room_index
                add_items(room.get("furniture"), f"root:room:{room_id}")

    return entities


def summarize_design_changes(
    previous_design: dict[str, Any] | None,
    next_design: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a compact semantic summary suitable for version-history badges."""
    summary: dict[str, Any] = {}
    total = 0

    for group in ENTITY_GROUPS:
        before = _collect_entities(previous_design, group)
        after = _collect_entities(next_design, group)
        before_keys = set(before)
        after_keys = set(after)
        added = len(after_keys - before_keys)
        removed = len(before_keys - after_keys)
        modified = sum(before[key] != after[key] for key in before_keys & after_keys)
        summary[group] = {
            "added": added,
            "removed": removed,
            "modified": modified,
        }
        total += added + removed + modified

    previous_root = {
        key: value
        for key, value in (previous_design or {}).items()
        if key not in TRANSIENT_DESIGN_KEYS and key not in ENTITY_GROUPS and key != "floors"
    }
    next_root = {
        key: value
        for key, value in (next_design or {}).items()
        if key not in TRANSIENT_DESIGN_KEYS and key not in ENTITY_GROUPS and key != "floors"
    }
    def floor_metadata(design: dict[str, Any] | None) -> list[dict[str, Any]]:
        floors = (design or {}).get("floors")
        if not isinstance(floors, list):
            return []
        return [
            {key: value for key, value in floor.items() if key not in ENTITY_GROUPS}
            for floor in floors
            if isinstance(floor, dict)
        ]

    summary["metadata_changed"] = (
        previous_root != next_root
        or floor_metadata(previous_design) != floor_metadata(next_design)
    )
    if summary["metadata_changed"]:
        total += 1
    summary["total"] = total
    return summary
