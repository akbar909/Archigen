"""
place_furniture.py
==================
Module responsible for locating, instantiating, and arranging furniture assets
inside generated rooms according to architectural rules, coordinates, and metadata.

Designed for Headless Blender execution (bpy).
"""

import os
import sys
import json
import math
from typing import Optional, Dict, Any, List

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None
    mathutils = None

# Allow importing helper scripts in the same directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    import import_asset
except ImportError:
    import_asset = None

try:
    import s3_asset_resolver
except ImportError:
    s3_asset_resolver = None


class FurnitureCatalog:
    """Manages index of available furniture assets and their metadata."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.metadata_dir = os.path.join(base_path, "metadata")
        self.assets_dir = os.path.join(base_path, "assets", "furniture")
        self.catalog: Dict[str, Dict[str, Any]] = {}
        self.load_catalog()

    def load_catalog(self) -> None:
        """Scans metadata directory for all asset .json files."""
        if not os.path.exists(self.metadata_dir):
            return

        for fname in os.listdir(self.metadata_dir):
            if fname.endswith(".json") and not fname.endswith(".schema.json"):
                fpath = os.path.join(self.metadata_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "id" in data:
                            self.catalog[data["id"]] = data
                except Exception as e:
                    print(f"[WARN] Failed to parse metadata file {fname}: {e}")

    def find_asset(self, category: str, room: Optional[str] = None, preferred_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Finds matching furniture metadata based on query criteria with synonym normalization."""
        if preferred_id and preferred_id in self.catalog:
            return self.catalog[preferred_id]

        cat_clean = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")

        # Synonyms dictionary
        synonyms = {
            "double_bed": "bed",
            "single_bed": "bed",
            "king_bed": "bed",
            "queen_bed": "bed",
            "couch": "sofa",
            "sectional": "sofa",
            "lounge_chair": "armchair",
            "accent_chair": "armchair",
            "side_chair": "chair",
            "dining_chair": "chair",
            "desk_chair": "chair",
            "center_table": "coffee_table",
            "tea_table": "coffee_table",
            "table": "coffee_table",
            "dinner_table": "dining_table",
            "study_desk": "desk",
            "workstation": "desk",
            "office_desk": "desk",
            "bedside_table": "nightstand",
            "end_table": "nightstand",
            "dresser": "wardrobe",
            "closet": "wardrobe",
            "tv_unit": "cabinet",
            "media_console": "cabinet",
            "credenza": "cabinet",
            "sideboard": "cabinet",
            "kitchen_cabinet": "cabinet",
            "fridge": "refrigerator",
            "freezer": "refrigerator",
            "kitchen_sink": "sink",
            "bathroom_sink": "sink",
            "washbasin": "sink",
            "vanity": "sink",
            "island": "kitchen_counter",
            "kitchen_island": "kitchen_counter",
            "counter": "kitchen_counter",
            "breakfast_bar": "kitchen_counter",
            "oven": "stove",
            "microwave": "stove",
            "tub": "bathtub",
            "bath": "bathtub",
            "commode": "toilet",
            "wc": "toilet",
            "floor_lamp": "lamp",
            "standing_lamp": "lamp",
        }

        normalized_cat = synonyms.get(cat_clean, cat_clean)

        # 1. Exact match on category + room
        for item_id, meta in self.catalog.items():
            m_cat = meta.get("category", "")
            m_room = meta.get("room", "")
            if (m_cat == normalized_cat or m_cat == cat_clean):
                if room is None or m_room == room or m_room == "general":
                    return meta

        # 2. Match on category alone (any room)
        for item_id, meta in self.catalog.items():
            m_cat = meta.get("category", "")
            if m_cat == normalized_cat or m_cat == cat_clean:
                return meta

        # 3. Match against tags
        for item_id, meta in self.catalog.items():
            tags = [str(t).lower() for t in meta.get("tags", [])]
            if normalized_cat in tags or cat_clean in tags:
                return meta

        return None


