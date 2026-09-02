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
        """Finds matching furniture metadata based on query criteria."""
        if preferred_id and preferred_id in self.catalog:
            return self.catalog[preferred_id]

        for item_id, meta in self.catalog.items():
            if meta.get("category") == category:
                if room is None or meta.get("room") == room or meta.get("room") == "general":
                    return meta

        # Fallback: any asset matching category
        for item_id, meta in self.catalog.items():
            if meta.get("category") == category:
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
    
    # Set coordinates and rotation
    obj.location = (position[0], position[1], position[2])
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation_deg))

    # Attach metadata
    import_asset.attach_metadata_properties(obj, asset_meta)

    # TODO: Implement clearance check and collision resolution
    # check_clearance(obj, min_clearance_meters=0.5)

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

    for req in reqs:
        category = req.get("category")
        preferred_id = req.get("preferred_id")
        pos = req.get("position", [0.0, 0.0, 0.0])
        rot = req.get("rotation_deg", 0.0)

        meta = catalog.find_asset(category=category, room=room_type, preferred_id=preferred_id)
        if meta:
            obj = place_furniture_item(meta, position=pos, rotation_deg=rot, base_blender_dir=base_blender_dir)
            placed_objects.append(obj)
        else:
            print(f"[INFO] No asset found for category '{category}' in room '{room_type}'.")
            # TODO: Generate procedural placeholder or skip

    return placed_objects


if __name__ == "__main__":
    print("ArchGen Furniture Placement Module loaded.")
