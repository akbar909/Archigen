"""Generated design normalization and schema validation."""

from typing import Any

from jsonschema import ValidationError, validate

from utils.architectural_preflight import validate_and_repair_design
from utils.architectural_validator import ArchitecturalValidator
from utils.gemini_furniture import normalize_furniture_asset
from utils.gemini_schema import HOME_DESIGN_SCHEMA, VALID_FURNITURE_ASSETS
from utils.layout_engine import ArchitecturalLayoutEngine


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
        path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at '{path}'" if path else ""
        errors.append(f"Design schema validation failed{location}: {exc.message}")

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


