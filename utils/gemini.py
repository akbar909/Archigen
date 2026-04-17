import json
import os
from typing import Any
from urllib import error, parse, request

from config import (
		GEMINI_API_BASE_URL,
		GEMINI_API_KEY,
		GEMINI_API_KEY_FILE,
		GEMINI_MODEL,
)


SYSTEM_PROMPT = """You are an AI Architectural Design Engine.

Your task is to generate realistic, structured home designs in JSON format.

STRICT RULES:

* Output ONLY valid JSON
* No explanation or extra text
* Use meters
* Rooms must not overlap
* Include at least:

	* 1 bedroom
	* 1 bathroom
	* 1 living room
* Each room must include:

	* type
	* width
	* length
	* height
	* position (x, y, z)
* Include:

	* rooms
	* doors
	* windows
* Maintain logical layout
* Use style: modern | minimal | classic
"""


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


def _validate_home_design_schema(design: dict[str, Any]) -> tuple[bool, list[str]]:
	"""Validate that design has required architectural elements."""
	errors = []

	if not isinstance(design, dict):
		errors.append("Design must be a dictionary")
		return False, errors

	if "rooms" not in design:
		errors.append("Design missing required 'rooms' field")
		return False, errors

	rooms = design.get("rooms", [])
	if not isinstance(rooms, list):
		errors.append("'rooms' must be a list")
		return False, errors

	if len(rooms) == 0:
		errors.append("Design must contain at least one room")
		return False, errors

	for required_list in ("doors", "windows"):
		if required_list not in design:
			errors.append(f"Design missing required '{required_list}' field")
		elif not isinstance(design.get(required_list), list):
			errors.append(f"'{required_list}' must be a list")

	# Check for required room types
	room_types = set()
	for room in rooms:
		if isinstance(room, dict) and "type" in room:
			room_type = room.get("type", "").strip()
			room_types.add(room_type)

	required_room_types = {"Bedroom", "Bathroom", "Living Room"}
	missing_types = required_room_types - room_types

	if missing_types:
		errors.append(f"Design missing required room types: {missing_types}")

	# Validate individual rooms (ensure required spatial fields)
	required_room_fields = {"type", "width", "length", "height", "position"}
	for i, room in enumerate(rooms):
		if not isinstance(room, dict):
			errors.append(f"Room {i} is not a dictionary")
			continue

		missing = required_room_fields - set(room.keys())
		if missing:
			errors.append(f"Room {i} missing fields: {missing}")

		pos = room.get("position")
		if not isinstance(pos, dict) or not all(k in pos for k in ("x", "y", "z")):
			errors.append(f"Room {i} position must include x, y, z")

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

	if open_braces != close_braces or open_brackets != close_brackets:
		return True

	if text.endswith(("}}", "]]", "},", "],", "...")):
		return True

	return False


def _attempt_json_repair(text: str) -> str | None:
	"""Attempt to repair incomplete JSON (add missing closing brackets)."""
	if not text or not text.strip():
		return None

	text = text.strip()

	# Count mismatched brackets
	open_braces = text.count("{")
	close_braces = text.count("}")
	open_brackets = text.count("[")
	close_brackets = text.count("]")

	# Add missing closing brackets
	repair = text
	repair += "}" * (open_braces - close_braces)
	repair += "]" * (open_brackets - close_brackets)

	return repair


def _safe_parse_json(
	text: str, strict: bool = True
) -> tuple[dict[str, Any] | None, str | None]:
	"""
	Safely parse JSON with error recovery.
	Returns (data, error_message) tuple.
	"""
	if not text or not isinstance(text, str):
		return None, "Response text is empty or not a string"

	text = text.strip()

	# Check for truncation
	if _is_response_truncated(text):
		if strict:
			return None, "Response appears truncated or incomplete"
		# Attempt repair
		repaired = _attempt_json_repair(text)
		if repaired:
			text = repaired

	# Try standard JSON parsing
	try:
		return json.loads(text), None
	except json.JSONDecodeError as e:
		if strict:
			return (
				None,
				f"Invalid JSON at line {e.lineno}, col {e.colno}: {e.msg}",
			)

		# Attempt repair
		repaired = _attempt_json_repair(text)
		if repaired and repaired != text:
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
				# Support files containing only the raw API key on one line.
				return line

	return None


def _get_api_key() -> str:
	# Prefer explicit env variable override
	if GEMINI_API_KEY:
		return GEMINI_API_KEY

	api_key_from_file = _read_api_key_from_env_file()
	if api_key_from_file:
		return api_key_from_file

	api_key_from_env = os.getenv("GEMINI_API_KEY")
	if api_key_from_env:
		return api_key_from_env

	raise EnvironmentError(
		"GEMINI API key not found. Set GEMINI_API_KEY or provide GEMINI_API_KEY_FILE."
	)


def generate_home_design(user_prompt: str, timeout: int = 45) -> dict[str, Any]:
	api_key = _get_api_key()

	endpoint = f"{GEMINI_API_BASE_URL}/{GEMINI_MODEL}:generateContent?key={parse.quote(api_key)}"

	payload = {
		"system_instruction": {
			"parts": [{"text": SYSTEM_PROMPT}],
		},
		"contents": [
			{
				"role": "user",
				"parts": [{"text": user_prompt}],
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
	except error.HTTPError as exc:
		detail = exc.read().decode("utf-8", errors="replace")
		raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc
	except error.URLError as exc:
		raise RuntimeError(f"Gemini API connection error: {exc.reason}") from exc

	response_data = json.loads(raw)
	response_text = _extract_text_from_response(response_data)

	# Safe JSON parsing with recovery
	parsed_json, parse_error = _safe_parse_json(response_text, strict=False)

	if parsed_json is None:
		raise ValueError(f"Failed to parse Gemini response: {parse_error}")

	# Validate schema
	is_valid, validation_errors = _validate_home_design_schema(parsed_json)
	if not is_valid:
		raise ValueError(
			f"Design validation failed: {'; '.join(validation_errors)}"
		)

	return parsed_json

