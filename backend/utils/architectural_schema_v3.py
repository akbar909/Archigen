"""
architectural_schema_v3.py
===========================
Defines the unified Architectural JSON Schema v3.0 for ArchiGen.
Acts as the Single Source of Truth across the 2D floor plan,
Blender procedural 3D generation, and Three.js viewer.
"""

from typing import Any, Dict, List, Tuple
from jsonschema import Draft7Validator, ValidationError

# ─── Unit Conversion Helpers ──────────────────────────────────────────────────
METERS_PER_FOOT = 0.3048
FEET_PER_METER = 3.28084

def ft_to_m(val: float) -> float:
    return round(float(val) * METERS_PER_FOOT, 3)

def m_to_ft(val: float) -> float:
    return round(float(val) * FEET_PER_METER, 2)


# ─── Architectural Constants & Standard Budgets ───────────────────────────────
VALID_STYLES = [
    "modern", "contemporary", "minimalist", "scandinavian",
    "industrial", "classic", "coastal", "biophilic", "mediterranean", "cozy"
]

VALID_ROOM_TYPES = [
    "living_room", "bedroom", "master_bedroom", "guest_room", "kitchen",
    "dining_room", "bathroom", "master_bathroom", "powder_room",
    "home_office", "hallway", "corridor", "foyer", "laundry", "garage",
    "balcony", "terrace", "pantry", "closet"
]

VALID_ORIENTATIONS = ["north", "south", "east", "west"]

VALID_ROOF_TYPES = ["flat", "parapet", "gable", "hip", "shed"]

# Minimum room dimensions in meters [width, depth]
MIN_ROOM_DIMENSIONS = {
    "living_room": (3.6, 3.6),
    "bedroom": (3.0, 3.0),
    "master_bedroom": (3.6, 3.8),
    "guest_room": (2.8, 3.0),
    "kitchen": (2.4, 2.7),
    "dining_room": (2.7, 3.0),
    "bathroom": (1.5, 2.0),
    "master_bathroom": (1.8, 2.4),
    "powder_room": (1.2, 1.4),
    "home_office": (2.4, 2.7),
    "hallway": (1.0, 1.5),
    "corridor": (1.0, 2.0),
    "foyer": (1.5, 1.8),
    "laundry": (1.5, 1.8),
    "garage": (3.2, 5.5),
    "balcony": (1.2, 2.4),
    "pantry": (1.2, 1.5),
    "closet": (1.2, 1.5),
}

# ─── Architectural JSON Schema v3.0 (Draft-07) ────────────────────────────────
ARCHITECTURAL_SCHEMA_V3: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ArchiGen Architectural JSON Specification v3.0",
    "type": "object",
    "required": ["schema_version", "project", "site", "building", "floors"],
    "properties": {
        "schema_version": {
            "type": "string",
            "enum": ["3.0", "3.0.0"]
        },
        "project": {
            "type": "object",
            "required": ["name", "unit", "style", "orientation"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "unit": {"type": "string", "enum": ["meters", "ft", "m"]},
                "style": {"type": "string"},
                "orientation": {"type": "string", "enum": VALID_ORIENTATIONS}
            }
        },
        "site": {
            "type": "object",
            "required": ["plot", "road", "setbacks"],
            "properties": {
                "plot": {
                    "type": "object",
                    "required": ["width", "depth"],
                    "properties": {
                        "width": {"type": "number", "minimum": 5.0},
                        "depth": {"type": "number", "minimum": 5.0}
                    }
                },
                "road": {
                    "type": "object",
                    "required": ["side"],
                    "properties": {
                        "side": {"type": "string", "enum": VALID_ORIENTATIONS},
                        "width": {"type": "number", "minimum": 0}
                    }
                },
                "setbacks": {
                    "type": "object",
                    "required": ["front", "back", "left", "right"],
                    "properties": {
                        "front": {"type": "number", "minimum": 0},
                        "back": {"type": "number", "minimum": 0},
                        "left": {"type": "number", "minimum": 0},
                        "right": {"type": "number", "minimum": 0}
                    }
                }
            }
        },
        "building": {
            "type": "object",
            "required": ["width", "depth", "wall_thickness", "floors"],
            "properties": {
                "width": {"type": "number", "minimum": 3.0},
                "depth": {"type": "number", "minimum": 3.0},
                "wall_thickness": {"type": "number", "minimum": 0.1, "maximum": 0.5},
                "slab_thickness": {"type": "number", "minimum": 0.1, "maximum": 0.4},
                "floors": {"type": "integer", "minimum": 1, "maximum": 4}
            }
        },
        "floors": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "level", "elevation", "floor_height", "rooms"],
                "properties": {
                    "id": {"type": "string"},
                    "level": {"type": "integer", "minimum": 0},
                    "elevation": {"type": "number", "minimum": 0},
                    "floor_height": {"type": "number", "minimum": 2.2, "maximum": 5.0},
                    "rooms": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["id", "type", "position", "dimensions"],
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "position": {
                                    "type": "object",
                                    "required": ["x", "y", "z"],
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"},
                                        "z": {"type": "number"}
                                    }
                                },
                                "dimensions": {
                                    "type": "object",
                                    "required": ["width", "depth", "height"],
                                    "properties": {
                                        "width": {"type": "number", "minimum": 1.0},
                                        "depth": {"type": "number", "minimum": 1.0},
                                        "height": {"type": "number", "minimum": 2.0}
                                    }
                                },
                                "materials": {"type": "object"}
                            }
                        }
                    },
                    "walls": {"type": "array"},
                    "doors": {"type": "array"},
                    "windows": {"type": "array"},
                    "stairs": {"type": "array"},
                    "furniture": {"type": "array"},
                    "ceiling": {"type": "object"}
                }
            }
        },
        "roof": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": VALID_ROOF_TYPES},
                "height": {"type": "number"},
                "overhang": {"type": "number"},
                "material": {"type": "string"},
                "elevation": {"type": "number"}
            }
        },
        "exterior": {
            "type": "object",
            "properties": {
                "facade_style": {"type": "string"},
                "main_entrance": {"type": "object"},
                "gate": {"type": "object"},
                "entrance_path": {"type": "object"},
                "boundary_wall": {"type": "object"},
                "driveway": {"type": "object"},
                "landscape": {"type": "object"}
            }
        },
        "validation": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "errors": {"type": "array", "items": {"type": "string"}},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "checked_at": {"type": "string"}
            }
        }
    }
}


def validate_schema_v3(doc: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validates an architectural JSON document against Schema v3.0."""
    validator = Draft7Validator(ARCHITECTURAL_SCHEMA_V3)
    errors = []
    for err in validator.iter_errors(doc):
        path = ".".join(str(p) for p in err.path)
        errors.append(f"{path}: {err.message}" if path else err.message)
    return len(errors) == 0, errors
