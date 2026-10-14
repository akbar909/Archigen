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
from typing import Optional, Dict, Any, List, Tuple

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


FLOOR_CONTACT_CLEARANCE = 0.008
DOOR_APPROACH_DEPTH = 1.15
DOOR_SIDE_CLEARANCE = 0.35
WALL_BACKED_CATEGORIES = {
    "bed", "toilet", "sink", "refrigerator", "wardrobe", "cabinet",
    "desk", "stove", "bathtub", "shower",
}


def _axis_aligned_footprint(
    x: float, y: float, width: float, depth: float, rotation_deg: float,
) -> Tuple[float, float, float, float]:
    angle = math.radians(float(rotation_deg) % 180.0)
    rotated_w = abs(math.cos(angle)) * width + abs(math.sin(angle)) * depth
    rotated_d = abs(math.sin(angle)) * width + abs(math.cos(angle)) * depth
    return (x - rotated_w / 2.0, y - rotated_d / 2.0, x + rotated_w / 2.0, y + rotated_d / 2.0)


def _rectangles_overlap(
    first: Tuple[float, float, float, float],
    second: Tuple[float, float, float, float],
    margin: float = 0.0,
) -> bool:
    return not (
        first[2] + margin <= second[0]
        or first[0] - margin >= second[2]
        or first[3] + margin <= second[1]
        or first[1] - margin >= second[3]
    )


def _opening_xy(opening: Dict[str, Any]) -> Tuple[float, float, float]:
    position = opening.get("position", {})
    if isinstance(position, dict):
        return (
            float(position.get("x", 0.0)),
            float(position.get("y", 0.0)),
            float(position.get("z", 0.0)),
        )
    if isinstance(position, (list, tuple)):
        return (
            float(position[0]) if len(position) > 0 else 0.0,
            float(position[1]) if len(position) > 1 else 0.0,
            float(position[2]) if len(position) > 2 else 0.0,
        )
    return (0.0, 0.0, 0.0)


def _nearest_wall_side(x: float, y: float, rx: float, ry: float, rw: float, rd: float) -> str:
    distances = {
        "south": abs(y - ry),
        "north": abs((ry + rd) - y),
        "west": abs(x - rx),
        "east": abs((rx + rw) - x),
    }
    return min(distances, key=distances.get)


def _wall_facing_rotation(
    category: str,
    position: List[float],
    room_bounds: Dict[str, Any],
    requested_rotation: float,
    anchor_wall: Optional[str] = None,
) -> float:
    """Orient wall-backed objects with their canonical back toward the wall."""
    normalized = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in WALL_BACKED_CATEGORIES and not anchor_wall:
        return float(requested_rotation)
    rx = float(room_bounds.get("x", 0.0))
    ry = float(room_bounds.get("y", 0.0))
    rw = float(room_bounds.get("width", 4.0))
    rd = float(room_bounds.get("depth", 4.0))
    side = str(anchor_wall or "").lower()
    aliases = {"front": "south", "back": "north", "left": "west", "right": "east"}
    side = aliases.get(side, side)
    if side not in {"north", "south", "east", "west"}:
        side = _nearest_wall_side(float(position[0]), float(position[1]), rx, ry, rw, rd)
    return {"north": 0.0, "west": 90.0, "south": 180.0, "east": -90.0}[side]


