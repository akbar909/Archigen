"""
gemini_layout.py
================
Layout inference, architectural snapping, normalization, and validation
for ArchGen's Gemini-generated home designs.
"""

import re
from typing import Any

from jsonschema import ValidationError, validate

from utils.gemini_schema import (
    HOME_DESIGN_SCHEMA,
    VALID_FURNITURE_ASSETS,
    VALID_ROOM_TYPES,
)
from utils.architectural_validator import ArchitecturalValidator
from utils.architectural_preflight import validate_and_repair_design
from utils.layout_engine import ArchitecturalLayoutEngine


# ─── Prompt Inference ─────────────────────────────────────────────────────────

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
    }

    # Word to digit mapping
    num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}

    # Detect architectural style
    for style in ("modern", "minimal", "minimalist", "classic", "industrial", "biophilic", "coastal", "scandinavian", "cozy"):
        if style in prompt_lower:
            constraints["preferred_style"] = "minimal" if style == "minimalist" else style
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

    # Multi-floor / Story detection
    floor_match = re.search(r"\b(one|two|three|\d+)\s*[- ]?(story|storey|floor|level)s?\b", prompt_lower)
    if floor_match:
        fval = floor_match.group(1)
        constraints["floors_count"] = num_map.get(fval, int(fval) if fval.isdigit() else 1)
    elif any(kw in prompt_lower for kw in ["duplex", "double story", "double storey", "two-story", "two story"]):
        constraints["floors_count"] = 2
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


# ─── Layout Snapping & Normalization ──────────────────────────────────────────

