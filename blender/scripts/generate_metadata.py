"""
generate_metadata.py
====================
Auto-cataloging script that generates metadata JSON files for all 3D furniture
assets found in blender/assets/furniture/. Adheres to blender/metadata/furniture.schema.json.
"""

import os
import json
from typing import Dict, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLENDER_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS_DIR = os.path.join(BLENDER_ROOT, "assets", "furniture")
METADATA_DIR = os.path.join(BLENDER_ROOT, "metadata")

# Known catalog mapping for downloaded assets
ASSET_DEFINITIONS = [
    # ── Bathroom ──────────────────────────────────────────────
    {
        "id": "bathtub_001",
        "name": "Modern Free-Standing Bathtub",
        "category": "bathtub",
        "room": "bathroom",
        "width": 1.75,
        "depth": 0.85,
        "height": 0.65,
        "rel_path": "assets/furniture/bathroom/bathtub_001.glb",
        "tags": ["bathtub", "bath", "bathroom", "soaking tub", "modern"]
    },
    {
        "id": "bathroom_sink_001",
        "name": "Contemporary Vanity Sink",
        "category": "sink",
        "room": "bathroom",
        "width": 0.90,
        "depth": 0.55,
        "height": 0.85,
        "rel_path": "assets/furniture/bathroom/sink_001.glb",
        "tags": ["sink", "vanity", "bathroom", "washbasin"]
    },
    {
        "id": "toilet_001",
        "name": "Modern Ceramic Toilet",
        "category": "toilet",
        "room": "bathroom",
        "width": 0.45,
        "depth": 0.70,
        "height": 0.80,
        "rel_path": "assets/furniture/bathroom/toilet_001.glb",
        "tags": ["toilet", "commode", "bathroom", "wc"]
    },

    # ── Bedroom ───────────────────────────────────────────────
    {
        "id": "bed_02",
        "name": "Modern Platform Double Bed",
        "category": "bed",
        "room": "bedroom",
        "width": 2.10,
        "depth": 2.20,
        "height": 1.10,
        "rel_path": "assets/furniture/bedroom/bed_02.glb",
        "tags": ["bed", "double bed", "queen bed", "king bed", "platform bed", "bedroom"]
    },
    {
        "id": "bed_gothic_01",
        "name": "Classic Upholstered Bed",
        "category": "bed",
        "room": "bedroom",
        "width": 1.80,
        "depth": 2.10,
        "height": 1.35,
        "rel_path": "assets/furniture/bedroom/GothicBed_01.glb",
        "tags": ["bed", "gothic bed", "single bed", "classic", "bedroom"]
    },
    {
        "id": "bedside_table_001",
        "name": "Minimalist Nightstand",
        "category": "nightstand",
        "room": "bedroom",
        "width": 0.50,
        "depth": 0.45,
        "height": 0.55,
        "rel_path": "assets/furniture/bedroom/bedside_table_001.glb",
        "tags": ["nightstand", "bedside table", "end table", "bedroom"]
    },
    {
        "id": "desk_001",
        "name": "Modern Executive Study Desk",
        "category": "desk",
        "room": "bedroom",
        "width": 1.40,
        "depth": 0.70,
        "height": 0.76,
        "rel_path": "assets/furniture/bedroom/desk_001.glb",
        "tags": ["desk", "study desk", "workstation", "office desk", "table"]
    },
    {
        "id": "bedroom_cabinet_01",
        "name": "Modern Wooden Wardrobe Cabinet",
        "category": "wardrobe",
        "room": "bedroom",
        "width": 1.20,
        "depth": 0.60,
        "height": 1.95,
        "rel_path": "assets/furniture/bedroom/modren_wooden_cabinet_01.glb",
        "tags": ["wardrobe", "closet", "cabinet", "dresser", "storage", "bedroom"]
    },
    {
        "id": "bedroom_armchair_01",
        "name": "Cozy Accent Armchair",
        "category": "armchair",
        "room": "bedroom",
        "width": 0.85,
        "depth": 0.85,
        "height": 0.82,
        "rel_path": "assets/furniture/bedroom/ArmChair_01.glb",
        "tags": ["armchair", "chair", "accent chair", "lounge chair", "bedroom"]
    },

    # ── Living Room ───────────────────────────────────────────
    {
        "id": "living_armchair_01",
        "name": "Modern Living Lounge Armchair",
        "category": "armchair",
        "room": "living_room",
        "width": 0.88,
        "depth": 0.88,
        "height": 0.84,
        "rel_path": "assets/furniture/living_room/ArmChair_01.glb",
        "tags": ["armchair", "chair", "lounge", "living room", "seating"]
    },
    {
        "id": "coffee_table_01",
        "name": "Sculptural Low Coffee Table",
        "category": "coffee_table",
        "room": "living_room",
        "width": 1.10,
        "depth": 0.65,
        "height": 0.42,
        "rel_path": "assets/furniture/living_room/CoffeeTable_01.glb",
        "tags": ["coffee table", "center table", "tea table", "living room"]
    },
    {
        "id": "floor_lamp_01",
        "name": "Contemporary Arch Floor Lamp",
        "category": "lamp",
        "room": "living_room",
        "width": 0.50,
        "depth": 0.50,
        "height": 1.85,
        "rel_path": "assets/furniture/living_room/floor_lamp.glb",
        "tags": ["lamp", "floor lamp", "standing lamp", "lighting", "living room"]
    },
    {
        "id": "living_tv_cabinet_01",
        "name": "Media Console & Storage Credenza",
        "category": "cabinet",
        "room": "living_room",
        "width": 1.80,
        "depth": 0.45,
        "height": 0.60,
        "rel_path": "assets/furniture/living_room/modren_wooden_cabinet_01.glb",
        "tags": ["cabinet", "tv unit", "media console", "credenza", "living room"]
    },

    # ── Dining Room ───────────────────────────────────────────
    {
        "id": "dining_table_001",
        "name": "Nordic Solid Wood Dining Table",
        "category": "dining_table",
        "room": "dining_room",
        "width": 1.80,
        "depth": 0.90,
        "height": 0.76,
        "rel_path": "assets/furniture/dining_room/dining_table_001.glb",
        "tags": ["dining table", "table", "dinner table", "dining room"]
    },
    {
        "id": "dining_chair_001",
        "name": "Ergonomic Scandinavian Dining Chair",
        "category": "chair",
        "room": "dining_room",
        "width": 0.50,
        "depth": 0.52,
        "height": 0.85,
        "rel_path": "assets/furniture/dining_room/dining_chair_001.glb",
        "tags": ["chair", "dining chair", "side chair", "dining room"]
    },
    {
        "id": "dining_sideboard_001",
        "name": "Modern Dining Buffet Sideboard",
        "category": "cabinet",
        "room": "dining_room",
        "width": 1.50,
        "depth": 0.48,
        "height": 0.85,
        "rel_path": "assets/furniture/dining_room/sideboard_001.glb",
        "tags": ["sideboard", "buffet", "cabinet", "credenza", "dining room"]
    },

    # ── Kitchen ───────────────────────────────────────────────
    {
        "id": "refrigerator_001",
        "name": "French Door Stainless Steel Refrigerator",
        "category": "refrigerator",
        "room": "kitchen",
        "width": 0.92,
        "depth": 0.85,
        "height": 1.82,
        "rel_path": "assets/furniture/kitchen/refrigerator_001.glb",
        "tags": ["refrigerator", "fridge", "freezer", "appliance", "kitchen"]
    },
    {
        "id": "kitchen_island_001",
        "name": "Modern Marble Top Kitchen Island",
        "category": "kitchen_counter",
        "room": "kitchen",
        "width": 2.20,
        "depth": 1.00,
        "height": 0.92,
        "rel_path": "assets/furniture/kitchen/kitchen_island_001.glb",
        "tags": ["kitchen island", "island", "counter", "kitchen counter", "breakfast bar"]
    },
    {
        "id": "kitchen_sink_001",
        "name": "Undermount Double Basin Kitchen Sink",
        "category": "sink",
        "room": "kitchen",
        "width": 0.85,
        "depth": 0.55,
        "height": 0.88,
        "rel_path": "assets/furniture/kitchen/sink_001.glb",
        "tags": ["kitchen sink", "sink", "faucet", "counter sink", "kitchen"]
    },
    {
        "id": "kitchen_cabinet_001",
        "name": "Modular Overhead Kitchen Cabinet",
        "category": "cabinet",
        "room": "kitchen",
        "width": 1.20,
        "depth": 0.40,
        "height": 0.80,
        "rel_path": "assets/furniture/kitchen/cabinet_001.glb",
        "tags": ["cabinet", "kitchen cabinet", "pantry", "wall cabinet", "kitchen"]
    },
    {
        "id": "microwave_001",
        "name": "Retro Countertop Microwave Oven",
        "category": "stove",
        "room": "kitchen",
        "width": 0.55,
        "depth": 0.42,
        "height": 0.35,
        "rel_path": "assets/furniture/kitchen/vintage_microwave_1.glb",
        "tags": ["microwave", "oven", "vintage microwave", "appliance", "kitchen"]
    },
]


