import json
import os
import re
from typing import Any
from urllib import error, parse, request

from jsonschema import ValidationError, validate

from config import (
	GEMINI_API_BASE_URL,
	GEMINI_API_KEY,
	GEMINI_API_KEY_FILE,
	GEMINI_MODEL,
)


SYSTEM_PROMPT = """You are an expert 3D architectural and interior designer AI.
Given a user's prompt, generate a realistic, well-organized 3D home or single room layout.
Respond ONLY with valid JSON - no markdown, no explanation, no backticks.

Follow this exact JSON schema:
{
  "style": "modern" | "cozy" | "minimalist" | "industrial" | "scandinavian" | "biophilic" | "coastal",
  "rooms": [
    {
      "id": "living_room",
      "type": "Living Room" | "Bedroom" | "Bathroom" | "Kitchen" | "Dining Room" | "Hallway" | "Balcony" | "Office",
      "width": 10.0,
      "length": 10.0,
      "height": 3.5,
      "position": { "x": 0.0, "y": 0.0, "z": 0.0 },
      "pbr_material": {
        "floor": {
          "color": "#2A1A5E",
          "roughness": 0.4,
          "metalness": 0.1,
          "pattern": "diamond_tile" | "hex_tile" | "checker_tile" | "wood_planks" | "marble_tile" | "carpet" | "concrete"
        },
        "walls": {
          "color": "#F0EAD6",
          "roughness": 0.9,
          "metalness": 0.0,
          "pattern": "plain" | "brick" | "wood_panel" | "concrete"
        },
        "accent_wall": {
          "side": "right" | "left" | "back" | "front",
          "color": "#B05050",
          "roughness": 0.85,
          "metalness": 0.0,
          "pattern": "brick" | "wood_panel" | "plain"
        },
        "ceiling": {
          "color": "#FAF7F2",
          "roughness": 0.95,
          "metalness": 0.0,
          "pattern": "plain"
        }
      },
      "furniture": [
        {
          "id": "sofa_main",
          "type": "sofa",
          "label": "3-seat fabric sofa",
          "position": { "x": 0.0, "y": 0.0, "z": -1.0 },
          "rotation_y": 0,
          "dimensions": { "w": 3.2, "h": 0.85, "d": 1.2 },
          "color": "#4A6FA5",
          "roughness": 0.8,
          "metalness": 0.05,
          "parts": {
            "base": { "w": 3.2, "h": 0.45, "d": 1.2, "offset_y": 0.225, "color": "#4A6FA5" },
            "back": { "w": 3.2, "h": 0.9, "d": 0.35, "offset_y": 0.85, "offset_z": -0.42, "color": "#4A6FA5" },
            "cushion_l": { "w": 1.3, "h": 0.2, "d": 0.8, "offset_y": 0.55, "offset_x": -0.7, "color": "#6B8FC7" },
            "cushion_r": { "w": 1.3, "h": 0.2, "d": 0.8, "offset_y": 0.55, "offset_x": 0.7, "color": "#6B8FC7" }
          }
        }
      ],
      "lights": [
        { "id": "ceiling_main", "type": "ceiling", "intensity": 1.6, "color": "#FFE5A0", "position": { "x": 0, "y": 3.2, "z": 0 } }
      ],
      "windows": [
        { "id": "win_1", "wall": "front", "position": { "x": 0, "y": 1.5, "z": 5.0 }, "dimensions": { "w": 2.2, "h": 1.8 }, "frame_color": "#F0EAD6", "glass_color": "#87CEEB", "glass_opacity": 0.35 }
      ],
      "doors": [
        { "id": "door_1", "wall": "right", "position": { "x": 5.0, "y": 1.1, "z": 0 }, "dimensions": { "w": 1.2, "h": 2.2 }, "frame_color": "#C0C0C0" }
      ]
    }
  ],
  "doors": [],
  "windows": []
}

KEY RULES FOR REALISM & ARCHITECTURAL LOGIC:
1. ROOM ORGANIZATION & SIZING:
   - If user asks for a complete house (e.g. 3 bedrooms, 2 attached washrooms, 1 kitchen, living room):
     * Create exactly the requested rooms (e.g. Living Room, Bedroom 1, Bedroom 2, Bedroom 3, Attached Bathroom 1, Attached Bathroom 2, Kitchen).
     * Place rooms side-by-side in a realistic floor plan grid. Coordinates must not overlap.
     * Living room is typically central (x: 0, z: 0).
     * For attached washrooms/bathrooms: place the washroom DIRECTLY adjacent to its designated bedroom (e.g. Bedroom at x: 12, z: 0; attached bathroom at x: 12, z: 8 or x: 18, z: 0), and connect them with a door.
     * Kitchen should be adjacent to Living/Dining room.
   - If user asks for a SINGLE room (e.g. "a modern bedroom", "just a kitchen", "luxury master room"):
     * Generate ONLY that one room, centered at x: 0, y: 0, z: 0, packed with rich furniture details!
2. FURNITURE REALISM & PARTS:
   - Include 4-8 furniture items per major room (sofa, coffee table, TV unit, rugs, lamps, plants, beds, nightstands, wardrobes, dining tables, counters, etc.).
   - Support "parts" dictionary on key furniture items (base, back, cushions, legs, pillows, drawers, screens) for ultra-realistic 3D assembly.
   - Furniture position is relative to room center (0,0,0). Keep within room boundaries.
3. MATERIALS & ACCENT WALLS:
   - Use curated PBR materials: floor patterns ('diamond_tile', 'hex_tile', 'checker_tile', 'wood_planks', 'marble_tile', 'carpet', 'concrete').
   - Include an 'accent_wall' (e.g. 'brick' or 'wood_panel') on one wall of living rooms or bedrooms.
4. DOORS & WINDOWS:
   - Doors must connect adjacent rooms or exterior.
   - Windows must be on exterior walls.
5. Return ONLY the JSON object. No explanation, no markdown text.
"""


