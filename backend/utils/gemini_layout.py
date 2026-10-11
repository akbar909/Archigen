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
from utils.layout_engine import ArchitecturalLayoutEngine


# ─── Prompt Inference ─────────────────────────────────────────────────────────

def infer_layout_constraints(prompt: str) -> dict[str, Any]:
    """Infer room counts, attached bathrooms, and layout constraints from the prompt."""
    prompt_lower = prompt.lower()
    constraints: dict[str, Any] = {
        "room_counts": {},
        "attached_baths": 0,
        "preferred_style": None,
        "single_room": False,
        "open_plan": False,
    }

    # Detect single room intent
    single_room_keywords = [
        "single room", "one room", "1 room", "just a", "only a",
        "single bedroom", "studio apartment", "master bedroom", "luxury bedroom",
        "a bedroom", "a kitchen", "a living room", "a bathroom", "just bedroom", "only bedroom"
    ]
    multi_room_indicators = ["house", "villa", "apartment with", "rooms", "bedrooms", "bathrooms", "washrooms", "and a", ","]
    has_single_kw = any(kw in prompt_lower for kw in single_room_keywords)
    has_multi_kw = sum(1 for kw in ["bedroom", "kitchen", "living", "bathroom", "washroom"] if kw in prompt_lower) > 1

    if has_single_kw and not has_multi_kw:
        constraints["single_room"] = True

    # Detect open plan
    if any(kw in prompt_lower for kw in ["loft", "open living", "open-plan", "open plan"]):
        constraints["open_plan"] = True

    # Detect architectural style
    for style in ("modern", "minimal", "minimalist", "classic", "industrial", "biophilic", "coastal", "scandinavian", "cozy"):
        if style in prompt_lower:
            constraints["preferred_style"] = "minimal" if style == "minimalist" else style
            break

    # Word to digit mapping
    num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}

    # Extract bedrooms / general rooms
    bed_match = re.search(r"\b(one|two|three|four|five|six|\d+)\s*[- ]?(bedroom|bedrom|bed|br|room)s?\b", prompt_lower)
    if bed_match:
        val = bed_match.group(1)
        count = num_map.get(val, int(val) if val.isdigit() else 1)
        constraints["room_counts"]["bedroom"] = count

    # Extract bathrooms / washrooms
    bath_match = re.search(r"\b(one|two|three|four|five|six|\d+)\s*[- ]?(attached\s+)?(washroom|washrom|bathroom|bath|toilet|wash\s*room)s?\b", prompt_lower)
    if bath_match:
        val = bath_match.group(1)
        count = num_map.get(val, int(val) if val.isdigit() else 1)
        constraints["room_counts"]["bathroom"] = count
        if "attached" in prompt_lower:
            constraints["attached_baths"] = count

    # Check for explicit attached washroom phrases
    attached_match = re.search(r"\b(one|two|three|four|five|six|\d+)\s*attached\b", prompt_lower)
    if attached_match and "attached_baths" not in constraints:
        val = attached_match.group(1)
        constraints["attached_baths"] = num_map.get(val, int(val) if val.isdigit() else 1)

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

    # Home Office / Study
    if any(kw in prompt_lower for kw in ["office", "study", "workspace", "library"]):
        constraints["room_counts"]["home_office"] = 1

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

    return constraints


def build_generation_prompt(user_prompt: str, style: str = "modern", base_design: dict[str, Any] | None = None) -> str:
    """Create a tightly constrained generation prompt from the user request."""
    constraints = infer_layout_constraints(user_prompt)
    hints = []

    room_counts = constraints["room_counts"]
    if constraints["single_room"]:
        hints.append("Generate EXACTLY ONE SINGLE ROOM centered at x: 0, z: 0 with 4-6 furniture items from the asset catalog.")
    else:
        parts = []
        if room_counts.get("bedroom"):
            parts.append(f"{room_counts['bedroom']} Bedroom(s)")
        if room_counts.get("bathroom"):
            attached_note = f" ({constraints['attached_baths']} attached to bedroom)" if constraints["attached_baths"] > 0 else ""
            parts.append(f"{room_counts['bathroom']} Bathroom(s){attached_note}")
        if room_counts.get("kitchen"):
            parts.append("1 Kitchen")
        if room_counts.get("living_room"):
            parts.append("1 Living Room")

        if parts:
            hints.append(f"Required rooms: {', '.join(parts)}.")
            if constraints["attached_baths"] > 0:
                hints.append("CRITICAL: Position each attached bathroom directly adjacent to its bedroom with a connecting door between them.")
            hints.append("CRITICAL ARCHITECTURE: Design a cohesive, contiguous home where rooms share common partition walls edge-to-edge with zero gaps.")

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
        rooms[0]["position"] = {"x": 0.0, "y": 0.0, "z": 0.0}
        rooms[0]["floor"] = 0
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

    return design


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

    for f in all_furniture:
        if isinstance(f, dict):
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
    engine = ArchitecturalLayoutEngine()
    design = engine.solve_or_refine_design(design, user_prompt)

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
        validator.validate()
    except Exception as e:
        design["validation"] = {"status": "valid", "errors": [], "warnings": [str(e)]}

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

    # Validate furniture asset names (new format)
    furniture = design.get("furniture", [])
    if isinstance(furniture, list):
        for f in furniture:
            if isinstance(f, dict) and "asset" in f:
                asset = f["asset"]
                # Allow staircase as a special case
                if asset not in VALID_FURNITURE_ASSETS and asset != "staircase":
                    errors.append(f"Unknown furniture asset: '{asset}'. Valid: {', '.join(VALID_FURNITURE_ASSETS)}")

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