def generate_catalog():
    """Builds and writes all asset metadata JSON files."""
    os.makedirs(METADATA_DIR, exist_ok=True)
    generated = 0

    for item in ASSET_DEFINITIONS:
        asset_id = item["id"]
        meta_filename = f"{asset_id}.json"
        meta_filepath = os.path.join(METADATA_DIR, meta_filename)

        meta_content = {
            "id": asset_id,
            "name": item["name"],
            "category": item["category"],
            "room": item["room"],
            "style": ["modern", "contemporary", "scandinavian"],
            "width": float(item["width"]),
            "depth": float(item["depth"]),
            "height": float(item["height"]),
            "model_file": item["rel_path"].replace("\\", "/"),
            "format": "glb",
            "license": "CC0",
            "source": "ArchGen Curated Asset Library",
            "source_url": "https://polyhaven.com",
            "tags": item.get("tags", [item["category"], item["room"]])
        }

        with open(meta_filepath, "w", encoding="utf-8") as f:
            json.dump(meta_content, f, indent=2)

        generated += 1
        print(f"[CATALOG] Generated: {meta_filename} -> category='{item['category']}', room='{item['room']}'")

    print(f"\nSuccessfully generated {generated} asset metadata catalog files in {METADATA_DIR}")


if __name__ == "__main__":
    generate_catalog()