HOME_DESIGN_SCHEMA: dict[str, Any] = {
	"type": "object",
	"required": ["style", "rooms"],
	"properties": {
		"style": {"type": "string"},
		"rooms": {
			"type": "array",
			"minItems": 1,
			"items": {
				"type": "object",
				"required": ["type", "width", "length", "height", "position"],
				"properties": {
					"id": {"type": "string"},
					"type": {"type": "string"},
					"width": {"type": "number"},
					"length": {"type": "number"},
					"height": {"type": "number"},
					"position": {
						"type": "object",
						"required": ["x", "y", "z"],
						"properties": {
							"x": {"type": "number"},
							"y": {"type": "number"},
							"z": {"type": "number"},
						},
					},
					"pbr_material": {"type": "object"},
					"furniture": {"type": "array"},
					"lights": {"type": "array"},
					"doors": {"type": "array"},
					"windows": {"type": "array"},
				},
			},
		},
		"doors": {"type": "array"},
		"windows": {"type": "array"},
	},
}


class GeminiTemporaryUnavailableError(RuntimeError):
	"""Raised when Gemini is temporarily unavailable after retry attempts."""


class GeminiSchemaValidationError(RuntimeError):
	"""Raised when Gemini returns a payload that does not match the design schema."""


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

	return constraints


