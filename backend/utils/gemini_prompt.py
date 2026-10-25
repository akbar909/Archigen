"""Prompt interpretation and generation instructions for architectural requests."""

import re
from typing import Any

from utils.floor_room_program import aggregate_floor_room_counts, parse_floor_room_counts


def infer_layout_constraints(prompt: str) -> dict[str, Any]:
    """Infer room counts, attached bathrooms, and layout constraints from the prompt."""
    # Only the current user instruction is authoritative.  Generation prompts
    # may also contain a serialized previous design; parsing that JSON used to
    # re-introduce rooms that the user had explicitly removed.
    prompt_text = str(prompt or "").split("[DESIGN SPECIFICATION]", 1)[0]
    prompt_text = prompt_text.split("Current design JSON:", 1)[0]
    prompt_lower = prompt_text.lower().strip()
    constraints: dict[str, Any] = {
        "room_counts": {},
        "attached_baths": 0,
        "connections": [],
        "preferred_style": None,
        "single_room": False,
        "open_plan": False,
        "replace_room_program": False,
        "main_gate": False,
        "bedroom_type": "bedroom",
        "floors_explicit": False,
        "floor_room_counts": {},
    }

    # Word to digit mapping
    num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}

    # Detect architectural style
    style_aliases = {
        "modern": "modern", "minimalist": "minimalist", "minimal": "minimalist",
        "contemporary": "contemporary", "classic": "classic", "industrial": "industrial",
        "biophilic": "biophilic", "coastal": "coastal", "scandinavian": "scandinavian",
        "mediterranean": "mediterranean", "cozy": "cozy",
    }
    for style in sorted(style_aliases, key=len, reverse=True):
        if style in prompt_lower:
            constraints["preferred_style"] = style_aliases[style]
            break

    # Extract bedrooms / general rooms
    bed_match = re.search(
        r"\b(one|two|three|four|five|six|\d+)\s*[- ]?(?:(master|guest)\s+)?(bedroom|bedrom|bed|br|room)s?\b",
        prompt_lower,
    )
    if bed_match:
        val = bed_match.group(1)
        count = num_map.get(val, int(val) if val.isdigit() else 1)
        constraints["room_counts"]["bedroom"] = count
        if bed_match.group(2):
            constraints["bedroom_type"] = (
                "master_bedroom" if bed_match.group(2) == "master" else "guest_room"
            )

    # Extract bathrooms / washrooms
    bath_match = re.search(r"\b(one|two|three|four|five|six|\d+)\s*[- ]?(attached\s+)?(washroom|washrom|bathroom|bath|toilet|wash\s*room)s?\b", prompt_lower)
    if bath_match:
        val = bath_match.group(1)
        count = num_map.get(val, int(val) if val.isdigit() else 1)
        constraints["room_counts"]["bathroom"] = count
        if bath_match.group(2):
            constraints["attached_baths"] = count

    # Attachment is opt-in. Merely mentioning a bedroom and bathroom must not
    # silently turn the shared bathroom into an ensuite.
    if re.search(r"\b(?:attached\s+(?:bathroom|bath|washroom|toilet)|en[ -]?suite)\b", prompt_lower):
        constraints["attached_baths"] = max(
            1,
            constraints["room_counts"].get("bathroom", 1),
        )

    # Kitchen (including common typos like kichten, kitchn)
    if any(kw in prompt_lower for kw in ["kitchen", "kichten", "kitchn", "kitch"]):
        k_match = re.search(r"\b(one|two|\d+)\s*(?:kitchen|kichten|kitchn|kitch)s?\b", prompt_lower)
        constraints["room_counts"]["kitchen"] = num_map.get(k_match.group(1), 1) if k_match else 1

    # Living room / lounge
    if any(kw in prompt_lower for kw in ["living", "lounge", "hall", "sitting"]):
        constraints["room_counts"]["living_room"] = 1

    # Dining room
    if any(kw in prompt_lower for kw in ["dining", "dinner"]):
        constraints["room_counts"]["dining_room"] = 1

    # Garage / Carport / Parking
    if any(kw in prompt_lower for kw in ["garage", "carport", "parking", "car porch"]):
        constraints["room_counts"]["garage"] = 1

    constraints["main_gate"] = bool(
        re.search(r"\b(?:main|entrance|entry|front)\s+gate\b", prompt_lower)
        or re.search(r"\bgated\s+entrance\b", prompt_lower)
    )

    # Home Office / Study
    if any(kw in prompt_lower for kw in ["office", "study", "workspace", "library"]):
        constraints["room_counts"]["home_office"] = 1

    # Detect open plan
    if any(kw in prompt_lower for kw in ["loft", "open living", "open-plan", "open plan"]):
        constraints["open_plan"] = True

    # Preserve explicit circulation edits during regeneration. Normalize common
    # phrasings into unordered room-type pairs for the deterministic door solver.
    room_aliases = {
        "bedroom": "bedroom", "bed room": "bedroom", "master bedroom": "master_bedroom",
        "bathroom": "bathroom", "bath room": "bathroom", "washroom": "bathroom",
        "kitchen": "kitchen", "living room": "living_room", "living": "living_room",
        "lounge": "living_room", "dining room": "dining_room", "dining": "dining_room",
        "corridor": "corridor", "hallway": "corridor", "foyer": "foyer", "garage": "garage",
    }
    alias_pattern = "|".join(sorted((re.escape(value) for value in room_aliases), key=len, reverse=True))
    connection_patterns = (
        rf"\b({alias_pattern})\b[^.;]*?\b(?:door|connected|connect|access|opens?)\b[^.;]*?\b(?:to|with|between|into|and)\b[^.;]*?\b({alias_pattern})\b",
        rf"\bdoor\b[^.;]*?\bbetween\b[^.;]*?\b({alias_pattern})\b[^.;]*?\b(?:and|with)\b[^.;]*?\b({alias_pattern})\b",
    )
    connections = []
    for pattern in connection_patterns:
        for match in re.finditer(pattern, prompt_lower):
            first = room_aliases.get(match.group(1), match.group(1).replace(" ", "_"))
            second = room_aliases.get(match.group(2), match.group(2).replace(" ", "_"))
            if first != second and [first, second] not in connections and [second, first] not in connections:
                connections.append([first, second])
    if constraints["attached_baths"] > 0 and not any(
        "bathroom" in pair and any("bedroom" in value for value in pair) for pair in connections
    ):
        connections.append(["bedroom", "bathroom"])
    constraints["connections"] = connections

    floor_room_counts = parse_floor_room_counts(prompt_text)
    if floor_room_counts:
        constraints["floor_room_counts"] = floor_room_counts
        constraints["room_counts"].update(aggregate_floor_room_counts(floor_room_counts))

    # Multi-floor / Story detection
    floor_match = re.search(r"\b(one|two|three|four|\d+)\s*[- ]?(story|storey|floor|level)s?\b", prompt_lower)
    if floor_room_counts:
        constraints["floors_count"] = max(floor_room_counts) + 1
        constraints["floors_explicit"] = True
    elif floor_match:
        fval = floor_match.group(1)
        constraints["floors_count"] = num_map.get(fval, int(fval) if fval.isdigit() else 1)
        constraints["floors_explicit"] = True
    elif any(kw in prompt_lower for kw in ["duplex", "double story", "double storey", "two-story", "two story"]):
        constraints["floors_count"] = 2
        constraints["floors_explicit"] = True
    else:
        # If total bedrooms >= 3 or total rooms >= 6 and not explicitly single floor, default to 2 floors for proper spacious zoning
        total_rooms_hint = sum(constraints["room_counts"].values())
        if total_rooms_hint >= 6 and "single story" not in prompt_lower and "single-story" not in prompt_lower and "ground only" not in prompt_lower:
            constraints["floors_count"] = 2
        else:
            constraints["floors_count"] = 1

    # Detect single room intent: STRICTLY when exactly 1 room category is requested and no secondary spaces
    total_distinct_rooms = sum(constraints["room_counts"].values())
    has_bathroom_mention = any(kw in prompt_lower for kw in ["bathroom", "washroom", "toilet", "bath", "wash room", "powder"])
    has_room_mention = any(kw in prompt_lower for kw in ["bedroom", "bed room", "room", "living", "kitchen", "studio", "hall"])
    has_multi_kw = sum(1 for kw in ["bedroom", "kitchen", "living", "bathroom", "washroom", "dining", "office", "garage", "room"] if kw in prompt_lower) > 1
    has_conjunction = any(w in prompt_lower for w in [" and ", " & ", " with ", " plus ", ",", "along with"])

    # If both bedroom/room and bathroom are in the prompt, it is definitely a multi-room layout
    if has_room_mention and has_bathroom_mention:
        constraints["single_room"] = False
        constraints["room_counts"].setdefault("bedroom", 1)
        constraints["room_counts"].setdefault("bathroom", 1)
    elif total_distinct_rooms == 1 and not has_multi_kw and not has_conjunction:
        single_room_keywords = [
            "single room", "one room", "1 room", "just a room", "only a room",
            "single bedroom", "studio apartment", "master bedroom", "luxury bedroom",
            "a bedroom", "a kitchen", "a living room", "just bedroom", "only bedroom", "just 1 room"
        ]
        if any(kw in prompt_lower for kw in single_room_keywords):
            constraints["single_room"] = True
    elif total_distinct_rooms == 0:
        # Fallback keyword check if no explicit counts matched
        single_room_keywords = [
            "single room", "one room", "1 room", "just a room", "only a room",
            "single bedroom", "studio apartment", "a bedroom", "just bedroom", "only bedroom"
        ]
        if any(kw in prompt_lower for kw in single_room_keywords) and not has_bathroom_mention and not has_conjunction:
            constraints["single_room"] = True
            constraints["room_counts"]["bedroom"] = 1

    # A complete design request replaces the previous room program.  Small
    # refinement instructions (remove a window, connect two rooms, etc.) do not.
    design_action = bool(re.search(
        r"\b(?:create|design|generate|build|plan|draw|give me|i want|i need)\b",
        prompt_lower,
    ))
    complete_home_noun = bool(re.search(
        r"\b(?:house|home|villa|apartment|flat|floor\s*plan|layout)\b",
        prompt_lower,
    ))
    constraints["replace_room_program"] = bool(
        floor_room_counts
        or
        constraints["single_room"]
        or (
            constraints["room_counts"]
            and design_action
            and (len(constraints["room_counts"]) >= 2 or complete_home_noun)
        )
    )

    return constraints


