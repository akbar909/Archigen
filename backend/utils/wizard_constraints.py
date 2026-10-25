"""Validation and canonicalization for structured Home Wizard submissions."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from utils.architectural_schema_v3 import ft_to_m
from utils.floor_room_program import floor_level


ROOM_TYPE_MAP = {
    "master_bedroom": "master_bedroom",
    "bedroom": "bedroom",
    "bathroom": "bathroom",
    "kitchen": "kitchen",
    "living_room": "living_room",
    "drawing_room": "drawing_room",
    "dining_room": "dining_room",
    "garage": "garage",
    "balcony": "balcony",
    "prayer_room": "prayer_room",
    "study_room": "home_office",
    "laundry_room": "laundry",
    "storage_room": "storage_room",
    "servant_room": "servant_room",
    "garden": "garden",
    "terrace": "terrace",
}


PROMPT_ROOM_ALIASES = {
    "master bedroom": "master_bedroom",
    "bedroom": "bedroom",
    "bathroom": "bathroom",
    "kitchen": "kitchen",
    "living room": "living_room",
    "drawing room": "drawing_room",
    "dining room": "dining_room",
    "garage": "garage",
    "balcony": "balcony",
    "prayer room": "prayer_room",
    "study room": "study_room",
    "home office": "study_room",
    "laundry room": "laundry_room",
    "storage room": "storage_room",
    "servant room": "servant_room",
    "terrace": "terrace",
}

PROMPT_FEATURE_ALIASES = {
    "front garden": "front_garden",
    "back garden": "back_garden",
    "boundary wall": "boundary_wall",
    "entrance gate": "entrance_gate",
    "main gate": "entrance_gate",
    "car parking": "car_parking",
    "open parking": "car_parking",
    "open parking / carport": "car_parking",
    "carport": "car_parking",
    "swimming pool": "swimming_pool",
    "outdoor seating": "outdoor_seating",
    "exterior lighting": "exterior_lighting",
    "solar panels": "solar_panels",
    # These can also exist as configured rooms. Keeping them as feature flags
    # does not create another room; it only preserves the requested amenity.
    "balcony": "balcony",
    "rooftop terrace": "rooftop_terrace",
    "laundry area": "laundry_area",
}

_COUNT_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _bounded_int(value: Any, *, minimum: int, maximum: int, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Wizard {label} must be an integer.") from exc
    if result < minimum or result > maximum:
        raise ValueError(f"Wizard {label} must be between {minimum} and {maximum}.")
    return result


def _positive_number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Wizard {label} must be a number.") from exc
    if result <= 0:
        raise ValueError(f"Wizard {label} must be greater than zero.")
    return result


def _nonnegative_number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Wizard {label} must be a number.") from exc
    if result < 0:
        raise ValueError(f"Wizard {label} must be zero or greater.")
    return result


def build_wizard_layout_constraints(wizard: Any) -> Dict[str, Any] | None:
    """Convert trusted wizard fields into deterministic layout constraints.

    The prompt remains useful for design language and Gemini styling, but exact
    quantities, levels, and plot dimensions come from this structure.
    """
    if wizard is None:
        return None
    if not isinstance(wizard, dict):
        raise ValueError("Wizard payload must be an object.")

    plot = wizard.get("plot")
    rooms = wizard.get("rooms")
    design = wizard.get("design") if isinstance(wizard.get("design"), dict) else {}
    if not isinstance(plot, dict) or not isinstance(rooms, list):
        raise ValueError("Wizard payload requires plot and rooms fields.")

    floors = _bounded_int(plot.get("floors"), minimum=1, maximum=4, label="floor count")
    width = _positive_number(plot.get("width"), "plot width")
    depth = _positive_number(plot.get("length"), "plot length")
    unit = str(plot.get("unit", "ft")).strip().lower()
    if unit not in {"ft", "m"}:
        raise ValueError("Wizard plot unit must be 'ft' or 'm'.")
    if unit == "ft":
        width, depth = ft_to_m(width), ft_to_m(depth)

    raw_setbacks = plot.get("setbacks") if isinstance(plot.get("setbacks"), dict) else {}
    setbacks: Dict[str, float] = {}
    for source_key, target_key in (("front", "front"), ("rear", "back"), ("left", "left"), ("right", "right")):
        raw_value = raw_setbacks.get(source_key)
        if raw_value in (None, ""):
            continue
        value = _nonnegative_number(raw_value, f"{source_key} setback")
        setbacks[target_key] = ft_to_m(value) if unit == "ft" else round(value, 3)

    if setbacks.get("left", 0) + setbacks.get("right", 0) >= width:
        raise ValueError("Wizard left and right setbacks leave no buildable plot width.")
    if setbacks.get("front", 0) + setbacks.get("back", 0) >= depth:
        raise ValueError("Wizard front and rear setbacks leave no buildable plot depth.")

    coverage = None
    if plot.get("coverage") not in (None, ""):
        coverage = _positive_number(plot.get("coverage"), "maximum coverage")
        if coverage > 100:
            raise ValueError("Wizard maximum coverage must be between 1 and 100 percent.")

    requested_rooms: List[Dict[str, Any]] = []
    room_counts: Dict[str, int] = {}
    floor_room_counts: Dict[int, Dict[str, int]] = {}
    type_ordinals: Dict[str, int] = {}
    attached_baths = 0
    required_connections: List[List[str]] = []

    def append_room(
        room_type: str, level: int, name: str, source: Dict[str, Any]
    ) -> Dict[str, Any]:
        type_ordinals[room_type] = type_ordinals.get(room_type, 0) + 1
        ordinal = type_ordinals[room_type]
        requested_room = {
            "id": f"wizard_{room_type}_f{level}_{ordinal:02d}",
            "type": room_type,
            "name": name if ordinal == 1 else f"{name} {ordinal}",
            "floor": level,
            "strict_floor": True,
            "preferred_size": source.get("preferredSize", "medium"),
            "preferred_location": source.get("preferredLocation", "no_preference"),
            "notes": str(source.get("notes", ""))[:300],
        }
        requested_rooms.append(requested_room)
        room_counts[room_type] = room_counts.get(room_type, 0) + 1
        level_counts = floor_room_counts.setdefault(level, {})
        level_counts[room_type] = level_counts.get(room_type, 0) + 1
        return requested_room

    if len(rooms) > 32:
        raise ValueError("Wizard supports at most 32 configured room groups.")
    for room in rooms:
        if not isinstance(room, dict):
            raise ValueError("Every wizard room must be an object.")
        raw_type = str(room.get("type", "")).strip().lower()
        room_type = ROOM_TYPE_MAP.get(raw_type)
        if not room_type:
            raise ValueError(f"Unsupported wizard room type '{raw_type}'.")
        count = _bounded_int(room.get("count", 1), minimum=1, maximum=10, label=f"{raw_type} count")
        level = _bounded_int(room.get("floor", 0), minimum=0, maximum=floors - 1, label=f"{raw_type} floor")
        label = raw_type.replace("_", " ").title()
        for _ in range(count):
            primary = append_room(room_type, level, label, room)
            if room.get("attachedBathroom") and room_type in {
                "bedroom", "master_bedroom", "servant_room"
            }:
                bath_type = "master_bathroom" if room_type == "master_bedroom" else "bathroom"
                bath_label = "Master Ensuite" if bath_type == "master_bathroom" else "Ensuite Bathroom"
                ensuite = append_room(bath_type, level, bath_label, room)
                # Preserve instance-level ownership. A generic
                # bedroom->bathroom preference cannot distinguish three
                # separate bedroom suites and previously allowed bath-to-bath
                # doors.
                primary["ensuite_id"] = ensuite["id"]
                ensuite["ensuite_for_room_id"] = primary["id"]
                ensuite["access"] = "ensuite_only"
                required_connections.append([primary["id"], ensuite["id"]])
                attached_baths += 1

    if not requested_rooms:
        raise ValueError("Wizard requires at least one room.")
    occupied_levels = {int(room["floor"]) for room in requested_rooms}
    missing_levels = [level for level in range(floors) if level not in occupied_levels]
    if missing_levels:
        labels = ", ".join("ground floor" if value == 0 else f"floor {value}" for value in missing_levels)
        raise ValueError(f"Assign at least one room to every requested floor; missing {labels}.")

    # Multi-storey homes require dedicated vertical circulation. Model it as a
    # system-generated lobby on every level so the aligned stair never consumes
    # a bedroom, dining area, or kitchen work zone.
    if floors > 1:
        for level in range(floors):
            append_room(
                "stair_lobby",
                level,
                "Stair Lobby",
                {"preferredSize": "medium", "notes": "Reserved vertical circulation"},
            )

    orientation = str(plot.get("orientation", "north")).strip().lower()
    if orientation not in {"north", "south", "east", "west"}:
        orientation = "north"

    raw_style = str(design.get("architecturalStyle", "modern")).strip().lower()
    style = {
        "traditional": "classic",
        "luxury": "contemporary",
    }.get(raw_style, raw_style)
    raw_roof = str(design.get("roofType", "flat")).strip().lower()
    roof_type = {"pitched": "gable"}.get(raw_roof, raw_roof)

    raw_features = wizard.get("features") if isinstance(wizard.get("features"), dict) else {}
    features = {str(key): bool(value) for key, value in raw_features.items()}
    feature_configs = (
        wizard.get("featureConfigs")
        if isinstance(wizard.get("featureConfigs"), dict)
        else {}
    )

    road_access = str(plot.get("roadAccess", "front")).strip().lower()
    if road_access not in {"front", "left", "right", "front_and_side"}:
        road_access = "front"

    return {
        "source": "home_wizard",
        "floors_count": floors,
        "floors_explicit": True,
        "replace_room_program": True,
        "strict_room_program": True,
        "floor_room_counts": floor_room_counts,
        "room_counts": room_counts,
        "requested_rooms": requested_rooms,
        "attached_baths": attached_baths,
        "connections": [],
        "required_connections": required_connections,
        "plot": {"width": round(width, 3), "depth": round(depth, 3)},
        "setbacks": setbacks,
        "max_coverage": coverage,
        "orientation": orientation,
        "road_access": road_access,
        "building_type": str(plot.get("buildingType", "house")).strip().lower(),
        "style": style,
        "roof_type": roof_type,
        "design_preferences": {
            "exterior_color": str(design.get("exteriorColor", "white")).strip().lower(),
            "wall_material": str(design.get("wallMaterial", "plaster")).strip().lower(),
            "interior_style": str(design.get("interiorStyle", "contemporary")).strip().lower(),
            "flooring_material": str(design.get("flooringMaterial", "tile")).strip().lower(),
            "furniture": str(design.get("furniture", "fully_furnished")).strip().lower(),
            "design_priority": str(design.get("designPriority", "balanced")).strip().lower(),
            "budget": str(design.get("budget", "standard")).strip().lower(),
        },
        "features": features,
        "feature_configs": feature_configs,
        "special_requirements": str(wizard.get("specialRequirements", ""))[:1000],
    }


def _prompt_field(prompt: str, label: str) -> str | None:
    match = re.search(
        rf"\b{re.escape(label)}\s*:\s*([^\.\r\n]+)",
        prompt,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _prompt_slug(value: str | None, default: str) -> str:
    if not value:
        return default
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_") or default


def build_prompt_layout_constraints(prompt: Any) -> Dict[str, Any] | None:
    """Parse the complete, machine-readable prompt emitted by Home Wizard.

    This deliberately requires plot dimensions, an explicit floor count, and
    several floor-assigned room clauses. Ordinary conversational prompts still
    use Gemini; a complete wizard-style sentence gets the same deterministic
    layout semantics as the structured wizard payload, even when it is pasted
    into the chat input or sent by an older frontend.
    """
    text = re.sub(r"\s+", " ", str(prompt or "")).strip()
    if not text or "rooms:" not in text.lower():
        return None

    plot_match = re.search(
        r"\bon\s+a\s+(?P<width>\d+(?:\.\d+)?)\s*[x×]\s*"
        r"(?P<depth>\d+(?:\.\d+)?)\s*(?P<unit>feet|foot|ft|meters?|metres?|m)\b",
        text,
        re.IGNORECASE,
    )
    floors_match = re.search(
        r"\b(?P<count>[1-4])\s+floors?\s+total\b",
        text,
        re.IGNORECASE,
    )
    if not plot_match or not floors_match:
        return None

    floors = int(floors_match.group("count"))
    unit_text = plot_match.group("unit").lower()
    unit = "m" if unit_text.startswith(("m", "met")) else "ft"
    building_match = re.search(r"\bdesign\s+a[n]?\s+([a-z][a-z -]*?)\s+on\s+a\s+\d", text, re.IGNORECASE)
    orientation_match = re.search(r"\b(north|south|east|west)[ -]facing\s+plot\b", text, re.IGNORECASE)
    road_match = re.search(r"\broad\s+access\s+from\s+([a-z_ &]+?)(?:\.|;)\s", text, re.IGNORECASE)

    setbacks: Dict[str, str] = {}
    setback_match = re.search(
        r"\bsetbacks?\s*:\s*(.*?)(?:\.\s*(?:(?:maximum|max)\s+coverage|rooms?|architectural style)\s*:)",
        text,
        re.IGNORECASE,
    )
    if setback_match:
        for key, value in re.findall(
            r"\b(front|rear|left|right)\s*:\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|m|meters?|metres?)?",
            setback_match.group(1),
            re.IGNORECASE,
        ):
            setbacks[key.lower()] = value

    rooms_match = re.search(
        r"\brooms?\s*:\s*(.*?)(?=\.\s*architectural\s+style\s*:)",
        text,
        re.IGNORECASE,
    )
    if not rooms_match:
        return None

    room_names = sorted(PROMPT_ROOM_ALIASES, key=len, reverse=True)
    room_token = "|".join(re.escape(name) for name in room_names)
    count_token = r"a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+"
    clauses = re.split(
        rf",\s*(?=(?:{count_token})\s+(?:{room_token})s?\b)",
        rooms_match.group(1),
        flags=re.IGNORECASE,
    )
    floor_token = (
        r"ground\s+floor|first\s+floor|second\s+floor|third\s+floor|"
        r"[0-3](?:st|nd|rd|th)?\s+floor|floor\s*[0-3]"
    )
    room_pattern = re.compile(
        rf"^\s*(?P<count>{count_token})\s+(?P<room>{room_token})s?\s+"
        rf"on\s+(?P<floor>{floor_token})\b(?P<details>.*)$",
        re.IGNORECASE,
    )
    rooms: List[Dict[str, Any]] = []
    for clause in clauses:
        match = room_pattern.match(clause.strip().rstrip("."))
        if not match:
            continue
        raw_count = match.group("count").lower()
        count = int(raw_count) if raw_count.isdigit() else _COUNT_WORDS.get(raw_count, 1)
        level = floor_level(match.group("floor"))
        if level is None or level >= floors:
            return None
        details = match.group("details").lower()
        size_match = re.search(r"\b(small|medium|large)\b", details)
        location_match = re.search(r"\bat\s+(front|back|left|right)\b", details)
        room = {
            "type": PROMPT_ROOM_ALIASES[match.group("room").lower()],
            "count": count,
            "floor": level,
            "preferredSize": size_match.group(1) if size_match else "medium",
            "preferredLocation": location_match.group(1) if location_match else "no_preference",
        }
        if re.search(r"\b(?:with\s+)?attached\s+(?:bathroom|bath|washroom)|\ben[ -]?suite\b", details):
            room["attachedBathroom"] = True
        rooms.append(room)

    # Requiring several recognized clauses makes false positives in normal chat
    # very unlikely and prevents silently accepting a partially parsed program.
    if len(rooms) < 4 or {room["floor"] for room in rooms} != set(range(floors)):
        return None

    coverage_match = re.search(
        r"\b(?:maximum|max)\s+coverage\s*:\s*(\d+(?:\.\d+)?)\s*%?",
        text,
        re.IGNORECASE,
    )
    plot: Dict[str, Any] = {
        "width": plot_match.group("width"),
        "length": plot_match.group("depth"),
        "unit": unit,
        "floors": floors,
        "buildingType": _prompt_slug(building_match.group(1) if building_match else None, "house"),
        "orientation": orientation_match.group(1).lower() if orientation_match else "north",
        "roadAccess": _prompt_slug(road_match.group(1) if road_match else None, "front"),
        "setbacks": setbacks,
    }
    if coverage_match:
        plot["coverage"] = coverage_match.group(1)

    design = {
        "architecturalStyle": _prompt_slug(_prompt_field(text, "Architectural style"), "modern"),
        "roofType": _prompt_slug(_prompt_field(text, "Roof"), "flat").removesuffix("_roof"),
        "exteriorColor": _prompt_slug(_prompt_field(text, "Exterior color"), "white"),
        "wallMaterial": _prompt_slug(_prompt_field(text, "Wall material"), "plaster"),
        "interiorStyle": _prompt_slug(_prompt_field(text, "Interior style"), "contemporary"),
        "flooringMaterial": _prompt_slug(_prompt_field(text, "Flooring"), "tile"),
        "furniture": _prompt_slug(_prompt_field(text, "Furniture"), "fully_furnished"),
        "designPriority": _prompt_slug(_prompt_field(text, "Design priority"), "balanced"),
        "budget": _prompt_slug(_prompt_field(text, "Budget"), "standard"),
    }

    features: Dict[str, bool] = {}
    feature_configs: Dict[str, Any] = {}
    feature_match = re.search(
        r"\badditional\s+features\s*:\s*(.*?)(?=\.\s*(?:special\s+requirements\s*:|$)|$)",
        text,
        re.IGNORECASE,
    )
    if feature_match:
        for raw_feature in feature_match.group(1).split(","):
            clean = re.sub(r"\s*\([^)]*\)\s*$", "", raw_feature).strip().lower()
            feature_id = PROMPT_FEATURE_ALIASES.get(clean)
            if not feature_id:
                continue
            features[feature_id] = True
            if feature_id == "car_parking":
                spaces_match = re.search(r"(\d+)\s*vehicles?", raw_feature, re.IGNORECASE)
                if spaces_match:
                    feature_configs[feature_id] = {"parkingSpaces": int(spaces_match.group(1))}

    special = _prompt_field(text, "Special requirements") or ""
    wizard = {
        "plot": plot,
        "rooms": rooms,
        "design": design,
        "features": features,
        "featureConfigs": feature_configs,
        "specialRequirements": special,
    }
    constraints = build_wizard_layout_constraints(wizard)
    if constraints is not None:
        constraints["source"] = "structured_prompt"
    return constraints