def place_furniture_item(
    asset_meta: Dict[str, Any],
    position: List[float],
    rotation_deg: float = 0.0,
    base_blender_dir: Optional[str] = None
) -> Any:
    """
    Imports and positions a furniture model in the scene.

    Args:
        asset_meta: Dictionary containing asset metadata.
        position: [x, y, z] world coordinates in meters.
        rotation_deg: Rotation angle around Z-axis (yaw) in degrees.
        base_blender_dir: Root directory of blender workspace.

    Returns:
        The placed Blender root object.
    """
    if bpy is None or import_asset is None:
        raise RuntimeError("Blender environment or import_asset module is not available.")

    rel_model_path = asset_meta.get("model_file", "")
    if base_blender_dir:
        abs_model_path = os.path.join(base_blender_dir, rel_model_path)
    else:
        abs_model_path = rel_model_path

    # Try downloading from S3 if missing locally
    if not os.path.exists(abs_model_path) and s3_asset_resolver is not None:
        downloaded = s3_asset_resolver.download_asset_if_missing(rel_model_path, base_blender_dir=base_blender_dir)
        if downloaded and os.path.exists(downloaded):
            abs_model_path = downloaded

    if not os.path.exists(abs_model_path):
        print(f"[WARN] 3D Model file not found: {abs_model_path}. Creating a placeholder cube.")
        # Create a placeholder bounding box representation
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(position[0], position[1], position[2] + (asset_meta.get("height", 1.0) / 2.0))
        )
        obj = bpy.context.active_object
        obj.name = f"placeholder_{asset_meta.get('id', 'furniture')}"
        obj.scale = (
            asset_meta.get("width", 1.0),
            asset_meta.get("depth", 1.0),
            asset_meta.get("height", 1.0)
        )
        return obj

    # Import the actual 3D model
    obj = import_asset.load_model(abs_model_path, name_prefix=asset_meta.get("id"))

    # Scale model accurately to match metadata target dimensions (e.g. standard bed 2.1m x 2.2m x 1.1m)
    target_w = float(asset_meta.get("width") or 0.0)
    target_d = float(asset_meta.get("depth") or 0.0)
    target_h = float(asset_meta.get("height") or 0.0)

    if target_w > 0 and target_d > 0 and target_h > 0:
        cur_w, cur_d, cur_h = import_asset.get_bounding_dimensions(obj)
        if cur_w > 0.01 and cur_d > 0.01 and cur_h > 0.01:
            sx = target_w / cur_w
            sy = target_d / cur_d
            sz = target_h / cur_h
            obj.scale = (obj.scale.x * sx, obj.scale.y * sy, obj.scale.z * sz)

    # Set coordinates and rotation
    obj.location = (position[0], position[1], position[2])
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation_deg))

    # Ensure furniture sits exactly on top of the floor slab (position[2])
    if bpy:
        try:
            bpy.context.view_layer.update()
            mesh_objs = [o for o in [obj] + list(obj.children_recursive) if o.type == 'MESH']
            if mesh_objs:
                actual_min_z = min(
                    (o.matrix_world @ mathutils.Vector(corner)).z
                    for o in mesh_objs
                    for corner in o.bound_box
                )
                z_diff = position[2] - actual_min_z
                if abs(z_diff) > 0.005:
                    obj.location.z += z_diff
        except Exception as e:
            print(f"[WARN] Failed to refine floor contact for {obj.name}: {e}")

    # Attach metadata
    import_asset.attach_metadata_properties(obj, asset_meta)

    return obj


def populate_room_furniture(
    room_data: Dict[str, Any],
    catalog: FurnitureCatalog,
    base_blender_dir: str
) -> List[Any]:
    """
    Places all requested furniture items for a given room.

    Args:
        room_data: Room dictionary from house layout JSON.
        catalog: Loaded FurnitureCatalog instance.
        base_blender_dir: Path to blender folder root.

    Returns:
        List of placed Blender objects.
    """
    placed_objects = []
    room_type = room_data.get("type", "general")
    reqs = room_data.get("furniture_requirements", [])

    bounds = room_data.get("bounds", {})
    rx = float(bounds.get("x", 0.0))
    ry = float(bounds.get("y", 0.0))
    rw = float(bounds.get("width", 4.0))
    rd = float(bounds.get("depth", 4.0))

    for req in reqs:
        category = req.get("category")
        preferred_id = req.get("preferred_id")
        pos = list(req.get("position", [0.0, 0.0, 0.0]))
        rot = req.get("rotation_deg", 0.0)

        meta = catalog.find_asset(category=category, room=room_type, preferred_id=preferred_id)
        if meta:
            # Deterministic clearance & boundary containment clamp
            item_hw = float(meta.get("width", 0.8)) / 2.0 + 0.10
            item_hd = float(meta.get("depth", 0.8)) / 2.0 + 0.10
            if rw > (item_hw * 2.0) and rd > (item_hd * 2.0):
                clamped_x = max(rx + item_hw, min(rx + rw - item_hw, pos[0]))
                clamped_y = max(ry + item_hd, min(ry + rd - item_hd, pos[1]))
                pos[0] = round(clamped_x, 2)
                pos[1] = round(clamped_y, 2)

            obj = place_furniture_item(meta, position=pos, rotation_deg=rot, base_blender_dir=base_blender_dir)
            placed_objects.append(obj)
        else:
            print(f"[INFO] No asset found for category '{category}' in room '{room_type}'.")

    return placed_objects


if __name__ == "__main__":
    print("ArchGen Furniture Placement Module loaded.")
