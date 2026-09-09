"""
gemini_schema.py
================
Compact architectural JSON schema and system prompt for Gemini.
Gemini generates high-level architectural decisions (rooms, furniture asset names,
materials, doors, windows) — NOT low-level geometry, vertices, or furniture parts.
"""

from typing import Any


# ─── Valid Enums ──────────────────────────────────────────────────────────────

VALID_ROOM_TYPES = [
    "Living Room", "Bedroom", "Bathroom", "Kitchen", "Dining Room",
    "Hallway", "Balcony", "Office", "Master Bedroom", "Guest Room",
    "Laundry", "Garage", "Pantry", "Lounge",
]

VALID_FURNITURE_ASSETS = [
    "sofa", "armchair", "coffee_table", "bed", "wardrobe", "nightstand",
    "desk", "chair", "dining_table", "dining_chair", "sideboard",
    "kitchen_cabinet", "kitchen_island", "refrigerator", "microwave",
    "kitchen_sink", "bathtub", "bathroom_sink", "toilet",
    "floor_lamp", "tv_cabinet",
]

VALID_FLOOR_PATTERNS = [
    "wood_planks", "marble_tile", "hex_tile", "checker_tile",
    "diamond_tile", "carpet", "concrete",
]

VALID_WALL_PATTERNS = ["plain", "brick", "wood_panel", "concrete"]

VALID_STYLES = [
    "modern", "cozy", "minimalist", "industrial",
    "scandinavian", "biophilic", "coastal", "classic",
]


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert architectural AI for the ArchGen 3D Home Architect app.
Given a user's prompt, generate a realistic, well-organized home layout.
Respond ONLY with valid JSON — no markdown, no explanation, no backticks.

CRITICAL: Keep the JSON compact. Do NOT generate geometry, vertices, furniture parts,
cushion offsets, leg dimensions, or detailed 3D coordinates. You are making ARCHITECTURAL
DESIGN DECISIONS, not constructing 3D geometry.

## JSON Structure

{
  "version": "2.0",
  "house": {
    "width": <total house width in meters>,
    "length": <total house length in meters>,
    "floorHeight": <floor-to-ceiling height, typically 3.0>,
    "floors": <number of floors, 1 or 2>,
    "style": "<architectural style>"
  },
  "rooms": [
    {
      "id": "<unique_id like living_01>",
      "type": "<room type>",
      "width": <meters>,
      "length": <meters>,
      "height": <meters, usually 3.0>,
      "position": { "x": <center x>, "y": <floor level: 0.0 for ground, 3.2 for upper>, "z": <center z> },
      "floor": <0 for ground, 1 for upper>,
      "materials": {
        "floor": { "color": "<hex>", "pattern": "<floor pattern>" },
        "walls": { "color": "<hex>", "pattern": "<wall pattern>" },
        "accent_wall": { "side": "back|front|left|right", "color": "<hex>", "pattern": "<wall pattern>" }
      }
    }
  ],
  "furniture": [
    {
      "id": "<unique_id like sofa_01>",
      "asset": "<asset name from catalog>",
      "roomId": "<matching room id>",
      "position": { "x": <relative to room center>, "y": 0, "z": <relative to room center> },
      "rotation": <degrees around Y axis>,
      "scale": <uniform scale, usually 1.0>
    }
  ],
  "doors": [
    {
      "id": "<unique_id>",
      "roomId": "<room this door belongs to>",
      "wall": "front|back|left|right",
      "position": { "x": <world x>, "y": <center height, ~1.05>, "z": <world z> },
      "width": <meters>,
      "height": <meters, typically 2.1>
    }
  ],
  "windows": [
    {
      "id": "<unique_id>",
      "roomId": "<room this window belongs to>",
      "wall": "front|back|left|right",
      "position": { "x": <world x>, "y": <center height, ~1.5>, "z": <world z> },
      "width": <meters>,
      "height": <meters, typically 1.5>
    }
  ]
}

