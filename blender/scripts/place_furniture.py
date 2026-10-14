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
            "tv_cabinet": "cabinet",
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
    base_blender_dir: Optional[str] = None,
    instance_id: Optional[str] = None,
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
    if not os.path.isfile(abs_model_path) and rel_model_path and s3_asset_resolver is not None:
        downloaded = s3_asset_resolver.download_asset_if_missing(rel_model_path, base_blender_dir=base_blender_dir)
        if downloaded and os.path.isfile(downloaded):
            abs_model_path = downloaded

    procedural_category = str(asset_meta.get("category") or asset_meta.get("id", "")).lower()
    if not os.path.isfile(abs_model_path) and procedural_category in ("shower", "vehicle", "sofa"):
        width = float(asset_meta.get("width", 0.9))
        depth = float(asset_meta.get("depth", 0.9))
        height = float(asset_meta.get("height", 2.0))
        root = bpy.data.objects.new(f"Furniture_{instance_id or procedural_category}", None)
        bpy.context.scene.collection.objects.link(root)
        root.location = (position[0], position[1], position[2])
        root.rotation_euler = (0.0, 0.0, math.radians(rotation_deg))

        if procedural_category == "shower":
            glass = bpy.data.materials.get("mat_procedural_shower_glass") or bpy.data.materials.new("mat_procedural_shower_glass")
            glass.diffuse_color = (0.65, 0.85, 0.95, 0.24)
            glass.use_nodes = True
            if hasattr(glass, "surface_render_method"):
                glass.surface_render_method = 'DITHERED'
            elif hasattr(glass, "blend_method"):
                glass.blend_method = 'BLEND'
            base = bpy.data.materials.get("mat_procedural_shower_base") or bpy.data.materials.new("mat_procedural_shower_base")
            base.diffuse_color = (0.9, 0.9, 0.88, 1.0)
            parts = [
                ("tray", (0, 0, 0.05), (width, depth, 0.10), base),
                ("back", (0, depth / 2.0, height / 2.0), (width, 0.025, height), glass),
                ("side", (width / 2.0, 0, height / 2.0), (0.025, depth, height), glass),
            ]
        elif procedural_category == "vehicle":
            body = bpy.data.materials.get("mat_procedural_vehicle_body") or bpy.data.materials.new("mat_procedural_vehicle_body")
            body.diffuse_color = (0.12, 0.18, 0.24, 1.0)
            window = bpy.data.materials.get("mat_procedural_vehicle_window") or bpy.data.materials.new("mat_procedural_vehicle_window")
            window.diffuse_color = (0.18, 0.32, 0.42, 1.0)
            parts = [
                ("chassis", (0, 0, height * 0.28), (width, depth, height * 0.45), body),
                ("cabin", (0, depth * 0.05, height * 0.66), (width * 0.78, depth * 0.52, height * 0.42), window),
            ]
        else:
            upholstery = bpy.data.materials.get("mat_procedural_sofa") or bpy.data.materials.new("mat_procedural_sofa")
            upholstery.diffuse_color = (0.30, 0.34, 0.39, 1.0)
            parts = [
                ("base", (0, 0, height * 0.22), (width, depth, height * 0.30), upholstery),
                ("seat", (0, depth * 0.06, height * 0.43), (width * 0.9, depth * 0.72, height * 0.18), upholstery),
                ("back", (0, depth * 0.42, height * 0.69), (width, depth * 0.16, height * 0.62), upholstery),
                ("arm_left", (-width * 0.46, 0, height * 0.52), (width * 0.08, depth, height * 0.48), upholstery),
                ("arm_right", (width * 0.46, 0, height * 0.52), (width * 0.08, depth, height * 0.48), upholstery),
            ]
        for suffix, local_position, dimensions, material in parts:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
            part = bpy.context.active_object
            part.name = f"Furniture_{instance_id or procedural_category}_{suffix}"
            part.parent = root
            part.location = local_position
            part.scale = dimensions
            part.data.materials.append(material)
        bpy.context.view_layer.update()
        mesh_parts = [obj for obj in root.children_recursive if obj.type == 'MESH']
        if mesh_parts:
            actual_min_z = min(
                (obj.matrix_world @ mathutils.Vector(corner)).z
                for obj in mesh_parts for corner in obj.bound_box
            )
            root.location.z += position[2] - actual_min_z
        root["archgen_procedural_fallback"] = True
        root["archgen_instance_id"] = instance_id or procedural_category
        root["archgen_asset_load_failed"] = False
        return root

    if not os.path.isfile(abs_model_path):
        print(f"[WARN] 3D Model file not found: {abs_model_path}. Creating a placeholder cube.")
        # Create a placeholder bounding box representation
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(position[0], position[1], position[2] + (asset_meta.get("height", 1.0) / 2.0))
        )
        obj = bpy.context.active_object
        obj.name = f"Furniture_{instance_id or asset_meta.get('id', 'furniture')}_MISSING_ASSET"
        obj.scale = (
            asset_meta.get("width", 1.0),
            asset_meta.get("depth", 1.0),
            asset_meta.get("height", 1.0)
        )
        obj.rotation_euler = (0.0, 0.0, math.radians(rotation_deg))
        obj["archgen_asset_load_failed"] = True
        obj["archgen_instance_id"] = instance_id or asset_meta.get("id", "furniture")
        return obj

    # Import the actual 3D model
    obj = import_asset.load_model(abs_model_path, name_prefix=f"Furniture_{instance_id or asset_meta.get('id', 'item')}")

    # Normalize the asset's authored horizontal axes before measuring/scaling.
    # This is catalog metadata, not a room- or asset-id code exception. For
    # example, the vanity sink is authored with its back along -X while the
    # architectural convention expects the back along -Y.
    yaw_offset = float(asset_meta.get("canonical_yaw_offset_deg", 0.0) or 0.0)
    if abs(yaw_offset) > 0.001:
        orientation = bpy.data.objects.new(f"{obj.name}_AxisNormalization", None)
        bpy.context.scene.collection.objects.link(orientation)
        orientation.parent = obj
        orientation.location = (0.0, 0.0, 0.0)
        direct_children = [child for child in list(obj.children) if child is not orientation]
        for child in direct_children:
            world = child.matrix_world.copy()
            child.parent = orientation
            child.matrix_world = world
        orientation.rotation_euler = (0.0, 0.0, math.radians(yaw_offset))
        bpy.context.view_layer.update()

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
    obj["archgen_instance_id"] = instance_id or asset_meta.get("id", "furniture")
    obj["archgen_asset_load_failed"] = False

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
            meta = dict(meta)
        else:
            # Preserve inventory and make the failure visible in both the scene
            # and diagnostics instead of silently omitting a requested object.
            print(f"[ERROR] Missing asset mapping for furniture '{req.get('id')}' category '{category}' in room '{room_type}'.")
            meta = {"id": category or "unsupported", "model_file": ""}
        requested_dimensions = req.get("dimensions", {})
        for key in ("width", "depth", "height"):
            if requested_dimensions.get(key) is not None:
                meta[key] = float(requested_dimensions[key])
        if meta:
            # Deterministic clearance & boundary containment clamp
            angle = math.radians(float(rot) % 180.0)
            width = float(meta.get("width", 0.8))
            depth = float(meta.get("depth", 0.8))
            rotated_w = abs(math.cos(angle)) * width + abs(math.sin(angle)) * depth
            rotated_d = abs(math.sin(angle)) * width + abs(math.cos(angle)) * depth
            item_hw = rotated_w / 2.0 + 0.10
            item_hd = rotated_d / 2.0 + 0.10
            if rw > (item_hw * 2.0) and rd > (item_hd * 2.0):
                clamped_x = max(rx + item_hw, min(rx + rw - item_hw, pos[0]))
                clamped_y = max(ry + item_hd, min(ry + rd - item_hd, pos[1]))
                pos[0] = round(clamped_x, 2)
                pos[1] = round(clamped_y, 2)

            instance_id = req.get("instance_id") or req.get("id")
            try:
                obj = place_furniture_item(
                    meta, position=pos, rotation_deg=rot, base_blender_dir=base_blender_dir,
                    instance_id=instance_id,
                )
            except Exception as exc:
                print(f"[ERROR] Asset load failed for furniture '{instance_id}': {exc}; using diagnostic placeholder.")
                fallback = dict(meta)
                fallback["model_file"] = ""
                obj = place_furniture_item(
                    fallback, position=pos, rotation_deg=rot, base_blender_dir=base_blender_dir,
                    instance_id=instance_id,
                )
                obj["archgen_asset_error"] = str(exc)
            obj["archgen_room_id"] = room_data.get("id", "")
            obj.name = f"Furniture_L{room_data.get('floor_level', 0)}_{instance_id}"
            placed_objects.append(obj)

    return placed_objects


if __name__ == "__main__":
    print("ArchGen Furniture Placement Module loaded.")