def snap_and_pack_architectural_layout(design: dict[str, Any]) -> dict[str, Any]:
    """
    Mathematically packs rooms into a cohesive contiguous architectural building:
    - Eliminates disconnected island gaps (rooms touch edge-to-edge sharing common walls).
    - Attached bathrooms snap flush against their parent bedrooms with zero void.
    - Multi-room houses are organized into Ground Floor (y: 0.0) and Upper Floor (y: 3.2).
    - Adds an architectural staircase connecting Ground to Upper floor.
    - Generates connecting doors between adjacent spaces and exterior sliding glass walls.
    """
    rooms = design.get("rooms", [])
    if not rooms:
        return design

    if len(rooms) == 1:
        single_r = rooms[0]
        lw = float(single_r.get("width") or 8.0)
        ll = float(single_r.get("length") or 7.0)
        single_r["position"] = {"x": 0.0, "y": 0.0, "z": 0.0}
        single_r["floor"] = 0
        single_r["width"] = lw
        single_r["length"] = ll

        rid = single_r.get("id", "room_01")
        design["doors"] = [
            {
                "id": f"door_main_{rid}",
                "roomId": rid,
                "room_id": rid,
                "wall": "front",
                "wall_side": "south",
                "position": {"x": 0.0, "y": 1.05, "z": round(-ll / 2.0, 2)},
                "width": 1.0,
                "height": 2.1,
            }
        ]
        design["windows"] = [
            {
                "id": f"win_{rid}_left",
                "roomId": rid,
                "room_id": rid,
                "wall": "left",
                "wall_side": "west",
                "position": {"x": round(-lw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.8,
                "height": 1.4,
            },
            {
                "id": f"win_{rid}_right",
                "roomId": rid,
                "room_id": rid,
                "wall": "right",
                "wall_side": "east",
                "position": {"x": round(lw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.8,
                "height": 1.4,
            },
        ]
        return design

    # Classify rooms by architectural role
    living_rooms = []
    kitchens = []
    bedrooms = []
    bathrooms = []
    other_rooms = []

    for r in rooms:
        rtype = str(r.get("type", "")).lower()
        if any(k in rtype for k in ["living", "lounge", "great", "family", "drawing"]):
            living_rooms.append(r)
        elif any(k in rtype for k in ["kitchen", "dining", "pantry"]):
            kitchens.append(r)
        elif any(k in rtype for k in ["bath", "wash", "toilet", "powder", "restroom"]):
            bathrooms.append(r)
        elif any(k in rtype for k in ["bed", "guest", "master"]):
            bedrooms.append(r)
        else:
            other_rooms.append(r)

    # Special handling for small 2-room home (e.g., Bedroom + Bathroom)
    if len(rooms) == 2 and not living_rooms:
        main_r = bedrooms[0] if bedrooms else rooms[0]
        second_r = bathrooms[0] if bathrooms else rooms[1]

        mw = float(main_r.get("width") or 7.0)
        ml = float(main_r.get("length") or 7.0)
        sw = float(second_r.get("width") or 3.5)
        sl = float(second_r.get("length") or 3.5)

        main_r["width"] = mw
        main_r["length"] = ml
        main_r["floor"] = 0
        main_r["position"] = {"x": round(-sw / 2.0, 2), "y": 0.0, "z": 0.0}

        second_r["width"] = sw
        second_r["length"] = sl
        second_r["floor"] = 0
        second_r["position"] = {"x": round(mw / 2.0, 2), "y": 0.0, "z": 0.0}

        m_id = main_r.get("id", "bedroom_01")
        s_id = second_r.get("id", "bathroom_01")

        design["doors"] = [
            {
                "id": "door_main_entrance",
                "roomId": m_id,
                "room_id": m_id,
                "wall": "front",
                "wall_side": "south",
                "position": {"x": round(-sw / 2.0, 2), "y": 1.05, "z": round(-ml / 2.0, 2)},
                "width": 1.0,
                "height": 2.1,
            },
            {
                "id": f"door_{m_id}_{s_id}_connect",
                "roomId": s_id,
                "room_id": s_id,
                "wall": "left",
                "wall_side": "west",
                "position": {"x": round((-sw / 2.0 + mw / 2.0) / 2.0, 2), "y": 1.05, "z": 0.0},
                "width": 0.9,
                "height": 2.1,
            },
        ]
        design["windows"] = [
            {
                "id": f"win_{m_id}_left",
                "roomId": m_id,
                "room_id": m_id,
                "wall": "left",
                "wall_side": "west",
                "position": {"x": round(-sw / 2.0 - mw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.8,
                "height": 1.4,
            },
            {
                "id": f"win_{m_id}_front",
                "roomId": m_id,
                "room_id": m_id,
                "wall": "front",
                "wall_side": "south",
                "position": {"x": round(-sw / 2.0, 2), "y": 1.5, "z": round(-ml / 2.0, 2)},
                "width": 1.8,
                "height": 1.4,
            },
            {
                "id": f"win_{s_id}_right",
                "roomId": s_id,
                "room_id": s_id,
                "wall": "right",
                "wall_side": "east",
                "position": {"x": round(mw / 2.0 + sw / 2.0, 2), "y": 1.5, "z": 0.0},
                "width": 1.2,
                "height": 1.2,
            },
        ]
        return design

    # Primary ground floor hub: Living room
    living = living_rooms[0] if living_rooms else rooms[0]
    lw = float(living.get("width") or 9.0)
    ll = float(living.get("length") or 8.0)
    living["width"] = lw
    living["length"] = ll
    living["position"] = {"x": 0.0, "y": 0.0, "z": 0.0}
    living["floor"] = 0

    # 1. Kitchen & Dining: Placed contiguous to Living Room on +X (Right side)
    kw = 6.5
    if kitchens:
        kit = kitchens[0]
        kw = float(kit.get("width") or 6.5)
        kl = float(kit.get("length") or 7.5)
        kit["width"] = kw
        kit["length"] = kl
        kit["position"] = {"x": round(lw / 2.0 + kw / 2.0, 2), "y": 0.0, "z": 0.0}
        kit["floor"] = 0

    # 2. Ground Floor Bedroom 1: Placed contiguous to Living Room on -X (Left side)
    ground_bed = None
    if bedrooms:
        ground_bed = bedrooms[0]
        bw = float(ground_bed.get("width") or 7.0)
        bl = float(ground_bed.get("length") or 7.0)
        ground_bed["width"] = bw
        ground_bed["length"] = bl
        ground_bed["position"] = {"x": round(-(lw / 2.0 + bw / 2.0), 2), "y": 0.0, "z": 0.0}
        ground_bed["floor"] = 0

    # 3. Ground Attached Bathroom: Snapped flush behind Ground Bedroom (-Z)
    if bathrooms and ground_bed:
        ground_bath = bathrooms[0]
        baw = float(ground_bath.get("width") or 4.0)
        bal = float(ground_bath.get("length") or 3.5)
        ground_bath["width"] = baw
        ground_bath["length"] = bal
        gb_pos = ground_bed["position"]
        gb_l = float(ground_bed["length"])
        ground_bath["position"] = {
            "x": gb_pos["x"],
            "y": 0.0,
            "z": round(gb_pos["z"] - (gb_l / 2.0 + bal / 2.0), 2),
        }
        ground_bath["floor"] = 0

    # 4. Master Bedroom Suite: Placed contiguous flush behind Living Room (-Z)
    upper_rooms = []
    if len(bedrooms) > 1:
        master_bed = bedrooms[1]
        mw = float(master_bed.get("width") or 8.0)
        ml = float(master_bed.get("length") or 7.0)
        master_bed["width"] = mw
        master_bed["length"] = ml
        master_bed["position"] = {
            "x": 0.0,
            "y": 0.0,
            "z": round(-(ll / 2.0 + ml / 2.0), 2),
        }
        master_bed["floor"] = 0

        if len(bathrooms) > 1:
            master_bath = bathrooms[1]
            mbw = float(master_bath.get("width") or 4.2)
            mbl = float(master_bath.get("length") or 3.8)
            master_bath["width"] = mbw
            master_bath["length"] = mbl
            master_bath["position"] = {
                "x": round(mw / 2.0 + mbw / 2.0, 2),
                "y": 0.0,
                "z": master_bed["position"]["z"],
            }
            master_bath["floor"] = 0

    # 5. Third Bedroom (if present, placed contiguous on rear wing next to Master Bedroom)
    if len(bedrooms) > 2:
        bed3 = bedrooms[2]
        b3w = float(bed3.get("width") or 6.5)
        b3l = float(bed3.get("length") or 6.5)
        bed3["width"] = b3w
        bed3["length"] = b3l
        mw = float(bedrooms[1].get("width") or 8.0)
        bed3["position"] = {
            "x": round(-(mw / 2.0 + b3w / 2.0), 2),
            "y": 0.0,
            "z": round(-(ll / 2.0 + b3l / 2.0), 2),
        }
        bed3["floor"] = 0

        if len(bathrooms) > 2:
            bath3 = bathrooms[2]
            b3bw = float(bath3.get("width") or 3.8)
            b3bl = float(bath3.get("length") or 3.2)
            bath3["width"] = b3bw
            bath3["length"] = b3bl
            bath3["position"] = {
                "x": bed3["position"]["x"],
                "y": 0.0,
                "z": round(bed3["position"]["z"] - (b3l / 2.0 + b3bl / 2.0), 2),
            }
            bath3["floor"] = 0

    # Handle any remaining other rooms (e.g. Office, Dining)
    for idx, o in enumerate(other_rooms):
        ow = float(o.get("width") or 5.0)
        ol = float(o.get("length") or 5.0)
        o["width"] = ow
        o["length"] = ol
        o["position"] = {"x": round(lw / 2.0 + kw / 2.0, 2), "y": 0.0, "z": round((idx + 1) * 6.0, 2)}
        o["floor"] = 0

    # Ensure connecting staircase exists in Living Room for multi-floor homes
    if upper_rooms:
        # Check both old format (room-level furniture) and new format (top-level furniture)
        living_furniture = living.get("furniture", [])
        top_level_furniture = design.get("furniture", [])
        has_stairs = any(
            f.get("type") in ["staircase", "stairs"] or f.get("asset") in ["staircase", "stairs"]
            for f in living_furniture
        )
        if not has_stairs:
            has_stairs = any(
                (f.get("asset") in ["staircase", "stairs"] and f.get("roomId") == living.get("id"))
                for f in top_level_furniture
            )
        if not has_stairs:
            # Add staircase to top-level furniture if using new format, else to room
            staircase_item = {
                "id": "main_staircase",
                "asset": "staircase",
                "roomId": living.get("id", "living_01"),
                "position": {"x": round(lw / 2.0 - 1.2, 2), "y": 0.0, "z": round(-ll / 2.0 + 2.0, 2)},
                "rotation": 0,
                "scale": 1.0,
            }
            if top_level_furniture is not None and isinstance(top_level_furniture, list):
                top_level_furniture.append(staircase_item)
                design["furniture"] = top_level_furniture
            else:
                # Fallback: add to room-level furniture (old format compat)
                living.setdefault("furniture", []).append({
                    "id": "main_staircase",
                    "type": "staircase",
                    "label": "Architectural Floating Stairs",
                    "position": {"x": round(lw / 2.0 - 1.2, 2), "y": 0.0, "z": round(-ll / 2.0 + 2.0, 2)},
                    "rotation_y": 0,
                    "dimensions": {"w": 1.2, "h": 3.2, "d": 3.8},
                    "color": "#7c5335",
                })

    # Generate clean, accurate doors and windows placed on snapped room wall boundaries
    snapped_doors = []
    snapped_windows = []

    # 1. Main entrance door on Living Room front wall
    snapped_doors.append({
        "id": "door_main_entrance",
        "roomId": living.get("id", "living_01"),
        "wall": "front",
        "position": {"x": round(living["position"]["x"], 2), "y": 1.05, "z": round(living["position"]["z"] - ll / 2.0, 2)},
        "width": 1.0,
        "height": 2.1,
    })

    # 2. Living -> Kitchen connecting passage
    if kitchens:
        snapped_doors.append({
            "id": "door_living_kitchen",
            "roomId": living.get("id", "living_01"),
            "wall": "right",
            "position": {"x": round(lw / 2.0, 2), "y": 1.05, "z": 0.0},
            "width": 1.2,
            "height": 2.1,
        })
        k_pos = kitchens[0]["position"]
        k_w = float(kitchens[0]["width"])
        snapped_windows.append({
            "id": "window_kitchen_ext",
            "roomId": kitchens[0].get("id", "kitchen_01"),
            "wall": "right",
            "position": {"x": round(k_pos["x"] + k_w / 2.0, 2), "y": 1.5, "z": round(k_pos["z"], 2)},
            "width": 1.8,
            "height": 1.4,
        })

    # 3. Living -> Ground Bedroom connecting door & bedroom window
    if ground_bed:
        snapped_doors.append({
            "id": "door_living_bedroom",
            "roomId": living.get("id", "living_01"),
            "wall": "left",
            "position": {"x": round(-lw / 2.0, 2), "y": 1.05, "z": 0.0},
            "width": 0.9,
            "height": 2.1,
        })
        gb_pos = ground_bed["position"]
        gb_w = float(ground_bed["width"])
        snapped_windows.append({
            "id": "window_bedroom_left",
            "roomId": ground_bed.get("id", "bedroom_01"),
            "wall": "left",
            "position": {"x": round(gb_pos["x"] - gb_w / 2.0, 2), "y": 1.5, "z": round(gb_pos["z"], 2)},
            "width": 2.0,
            "height": 1.5,
        })
        if bathrooms:
            snapped_doors.append({
                "id": "door_bed_bath_01",
                "roomId": ground_bed.get("id", "bedroom_01"),
                "wall": "back",
                "position": {"x": round(gb_pos["x"], 2), "y": 1.05, "z": round(gb_pos["z"] - float(ground_bed["length"]) / 2.0, 2)},
                "width": 0.85,
                "height": 2.1,
            })

    # 4. Panoramic living room front windows
    snapped_windows.append({
        "id": "window_living_front_01",
        "roomId": living.get("id", "living_01"),
        "wall": "front",
        "position": {"x": round(living["position"]["x"] + lw / 3.2, 2), "y": 1.5, "z": round(living["position"]["z"] - ll / 2.0, 2)},
        "width": 2.2,
        "height": 1.6,
    })
    snapped_windows.append({
        "id": "window_living_front_02",
        "roomId": living.get("id", "living_01"),
        "wall": "front",
        "position": {"x": round(living["position"]["x"] - lw / 3.2, 2), "y": 1.5, "z": round(living["position"]["z"] - ll / 2.0, 2)},
        "width": 2.2,
        "height": 1.6,
    })

    # 5. Master Suite connecting doors and windows
    if len(bedrooms) > 1:
        snapped_doors.append({
            "id": "door_living_master_bed",
            "roomId": living.get("id", "living_01"),
            "wall": "back",
            "position": {"x": round(living["position"]["x"], 2), "y": 1.05, "z": round(living["position"]["z"] - ll / 2.0, 2)},
            "width": 1.0,
            "height": 2.1,
        })
        m_pos = bedrooms[1]["position"]
        m_l = float(bedrooms[1]["length"])
        snapped_windows.append({
            "id": "window_master_bedroom_back",
            "roomId": bedrooms[1].get("id", "bedroom_02"),
            "wall": "back",
            "position": {"x": round(m_pos["x"], 2), "y": 1.5, "z": round(m_pos["z"] - m_l / 2.0, 2)},
            "width": 2.2,
            "height": 1.5,
        })
        if len(bathrooms) > 1:
            mb_w = float(bedrooms[1]["width"])
            snapped_doors.append({
                "id": "door_master_bed_bath",
                "roomId": bedrooms[1].get("id", "bedroom_02"),
                "wall": "right",
                "position": {"x": round(m_pos["x"] + mb_w / 2.0, 2), "y": 1.05, "z": round(m_pos["z"], 2)},
                "width": 0.85,
                "height": 2.1,
            })

    design["doors"] = snapped_doors
    design["windows"] = snapped_windows

    # Exterior elements metadata for 3D renderer
    design["exterior"] = {
        "pool": {
            "enabled": True,
            "width": 10.5,
            "length": 4.8,
            "depth": 1.6,
            "position": {"x": 2.5, "y": -0.2, "z": round(ll / 2.0 + 5.5, 2)},
        },
        "patio": {
            "enabled": True,
            "width": round(lw + 6.0, 2),
            "length": 4.2,
            "position": {"x": 0.0, "y": 0.0, "z": round(ll / 2.0 + 2.1, 2)},
        },
    }

# ─── Furniture Asset Normalization ───────────────────────────────────────────

FURNITURE_SYNONYMS: dict[str, str] = {
    "shower": "shower",
    "shower_stall": "shower",
    "shower_cabin": "shower",
    "shower_enclosure": "shower",
    "walk_in_shower": "shower",
    "tub": "bathtub",
    "bath": "bathtub",
    "bathtub": "bathtub",
    "jacuzzi": "bathtub",
    "soaking_tub": "bathtub",
    "washbasin": "bathroom_sink",
    "basin": "bathroom_sink",
    "sink": "bathroom_sink",
    "vanity": "bathroom_sink",
    "bathroom_vanity": "bathroom_sink",
    "lavatory": "bathroom_sink",
    "commode": "toilet",
    "wc": "toilet",
    "water_closet": "toilet",
    "toilet_seat": "toilet",
    "couch": "sofa",
    "sectional": "sofa",
    "sofa_3seater": "sofa",
    "chesterfield": "sofa",
    "loveseat": "sofa",
    "tv": "tv_cabinet",
    "tv_unit": "tv_cabinet",
    "tv_stand": "tv_cabinet",
    "television": "tv_cabinet",
    "media_console": "tv_cabinet",
    "entertainment_center": "tv_cabinet",
    "fridge": "refrigerator",
    "freezer": "refrigerator",
    "table": "dining_table",
    "dinner_table": "dining_table",
    "counter": "kitchen_island",
    "kitchen_counter": "kitchen_island",
    "island": "kitchen_island",
    "breakfast_bar": "kitchen_island",
    "cabinet": "kitchen_cabinet",
    "stove": "microwave",
    "oven": "microwave",
    "cooktop": "microwave",
    "closet": "wardrobe",
    "cupboard": "wardrobe",
    "dresser": "wardrobe",
    "wardrobe_closet": "wardrobe",
    "lamp": "floor_lamp",
    "standing_lamp": "floor_lamp",
    "light": "floor_lamp",
    "night_stand": "nightstand",
    "bedside_table": "nightstand",
    "bedside": "nightstand",
    "desk_chair": "chair",
    "office_chair": "chair",
    "arm_chair": "armchair",
    "lounge_chair": "armchair",
    "recliner": "armchair",
    "stairs": "staircase",
    "stairway": "staircase",
    "steps": "staircase",
}

def normalize_furniture_asset(raw_asset: str, room_type: str = "") -> str:
    """Map any LLM raw furniture asset name to a validated canonical catalog asset name."""
    if not raw_asset or not isinstance(raw_asset, str):
        return "chair"

    clean = raw_asset.strip().lower().replace("-", "_").replace(" ", "_")
    valid_set = set(VALID_FURNITURE_ASSETS) | {"staircase", "shower"}

    # 1. Exact match in valid assets
    if clean in valid_set:
        return clean

    # 2. Known synonym dictionary
    if clean in FURNITURE_SYNONYMS:
        syn = FURNITURE_SYNONYMS[clean]
        if syn in valid_set:
            return syn

    # 3. Substring matching
    if "shower" in clean:
        return "shower"
    if "bath" in clean or "tub" in clean:
        return "bathtub"
    if "bed" in clean:
        return "bed"
    if "sofa" in clean or "couch" in clean:
        return "sofa"
    if "toilet" in clean or "commode" in clean or "wc" in clean:
        return "toilet"
    if "sink" in clean or "basin" in clean or "vanity" in clean:
        if "kitchen" in room_type.lower():
            return "kitchen_sink"
        return "bathroom_sink"
    if "lamp" in clean or "light" in clean:
        return "floor_lamp"
    if "tv" in clean:
        return "tv_cabinet"
    if "fridge" in clean or "refrigerator" in clean:
        return "refrigerator"
    if "wardrobe" in clean or "closet" in clean or "cupboard" in clean:
        return "wardrobe"
    if "nightstand" in clean or "bedside" in clean:
        return "nightstand"
    if "desk" in clean:
        return "desk"
    if "chair" in clean:
        return "chair"
    if "table" in clean:
        if "coffee" in clean:
            return "coffee_table"
        return "dining_table"
    if "island" in clean or "counter" in clean:
        return "kitchen_island"
    if "cabinet" in clean:
        return "kitchen_cabinet"
    if "stair" in clean:
        return "staircase"

    # 4. Fallback based on room type
    r_lower = room_type.lower()
    if "bath" in r_lower:
        return "bathroom_sink"
    if "bed" in r_lower:
        return "nightstand"
    if "kitchen" in r_lower:
        return "kitchen_cabinet"
    if "living" in r_lower or "lounge" in r_lower:
        return "armchair"

    return "chair"


def _normalize_design(design: dict[str, Any], user_prompt: str = "") -> dict[str, Any]:
    """Ensure design has all required fields, valid coordinates, and character metadata.
    Supports both old format (room-level furniture/doors/windows) and new format (top-level)."""
    if not isinstance(design, dict):
        return {"style": "modern", "rooms": [], "furniture": [], "doors": [], "windows": []}

    design.setdefault("style", "modern")
    # Support new format house metadata
    if "house" not in design or not isinstance(design["house"], dict):
        design["house"] = {"style": design.get("style", "modern"), "floors": 1, "floorHeight": 3.0}
    else:
        house = design["house"]
        try:
            if "width" in house:
                house["width"] = max(2.0, float(house["width"]))
        except (ValueError, TypeError):
            house["width"] = 12.0
        try:
            if "length" in house:
                house["length"] = max(2.0, float(house["length"]))
        except (ValueError, TypeError):
            house["length"] = 12.0
        try:
            if "floorHeight" in house:
                house["floorHeight"] = max(2.0, min(6.0, float(house["floorHeight"])))
        except (ValueError, TypeError):
            house["floorHeight"] = 3.0
        try:
            if "floors" in house:
                house["floors"] = max(1, min(4, int(house["floors"])))
        except (ValueError, TypeError):
            house["floors"] = 1

    rooms = design.get("rooms", [])
    if not isinstance(rooms, list):
        rooms = []
        design["rooms"] = rooms

    # Collect top-level doors/windows (new format) or aggregate from rooms (old format)
    all_doors = list(design.get("doors", []))
    all_windows = list(design.get("windows", []))
    all_furniture = list(design.get("furniture", []))

    for idx, room in enumerate(rooms):
        if not isinstance(room, dict):
            continue

        room.setdefault("id", f"room_{idx}")
        room.setdefault("type", "Room")

        try:
            room["width"] = max(1.5, float(room.get("width", 8.0)))
        except (ValueError, TypeError):
            room["width"] = 8.0

        try:
            room["length"] = max(1.5, float(room.get("length", 8.0)))
        except (ValueError, TypeError):
            room["length"] = 8.0

        try:
            room["height"] = max(2.0, min(6.0, float(room.get("height", 3.2))))
        except (ValueError, TypeError):
            room["height"] = 3.2

        try:
            room["floor"] = max(0, min(3, int(room.get("floor", 0))))
        except (ValueError, TypeError):
            room["floor"] = 0

        pos = room.setdefault("position", {})
        pos.setdefault("x", float(idx * 9.0))
        pos.setdefault("y", 0.0)
        pos.setdefault("z", 0.0)

        # Normalize materials (support both old pbr_material and new materials format)
        if "materials" not in room and "pbr_material" in room:
            # Convert old format to new
            pbr = room["pbr_material"]
            room["materials"] = {
                "floor": {
                    "color": pbr.get("floor", {}).get("color", "#8B7355"),
                    "pattern": pbr.get("floor", {}).get("pattern", "wood_planks"),
                },
                "walls": {
                    "color": pbr.get("walls", {}).get("color", "#F0EAD6"),
                    "pattern": pbr.get("walls", {}).get("pattern", "plain"),
                },
            }
            if "accent_wall" in pbr:
                room["materials"]["accent_wall"] = {
                    "side": pbr["accent_wall"].get("side", "back"),
                    "color": pbr["accent_wall"].get("color", "#8B3A3A"),
                    "pattern": pbr["accent_wall"].get("pattern", "brick"),
                }
            # Keep old format for backward compat with Three.js preview
        elif "materials" not in room:
            room["materials"] = {
                "floor": {"color": "#8B7355", "pattern": "wood_planks"},
                "walls": {"color": "#F0EAD6", "pattern": "plain"},
            }

        # Also ensure pbr_material exists for backward compat with Three.js preview
        if "pbr_material" not in room:
            mat = room.get("materials", {})
            room["pbr_material"] = {
                "floor": {
                    "color": mat.get("floor", {}).get("color", "#8B7355"),
                    "roughness": 0.4,
                    "metalness": 0.1,
                    "pattern": mat.get("floor", {}).get("pattern", "wood_planks"),
                },
                "walls": {
                    "color": mat.get("walls", {}).get("color", "#F0EAD6"),
                    "roughness": 0.9,
                    "metalness": 0.0,
                    "pattern": mat.get("walls", {}).get("pattern", "plain"),
                },
                "ceiling": {"color": "#FAFAF8", "roughness": 0.95, "metalness": 0.0, "pattern": "plain"},
            }
            if "accent_wall" in mat:
                room["pbr_material"]["accent_wall"] = {
                    "side": mat["accent_wall"].get("side", "back"),
                    "color": mat["accent_wall"].get("color", "#8B3A3A"),
                    "roughness": 0.85,
                    "metalness": 0.0,
                    "pattern": mat["accent_wall"].get("pattern", "brick"),
                }

        # Default lights
        room.setdefault("lights", [{"type": "ceiling", "intensity": 1.5, "color": "#FFE5A0", "position": {"x": 0, "y": 2.8, "z": 0}}])

        # Collect doors and windows from room-level into top-level lists (old format compat)
        room_doors = room.get("doors", [])
        if isinstance(room_doors, list):
            for d in room_doors:
                if isinstance(d, dict) and d not in all_doors:
                    d.setdefault("room_id", room.get("id"))
                    d.setdefault("roomId", room.get("id"))
                    all_doors.append(d)

        room_windows = room.get("windows", [])
        if isinstance(room_windows, list):
            for w in room_windows:
                if isinstance(w, dict) and w not in all_windows:
                    w.setdefault("room_id", room.get("id"))
                    w.setdefault("roomId", room.get("id"))
                    all_windows.append(w)

        # Collect old-format room-level furniture into top-level list
        room_furniture = room.get("furniture", [])
        if isinstance(room_furniture, list):
            for f in room_furniture:
                if isinstance(f, dict):
                    f.setdefault("roomId", room.get("id"))
                    # Only add if not already in top-level (avoid duplicates)
                    f_id = f.get("id")
                    if f_id and not any(tf.get("id") == f_id for tf in all_furniture):
                        all_furniture.append(f)

    room_type_map = {r.get("id"): r.get("type", "") for r in rooms if isinstance(r, dict)}
    for f in all_furniture:
        if isinstance(f, dict):
            if "asset" in f:
                f["asset"] = normalize_furniture_asset(str(f["asset"]), room_type_map.get(f.get("roomId", ""), ""))
            try:
                if "scale" in f:
                    f["scale"] = max(0.1, min(5.0, float(f["scale"])))
                else:
                    f["scale"] = 1.0
            except (ValueError, TypeError):
                f["scale"] = 1.0
            try:
                if "rotation" in f:
                    f["rotation"] = float(f["rotation"])
                else:
                    f["rotation"] = 0.0
            except (ValueError, TypeError):
                f["rotation"] = 0.0

    design["doors"] = all_doors
    design["windows"] = all_windows
    design["furniture"] = all_furniture

    # Deterministically solve architectural layout using ArchitecturalLayoutEngine
    # Gemini/schema-v3 coordinates are canonical metres.  The engine's legacy
    # constructor default is feet, which used to convert an 11 m plot as if it
    # were 11 ft and then silently expand it to its fallback minimum.
    engine = ArchitecturalLayoutEngine(unit="meters")
    design = engine.solve_or_refine_design(design, user_prompt)

    # Floors are the canonical source for both renderers.  Preflight synchronizes
    # compatibility views, repairs safe transform issues, and records any
    # generation-blocking conflict without dropping requested objects.
    design, generation_report = validate_and_repair_design(design, repair=True)

    # Character avatar starting position
    all_rooms = design.get("rooms", [])
    first_room = all_rooms[0] if all_rooms else None
    first_pos = first_room.get("position", {}) if first_room else {}
    design["character"] = {
        "enabled": True,
        "start_position": {
            "x": float(first_pos.get("x", 0.0)),
            "y": 0.0,
            "z": float(first_pos.get("z", first_pos.get("y", 0.0))),
        },
        "start_room": first_room.get("name", "Living Room") if first_room else "Living Room",
        "speed": 3.2,
    }

    # Run 20-Point Architectural Validator
    try:
        validator = ArchitecturalValidator(design)
        _, architectural_report = validator.validate()
        architectural_report["critical_errors"] = list(generation_report["critical_errors"])
        architectural_report["repairs"] = list(generation_report["repairs"])
        architectural_report["inventory"] = dict(generation_report["inventory"])
        if generation_report["critical_errors"]:
            architectural_report["status"] = "invalid"
            architectural_report["errors"] = (
                list(generation_report["critical_errors"]) + architectural_report.get("errors", [])
            )
        design["validation"] = architectural_report
    except Exception as e:
        design["validation"] = {
            "status": generation_report["status"],
            "errors": list(generation_report["critical_errors"]),
            "critical_errors": list(generation_report["critical_errors"]),
            "repairs": list(generation_report["repairs"]),
            "warnings": [f"Architectural validator failed: {e}"],
            "inventory": dict(generation_report["inventory"]),
        }

    return design


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_home_design_schema(design: dict[str, Any], user_prompt: str = "") -> tuple[bool, list[str]]:
    """Validate that design meets the home design schema."""
    errors = []

    if not isinstance(design, dict):
        errors.append("Design must be a dictionary")
        return False, errors

    rooms = design.get("rooms", [])
    if not isinstance(rooms, list) or len(rooms) == 0:
        errors.append("Design must contain at least one room")
        return False, errors

    try:
        validate(instance=design, schema=HOME_DESIGN_SCHEMA)
    except ValidationError as exc:
        errors.append(f"Design schema validation failed: {exc.message}")

    # Validate and normalize furniture asset names (never crash on slight naming variations)
    furniture = design.get("furniture", [])
    valid_assets_set = set(VALID_FURNITURE_ASSETS) | {"staircase", "shower"}
    room_type_map = {r.get("id"): r.get("type", "") for r in rooms if isinstance(r, dict)}
    if isinstance(furniture, list):
        for f in furniture:
            if isinstance(f, dict) and "asset" in f:
                asset = f["asset"]
                if asset not in valid_assets_set:
                    # Sanitize through normalization rather than fatal error
                    f["asset"] = normalize_furniture_asset(str(asset), room_type_map.get(f.get("roomId", ""), ""))

    # Check for duplicate room IDs
    room_ids = [r.get("id") for r in rooms if isinstance(r, dict) and r.get("id")]
    if len(room_ids) != len(set(room_ids)):
        errors.append("Duplicate room IDs detected")

    # Validate furniture roomId references
    room_id_set = set(room_ids)
    for f in furniture:
        if isinstance(f, dict) and "roomId" in f:
            if f["roomId"] not in room_id_set:
                errors.append(f"Furniture '{f.get('id', '?')}' references non-existent room '{f['roomId']}'")

    return len(errors) == 0, errors


snap_and_normalize_architectural_layout = snap_and_pack_architectural_layout
