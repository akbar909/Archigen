"""
generate_metadata.py
====================
Auto-cataloging script that dynamically discovers and generates metadata JSON files
for all 3D assets found in blender/assets/. Adheres to blender/metadata/furniture.schema.json.
"""

import os
import re
import json
from typing import Dict, Any, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLENDER_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS_ROOT = os.path.join(BLENDER_ROOT, "assets")
METADATA_DIR = os.path.join(BLENDER_ROOT, "metadata")

CATEGORY_DEFAULTS = {
    "sofa": (2.20, 0.95, 0.85, "living_room"),
    "armchair": (0.88, 0.88, 0.84, "living_room"),
    "chair": (0.55, 0.55, 0.85, "dining_room"),
    "coffee_table": (1.10, 0.65, 0.45, "living_room"),
    "dining_table": (1.80, 0.90, 0.76, "dining_room"),
    "desk": (1.40, 0.70, 0.76, "general"),
    "bed": (2.00, 2.10, 1.10, "bedroom"),
    "nightstand": (0.50, 0.45, 0.55, "bedroom"),
    "wardrobe": (1.60, 0.60, 2.00, "bedroom"),
    "bookshelf": (1.20, 0.35, 1.80, "living_room"),
    "cabinet": (1.20, 0.45, 0.85, "living_room"),
    "kitchen_counter": (2.20, 1.00, 0.92, "kitchen"),
    "refrigerator": (0.92, 0.85, 1.82, "kitchen"),
    "stove": (0.60, 0.60, 0.85, "kitchen"),
    "sink": (0.85, 0.55, 0.85, "kitchen"),
    "toilet": (0.45, 0.70, 0.80, "bathroom"),
    "bathtub": (1.75, 0.85, 0.65, "bathroom"),
    "shower": (1.00, 1.00, 2.10, "bathroom"),
    "lamp": (0.45, 0.45, 1.50, "living_room"),
    "plant": (0.50, 0.50, 1.40, "living_room"),
    "outdoor_chair": (0.75, 0.75, 0.80, "outdoor"),
    "outdoor_table": (1.40, 0.80, 0.75, "outdoor"),
    "general": (1.00, 0.50, 1.00, "general"),
}

KNOWN_PRESETS: Dict[str, Dict[str, Any]] = {
    "bathtub_001": {"category": "bathtub", "room": "bathroom", "width": 1.75, "depth": 0.85, "height": 0.65},
    "sink_001": {"category": "sink", "room": "bathroom", "width": 0.90, "depth": 0.55, "height": 0.85},
    "toilet_001": {"category": "toilet", "room": "bathroom", "width": 0.45, "depth": 0.70, "height": 0.80},
    "bed_02": {"category": "bed", "room": "bedroom", "width": 2.10, "depth": 2.20, "height": 1.10},
    "gothicbed_01": {"category": "bed", "room": "bedroom", "width": 1.80, "depth": 2.10, "height": 1.35},
    "bedside_table_001": {"category": "nightstand", "room": "bedroom", "width": 0.50, "depth": 0.45, "height": 0.55},
    "desk_001": {"category": "desk", "room": "bedroom", "width": 1.40, "depth": 0.70, "height": 0.76},
    "car": {"category": "general", "room": "general", "width": 1.90, "depth": 4.60, "height": 1.55},
    "gate": {"category": "general", "room": "general", "width": 4.63, "depth": 0.17, "height": 2.15},
    "roller_garager_door_01": {"category": "general", "room": "general", "width": 2.80, "depth": 0.10, "height": 2.40},
}


