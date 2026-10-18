"""Deterministic room additions and removals for an existing canonical design."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.architectural_preflight import validate_and_repair_design
from utils.floor_room_program import floor_level, parse_floor_room_counts
from utils.layout_engine import ArchitecturalLayoutEngine


ROOM_NAMES = {
    "master bedroom": "master_bedroom",
    "guest bedroom": "bedroom",
    "bed room": "bedroom",
    "bedroom": "bedroom",
    "wash room": "bathroom",
    "washroom": "bathroom",
    "bath room": "bathroom",
    "bathroom": "bathroom",
    "living room": "living_room",
    "lounge": "living_room",
    "kitchen": "kitchen",
    "dining room": "dining_room",
    "home office": "home_office",
    "office": "home_office",
    "study": "home_office",
    "garage": "garage",
    "foyer": "foyer",
    "corridor": "corridor",
    "hallway": "corridor",
    "laundry": "laundry",
}

NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "another": 1,
    "two": 2, "three": 3, "four": 4,
    "1": 1, "2": 2, "3": 3, "4": 4,
}

ROOM_PATTERN = "|".join(sorted((re.escape(name) for name in ROOM_NAMES), key=len, reverse=True))
MUTATION_RE = re.compile(
    rf"\b(?P<action>add|include|insert|create|remove|delete)\s+"
    rf"(?:(?P<count>a|an|one|two|three|four|[1-4])\s+)?"
    rf"(?:(?:new|more|additional)\s+)?(?P<room>{ROOM_PATTERN})s?\b",
    re.IGNORECASE,
)


def _floor_level_from_prompt(prompt: str, floor_count: int) -> Optional[int]:
    text = prompt.lower()
    named = (
        (r"\bground(?:\s+floor|\s+level)?\b", 0),
        (r"\bfirst(?:\s+floor|\s+level|\s+storey|\s+story)\b", 1),
        (r"\bsecond(?:\s+floor|\s+level|\s+storey|\s+story)\b", 2),
        (r"\bthird(?:\s+floor|\s+level|\s+storey|\s+story)\b", 3),
    )
    for pattern, level in named:
        if re.search(pattern, text):
            return min(level, floor_count - 1)
    numeric = re.search(r"\b(?:floor|level)\s*([0-3])\b", text)
    if numeric:
        return min(int(numeric.group(1)), floor_count - 1)
    return None


def parse_room_program_mutations(prompt: str, floor_count: int) -> List[Dict[str, Any]]:
    """Parse explicit room additions/removals without treating locator rooms as edits."""
    mutations = []
    for match in MUTATION_RE.finditer(prompt):
        action = match.group("action").lower()
        room_type = ROOM_NAMES[match.group("room").lower()]
        count = NUMBER_WORDS.get((match.group("count") or "one").lower(), 1)
        tail = prompt[match.end():]
        boundary = re.search(r"\s*(?:,|;|\band\b|&)\s*", tail, re.IGNORECASE)
        clause_tail = tail[:boundary.start()] if boundary else tail
        parsed_level = floor_level(clause_tail)
        target_level = min(parsed_level, floor_count - 1) if parsed_level is not None and floor_count else None
        mutations.append({
            "action": "remove" if action in {"remove", "delete"} else "add",
            "room_type": room_type,
            "count": count,
            "floor_level": target_level,
        })
    return mutations


def _default_level(room_type: str, floors: List[Dict[str, Any]]) -> int:
    if room_type in {"living_room", "kitchen", "dining_room", "garage", "foyer", "laundry"}:
        return 0
    candidates = floors[1:] or floors
    return int(min(candidates, key=lambda floor: len(floor.get("rooms", []))).get("level", 0))


def _unique_room_id(room_type: str, rooms: List[Dict[str, Any]]) -> str:
    existing = {str(room.get("id")) for room in rooms}
    index = 1
    while f"{room_type}_{index:02d}" in existing:
        index += 1
    return f"{room_type}_{index:02d}"


def _copy_finish_language(base_design: Dict[str, Any], generated: Dict[str, Any]) -> None:
    finishes: Dict[str, Dict[str, Any]] = {}
    for floor in base_design.get("floors", []):
        for room in floor.get("rooms", []):
            room_type = str(room.get("type", ""))
            finishes.setdefault(room_type, {
                "materials": copy.deepcopy(room.get("materials", {})),
                "pbr_material": copy.deepcopy(room.get("pbr_material", {})),
            })
    for floor in generated.get("floors", []):
        for room in floor.get("rooms", []):
            finish = finishes.get(str(room.get("type", "")))
            if finish:
                room.update(copy.deepcopy(finish))


def apply_room_program_refinement(
    base_design: Dict[str, Any], prompt: str, report: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Reflow the canonical plan after explicit room additions or removals."""
    floors = base_design.get("floors", [])
    mutations = parse_room_program_mutations(prompt, len(floors))
    floor_assignments = parse_floor_room_counts(prompt)
    exact_assignment = bool(
        floor_assignments
        and not mutations
        and not re.search(r"\b(?:add|include|insert|create|remove|delete)\b", prompt, re.IGNORECASE)
    )
    if not mutations and not exact_assignment:
        return None, report

    report["handled"] = True
    program = []
    for floor_index, floor in enumerate(floors):
        level = int(floor.get("level", floor_index))
        for room in floor.get("rooms", []):
            program.append({
                "id": str(room.get("id")),
                "name": room.get("name") or str(room.get("type", "room")).replace("_", " ").title(),
                "type": str(room.get("type", "room")),
                "floor": level,
            })

    floor_count = len(floors)
    if exact_assignment:
        floor_count = max(floor_count, max(floor_assignments) + 1)
        affected_types = set()
        for counts in floor_assignments.values():
            affected_types.update(counts)

        def room_family(room_type: str) -> str:
            if room_type in {"bedroom", "master_bedroom", "guest_room"}:
                return "bedroom"
            if room_type in {"bathroom", "master_bathroom"}:
                return "bathroom"
            return room_type

        affected_families = {room_family(room_type) for room_type in affected_types}
        program = [room for room in program if room_family(room["type"]) not in affected_families]
        for level, counts in sorted(floor_assignments.items()):
            for room_type, count in counts.items():
                for _ in range(count):
                    room_id = _unique_room_id(room_type, program)
                    program.append({
                        "id": room_id,
                        "name": room_type.replace("_", " ").title(),
                        "type": room_type,
                        "floor": level,
                        "strict_floor": True,
                    })
                    report["changes"].append(
                        f"Set room '{room_id}' on floor level {level} and reflowed the exact floor program."
                    )

    for mutation in mutations:
        room_type = mutation["room_type"]
        target_level = mutation["floor_level"]
        if target_level is None:
            target_level = _default_level(room_type, floors)
        if mutation["action"] == "add":
            for _ in range(mutation["count"]):
                room_id = _unique_room_id(room_type, program)
                program.append({
                    "id": room_id,
                    "name": room_type.replace("_", " ").title(),
                    "type": room_type,
                    "floor": target_level,
                })
                report["changes"].append(
                    f"Added room '{room_id}' to floor level {target_level} and reflowed that room program safely."
                )
        else:
            matches = [
                room for room in reversed(program)
                if room["type"] == room_type
                and (mutation["floor_level"] is None or room["floor"] == target_level)
            ]
            if len(matches) < mutation["count"]:
                report["errors"].append(
                    f"Cannot remove {mutation['count']} {room_type.replace('_', ' ')} room(s); only {len(matches)} match."
                )
                return None, report
            for room in matches[:mutation["count"]]:
                program.remove(room)
                report["changes"].append(
                    f"Removed room '{room['id']}' from floor level {room['floor']} and reflowed that room program safely."
                )

    if any(not any(room["floor"] == level for room in program) for level in range(floor_count)):
        report["errors"].append("The edit would leave a requested floor without any usable room.")
        return None, report

    site = base_design.get("site", {})
    plot = site.get("plot", {})
    building = base_design.get("building", {})
    requirements = {
        "project_name": base_design.get("project", {}).get("name") or base_design.get("project_name", "ArchiGen Home"),
        "style": base_design.get("style") or base_design.get("project", {}).get("style") or "modern",
        "orientation": site.get("road", {}).get("side", "south"),
        "plot": {
            "width": float(plot.get("width", building.get("width", 14.0))),
            "depth": float(plot.get("depth", building.get("depth", 18.0))),
        },
        "floors": floor_count,
        "rooms": program,
        "strict_room_program": True,
        "strict_floor_program": exact_assignment,
        "roof_type": base_design.get("roof", {}).get("type", "parapet"),
    }

    try:
        generated = ArchitecturalLayoutEngine(unit="meters").generate_layout(requirements)
        _copy_finish_language(base_design, generated)
        generated, validation = validate_and_repair_design(generated, repair=True)
    except (TypeError, ValueError) as exc:
        report["errors"].append(str(exc))
        return None, report
    if validation["critical_errors"]:
        report["errors"].extend(validation["critical_errors"])
        return None, report

    generated.pop("glb_url", None)
    generated.pop("approved_at", None)
    generated["layout_approved"] = False
    report["layout_preserved"] = False
    report["scope"] = "room_program_reflow"
    generated["refinement"] = report
    return generated, report