def _door_clearance_zones(
    room_data: Dict[str, Any], door_openings: Optional[List[Dict[str, Any]]],
) -> List[Tuple[float, float, float, float]]:
    bounds = room_data.get("bounds", {})
    rx = float(bounds.get("x", 0.0))
    ry = float(bounds.get("y", 0.0))
    rw = float(bounds.get("width", 4.0))
    rd = float(bounds.get("depth", 4.0))
    rz = float(bounds.get("z", 0.0))
    room_id = str(room_data.get("id", ""))
    zones = []
    for door in door_openings or []:
        dx, dy, dz = _opening_xy(door)
        if abs(dz - rz) > 0.35:
            continue
        connected = {
            str(value) for value in (door.get("connected_room_ids") or door.get("connected_rooms") or [])
        }
        direct_room = door.get("room_id") or door.get("roomId")
        if direct_room is not None:
            connected.add(str(direct_room))
        on_boundary = (
            rx - 0.3 <= dx <= rx + rw + 0.3
            and ry - 0.3 <= dy <= ry + rd + 0.3
            and min(abs(dx - rx), abs(dx - (rx + rw)), abs(dy - ry), abs(dy - (ry + rd))) <= 0.35
        )
        if room_id not in connected and not on_boundary:
            continue
        side = _nearest_wall_side(dx, dy, rx, ry, rw, rd)
        half_width = float(door.get("width", 0.9)) / 2.0 + DOOR_SIDE_CLEARANCE
        if side == "south":
            zone = (dx - half_width, ry, dx + half_width, min(ry + rd, ry + DOOR_APPROACH_DEPTH))
        elif side == "north":
            zone = (dx - half_width, max(ry, ry + rd - DOOR_APPROACH_DEPTH), dx + half_width, ry + rd)
        elif side == "west":
            zone = (rx, dy - half_width, min(rx + rw, rx + DOOR_APPROACH_DEPTH), dy + half_width)
        else:
            zone = (max(rx, rx + rw - DOOR_APPROACH_DEPTH), dy - half_width, rx + rw, dy + half_width)
        zones.append((max(rx, zone[0]), max(ry, zone[1]), min(rx + rw, zone[2]), min(ry + rd, zone[3])))
    return zones


def _find_clear_position(
    desired: List[float], width: float, depth: float, rotation_deg: float,
    bounds: Dict[str, Any], forbidden: List[Tuple[float, float, float, float]],
    occupied: List[Tuple[float, float, float, float]],
) -> Tuple[List[float], Tuple[float, float, float, float]]:
    rx = float(bounds.get("x", 0.0))
    ry = float(bounds.get("y", 0.0))
    rw = float(bounds.get("width", 4.0))
    rd = float(bounds.get("depth", 4.0))
    raw = _axis_aligned_footprint(0.0, 0.0, width, depth, rotation_deg)
    half_w, half_d = (raw[2] - raw[0]) / 2.0, (raw[3] - raw[1]) / 2.0
    min_x, max_x = rx + half_w + 0.10, rx + rw - half_w - 0.10
    min_y, max_y = ry + half_d + 0.10, ry + rd - half_d - 0.10
    if min_x > max_x or min_y > max_y:
        footprint = _axis_aligned_footprint(desired[0], desired[1], width, depth, rotation_deg)
        return desired, footprint

    desired_x = max(min_x, min(max_x, float(desired[0])))
    desired_y = max(min_y, min(max_y, float(desired[1])))
    candidates = [(desired_x, desired_y)]
    step = 0.25
    x = min_x
    while x <= max_x + 0.001:
        y = min_y
        while y <= max_y + 0.001:
            candidates.append((x, y))
            y += step
        x += step
    candidates.sort(key=lambda value: (value[0] - desired_x) ** 2 + (value[1] - desired_y) ** 2)

    def choose(avoid_occupied: bool) -> Optional[Tuple[float, float, Tuple[float, float, float, float]]]:
        for cx, cy in candidates:
            footprint = _axis_aligned_footprint(cx, cy, width, depth, rotation_deg)
            if any(_rectangles_overlap(footprint, zone, 0.04) for zone in forbidden):
                continue
            if avoid_occupied and any(_rectangles_overlap(footprint, other, 0.12) for other in occupied):
                continue
            return cx, cy, footprint
        return None

    selected = choose(True) or choose(False)
    if selected is None:
        raise RuntimeError(
            "No furniture position preserves the required door-approach clearance "
            f"inside room bounds {bounds}."
        )
    cx, cy, footprint = selected
    return [round(cx, 2), round(cy, 2), desired[2]], footprint