def infer_category_and_room(rel_path: str, filename: str) -> Tuple[str, str, Tuple[float, float, float]]:
    """Infers category, room, and default dimensions from relative folder path and filename."""
    norm_path = rel_path.lower().replace("\\", "/")
    base_name = os.path.splitext(filename)[0].lower()

    if base_name in KNOWN_PRESETS:
        p = KNOWN_PRESETS[base_name]
        return p["category"], p["room"], (p["width"], p["depth"], p["height"])

    cat = "general"
    room = "general"

    if "sofa" in norm_path or "couch" in norm_path:
        cat, room = "sofa", "living_room"
    elif "armchair" in norm_path:
        cat, room = "armchair", "living_room"
    elif "coffee_table" in norm_path or "center_table" in norm_path:
        cat, room = "coffee_table", "living_room"
    elif "side_table" in norm_path or "sidetable" in norm_path:
        cat, room = "coffee_table", "living_room"
    elif "tv_unit" in norm_path or "tv_wall" in norm_path or "tv_stand" in norm_path:
        cat, room = "cabinet", "living_room"
    elif "bookshel" in norm_path or "shelf" in norm_path:
        cat, room = "bookshelf", "general"
    elif "dining_table" in norm_path or ("dining" in norm_path and "table" in norm_path):
        cat, room = "dining_table", "dining_room"
    elif "dining_chair" in norm_path or "bar_stool" in norm_path:
        cat, room = "chair", "dining_room"
    elif "sideboard" in norm_path:
        cat, room = "cabinet", "dining_room"
    elif "bed" in norm_path and "side" not in norm_path:
        cat, room = "bed", "bedroom"
    elif "nightstand" in norm_path or "bedside" in norm_path:
        cat, room = "nightstand", "bedroom"
    elif "wardrobe" in norm_path or "closet" in norm_path or "dresser" in norm_path:
        cat, room = "wardrobe", "bedroom"
    elif "vanity_table" in norm_path:
        cat, room = "desk", "bedroom"
    elif "kitchen_island" in norm_path or "island" in norm_path:
        cat, room = "kitchen_counter", "kitchen"
    elif "refrigerator" in norm_path or "fridge" in norm_path:
        cat, room = "refrigerator", "kitchen"
    elif "microwave" in norm_path or "oven" in norm_path or "stove" in norm_path:
        cat, room = "stove", "kitchen"
    elif "bathtub" in norm_path:
        cat, room = "bathtub", "bathroom"
    elif "shower" in norm_path:
        cat, room = "shower", "bathroom"
    elif "toilet" in norm_path:
        cat, room = "toilet", "bathroom"
    elif "vanity" in norm_path or "sink" in norm_path or "wash_basin" in norm_path:
        cat, room = "sink", "bathroom" if "bathroom" in norm_path else "kitchen"
    elif "lamp" in norm_path or "chandelier" in norm_path or "light" in norm_path or "sconce" in norm_path:
        cat, room = "lamp", "living_room" if "floor" in norm_path else "general"
    elif "plant" in norm_path or "planter" in norm_path:
        cat, room = "plant", "outdoor" if "outdoor" in norm_path else "living_room"
    elif "patio" in norm_path or "outdoor" in norm_path:
        cat, room = "outdoor_chair" if "seating" in norm_path else "outdoor_table", "outdoor"
    elif "office" in norm_path and "desk" in norm_path:
        cat, room = "desk", "general"
    elif "office" in norm_path and "chair" in norm_path:
        cat, room = "chair", "general"
    elif "bench" in norm_path:
        cat, room = "chair", "general"
    elif "kitchen" in norm_path and "cabinet" in norm_path:
        cat, room = "cabinet", "kitchen"

    w, d, h, _ = CATEGORY_DEFAULTS.get(cat, CATEGORY_DEFAULTS["general"])
    return cat, room, (w, d, h)


def sanitize_id(raw_name: str) -> str:
    """Produces a clean alphanumeric + underscore asset id."""
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", raw_name).strip("_").lower()
    return clean or "asset_unnamed"


def human_name(raw_name: str) -> str:
    """Formats raw asset name into clean Title Case."""
    name = re.sub(r"[_\-]+", " ", raw_name).strip()
    return " ".join(word.capitalize() for word in name.split())


def generate_all_metadata():
    """Scans blender/assets/ and creates metadata JSON files for all 3D models."""
    os.makedirs(METADATA_DIR, exist_ok=True)
    generated = 0
    seen_ids = set()

    for root, _, files in os.walk(ASSETS_ROOT):
        for f in files:
            if not f.lower().endswith((".glb", ".gltf")):
                continue

            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, BLENDER_ROOT).replace("\\", "/")
            base_name = os.path.splitext(f)[0]

            asset_id = sanitize_id(base_name)
            if asset_id in seen_ids:
                folder_tag = sanitize_id(os.path.basename(root))
                asset_id = f"{asset_id}_{folder_tag}"
            seen_ids.add(asset_id)

            category, room, (width, depth, height) = infer_category_and_room(rel_path, f)

            tags = list(set([
                category,
                room,
                base_name.lower().replace("_", " "),
                os.path.basename(root).lower().replace("_", " "),
            ]))

            meta_content = {
                "id": asset_id,
                "name": human_name(base_name),
                "category": category,
                "room": room,
                "style": ["modern", "contemporary", "scandinavian"],
                "width": round(float(width), 2),
                "depth": round(float(depth), 2),
                "height": round(float(height), 2),
                "model_file": rel_path,
                "format": "gltf" if f.lower().endswith(".gltf") else "glb",
                "license": "CC0",
                "source": "ArchGen Curated Asset Library",
                "source_url": "https://cgtrader.com",
                "tags": [t for t in tags if t and t != "general"],
            }

            meta_filename = f"{asset_id}.json"
            meta_filepath = os.path.join(METADATA_DIR, meta_filename)

            with open(meta_filepath, "w", encoding="utf-8") as out_f:
                json.dump(meta_content, out_f, indent=2)

            generated += 1

    print(f"[CATALOG] Successfully scanned and generated {generated} asset metadata files in {METADATA_DIR}")


if __name__ == "__main__":
    generate_all_metadata()
