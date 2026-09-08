"""
gemini.py
=========
Core Gemini API communication: sends prompts, parses JSON responses,
handles retries and error recovery.

Schema/prompt defined in gemini_schema.py.
Layout/validation logic in gemini_layout.py.
"""

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
from utils.gemini_schema import SYSTEM_PROMPT
from utils.gemini_layout import (
    _normalize_design,
    _validate_home_design_schema,
    build_generation_prompt,
    infer_layout_constraints,
    validate_architectural_prompt,
)


# ─── Error Classes ────────────────────────────────────────────────────────────

class GeminiTemporaryUnavailableError(RuntimeError):
    """Raised when Gemini is temporarily unavailable after retry attempts."""


class GeminiSchemaValidationError(RuntimeError):
    """Raised when Gemini returns a payload that does not match the design schema."""


# ─── JSON Parsing Helpers ─────────────────────────────────────────────────────

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


# ─── API Key Management ──────────────────────────────────────────────────────

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


# ─── Main Generation Function ────────────────────────────────────────────────

def generate_home_design(user_prompt: str, timeout: int = 120) -> dict[str, Any]:
    api_key = _get_api_key()
    endpoint = f"{GEMINI_API_BASE_URL}/{GEMINI_MODEL}:generateContent?key={parse.quote(api_key)}"

    generation_prompt = user_prompt if "[DESIGN SPECIFICATION]" in user_prompt else build_generation_prompt(user_prompt)

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
            "thinkingConfig": {"thinkingBudget": 0},
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