## Available Furniture Assets (use ONLY these names in "asset" field)
""" + ", ".join(VALID_FURNITURE_ASSETS) + """

## Available Floor Patterns
""" + ", ".join(VALID_FLOOR_PATTERNS) + """

## Available Wall Patterns
""" + ", ".join(VALID_WALL_PATTERNS) + """

## Available Styles
""" + ", ".join(VALID_STYLES) + """

## Room Types
""" + ", ".join(VALID_ROOM_TYPES) + """

## KEY RULES
1. ROOM ORGANIZATION:
   - If user asks for a complete house: create all requested rooms with realistic adjacency.
   - Living room is typically central at x:0, z:0.
   - Attached bathrooms must be directly adjacent to their bedroom.
   - Kitchen should be adjacent to Living/Dining room.
   - If user asks for a SINGLE room: generate ONLY that room centered at x:0, y:0, z:0.
   - Rooms must NOT overlap. Position them edge-to-edge sharing partition walls.

2. FURNITURE:
   - Use ONLY asset names from the catalog above. Do NOT invent new names.
   - Include 3-6 furniture items per major room.
   - Furniture position is RELATIVE to room center (0,0,0). Keep within room boundaries.
   - Do NOT include "parts", "dimensions", "color", "roughness", or "metalness" on furniture.

3. MATERIALS:
   - Use hex colors for floors and walls.
   - Include accent_wall on living rooms and bedrooms (brick or wood_panel).
   - Bathrooms/kitchens: use marble_tile or hex_tile floors.
   - Bedrooms/living: use wood_planks floors.

4. DOORS & WINDOWS:
   - Doors connect adjacent rooms or lead to exterior.
   - Windows go on exterior walls only.
   - For all doors and windows, the "wall" field is REQUIRED: use "front" | "back" | "left" | "right".
     * "front" / "back" walls run along the X-axis (width of house).
     * "left" / "right" walls run along the Z-axis (depth of house).
   - Each room should have at least one door.

5. MULTI-FLOOR:
   - Upper floor rooms use y: 3.2 in position and floor: 1.
   - Add connecting staircase furniture item in the living room for multi-floor homes.

6. Return ONLY the JSON object. No explanation, no markdown.
"""

GEMINI_SYSTEM_PROMPT = SYSTEM_PROMPT



# ─── JSON Schema for Validation ───────────────────────────────────────────────

HOME_DESIGN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["rooms"],
    "properties": {
        "version": {"type": "string"},
        "house": {
            "type": "object",
            "properties": {
                "width": {"type": "number", "minimum": 2},
                "length": {"type": "number", "minimum": 2},
                "floorHeight": {"type": "number", "minimum": 2, "maximum": 6},
                "floors": {"type": "integer", "minimum": 1, "maximum": 4},
                "style": {"type": "string"},
            },
        },
        "rooms": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "width", "length"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "width": {"type": "number", "minimum": 1.5},
                    "length": {"type": "number", "minimum": 1.5},
                    "height": {"type": "number", "minimum": 2, "maximum": 6},
                    "floor": {"type": "integer", "minimum": 0, "maximum": 3},
                    "position": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"},
                        },
                    },
                    "materials": {"type": "object"},
                },
            },
        },
        "furniture": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["asset", "roomId"],
                "properties": {
                    "id": {"type": "string"},
                    "asset": {"type": "string"},
                    "roomId": {"type": "string"},
                    "position": {"type": "object"},
                    "rotation": {"type": "number"},
                    "scale": {"type": "number", "minimum": 0.1, "maximum": 5},
                },
            },
        },
        "doors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "roomId": {"type": "string"},
                    "wall": {"type": "string", "enum": ["front", "back", "left", "right"]},
                    "position": {"type": "object"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                },
            },
        },
        "windows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "roomId": {"type": "string"},
                    "wall": {"type": "string", "enum": ["front", "back", "left", "right"]},
                    "position": {"type": "object"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                },
            },
        },
    },
}
