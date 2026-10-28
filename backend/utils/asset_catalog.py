"""Browser-ready catalog of the assets synchronized to the ArchGen S3 bucket."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

from config import AWS_S3_BUCKET, AWS_S3_PUBLIC_BASE_URL
from utils.s3_storage import generate_presigned_url, get_s3_client


BACKEND_ROOT = Path(__file__).resolve().parents[1]
BLENDER_ROOT = BACKEND_ROOT.parent / "blender"
ASSET_ROOT = BLENDER_ROOT / "assets"
METADATA_ROOT = BLENDER_ROOT / "metadata"
# Browser swaps must be self-contained. Standalone .gltf files can reference
# sibling buffers/textures that do not inherit the parent object's signed URL.
MODEL_EXTENSIONS = {".glb"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_INVENTORY_TTL_SECONDS = 300
_FAILURE_RETRY_SECONDS = 60
_inventory_lock = Lock()
_inventory_keys: list[str] = []
_inventory_refresh_at = 0.0


def _friendly_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("-", "_").split("_") if part)


def _classification(relative_key: str) -> tuple[str, str]:
    key = relative_key.lower().replace("\\", "/")
    if 'curtains_blinds/' in key:
        return 'curtain', 'curtain'
    if 'architecture/ceilings/' in key or 'lighting/ceiling_lights/' in key:
        return 'ceiling_asset', 'ceiling_light'
    if 'roof' in key and key.endswith('.glb'):
        return 'roof_asset', 'roof'
    if key.startswith("textures/walls/"):
        return "wall_finish", "wall"
    if key.startswith("textures/floors/"):
        return "floor_finish", "floor"
    if key.startswith("textures/grounds/"):
        return "ground_finish", "ground"
    if "architecture/walls/designs/" in key:
        return "wall_panel", "wall_panel"
    if any(token in key for token in (
        "decorations/wall_art/", "decorations/mirrors/", "decorations/clocks/",
        "lighting/wall_sconces/",
    )):
        return "wall_decor", "wall_decor"
    if "decorations/carpets_rugs/" in key:
        return "floor_overlay", "rug"
    if key.startswith("furniture/outdoor/"):
        return "ground_decor", "outdoor"

    mappings = (
        ("dining_chairs/", "dining_chair"), ("dining_tables/", "dining_table"),
        ("coffee_tables/", "coffee_table"), ("side_tables/", "side_table"),
        ("armchairs/", "armchair"), ("sofas/", "sofa"), ("beds/", "bed"),
        ("nightstands/", "nightstand"), ("wardrobes/", "wardrobe"),
        ("dressers/", "dresser"), ("vanity_tables/", "vanity_table"),
        ("desks/", "desk"), ("office_chairs/", "office_chair"),
        ("bookshelves/", "bookshelf"), ("tv_units/", "tv_unit"),
        ("islands/", "kitchen_island"), ("cabinets_base/", "kitchen_cabinet"),
        ("bar_stools/", "bar_stool"), ("refrigerator", "refrigerator"),
        ("toilets/", "toilet"), ("bathtubs/", "bathtub"),
        ("showers/", "shower"), ("vanities/", "bathroom_sink"),
        ("floor_lamps/", "floor_lamp"), ("ceiling_lights/", "ceiling_light"),
        ("garage/car", "vehicle"),
    )
    for token, category in mappings:
        if token in key:
            return "furniture", category
    if key.startswith(("furniture/", "appliances/")):
        basename = Path(key).stem
        return "furniture", basename.rsplit("_", 1)[0]
    return "other", "other"


@lru_cache(maxsize=1)
def _metadata_by_id() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not METADATA_ROOT.is_dir():
        return result
    for path in METADATA_ROOT.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get('is_template') or path.name.endswith('.schema.json'):
            continue
        asset_id = str(payload.get("id") or path.stem)
        result[asset_id.lower()] = payload
    return result


def _entry(key: str, source: str) -> dict[str, Any] | None:
    normalized = key.replace("\\", "/").lstrip("/")
    relative = normalized[len("assets/"):] if normalized.startswith("assets/") else normalized
    suffix = Path(relative).suffix.lower()
    if suffix not in MODEL_EXTENSIONS | IMAGE_EXTENSIONS:
        return None
    group, category = _classification(relative)
    if group == "other":
        return None
    asset_id = Path(relative).stem
    metadata = _metadata_by_id().get(asset_id.lower(), {})
    mounting = metadata.get('mounting', {})
    if group == 'wall_decor' and mounting.get('surface') in {'floor', 'tabletop'}:
        group = 'furniture'
        category = 'floor_mirror' if mounting['surface'] == 'floor' else 'table_clock'
    audit = _audit_by_path().get(f'assets/{relative}') or next(
        (v for p, v in _audit_by_path().items() if Path(p).stem.lower() == asset_id.lower()), {})
    defaults = {
        'nightstand': (0.55, 0.5, 0.65), 'side_table': (0.6, 0.6, 0.65),
        'dining_chair': (0.5, 0.55, 0.95), 'curtain': (1.8, 0.25, 2.3),
        'ceiling_light': (1.2, 1.2, 0.65),
        'table_clock': (0.18, 0.12, 0.22), 'floor_mirror': (0.65, 0.4, 1.65),
    }
    fallback = defaults.get(category, (1.0, 0.08 if group.startswith('wall_') else 1.0, 1.0))
    # A number of legacy records mistakenly classify nightstands as beds.
    trusted = metadata if metadata.get('category') == category else {}
    dimensions = {
        "width": float(trusted.get("width") or fallback[0]),
        "depth": float(trusted.get("depth") or fallback[1]),
        "height": float(trusted.get("height") or fallback[2]),
    }
    if 'with_chairs' in asset_id.lower():
        dimensions = {'width': 2.6, 'depth': 2.6, 'height': 1.1}
    raw = audit.get('dimensions', {})
    yaw = float(metadata.get('canonical_yaw_offset_deg') or 0)
    pitch = 90 if '/fans/' in relative and raw.get('depth', 1) < min(raw.get('height', 0), raw.get('width', 0)) * 0.6 else 0
    # Bounding boxes cannot distinguish a decorated front from its blank back,
    # and a projecting lamp can be deeper than it is wide. Use reviewed axes.
    if mounting.get('orientation_verified') and mounting.get('up_axis') == '+y':
        yaw = {'+z': 0, '-z': 180, '+x': -90, '-x': 90}.get(mounting.get('front_axis'), yaw)
    if raw and all(raw.get(k, 0) > 0 for k in dimensions):
        oriented = dict(raw)
        if pitch:
            oriented['height'], oriented['depth'] = raw['depth'], raw['height']
        if abs(yaw % 180) > 0.001:
            oriented['width'], oriented['depth'] = raw['depth'], raw['width']
        factor = min(dimensions[k] / oriented[k] for k in dimensions if k != 'depth' or group not in {'wall_decor', 'wall_panel', 'curtain'})
        dimensions = {k: round(oriented[k] * factor, 5) for k in dimensions}
    return {
        "id": asset_id,
        "asset_id": asset_id,
        "name": metadata.get("name") or _friendly_name(asset_id),
        "group": group,
        "category": category,
        "kind": "model" if suffix in MODEL_EXTENSIONS else "texture",
        "s3_key": f"assets/{relative}",
        "relative_path": relative,
        "dimensions": dimensions,
        "source": source,
        "content_hash": audit.get('sha256'),
        "canonical_yaw_offset_deg": yaw,
        "canonical_pitch_offset_deg": pitch,
        "mounting": mounting,
        "is_assembly": 'with_chairs' in asset_id.lower(),
    }


@lru_cache(maxsize=1)
def _audit_by_path():
    try:
        report = json.loads((BLENDER_ROOT / 'asset-audit.json').read_text(encoding='utf-8'))
        return {m['path']: m for m in report['models'] if 'error' not in m}
    except (OSError, ValueError, KeyError):
        return {}


def _s3_keys() -> list[str]:
    global _inventory_keys, _inventory_refresh_at
    # Serialize refreshes so concurrent browser requests share one listing.
    with _inventory_lock:
        if monotonic() < _inventory_refresh_at:
            return list(_inventory_keys)
        try:
            client = get_s3_client(catalog=True)
            if not client or not AWS_S3_BUCKET:
                return []
            keys: list[str] = []
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=AWS_S3_BUCKET, Prefix="assets/"):
                keys.extend(
                    str(obj.get("Key")) for obj in page.get("Contents", [])
                    if obj.get("Key") and not str(obj.get("Key")).endswith("/")
                )
        except Exception as exc:
            print(f"[WARN] Failed to list S3 asset catalog; retrying in {_FAILURE_RETRY_SECONDS}s: {exc}")
            _inventory_refresh_at = monotonic() + _FAILURE_RETRY_SECONDS
            return list(_inventory_keys)
        # Only replace a complete inventory; a failed later page must not
        # discard the last known good catalog.
        _inventory_keys = keys
        _inventory_refresh_at = monotonic() + _INVENTORY_TTL_SECONDS
        return list(keys)


def _local_keys() -> list[str]:
    if not ASSET_ROOT.is_dir():
        return []
    return [
        f"assets/{path.relative_to(ASSET_ROOT).as_posix()}"
        for path in ASSET_ROOT.rglob("*") if path.is_file()
    ]


def list_uploaded_assets() -> tuple[list[dict[str, Any]], str]:
    """Return actual S3 inventory, falling back to its synchronized local cache."""
    try:
        keys = _s3_keys()
    except Exception as exc:
        print(f"[WARN] Failed to list S3 asset catalog: {exc}")
        keys = []
    source = "s3" if keys else "local_sync"
    if not keys:
        keys = _local_keys()
    raw_entries = [entry for key in keys if (entry := _entry(key, source))]
    # Older uploads include convenience copies such as
    # furniture/dining_room/dining_chair_001.glb alongside the curated
    # dining_chairs/dining_chair_001.glb. Show each uploaded asset identity
    # once and prefer the deeper canonical catalog path.
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in raw_entries:
        identity = entry.get('content_hash') or entry['id'].lower()
        current = unique.get(identity)
        if current is None or entry["relative_path"].count("/") > current["relative_path"].count("/"):
            unique[identity] = entry
    entries = list(unique.values())
    entries.sort(key=lambda item: (item["group"], item["category"], item["name"]))
    return entries, source


def browser_url(entry: dict[str, Any], local_url: str) -> str:
    if entry.get("source") == "s3":
        # Textures must work even when the CDN behavior only exposes GLB keys.
        if AWS_S3_PUBLIC_BASE_URL and entry.get('kind') != 'texture':
            from urllib.parse import quote
            return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{quote(entry['s3_key'].lstrip('/'))}"
        return generate_presigned_url(entry["s3_key"]) or ""
    return local_url

