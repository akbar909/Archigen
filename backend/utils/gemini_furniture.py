"""Furniture asset name normalization."""

from utils.gemini_schema import VALID_FURNITURE_ASSETS


FURNITURE_SYNONYMS: dict[str, str] = {
    "shower": "shower",
    "shower_stall": "shower",
    "shower_cabin": "shower",
    "shower_enclosure": "shower",
    "walk_in_shower": "shower",
    "tub": "bathtub",
    "bath": "bathtub",
    "bathtub": "bathtub",
    "jacuzzi": "bathtub",
    "soaking_tub": "bathtub",
    "washbasin": "bathroom_sink",
    "basin": "bathroom_sink",
    "sink": "bathroom_sink",
    "vanity": "bathroom_sink",
    "bathroom_vanity": "bathroom_sink",
    "lavatory": "bathroom_sink",
    "commode": "toilet",
    "wc": "toilet",
    "water_closet": "toilet",
    "toilet_seat": "toilet",
    "couch": "sofa",
    "sectional": "sofa",
    "sofa_3seater": "sofa",
    "chesterfield": "sofa",
    "loveseat": "sofa",
    "tv": "tv_cabinet",
    "tv_unit": "tv_cabinet",
    "tv_stand": "tv_cabinet",
    "television": "tv_cabinet",
    "media_console": "tv_cabinet",
    "entertainment_center": "tv_cabinet",
    "fridge": "refrigerator",
    "freezer": "refrigerator",
    "table": "dining_table",
    "dinner_table": "dining_table",
    "counter": "kitchen_island",
    "kitchen_counter": "kitchen_island",
    "island": "kitchen_island",
    "breakfast_bar": "kitchen_island",
    "cabinet": "kitchen_cabinet",
    "stove": "microwave",
    "oven": "microwave",
    "cooktop": "microwave",
    "closet": "wardrobe",
    "cupboard": "wardrobe",
    "dresser": "wardrobe",
    "wardrobe_closet": "wardrobe",
    "lamp": "floor_lamp",
    "standing_lamp": "floor_lamp",
    "light": "floor_lamp",
    "night_stand": "nightstand",
    "bedside_table": "nightstand",
    "bedside": "nightstand",
    "desk_chair": "chair",
    "office_chair": "chair",
    "arm_chair": "armchair",
    "lounge_chair": "armchair",
    "recliner": "armchair",
    "stairs": "staircase",
    "stairway": "staircase",
    "steps": "staircase",
}

def normalize_furniture_asset(raw_asset: str, room_type: str = "") -> str:
    """Map any LLM raw furniture asset name to a validated canonical catalog asset name."""
    if not raw_asset or not isinstance(raw_asset, str):
        return "chair"

    clean = raw_asset.strip().lower().replace("-", "_").replace(" ", "_")
    valid_set = set(VALID_FURNITURE_ASSETS) | {"staircase", "shower"}

    # 1. Exact match in valid assets
    if clean in valid_set:
        return clean

    # 2. Known synonym dictionary
    if clean in FURNITURE_SYNONYMS:
        syn = FURNITURE_SYNONYMS[clean]
        if syn in valid_set:
            return syn

    # 3. Substring matching
    if "shower" in clean:
        return "shower"
    if "bath" in clean or "tub" in clean:
        return "bathtub"
    if "bed" in clean:
        return "bed"
    if "sofa" in clean or "couch" in clean:
        return "sofa"
    if "toilet" in clean or "commode" in clean or "wc" in clean:
        return "toilet"
    if "sink" in clean or "basin" in clean or "vanity" in clean:
        if "kitchen" in room_type.lower():
            return "kitchen_sink"
        return "bathroom_sink"
    if "lamp" in clean or "light" in clean:
        return "floor_lamp"
    if "tv" in clean:
        return "tv_cabinet"
    if "fridge" in clean or "refrigerator" in clean:
        return "refrigerator"
    if "wardrobe" in clean or "closet" in clean or "cupboard" in clean:
        return "wardrobe"
    if "nightstand" in clean or "bedside" in clean:
        return "nightstand"
    if "desk" in clean:
        return "desk"
    if "chair" in clean:
        return "chair"
    if "table" in clean:
        if "coffee" in clean:
            return "coffee_table"
        return "dining_table"
    if "island" in clean or "counter" in clean:
        return "kitchen_island"
    if "cabinet" in clean:
        return "kitchen_cabinet"
    if "stair" in clean:
        return "staircase"

    # 4. Fallback based on room type
    r_lower = room_type.lower()
    if "bath" in r_lower:
        return "bathroom_sink"
    if "bed" in r_lower:
        return "nightstand"
    if "kitchen" in r_lower:
        return "kitchen_cabinet"
    if "living" in r_lower or "lounge" in r_lower:
        return "armchair"

    return "chair"