def build_generation_prompt(user_prompt: str, style: str = "modern", base_design: dict[str, Any] | None = None) -> str:
	"""Create a tightly constrained generation prompt from the user request."""
	constraints = infer_layout_constraints(user_prompt)
	hints = []

	room_counts = constraints["room_counts"]
	if constraints["single_room"]:
		hints.append("Generate EXACTLY ONE SINGLE ROOM centered at x: 0, z: 0 with rich furniture and accent wall details.")
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
			hints.append("CRITICAL ARCHITECTURE: Design a cohesive, contiguous home where rooms share common partition walls edge-to-edge with zero gaps. Ground floor features central Living Room opening to patio and open kitchen; multi-floor homes place Master Bedroom and attached bathroom on upper floor (y: 3.2) with connecting staircase.")

	if constraints["open_plan"]:
		hints.append("Open-plan layout connecting living, dining, and kitchen zones.")

	style_hint = constraints["preferred_style"] or style
	hints.append(f"Architectural style: {style_hint}.")

	if base_design:
		hints.append("Preserve the original room layout and style unless explicit modifications were requested.")

	hint_str = " ".join(hints)
	return f"{user_prompt}\n\n[DESIGN SPECIFICATION]: {hint_str}\nReturn ONLY the completed JSON design object with all rooms, detailed furniture parts, doors, and windows."


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
		elif any(k in rtype for k in ["bed", "guest", "master"]):
			bedrooms.append(r)
		elif any(k in rtype for k in ["bath", "wash", "toilet", "powder", "restroom"]):
			bathrooms.append(r)
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

	# 4. Upper Floor Rooms (Two-Story House Layout)
	upper_rooms = []
	if len(bedrooms) > 1:
		master_bed = bedrooms[1]
		mw = float(master_bed.get("width") or 8.0)
		ml = float(master_bed.get("length") or 7.0)
		master_bed["width"] = mw
		master_bed["length"] = ml
		master_bed["position"] = {"x": 0.0, "y": 3.2, "z": -0.5}
		master_bed["floor"] = 1
		upper_rooms.append(master_bed)

		if len(bathrooms) > 1:
			master_bath = bathrooms[1]
			mbw = float(master_bath.get("width") or 4.2)
			mbl = float(master_bath.get("length") or 3.8)
			master_bath["width"] = mbw
			master_bath["length"] = mbl
			master_bath["position"] = {
				"x": round(mw / 2.0 + mbw / 2.0, 2),
				"y": 3.2,
				"z": -0.5,
			}
			master_bath["floor"] = 1
			upper_rooms.append(master_bath)

	# 5. Third Bedroom (if present)
	if len(bedrooms) > 2:
		bed3 = bedrooms[2]
		b3w = float(bed3.get("width") or 6.5)
		b3l = float(bed3.get("length") or 6.5)
		bed3["width"] = b3w
		bed3["length"] = b3l
		mw = float(bedrooms[1].get("width") or 8.0)
		bed3["position"] = {"x": round(-(mw / 2.0 + b3w / 2.0), 2), "y": 3.2, "z": -0.5}
		bed3["floor"] = 1
		upper_rooms.append(bed3)

		if len(bathrooms) > 2:
			bath3 = bathrooms[2]
			b3bw = float(bath3.get("width") or 3.8)
			b3bl = float(bath3.get("length") or 3.2)
			bath3["width"] = b3bw
			bath3["length"] = b3bl
			bath3["position"] = {
				"x": bed3["position"]["x"],
				"y": 3.2,
				"z": round(-0.5 - (b3l / 2.0 + b3bl / 2.0), 2),
			}
			bath3["floor"] = 1
			upper_rooms.append(bath3)

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
		has_stairs = any(f.get("type") in ["staircase", "stairs"] for f in living.get("furniture", []))
		if not has_stairs:
			living.setdefault("furniture", []).append({
				"id": "main_staircase",
				"type": "staircase",
				"label": "Architectural Floating Stairs",
				"position": {"x": round(lw / 2.0 - 1.2, 2), "y": 0.0, "z": round(-ll / 2.0 + 2.0, 2)},
				"rotation_y": 0,
				"dimensions": {"w": 1.2, "h": 3.2, "d": 3.8},
				"color": "#7c5335",
			})

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
	"""Ensure design has all required fields, valid coordinates, and character metadata."""
	if not isinstance(design, dict):
		return {"style": "modern", "rooms": [], "doors": [], "windows": []}

	design.setdefault("style", "modern")
	rooms = design.get("rooms", [])
	if not isinstance(rooms, list):
		rooms = []
		design["rooms"] = rooms

	all_doors = list(design.get("doors", []))
	all_windows = list(design.get("windows", []))

	for idx, room in enumerate(rooms):
		if not isinstance(room, dict):
			continue

		room.setdefault("id", f"room_{idx}")
		room.setdefault("type", "Room")
		room.setdefault("width", 8.0)
		room.setdefault("length", 8.0)
		room.setdefault("height", 3.2)

		pos = room.setdefault("position", {})
		pos.setdefault("x", float(idx * 9.0))
		pos.setdefault("y", 0.0)
		pos.setdefault("z", 0.0)

		# PBR materials
		mat = room.setdefault("pbr_material", {})
		mat.setdefault("floor", {"color": "#2A1A5E", "roughness": 0.4, "metalness": 0.1, "pattern": "wood_planks"})
		mat.setdefault("walls", {"color": "#F0EAD6", "roughness": 0.9, "metalness": 0.0, "pattern": "plain"})
		mat.setdefault("ceiling", {"color": "#FAFAF8", "roughness": 0.95, "metalness": 0.0, "pattern": "plain"})

		# Furniture
		room.setdefault("furniture", [])
		room.setdefault("lights", [{"type": "ceiling", "intensity": 1.5, "color": "#FFE5A0", "position": {"x": 0, "y": 2.8, "z": 0}}])

		# Collect doors and windows into top-level lists if they are in room
		room_doors = room.get("doors", [])
		if isinstance(room_doors, list):
			for d in room_doors:
				if isinstance(d, dict) and d not in all_doors:
					d.setdefault("room_id", room.get("id"))
					all_doors.append(d)

		room_windows = room.get("windows", [])
		if isinstance(room_windows, list):
			for w in room_windows:
				if isinstance(w, dict) and w not in all_windows:
					w.setdefault("room_id", room.get("id"))
					all_windows.append(w)

	design["doors"] = all_doors
	design["windows"] = all_windows

	# Snap rooms to contiguous architectural layout
	design = snap_and_pack_architectural_layout(design)

	# Character avatar starting position
	if "character" not in design or not isinstance(design["character"], dict):
		first_room = rooms[0] if rooms else None
		first_pos = first_room.get("position", {}) if first_room else {}
		design["character"] = {
			"enabled": True,
			"start_position": {
				"x": float(first_pos.get("x", 0.0)),
				"y": 0.0,
				"z": float(first_pos.get("z", 0.0)),
			},
			"start_room": first_room.get("type", "Living Room") if first_room else "Living Room",
			"speed": 3.2,
		}

	return design


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

	return len(errors) == 0, errors


