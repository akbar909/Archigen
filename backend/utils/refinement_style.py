"""Appearance-only architectural refinements."""

from utils.refinement_common import *

def _is_window_removal(prompt: str) -> bool:
    normal = " ".join(prompt.lower().split())
    explicit = re.search(r"\b(?:remove|delete|omit|take\s+out)\b[^.;]{0,80}\bwindow\b", normal)
    # Common dictation/typing error observed in refinement prompts:
    # "room one window from bedroom" means "remove one window ...".
    remove_typo = re.search(r"\broom\s+(?:one|1|a)\s+window\s+from\b", normal)
    return bool(explicit or remove_typo)


def _canonical_style(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    if text in STYLE_ALIASES:
        return STYLE_ALIASES[text]
    for alias in sorted(STYLE_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return STYLE_ALIASES[alias]
    return None


def _explicit_prompt_style(prompt: str) -> Optional[str]:
    text = " ".join(str(prompt or "").lower().split())
    for alias in sorted(STYLE_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return STYLE_ALIASES[alias]
    return None


def _is_style_only_refinement(prompt: str) -> bool:
    """Conservatively recognize appearance edits that must not alter geometry."""
    text = " ".join(str(prompt or "").lower().split())
    appearance_intent = bool(
        _explicit_prompt_style(text)
        or re.search(
            r"\b(?:style|styling|aesthetic|appearance|look|facade|faÃ§ade|elevation|"
            r"palette|finish|finishes|theme|material|materials|color|colour|paint|"
            r"tile|tiles|flooring|brick|timber|wood|marble|porcelain|concrete|"
            r"aluminium|aluminum|frame|frames|unique|distinctive|generic|boring|"
            r"warm|warmer|luxury|luxurious|elegant|bold|neutral|earthy)\b",
            text,
        )
    )
    if not appearance_intent:
        return False

    # Mixed geometry + style instructions need the full architectural path.
    # Keeping this list conservative is intentional: false positives here could
    # silently discard a requested spatial change.
    geometry_intent = bool(re.search(
        r"\b(?:add|remove|delete|omit|move|relocate|reposition|resize|enlarge|"
        r"shrink|expand|reduce|connect|disconnect|separate|swap)\b[^.;]{0,80}\b"
        r"(?:room|bedroom|bathroom|kitchen|living|garage|corridor|door|window|wall|"
        r"entrance|gate|driveway|path|stair|layout|floor|furniture|sofa|bed|table|chair)\b|"
        r"\b(?:layout|floor\s*plan|room\s+position|room\s+size|dimensions?)\b",
        text,
    ))
    return not geometry_intent


def _base_design_style(design: Dict[str, Any]) -> Optional[str]:
    project = design.get("project") if isinstance(design.get("project"), dict) else {}
    house = design.get("house") if isinstance(design.get("house"), dict) else {}
    exterior = design.get("exterior") if isinstance(design.get("exterior"), dict) else {}
    for value in (
        design.get("style"), project.get("style"), house.get("style"),
        exterior.get("facade_style"),
    ):
        style = _canonical_style(value)
        if style:
            return style
    return None


def _floor_finish_for_room(room_type: str, preset: Dict[str, Any]) -> Dict[str, Any]:
    grouped = _type_group(room_type)
    if grouped == "bathroom":
        return copy.deepcopy(preset["wet_floor"])
    if grouped in {"bedroom", "master_bedroom", "guest_room"}:
        return copy.deepcopy(preset["bedroom_floor"])
    if grouped == "garage":
        return copy.deepcopy(preset["garage_floor"])
    return copy.deepcopy(preset["public_floor"])


def _apply_room_finish(room: Dict[str, Any], preset: Dict[str, Any]) -> None:
    materials = room.get("materials") if isinstance(room.get("materials"), dict) else {}
    materials = copy.deepcopy(materials)
    materials["floor"] = _floor_finish_for_room(str(room.get("type", "")), preset)
    materials["walls"] = copy.deepcopy(preset["walls"])
    if _type_group(room.get("type")) in {
        "living_room", "bedroom", "master_bedroom", "dining_room",
    }:
        materials["accent_wall"] = copy.deepcopy(preset["accent"])
    room["materials"] = materials

    # Keep the legacy material view synchronized for the Three.js and Blender
    # adapters without touching any spatial room fields.
    pbr = room.get("pbr_material") if isinstance(room.get("pbr_material"), dict) else {}
    pbr = copy.deepcopy(pbr)
    pbr["floor"] = copy.deepcopy(materials["floor"])
    pbr["walls"] = copy.deepcopy(materials["walls"])
    if "accent_wall" in materials:
        pbr["accent_wall"] = copy.deepcopy(materials["accent_wall"])
    else:
        pbr.pop("accent_wall", None)
    room["pbr_material"] = pbr


def _apply_style_refinement(
    base_design: Dict[str, Any], prompt: str, requested_style: Optional[str], report: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Apply a visual whitelist to a copy of the design; geometry stays byte-for-byte stable."""
    design = copy.deepcopy(base_design)
    explicit_style = _explicit_prompt_style(prompt)
    wants_signature = bool(re.search(
        r"\b(?:unique|distinctive|not\s+(?:unique|distinctive)|too\s+generic|generic|boring)\b",
        prompt.lower(),
    ))
    # Negative/vague feedback should enhance the current design language.  For
    # an explicit "change style" command, the selected UI style remains the
    # fallback when the prompt itself does not name a style.
    target_style = explicit_style or (
        (_base_design_style(base_design) or _canonical_style(requested_style))
        if wants_signature
        else (_canonical_style(requested_style) or _base_design_style(base_design))
    ) or "modern"
    preset = UNIQUE_STYLE_PRESET if wants_signature else STYLE_PRESETS.get(target_style, STYLE_PRESETS["modern"])
    concept = f"signature_{target_style}" if wants_signature else target_style

    design["style"] = target_style
    if isinstance(design.get("project"), dict):
        design["project"]["style"] = target_style
    if isinstance(design.get("house"), dict):
        design["house"]["style"] = target_style

    building = design.setdefault("building", {})
    building["wall_style"] = copy.deepcopy(preset["walls"])
    exterior = design.setdefault("exterior", {})
    exterior["facade_style"] = target_style
    exterior["design_concept"] = concept
    exterior["material_palette"] = {
        "walls": copy.deepcopy(preset["walls"]),
        "accent": copy.deepcopy(preset["accent"]),
    }

    rooms_by_id: Dict[str, Dict[str, Any]] = {}
    for floor in design.get("floors", []):
        for room in floor.get("rooms", []):
            if isinstance(room, dict):
                _apply_room_finish(room, preset)
                rooms_by_id[str(room.get("id"))] = room

    # Mongo serialization removes shared Python references, so explicitly sync
    # the top-level compatibility room list with the canonical floor rooms.
    for room in design.get("rooms", []):
        canonical = rooms_by_id.get(str(room.get("id"))) if isinstance(room, dict) else None
        if canonical:
            room["materials"] = copy.deepcopy(canonical.get("materials", {}))
            room["pbr_material"] = copy.deepcopy(canonical.get("pbr_material", {}))

    design.pop("glb_url", None)
    design.pop("approved_at", None)
    design["layout_approved"] = False
    report["handled"] = True
    report["kind"] = "style_only"
    report["changes"].append(
        f"Applied the '{concept}' visual palette without changing layout geometry."
    )
    design["refinement"] = report
    return design, report


WALL_ROTATIONS = {"north": 0.0, "west": 90.0, "south": 180.0, "east": 270.0}
OPPOSITE_SIDE = {"north": "south", "south": "north", "east": "west", "west": "east"}
FACING_ROTATIONS = {"north": 180.0, "east": 90.0, "south": 0.0, "west": 270.0}
ROTATION_WALLS = {0: "north", 90: "west", 180: "south", 270: "east"}
FURNITURE_SYNONYMS = {
    "wardrobe": ("almari", "almarah", "closet", "cupboard", "wadrobe"),
    "sofa": ("couch", "settee"),
    "nightstand": ("bedside table", "side table"),
    "refrigerator": ("fridge",),
    "television": ("tv",),
    "coffee table": ("center table",),
    "armchair": ("chair",),
}

__all__ = [name for name in globals() if not name.startswith('__')]
