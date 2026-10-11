"""
blender_service.py
==================
Client service responsible for communicating with the Headless Blender worker.
Transforms Gemini architectural layout JSON into Blender-compatible specifications,
invokes generation, and retrieves the exported .glb model URL.
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import requests

from config import (
    BLENDER_ENABLED,
    BLENDER_SERVICE_URL,
    BLENDER_TIMEOUT_SECONDS,
)
from utils.s3_storage import resolve_s3_url_to_presigned

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_str: str) -> List[float]:
    """Converts hex color string to normalized RGB list [r, g, b]."""
    hex_str = str(hex_str).lstrip("#")
    if len(hex_str) == 6:
        try:
            return [
                round(int(hex_str[0:2], 16) / 255.0, 3),
                round(int(hex_str[2:4], 16) / 255.0, 3),
                round(int(hex_str[4:6], 16) / 255.0, 3),
            ]
        except ValueError:
            pass
    return [0.8, 0.8, 0.8]


def adapt_gemini_to_blender_layout(
    design_data: Dict[str, Any],
    project_id: Optional[str] = None,
    version_num: int = 1,
) -> Dict[str, Any]:
    """
    Translates Gemini's room/furniture output into the standardized schema
    expected by blender/scripts/generate_house.py.
    """
    house_id = f"proj_{project_id or 'anon'}_v{version_num}_{uuid.uuid4().hex[:6]}"
    style = design_data.get("style", "modern")

    raw_rooms = design_data.get("rooms", [])
    adapted_rooms = []
    collected_doors = []
    collected_windows = []

    for idx, r in enumerate(raw_rooms):
        room_id = r.get("id") or f"room_{idx + 1}"
        room_type = (r.get("type") or "Living Room").lower().replace(" ", "_")
        w = float(r.get("width") or 6.0)
        d = float(r.get("length") or r.get("depth") or 6.0)

        # Handle bounds or position format accurately
        pos = r.get("position", {})
        bounds = r.get("bounds", {})
        bw = float(r.get("dimensions", {}).get("width", r.get("width", w)))
        bd = float(r.get("dimensions", {}).get("depth", r.get("length", d)))

        if bounds:
            bx = float(bounds.get("x", 0.0))
            by = float(bounds.get("y", 0.0))
            bw = float(bounds.get("width", bw))
            bd = float(bounds.get("depth", bd))
        else:
            bx = float(pos.get("x", 0.0))
            by = float(pos.get("y", pos.get("z", 0.0)))

        # Flooring and Wall material extraction
        materials = r.get("materials", {})
        pbr = r.get("pbr_material", {})
        floor_info = materials.get("floor", pbr.get("floor", {}))
        floor_color = hex_to_rgb(floor_info.get("color", "#CCCCCC"))
        floor_pattern = floor_info.get("pattern", "wood_planks")

        wall_info = materials.get("wall", pbr.get("wall", {}))
        wall_color = hex_to_rgb(wall_info.get("color", "#F0EDE8"))
        wall_pattern = wall_info.get("pattern", "plaster")

        # Furniture extraction: combine room-level (old) + top-level filtered by roomId (new)
        furniture_reqs = []
        room_furniture = list(r.get("furniture", []))

        # Also gather top-level furniture assigned to this room
        top_level_furniture = design_data.get("furniture", [])
        if isinstance(top_level_furniture, list):
            for tf in top_level_furniture:
                if isinstance(tf, dict) and tf.get("roomId") == room_id:
                    room_furniture.append(tf)

        for f in room_furniture:
            # Support both old format ("type") and new format ("asset")
            cat = str(f.get("asset") or f.get("type", "sofa")).lower()
            fpos = f.get("position", {})
            fx = float(fpos.get("x", 0.0)) if isinstance(fpos, dict) else 0.0
            fy_val = float(fpos.get("y", 0.0)) if isinstance(fpos, dict) else 0.0
            fz_val = float(fpos.get("z", 0.0)) if isinstance(fpos, dict) else 0.0
            elev = float(fpos.get("elevation", 0.0)) if isinstance(fpos, dict) else 0.0
            rot = float(f.get("rotation", f.get("rotation_y", 0.0)))

            # If fx is already an absolute scene position within the room bounds:
            if (bx - 0.5) <= fx <= (bx + bw + 0.5):
                abs_x = fx
                abs_y = fy_val if (by - 0.5) <= fy_val <= (by + bd + 0.5) else (fz_val if (by - 0.5) <= fz_val <= (by + bd + 0.5) else (by + bd / 2.0))
            else:
                # Relative to room origin
                abs_x = bx + (bw / 2.0) + fx
                abs_y = by + (bd / 2.0) + (fy_val if fy_val != 0 else fz_val)

            # Target elevation: finished floor slab top (0.22m for ground floor, 3.22m for upper)
            room_elev = float(r.get("position", {}).get("z", 0.0))
            target_z = elev if elev > 0.05 else (fz_val if fz_val > 0.05 and abs(fz_val - abs_y) > 0.5 else room_elev + 0.22)
            if target_z < 0.20:
                target_z = 0.22

            furniture_reqs.append({
                "category": cat,
                "preferred_id": f.get("id"),
                "placement_hint": "center",
                "position": [round(abs_x, 2), round(abs_y, 2), round(target_z, 2)],
                "rotation_deg": rot,
            })

        # Smart adaptive furniture cap: 3 for small rooms (<6m²), 6 for large rooms (>=16m²), 4 for standard rooms
        room_area = bw * bd
        max_furn = 3 if room_area < 6.0 else (6 if room_area >= 16.0 else 4)
        if len(furniture_reqs) > max_furn:
            priority_cats = {"bed", "sofa", "dining_table", "kitchen_island", "kitchen_cabinet", "bathtub", "toilet", "desk"}
            furniture_reqs.sort(key=lambda item: 0 if item["category"] in priority_cats else 1)
            furniture_reqs = furniture_reqs[:max_furn]

        # Doors inside room
        for d_item in r.get("doors", []):
            dpos = d_item.get("position", {})
            if isinstance(dpos, dict):
                dx = float(dpos.get("x", 0.0))
                dz = float(dpos.get("z", dpos.get("y", 0.0)))
            elif isinstance(dpos, (list, tuple)):
                dx = float(dpos[0]) if len(dpos) > 0 else 0.0
                dz = float(dpos[1]) if len(dpos) > 1 else 0.0
            else:
                dx, dz = 0.0, 0.0
            dim = d_item.get("dimensions", {})
            collected_doors.append({
                "id": d_item.get("id") or f"door_{len(collected_doors)+1}",
                "type": "interior_door",
                "position": [round(bx + (bw / 2.0) + dx, 2), round(by + (bd / 2.0) + dz, 2), 0.0],
                "width": float(dim.get("w", d_item.get("width", 0.9))),
                "height": float(dim.get("h", d_item.get("height", 2.1))),
                "wall": d_item.get("wall", "front"),
            })

        # Windows inside room
        for w_item in r.get("windows", []):
            wpos = w_item.get("position", {})
            if isinstance(wpos, dict):
                wx = float(wpos.get("x", 0.0))
                wz = float(wpos.get("z", wpos.get("y", 0.0)))
            elif isinstance(wpos, (list, tuple)):
                wx = float(wpos[0]) if len(wpos) > 0 else 0.0
                wz = float(wpos[1]) if len(wpos) > 1 else 0.0
            else:
                wx, wz = 0.0, 0.0
            dim = w_item.get("dimensions", {})
            collected_windows.append({
                "id": w_item.get("id") or f"win_{len(collected_windows)+1}",
                "position": [round(bx + (bw / 2.0) + wx, 2), round(by + (bd / 2.0) + wz, 2), 1.0],
                "width": float(dim.get("w", w_item.get("width", 1.5))),
                "height": float(dim.get("h", w_item.get("height", 1.4))),
                "wall": w_item.get("wall", "front"),
            })

        adapted_rooms.append({
            "id": room_id,
            "name": r.get("name") or r.get("type") or f"Room {idx+1}",
            "type": room_type,
            "style": style,
            "bounds": {
                "x": round(bx, 2),
                "y": round(by, 2),
                "width": round(bw, 2),
                "depth": round(bd, 2),
            },
            "flooring": {
                "material": floor_pattern,
                "color": floor_color,
            },
            "walls": {
                "pattern": wall_pattern,
                "color": wall_color,
            },
            "furniture_requirements": furniture_reqs,
        })

    # Add top-level doors/windows if not already captured from rooms
    seen_door_ids = {d["id"] for d in collected_doors if "id" in d}
    for d_item in design_data.get("doors", []):
        if isinstance(d_item, dict):
            d_id = d_item.get("id")
            if d_id and d_id in seen_door_ids:
                continue
            pos = d_item.get("position", {})
            dim = d_item.get("dimensions", {})
            if isinstance(pos, dict):
                dx = float(pos.get("x", 0.0))
                dz = float(pos.get("z", pos.get("y", 0.0)))
            elif isinstance(pos, (list, tuple)):
                dx = float(pos[0]) if len(pos) > 0 else 0.0
                dz = float(pos[1]) if len(pos) > 1 else 0.0
            else:
                dx, dz = 0.0, 0.0
            collected_doors.append({
                "id": d_id or f"door_{len(collected_doors)+1}",
                "type": "door",
                "position": [round(dx, 2), round(dz, 2), 0.0],
                "width": float(dim.get("w", d_item.get("width", 0.95))),
                "height": float(dim.get("h", d_item.get("height", 2.1))),
                "wall": d_item.get("wall", "front"),
            })
            if d_id:
                seen_door_ids.add(d_id)

    seen_win_ids = {w["id"] for w in collected_windows if "id" in w}
    for w_item in design_data.get("windows", []):
        if isinstance(w_item, dict):
            w_id = w_item.get("id")
            if w_id and w_id in seen_win_ids:
                continue
            pos = w_item.get("position", {})
            dim = w_item.get("dimensions", {})
            if isinstance(pos, dict):
                wx = float(pos.get("x", 0.0))
                wz = float(pos.get("z", pos.get("y", 0.0)))
            elif isinstance(pos, (list, tuple)):
                wx = float(pos[0]) if len(pos) > 0 else 0.0
                wz = float(pos[1]) if len(pos) > 1 else 0.0
            else:
                wx, wz = 0.0, 0.0
            collected_windows.append({
                "id": w_id or f"win_{len(collected_windows)+1}",
                "position": [round(wx, 2), round(wz, 2), 1.0],
                "width": float(dim.get("w", w_item.get("width", 1.4))),
                "height": float(dim.get("h", w_item.get("height", 1.2))),
                "wall": w_item.get("wall", "front"),
            })
            if w_id:
                seen_win_ids.add(w_id)

    return {
        "house_id": house_id,
        "project_name": f"ArchGen {style.capitalize()} House",
        "unit": "meters",
        "building": {
            "wall_height": 2.8,
            "wall_thickness": 0.2,
            "slab_thickness": 0.25,
            "floors": len(design_data.get("floors", [])) or 1,
        },
        "floors": design_data.get("floors", []),
        "roof": design_data.get("roof", {}),
        "exterior": design_data.get("exterior", {}),
        "site": design_data.get("site", {}),
        "rooms": adapted_rooms,
        "openings": {
            "doors": collected_doors,
            "windows": collected_windows,
        },
    }


def generate_3d_house_model(
    design_data: Dict[str, Any],
    project_id: Optional[str] = None,
    version_num: int = 1,
) -> Optional[str]:
    """
    Sends layout to Blender worker microservice to procedurally build the 3D model.
    Returns the GLB download URL or None if generation is disabled or fails.
    """
    if not BLENDER_ENABLED:
        logger.info("[BLENDER] 3D Generation is disabled in config (BLENDER_ENABLED=False).")
        return None

    try:
        adapted_layout = adapt_gemini_to_blender_layout(design_data, project_id, version_num)
        endpoint = f"{BLENDER_SERVICE_URL.rstrip('/')}/generate"

        logger.info(f"[BLENDER] Invoking Blender worker at {endpoint} for house {adapted_layout['house_id']}...")
        response = requests.post(
            endpoint,
            json={"layout": adapted_layout},
            headers={"Content-Type": "application/json"},
            timeout=BLENDER_TIMEOUT_SECONDS,
        )

        if response.status_code == 200:
            result = response.json()
            raw_glb_url = result.get("glb_url")
            glb_url = resolve_s3_url_to_presigned(raw_glb_url) or raw_glb_url
            logger.info(f"[BLENDER] Generation succeeded! GLB URL: {glb_url}")
            return glb_url
        else:
            logger.warning(
                f"[BLENDER] Worker responded with HTTP {response.status_code}: {response.text[:300]}"
            )
            return None

    except requests.exceptions.ConnectionError:
        logger.warning(
            f"[BLENDER] Could not connect to Blender worker at {BLENDER_SERVICE_URL}. "
            "Ensure worker_server.py is running or EC2 instance is online."
        )
        return None
    except requests.exceptions.Timeout:
        logger.warning(f"[BLENDER] Request timed out after {BLENDER_TIMEOUT_SECONDS}s.")
        return None
    except Exception as e:
        logger.error(f"[BLENDER] Unexpected error during 3D generation: {e}")
        return None
