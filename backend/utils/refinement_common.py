"""Deterministic edits applied to an existing canonical architectural version.

Small structural refinements must not be sent through whole-house generation:
doing so lets an LLM rewrite the plot, room dimensions, furniture, and unrelated
openings.  This module recognizes supported targeted operations and changes only
the addressed canonical object before running the shared architectural preflight.
"""

from __future__ import annotations

import copy
import itertools
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.architectural_preflight import WALL_MARGIN, validate_and_repair_design
from utils.architectural_schema_v3 import MIN_ROOM_DIMENSIONS
from utils.layout_engine import ArchitecturalLayoutEngine
from utils.room_program_refinement import apply_room_program_refinement


ROOM_ALIASES = {
    "master bedroom": "master_bedroom",
    "bed room": "bedroom",
    "bedroom": "bedroom",
    "sleeping room": "bedroom",
    "wash room": "bathroom",
    "washroom": "bathroom",
    "bath room": "bathroom",
    "bathroom": "bathroom",
    "living room": "living_room",
    "living": "living_room",
    "lounge": "living_room",
    "kitchen": "kitchen",
    "dining room": "dining_room",
    "dining": "dining_room",
    "corridor": "corridor",
    "hallway": "corridor",
    "foyer": "foyer",
    "garage": "garage",
}


ROOM_RESIZE_VERBS_RE = re.compile(
    r"\b(?:increase|expand|enlarge|extend|grow|widen|broaden|resize|make|give)\b",
    re.IGNORECASE,
)

ROOM_RESIZE_SMALLER_RE = re.compile(
    r"\b(?:decrease|reduce|shrink|narrow|smaller|less\s+(?:wide|deep|space))\b",
    re.IGNORECASE,
)


STYLE_ALIASES = {
    "modern": "modern",
    "contemporary": "contemporary",
    "minimal": "minimalist",
    "minimalist": "minimalist",
    "scandinavian": "scandinavian",
    "industrial": "industrial",
    "classic": "classic",
    "coastal": "coastal",
    "biophilic": "biophilic",
    "mediterranean": "mediterranean",
    "cozy": "cozy",
}

