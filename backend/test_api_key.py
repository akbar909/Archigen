#!/usr/bin/env python
"""Test script to verify Gemini API key validity."""

import json
import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.gemini import generate_home_design

def test_api_key():
    """Test if the API key is valid by making a simple request."""
    print("Testing Gemini API key...")
    print("-" * 50)
    
    try:
        # Simple test prompt for a minimal home design
        test_prompt = "Generate a simple 1 bedroom apartment design in modern style."
        
        print(f"Sending request: {test_prompt}")
        print("Waiting for Gemini response...")
        
        result = generate_home_design(test_prompt, timeout=120)
        
        print("\n[OK] API Key is VALID!")
        print("-" * 50)
        print("Response received:")
        print(json.dumps(result, indent=2))
        return True
        
    except EnvironmentError as e:
        print(f"\n[ERROR] Configuration Error: {e}")
        return False
    except RuntimeError as e:
        print(f"\n[ERROR] API Error: {e}")
        return False
    except ValueError as e:
        print(f"\n[ERROR] Response Error: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_api_key()
    sys.exit(0 if success else 1)