def _is_response_truncated(text: str) -> bool:
	"""Check if JSON response appears truncated or incomplete."""
	if not text:
		return True
	text = text.strip()
	open_braces = text.count("{")
	close_braces = text.count("}")
	open_brackets = text.count("[")
	close_brackets = text.count("]")
	return open_braces != close_braces or open_brackets != close_brackets


def _attempt_json_repair(text: str) -> str | None:
	"""Attempt to repair incomplete JSON (add missing closing brackets)."""
	if not text or not text.strip():
		return None

	text = text.strip()
	# Strip markdown wrappers if any
	if text.startswith("```"):
		lines = text.splitlines()
		if lines[0].startswith("```"):
			lines = lines[1:]
		if lines and lines[-1].startswith("```"):
			lines = lines[:-1]
		text = "\n".join(lines).strip()

	open_braces = text.count("{")
	close_braces = text.count("}")
	open_brackets = text.count("[")
	close_brackets = text.count("]")

	repair = text
	repair += "}" * max(0, open_braces - close_braces)
	repair += "]" * max(0, open_brackets - close_brackets)
	return repair


def _safe_parse_json(text: str, strict: bool = False) -> tuple[dict[str, Any] | None, str | None]:
	"""Safely parse JSON with error recovery."""
	if not text or not isinstance(text, str):
		return None, "Response text is empty or not a string"

	clean_text = text.strip()
	if clean_text.startswith("```"):
		lines = clean_text.splitlines()
		if lines[0].startswith("```"):
			lines = lines[1:]
		if lines and lines[-1].startswith("```"):
			lines = lines[:-1]
		clean_text = "\n".join(lines).strip()

	try:
		return json.loads(clean_text), None
	except json.JSONDecodeError as e:
		repaired = _attempt_json_repair(clean_text)
		if repaired:
			try:
				return json.loads(repaired), None
			except json.JSONDecodeError:
				pass
		return None, f"JSON parse failed: {e.msg}"


