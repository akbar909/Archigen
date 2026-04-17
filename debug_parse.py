#!/usr/bin/env python
"""Debug parsing to see what's being returned."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.gemini import generate_home_design, _safe_parse_json, _validate_home_design_schema

def debug_parsing():
    """Debug the parsing flow."""
    print("Testing raw Gemini response...")
    print("-" * 60)
    
    try:
        # Call the function but catch at parsing level
        test_prompt = "Generate a simple 1 bedroom apartment design in modern style."
        
        # Manually call parts to debug
        import os
        from urllib import error, parse, request
        from utils.gemini import (
            MODEL_NAME, API_BASE_URL, SYSTEM_PROMPT, _get_api_key, 
            _extract_text_from_response, _safe_parse_json,
            _validate_home_design_schema
        )
        
        api_key = _get_api_key()
        endpoint = f"{API_BASE_URL}/{MODEL_NAME}:generateContent?key={parse.quote(api_key)}"
        
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": test_prompt}]}],
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
        
        print("Raw response text (first 500 chars):")
        print(response_text[:500])
        print("\n" + "-" * 60)
        
        # Try parsing
        parsed_json, parse_error = _safe_parse_json(response_text, strict=False)
        print(f"Parse error: {parse_error}")
        print(f"Parsed JSON keys: {list(parsed_json.keys()) if parsed_json else 'None'}")
        print("\n" + "-" * 60)
        
        if parsed_json:
            is_valid, validation_errors = _validate_home_design_schema(parsed_json)
            print(f"Schema valid: {is_valid}")
            print(f"Validation errors: {validation_errors}")
            print("\n" + "-" * 60)
            print("Full parsed JSON:")
            print(json.dumps(parsed_json, indent=2)[:1000])
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_parsing()
