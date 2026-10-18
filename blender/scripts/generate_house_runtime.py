"""Shared Blender runtime imports and script paths."""

import os
import sys

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None
    mathutils = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLENDER_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

try:
    import import_asset
    import place_furniture
    import export_glb
except ImportError as err:
    import_asset = None
    place_furniture = None
    export_glb = None
    print(f"[WARN] Failed to import helper modules: {err}")