def build_generation_prompt(user_prompt: str, style: str = "modern", base_design: dict[str, Any] | None = None) -> str:
    """Create a tightly constrained generation prompt from the user request."""
    constraints = infer_layout_constraints(user_prompt)
    hints = []

    room_counts = constraints["room_counts"]
    if constraints["single_room"]:
        hints.append("Generate EXACTLY ONE SINGLE ROOM centered at x: 0, z: 0 with 4-6 furniture items from the asset catalog, 1 exterior main entrance door on the front perimeter wall, and 2 exterior windows.")
    else:
        parts = []
        if room_counts.get("bedroom"):
            bedroom_label = constraints.get("bedroom_type", "bedroom").replace("_", " ").title()
            parts.append(f"{room_counts['bedroom']} {bedroom_label}(s)")
        if room_counts.get("bathroom"):
            attached_note = f" ({constraints['attached_baths']} attached to bedroom)" if constraints["attached_baths"] > 0 else ""
            parts.append(f"{room_counts['bathroom']} Bathroom(s){attached_note}")
        if room_counts.get("kitchen"):
            parts.append(f"{room_counts['kitchen']} Kitchen")
        if room_counts.get("living_room"):
            parts.append("1 Living Room")
        if room_counts.get("dining_room"):
            parts.append("1 Dining Room")
        if room_counts.get("home_office"):
            parts.append("1 Home Office")
        if room_counts.get("garage"):
            parts.append("1 Garage")

        if parts:
            hints.append(f"Required rooms: {', '.join(parts)}.")
            if constraints["replace_room_program"]:
                hints.append("EXACT ROOM PROGRAM: Use exactly the requested room categories and counts. Bedroom, master bedroom, and guest bedroom all count toward the same total bedroom count. Do not add unrequested rooms.")
            if constraints["attached_baths"] > 0:
                hints.append("CRITICAL: Position each attached bathroom directly adjacent to its bedroom with a connecting door between them on their shared partition wall.")
            hints.append("CRITICAL ARCHITECTURE: Design a cohesive, contiguous home where rooms share common partition walls edge-to-edge with zero gaps. Include an exterior entrance door on the front wall and windows on perimeter walls.")

        if constraints.get("floor_room_counts"):
            floor_labels = {0: "ground floor", 1: "first floor", 2: "second floor", 3: "third floor"}
            assignments = []
            for level, counts in sorted(constraints["floor_room_counts"].items()):
                rooms = ", ".join(f"{count} {room_type.replace('_', ' ')}" for room_type, count in counts.items())
                assignments.append(f"{floor_labels.get(level, f'floor {level}')}: {rooms}")
            hints.append("STRICT PER-FLOOR PROGRAM: " + "; ".join(assignments) + ". Do not move these rooms to another floor.")

    if constraints["main_gate"]:
        hints.append("Include a visible vehicle entrance gate on the front plot boundary aligned with the driveway or car parking entrance.")

    if constraints["open_plan"]:
        hints.append("Open-plan layout connecting living, dining, and kitchen zones.")

    style_hint = constraints["preferred_style"] or style
    hints.append(f"Architectural style: {style_hint}.")

    if base_design:
        hints.append("Preserve the original room layout and style unless explicit modifications were requested. Modify only what the user asked to change.")

    hint_str = " ".join(hints)
    return f"{user_prompt}\n\n[DESIGN SPECIFICATION]: {hint_str}\nReturn ONLY the completed JSON design object."


def validate_architectural_prompt(prompt: str) -> tuple[bool, str | None]:
    """Validate that a prompt is about architectural/design topics."""
    if not prompt or not isinstance(prompt, str):
        return False, "Prompt cannot be empty"

    prompt_lower = prompt.lower().strip()

    # Reject conversational queries
    rejection_keywords = {
        "how are you", "who are you", "what's your name", "tell me about yourself",
        "hello", "hi ", "hey ", "goodbye", "bye ",
        "what time", "what date", "what's the weather",
        "tell me a joke", "sing a song", "write a poem",
        "calculate", "solve", "math problem",
    }

    for keyword in rejection_keywords:
        if prompt_lower.startswith(keyword) or prompt_lower == keyword.strip():
            return False, "❌ This is not an architectural design request. Please describe a space or house you want to design."

    if len(prompt_lower) < 5:
        return False, "❌ Prompt too short. Please describe what you want to design (e.g., '3 bedroom house with kitchen and living room')."

    return True, None
