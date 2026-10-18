"""
layout_engine.py
================
Deterministic Architectural Layout Engine for ArchiGen.
Solves contiguous spatial layouts, room relationships, shared wall networks,
wall-hosted openings, staircase alignment, and furniture placement rules
for 2D CAD plans, Blender Headless 3D, and Three.js viewer.
"""

import copy
import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

from utils.layout_engine_furniture import FurnitureMixin
from utils.layout_engine_generation import LayoutGenerationMixin
from utils.layout_engine_openings import OpeningsMixin
from utils.layout_engine_refinement import RefinementMixin
from utils.layout_engine_rooms import RoomPlacementMixin
from utils.architectural_schema_v3 import (
    MIN_ROOM_DIMENSIONS,
    VALID_ORIENTATIONS,
    VALID_ROOM_TYPES,
    VALID_STYLES,
    ft_to_m,
    m_to_ft,
)


# ─── Coordinate Conversion Utilities ──────────────────────────────────────────

def json_to_svg_coords(x: float, y: float, plot_depth: float, scale: float = 40.0, margin: float = 2.0) -> Tuple[float, float]:
    """
    Converts architectural JSON coordinates (X = width from left, Y = depth from front/south)
    to 2D SVG canvas coordinates (origin top-left).
    """
    svg_x = (margin + x) * scale
    svg_y = (margin + (plot_depth - y)) * scale
    return round(svg_x, 2), round(svg_y, 2)


def json_to_blender_coords(x: float, y: float, z: float, origin_offset: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float, float]:
    """
    Converts architectural JSON coordinates to Blender world space:
    Blender: X = width, Y = depth, Z = elevation (up).
    """
    bx = x - origin_offset[0]
    by = y - origin_offset[1]
    bz = z
    return round(bx, 3), round(by, 3), round(bz, 3)


def json_to_threejs_coords(x: float, y: float, z: float, origin_offset: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float, float]:
    """
    Converts architectural JSON coordinates to Three.js coordinates:
    Three.js: X = width, Y = elevation (up), Z = depth.
    """
    tx = x - origin_offset[0]
    ty = z
    tz = y - origin_offset[1]
    return round(tx, 3), round(ty, 3), round(tz, 3)


# ─── Layout Generation Engine ─────────────────────────────────────────────────

class ArchitecturalLayoutEngine(
    LayoutGenerationMixin,
    RoomPlacementMixin,
    OpeningsMixin,
    FurnitureMixin,
    RefinementMixin,
):
    """
    Deterministically arranges rooms, stairs, openings, roof, and exterior features
    from architectural requirements while satisfying geometric constraints.
    """

    def __init__(self, unit: str = "ft"):
        self.unit = unit.lower()
        self.is_feet = self.unit in ["ft", "feet"]

    def _to_meters(self, val: float) -> float:
        return ft_to_m(val) if self.is_feet else float(val)

    @staticmethod
    def _set_room_rect(
        room: Dict[str, Any],
        *,
        x: float,
        y: float,
        width: float,
        depth: float,
    ) -> None:
        """Update canonical and legacy room geometry together."""
        x, y = round(x, 2), round(y, 2)
        width, depth = round(width, 2), round(depth, 2)
        room.setdefault("position", {})["x"] = x
        room["position"]["y"] = y
        room.setdefault("dimensions", {})["width"] = width
        room["dimensions"]["depth"] = depth
        room["width"] = width
        room["length"] = depth

    def _repair_schema_minimum_room_spans(
        self,
        rooms: List[Dict[str, Any]],
        minimum: float = 1.5,
    ) -> None:
        """Borrow space from a matching adjacent room instead of emitting slivers.

        The legacy response schema requires every room width and depth to be at
        least 1.5 m. Layout bands can occasionally leave a small final bedroom
        or kitchen. Because walls and furniture are generated after this method,
        shifting the shared boundary here keeps the canonical geometry coherent.
        """
        tolerance = 0.02

        def rect(room: Dict[str, Any]) -> tuple[float, float, float, float]:
            position = room["position"]
            dimensions = room["dimensions"]
            return (
                float(position["x"]),
                float(position["y"]),
                float(dimensions["width"]),
                float(dimensions["depth"]),
            )

        def label(room: Dict[str, Any]) -> str:
            return str(room.get("name") or room.get("type") or room.get("id") or "Room")

        # A repair can expose another undersized donor, so re-check the complete
        # set after every shared-boundary move.
        for _ in range(max(1, len(rooms) * 4)):
            target = next(
                (
                    room
                    for room in rooms
                    if float(room["dimensions"]["width"]) < minimum - tolerance
                    or float(room["dimensions"]["depth"]) < minimum - tolerance
                ),
                None,
            )
            if target is None:
                for room in rooms:
                    x, y, width, depth = rect(room)
                    self._set_room_rect(room, x=x, y=y, width=width, depth=depth)
                return

            tx, ty, tw, td = rect(target)
            repaired = False

            if tw < minimum - tolerance:
                deficit = minimum - tw
                for donor in rooms:
                    if donor is target:
                        continue
                    dx, dy, dw, dd = rect(donor)
                    same_band = abs(dy - ty) <= tolerance and abs(dd - td) <= tolerance
                    if not same_band or dw - deficit < minimum - tolerance:
                        continue
                    if abs(dx - (tx + tw)) <= tolerance:
                        self._set_room_rect(target, x=tx, y=ty, width=tw + deficit, depth=td)
                        self._set_room_rect(donor, x=dx + deficit, y=dy, width=dw - deficit, depth=dd)
                        repaired = True
                        break
                    if abs((dx + dw) - tx) <= tolerance:
                        self._set_room_rect(target, x=tx - deficit, y=ty, width=tw + deficit, depth=td)
                        self._set_room_rect(donor, x=dx, y=dy, width=dw - deficit, depth=dd)
                        repaired = True
                        break

            if not repaired and td < minimum - tolerance:
                deficit = minimum - td
                for donor in rooms:
                    if donor is target:
                        continue
                    dx, dy, dw, dd = rect(donor)
                    same_band = abs(dx - tx) <= tolerance and abs(dw - tw) <= tolerance
                    if not same_band or dd - deficit < minimum - tolerance:
                        continue
                    if abs(dy - (ty + td)) <= tolerance:
                        self._set_room_rect(target, x=tx, y=ty, width=tw, depth=td + deficit)
                        self._set_room_rect(donor, x=dx, y=dy + deficit, width=dw, depth=dd - deficit)
                        repaired = True
                        break
                    if abs((dy + dd) - ty) <= tolerance:
                        self._set_room_rect(target, x=tx, y=ty - deficit, width=tw, depth=td + deficit)
                        self._set_room_rect(donor, x=dx, y=dy, width=dw, depth=dd - deficit)
                        repaired = True
                        break

            if not repaired:
                narrow_value = min(tw, td)
                raise ValueError(
                    f"{label(target)} is only {narrow_value:.2f} m wide/deep. "
                    "The requested rooms do not fit safely on this floor; "
                    "increase the plot size, remove a room, or use another floor."
                )

        raise ValueError("Room dimensions could not be repaired safely.")