def _settle_on_finished_floor(obj: Any, floor_z: float) -> float:
    """Seat any imported hierarchy from its evaluated world-space mesh bounds."""
    if bpy is None or mathutils is None or obj is None:
        return floor_z
    bpy.context.view_layer.update()
    meshes = [item for item in [obj] + list(obj.children_recursive) if item.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"Asset '{getattr(obj, 'name', 'unknown')}' contains no mesh geometry")
    actual_min_z = min(
        (mesh.matrix_world @ mathutils.Vector(corner)).z
        for mesh in meshes
        for corner in mesh.bound_box
    )
    target_min_z = float(floor_z) + FLOOR_CONTACT_CLEARANCE
    obj.location.z += target_min_z - actual_min_z
    bpy.context.view_layer.update()

    settled_min_z = min(
        (mesh.matrix_world @ mathutils.Vector(corner)).z
        for mesh in meshes
        for corner in mesh.bound_box
    )
    if abs(settled_min_z - target_min_z) > 0.002:
        raise RuntimeError(
            f"Asset '{obj.name}' could not be seated on floor {floor_z:.3f}; "
            f"evaluated bottom is {settled_min_z:.3f}"
        )
    obj["archgen_floor_z"] = float(floor_z)
    obj["archgen_floor_clearance"] = FLOOR_CONTACT_CLEARANCE
    return settled_min_z


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
        _settle_on_finished_floor(root, position[2])
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
        _settle_on_finished_floor(obj, position[2])
        obj["archgen_asset_load_failed"] = True
        obj["archgen_instance_id"] = instance_id or asset_meta.get("id", "furniture")
        return obj

    # Import the actual 3D model
    obj = import_asset.load_model(abs_model_path, name_prefix=f"Furniture_{instance_id or asset_meta.get('id', 'item')}")

    # Normalize the asset's authored horizontal axes before measuring/scaling.
    # This is catalog metadata, not a room- or asset-id code exception. For
    # example, an asset authored with its back along -X needs a -90-degree
    # normalization so its back follows ArchGen's canonical +Y direction.
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

    # Use evaluated post-scale/post-rotation bounds. Metadata origins and GLB
    # wrapper pivots are never trusted for vertical placement.
    _settle_on_finished_floor(obj, position[2])

    # Attach metadata
    import_asset.attach_metadata_properties(obj, asset_meta)
    obj["archgen_instance_id"] = instance_id or asset_meta.get("id", "furniture")
    obj["archgen_asset_load_failed"] = False

    return obj


def populate_room_furniture(
    room_data: Dict[str, Any],
    catalog: FurnitureCatalog,
    base_blender_dir: str,
    door_openings: Optional[List[Dict[str, Any]]] = None,
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
    forbidden_zones = _door_clearance_zones(room_data, door_openings)
    occupied_footprints: List[Tuple[float, float, float, float]] = []

    for req in reqs:
        category = req.get("category")
        preferred_id = req.get("preferred_id")
        pos = list(req.get("position", [0.0, 0.0, 0.0]))
        rot = float(req.get("rotation_deg", 0.0))

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
            rot = _wall_facing_rotation(
                str(meta.get("category") or category or ""),
                pos,
                bounds,
                rot,
                req.get("anchor_wall"),
            )
            # Deterministic clearance & boundary containment clamp
            width = float(meta.get("width", 0.8))
            depth = float(meta.get("depth", 0.8))
            item_forbidden_zones = [] if str(category or "").lower() == "vehicle" else forbidden_zones
            pos, footprint = _find_clear_position(
                pos, width, depth, rot, bounds, item_forbidden_zones, occupied_footprints,
            )

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
            obj["archgen_semantic_rotation_deg"] = float(rot)
            obj["archgen_door_clearance_checked"] = True
            obj.name = f"Furniture_L{room_data.get('floor_level', 0)}_{instance_id}"
            placed_objects.append(obj)
            occupied_footprints.append(footprint)

    return placed_objects


if __name__ == "__main__":
    print("ArchGen Furniture Placement Module loaded.")
