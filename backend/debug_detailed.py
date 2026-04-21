#!/usr/bin/env python
"""Debug what's actually being validated."""

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils.gemini import (
    _get_api_key, MODEL_NAME, API_BASE_URL, SYSTEM_PROMPT,
    _extract_text_from_response, _safe_parse_json, _validate_home_design_schema
)
from urllib import error, parse, request

try:
    api_key = _get_api_key()
    endpoint = f"{API_BASE_URL}/{MODEL_NAME}:generateContent?key={parse.quote(api_key)}"
    
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": "Generate a simple 1 bedroom apartment design in modern style."}]}],
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
    
    with request.urlopen(req, timeout=60) as response:
        raw = response.read().decode("utf-8")
    
    response_data = json.loads(raw)
    response_text = _extract_text_from_response(response_data)
    
    parsed_json, parse_error = _safe_parse_json(response_text, strict=False)
    
    print("Type of parsed_json:", type(parsed_json))
    print("Keys in parsed_json:", list(parsed_json.keys()) if isinstance(parsed_json, dict) else "NOT A DICT")
    print("Type of parsed_json['rooms']:", type(parsed_json.get('rooms')))
    print("Number of rooms:", len(parsed_json.get('rooms', [])))
    
    if parsed_json.get('rooms'):
        print("\nFirst room:")
        first_room = parsed_json['rooms'][0]
        print(f"  Type: {type(first_room)}")
        print(f"  Keys: {list(first_room.keys())}")
        print(f"  room['type'] = {first_room.get('type')}")
        print(f"  repr(room['type']) = {repr(first_room.get('type'))}")
        
        print("\nAll room types:")
        for i, room in enumerate(parsed_json.get('rooms', [])):
            print(f"  Room {i}: type = {repr(room.get('type'))}")
    
    print("\n\nNow running validation...")
    is_valid, errors = _validate_home_design_schema(parsed_json)
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")
    
except Exception as e:
    import traceback
    traceback.print_exc()