# These presets deliberately contain finishes only.  A style refinement must
# never use the layout engine, because repacking an approved design can change
# rooms, openings, circulation, and site geometry.  The "signature" preset is
# used for feedback such as "that is not unique style": it keeps the selected
# architectural family while making the material language visibly distinctive.
STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "modern": {
        "walls": {"pattern": "plain", "color": "#EEEAE2"},
        "public_floor": {"pattern": "marble_tile", "color": "#D9D1C3"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#8A6748"},
        "wet_floor": {"pattern": "hex_tile", "color": "#777C80"},
        "garage_floor": {"pattern": "concrete", "color": "#777A7D"},
        "accent": {"side": "back", "pattern": "wood_panel", "color": "#7B5438"},
    },
    "minimalist": {
        "walls": {"pattern": "plain", "color": "#F2EFE8"},
        "public_floor": {"pattern": "marble_tile", "color": "#DDD4C5"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#927458"},
        "wet_floor": {"pattern": "hex_tile", "color": "#85898B"},
        "garage_floor": {"pattern": "concrete", "color": "#858585"},
        "accent": {"side": "back", "pattern": "wood_panel", "color": "#806044"},
    },
    "contemporary": {
        "walls": {"pattern": "plain", "color": "#E9E5DD"},
        "public_floor": {"pattern": "marble_tile", "color": "#CFC7B9"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#73543B"},
        "wet_floor": {"pattern": "diamond_tile", "color": "#686D70"},
        "garage_floor": {"pattern": "concrete", "color": "#666A6D"},
        "accent": {"side": "back", "pattern": "brick", "color": "#A47D60"},
    },
    "industrial": {
        "walls": {"pattern": "brick", "color": "#806B5B"},
        "public_floor": {"pattern": "concrete", "color": "#6E7071"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#594536"},
        "wet_floor": {"pattern": "hex_tile", "color": "#4F5558"},
        "garage_floor": {"pattern": "concrete", "color": "#55595B"},
        "accent": {"side": "back", "pattern": "concrete", "color": "#3F4345"},
    },
    "scandinavian": {
        "walls": {"pattern": "plain", "color": "#F5F3ED"},
        "public_floor": {"pattern": "wood_planks", "color": "#C8AA7A"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#C2A276"},
        "wet_floor": {"pattern": "hex_tile", "color": "#AEB6B7"},
        "garage_floor": {"pattern": "concrete", "color": "#92999A"},
        "accent": {"side": "back", "pattern": "wood_panel", "color": "#A98358"},
    },
    "biophilic": {
        "walls": {"pattern": "plain", "color": "#E7E9DD"},
        "public_floor": {"pattern": "wood_planks", "color": "#8B704E"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#806548"},
        "wet_floor": {"pattern": "hex_tile", "color": "#758078"},
        "garage_floor": {"pattern": "concrete", "color": "#747974"},
        "accent": {"side": "back", "pattern": "wood_panel", "color": "#667255"},
    },
    "coastal": {
        "walls": {"pattern": "plain", "color": "#F1F4F1"},
        "public_floor": {"pattern": "wood_planks", "color": "#C9B38E"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#C2AA83"},
        "wet_floor": {"pattern": "hex_tile", "color": "#8FA8AD"},
        "garage_floor": {"pattern": "concrete", "color": "#A0A6A5"},
        "accent": {"side": "back", "pattern": "wood_panel", "color": "#78979B"},
    },
    "classic": {
        "walls": {"pattern": "plain", "color": "#EEE5D5"},
        "public_floor": {"pattern": "marble_tile", "color": "#D8C9AD"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#745139"},
        "wet_floor": {"pattern": "checker_tile", "color": "#8A8176"},
        "garage_floor": {"pattern": "concrete", "color": "#807B74"},
        "accent": {"side": "back", "pattern": "wood_panel", "color": "#6E4933"},
    },
    "mediterranean": {
        "walls": {"pattern": "plain", "color": "#F0DFC4"},
        "public_floor": {"pattern": "diamond_tile", "color": "#C78E63"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#8A5B3D"},
        "wet_floor": {"pattern": "diamond_tile", "color": "#728F92"},
        "garage_floor": {"pattern": "concrete", "color": "#8B8174"},
        "accent": {"side": "back", "pattern": "brick", "color": "#B56F4E"},
    },
    "cozy": {
        "walls": {"pattern": "plain", "color": "#F1E4D2"},
        "public_floor": {"pattern": "wood_planks", "color": "#936A48"},
        "bedroom_floor": {"pattern": "wood_planks", "color": "#80583E"},
        "wet_floor": {"pattern": "hex_tile", "color": "#8B8179"},
        "garage_floor": {"pattern": "concrete", "color": "#7F7A75"},
        "accent": {"side": "back", "pattern": "brick", "color": "#A46F55"},
    },
}

UNIQUE_STYLE_PRESET: Dict[str, Any] = {
    "walls": {"pattern": "brick", "color": "#D8C7AE"},
    "public_floor": {"pattern": "marble_tile", "color": "#D9CFBD"},
    "bedroom_floor": {"pattern": "wood_planks", "color": "#6F4D35"},
    "wet_floor": {"pattern": "hex_tile", "color": "#6E7476"},
    "garage_floor": {"pattern": "concrete", "color": "#686C6E"},
    "accent": {"side": "back", "pattern": "wood_panel", "color": "#72503A"},
}

FURNITURE_CONFLICT_RE = re.compile(
    r"Furniture\s+'(?P<item>[^']+)'\s+cannot fit safely inside room\s+'(?P<room>[^']+)'",
    re.IGNORECASE,
)

# Small but realistic fallback footprints.  These are attempted only after
# position/order/rotation-only repairs fail, and only for the object named by a
# furniture validation conflict.
COMPACT_FURNITURE_DIMENSIONS = {
    "bed": {"width": 1.60, "depth": 2.00},
    "wardrobe": {"width": 1.20, "depth": 0.55},
    "nightstand": {"width": 0.40, "depth": 0.40},
    "sofa": {"width": 1.80, "depth": 0.85},
    "armchair": {"width": 0.75, "depth": 0.75},
    "coffee_table": {"width": 0.85, "depth": 0.50},
    "dining_table": {"width": 1.20, "depth": 0.75},
}

OPTIONAL_FURNITURE_CATEGORIES = {
    "nightstand", "coffee_table", "armchair", "floor_lamp", "dining_chair", "sideboard",
}


def is_explicit_full_redesign(prompt: str) -> bool:
    """Return True only when the user clearly authorizes rebuilding the layout.

    Ordinary follow-ups are edits to the selected version.  Broad generation is
    intentionally opt-in because it can repack rooms and invalidate previously
    approved circulation constraints.
    """
    text = " ".join(str(prompt or "").lower().split())
    return bool(re.search(
        r"\b(?:"
        r"redesign|regenerate|rebuild|recreate"
        r")\b[^.;]{0,60}\b(?:entire|whole|complete|all|layout|floor\s*plan|house|home)\b|"
        r"\b(?:start\s+over|from\s+scratch|brand[ -]?new\s+(?:layout|floor\s*plan|design))\b|"
        r"\b(?:replace|change)\b[^.;]{0,40}\b(?:entire|whole|complete)\b[^.;]{0,40}\b"
        r"(?:layout|floor\s*plan|design)\b|"
        r"\b(?:rearrange|rework)\b[^.;]{0,40}\b(?:all|every|entire|whole)\b[^.;]{0,40}\brooms?\b",
        text,
    ))


def _type_group(value: Any) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    if "bath" in text or "wash" in text or "toilet" in text:
        return "bathroom"
    if "bed" in text:
        return "master_bedroom" if "master" in text else "bedroom"
    if "living" in text or "lounge" in text:
        return "living_room"
    if "kitchen" in text:
        return "kitchen"
    if "dining" in text:
        return "dining_room"
    if "corridor" in text or "hallway" in text:
        return "corridor"
    return text


def _requested_room_type(prompt: str) -> Optional[str]:
    prompt = prompt.lower()
    for alias in sorted(ROOM_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", prompt):
            return ROOM_ALIASES[alias]
    return None


def _mentions_existing_furniture(design: Dict[str, Any], prompt: str) -> bool:
    """Cheap early guard used before the full furniture matcher is imported."""
    text = " ".join(str(prompt or "").lower().replace("_", " ").split())
    synonyms = {
        "wardrobe": ("almari", "almarah", "closet", "cupboard", "wadrobe"),
        "sofa": ("couch", "settee"),
        "refrigerator": ("fridge",),
        "television": ("tv",),
        "nightstand": ("bedside table", "side table"),
        "coffee table": ("center table",),
    }
    for floor in design.get("floors", []):
        for item in floor.get("furniture", []):
            values = {
                " ".join(str(item.get(key, "")).lower().replace("_", " ").split())
                for key in ("category", "asset", "asset_id", "type")
                if item.get(key)
            }
            for value in tuple(values):
                values.update(synonyms.get(value, ()))
            if any(re.search(rf"\b{re.escape(value)}\b", text) for value in values if value):
                return True
    return False


def _is_validation_repair_request(prompt: str, design: Dict[str, Any]) -> bool:
    """Recognize requests to repair the active room/design validation problem."""
    text = " ".join(str(prompt or "").lower().split())
    if not re.search(r"\b(?:fix|repair|resolve|correct|auto[ -]?fix)\b", text):
        return False
    if re.search(r"\b(?:collision|conflict|validation|error|issue|problem|fit|clearance)\b", text):
        return True
    if _requested_room_type(text) and not _mentions_existing_furniture(design, text):
        return True
    # "Fix it" can safely refer to a single active critical conflict.
    stored = design.get("generation_validation") or design.get("validation") or {}
    critical = stored.get("critical_errors", []) if isinstance(stored, dict) else []
    return bool(re.search(r"\b(?:it|this)\b", text) and len(critical) == 1)


def _room_type_matches(requested: Optional[str], actual: Any) -> bool:
    if not requested:
        return True
    actual_group = _type_group(actual)
    if requested == "bedroom":
        return actual_group in {"bedroom", "master_bedroom"}
    return actual_group == requested


def _parse_room_resize_intent(prompt: str) -> Optional[Dict[str, Any]]:
    """Translate varied room-growth wording into one typed resize operation.

    Language interpretation is deliberately separate from geometry mutation.  A
    recognized request produces a small operation; the operation is then solved
    and validated against the current plan instead of regenerating the house.
    """
    text = " ".join(str(prompt or "").lower().replace("â€™", "'").split())
    room_type = _requested_room_type(text)
    if not room_type or ROOM_RESIZE_SMALLER_RE.search(text):
        return None

    growth_language = bool(re.search(
        r"\b(?:increase|expand|enlarge|extend|grow|widen|broaden|wider|broader|"
        r"larger|bigger|more\s+spacious|more\s+(?:(?:horizontal|sideways)\s+)?(?:room|space)|"
        r"extra\s+(?:(?:horizontal|sideways)\s+)?(?:room|space))\b",
        text,
    ))
    width_language = bool(re.search(r"\b(?:width|wide|wider|horizontal(?:ly)?|sideways)\b", text))
    if not growth_language or not ROOM_RESIZE_VERBS_RE.search(text):
        # Natural forms such as "bedroom needs more width" do not contain an
        # imperative verb, but still express an unambiguous growth operation.
        if not re.search(r"\b(?:needs?|should\s+have|could\s+use)\b", text) or not (
            width_language or "more space" in text or "more room" in text
        ):
            return None

    direction = None
    if re.search(r"\b(?:towards?|from|on)\s+(?:the\s+)?(?:left|west)\b", text):
        direction = "west"
    elif re.search(r"\b(?:towards?|from|on)\s+(?:the\s+)?(?:right|east)\b", text):
        direction = "east"

    number = r"(?P<amount>\d+(?:\.\d+)?)"
    unit = r"(?P<unit>m|metres?|meters?|ft|feet|foot)?"
    amount_match = re.search(rf"\bby\s+{number}\s*{unit}\b", text)
    mode = "by" if amount_match else None
    if not amount_match:
        amount_match = re.search(
            rf"\b(?:width|wide)\b[^.;]{{0,24}}?\b(?:to|of|=)\s*{number}\s*{unit}\b",
            text,
        )
        mode = "to" if amount_match else None
    if not amount_match:
        amount_match = re.search(rf"\bto\s+{number}\s*{unit}\s+(?:wide|in\s+width)\b", text)
        mode = "to" if amount_match else None

    amount = None
    if amount_match:
        amount = float(amount_match.group("amount"))
        if str(amount_match.group("unit") or "").lower() in {"ft", "feet", "foot"}:
            amount *= 0.3048

    return {
        "operation": "resize_room",
        "room_type": room_type,
        "axis": "width",
        "mode": mode,
        "amount": amount,
        "direction": direction,
    }

__all__ = [name for name in globals() if not name.startswith('__')]