def _read_api_key_from_env_file(env_file_path: str = GEMINI_API_KEY_FILE) -> str | None:
	if not os.path.isfile(env_file_path):
		return None

	with open(env_file_path, "r", encoding="utf-8") as env_file:
		for raw_line in env_file:
			line = raw_line.strip()
			if not line or line.startswith("#"):
				continue
			if "=" in line:
				key, value = line.split("=", 1)
				if key.strip() == "GEMINI_API_KEY":
					clean_value = value.strip().strip('"').strip("'")
					if clean_value:
						return clean_value
			else:
				return line
	return None


def _get_api_key() -> str:
	if GEMINI_API_KEY:
		return GEMINI_API_KEY
	api_key_from_file = _read_api_key_from_env_file()
	if api_key_from_file:
		return api_key_from_file
	api_key_from_env = os.getenv("GEMINI_API_KEY")
	if api_key_from_env:
		return api_key_from_env
	raise EnvironmentError("GEMINI API key not found. Set GEMINI_API_KEY or provide GEMINI_API_KEY_FILE.")


def _extract_text_from_response(response_data: dict[str, Any]) -> str:
	candidates = response_data.get("candidates", [])
	if not candidates:
		raise ValueError("No candidates returned by Gemini API.")
	content = candidates[0].get("content", {})
	parts = content.get("parts", [])
	if not parts:
		raise ValueError("Gemini response is missing content parts.")
	text_chunks = [part.get("text", "") for part in parts if isinstance(part, dict)]
	text = "".join(text_chunks).strip()
	if not text:
		raise ValueError("Gemini returned an empty response text.")
	return text


def generate_home_design(user_prompt: str, timeout: int = 120) -> dict[str, Any]:
	api_key = _get_api_key()
	endpoint = f"{GEMINI_API_BASE_URL}/{GEMINI_MODEL}:generateContent?key={parse.quote(api_key)}"

	generation_prompt = build_generation_prompt(user_prompt)

	payload = {
		"system_instruction": {
			"parts": [{"text": SYSTEM_PROMPT}],
		},
		"contents": [
			{
				"role": "user",
				"parts": [{"text": generation_prompt}],
			}
		],
		"generationConfig": {
			"responseMimeType": "application/json",
			"temperature": 0.2,
		},
	}

	req = request.Request(
		endpoint,
		data=json.dumps(payload).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	try:
		with request.urlopen(req, timeout=timeout) as response:
			raw = response.read().decode("utf-8")

		response_data = json.loads(raw)
		response_text = _extract_text_from_response(response_data)

		parsed_json, parse_error = _safe_parse_json(response_text, strict=False)
		if parsed_json is None:
			raise ValueError(f"Failed to parse Gemini response: {parse_error}")

		# Normalize design structure, add defaults & character metadata
		normalized = _normalize_design(parsed_json, user_prompt)

		# Validate schema
		is_valid, validation_errors = _validate_home_design_schema(normalized, user_prompt)
		if not is_valid:
			raise GeminiSchemaValidationError(f"Design validation failed: {'; '.join(validation_errors)}")

		return normalized

	except error.HTTPError as exc:
		status_code = exc.code
		detail = exc.read().decode("utf-8", errors="replace")
		if status_code in (429, 500, 502, 503, 504):
			raise GeminiTemporaryUnavailableError(
				f"Gemini API error {status_code}: {detail}"
			) from exc
		raise RuntimeError(f"Gemini API error {status_code}: {detail}") from exc

	except error.URLError as exc:
		raise GeminiTemporaryUnavailableError(
			f"Gemini API connection error: {exc.reason}"
		) from exc
