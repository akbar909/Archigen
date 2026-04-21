#!/usr/bin/env python
"""Simple test without unicode characters."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils.gemini import generate_home_design

try:
    result = generate_home_design("Generate a simple 1 bedroom apartment design in modern style.", timeout=60)
    print("SUCCESS! Generated design:")
    print(f"Style: {result.get('style')}")
    print(f"Number of rooms: {len(result.get('rooms', []))}")
    for room in result.get('rooms', []):
        print(f"  - {room.get('type')}: {room.get('id')}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}")
    print(f"Message: {e}")
    import traceback
    traceback.print_exc()
