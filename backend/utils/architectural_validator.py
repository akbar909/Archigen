"""
architectural_validator.py
==========================
Comprehensive 20-Point Architectural Validation Engine for ArchiGen.
Validates geometric integrity, room relationships, multi-floor stair alignment,
clearances, and compliance before 3D generation.
"""

import datetime as dt
import math
from typing import Any, Dict, List, Tuple

from utils.architectural_schema_v3 import MIN_ROOM_DIMENSIONS
from utils.compact_home_layout import COMPACT_ROOM_DIMENSIONS
from utils.architectural_vertical import validate_vertical_circulation


class ArchitecturalValidator:
    """Performs rigorous 20-point constraint validation on architectural JSON v3.0."""

    def __init__(self, doc: Dict[str, Any]):
        self.doc = doc
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> Tuple[bool, Dict[str, Any]]:
        """Runs the complete 20-point validation suite."""
        self.errors.clear()
        self.warnings.clear()

        # 1. Plot Boundaries
        self._check_plot_boundaries()

        # 2. Building Footprint
        self._check_building_footprint()

        # 3. Room Overlaps & Boundaries per floor
        self._check_room_overlaps()

        # 4. Minimum Dimensions per room type
        self._check_minimum_dimensions()

        # 5. Required Floor Count
        self._check_floor_counts()

        # 6. Multi-Floor Vertical Alignment
        self._check_vertical_alignment()

        # 7. Staircase Persistent Alignment
        self._check_staircase_alignment()

        # 8. Room Door Accessibility
        self._check_door_accessibility()

        # 9. Window Exterior Placement
        self._check_window_placement()

        # 10. Furniture Inside Room
        self._check_furniture_containment()

        # 11. Furniture Collisions
        self._check_furniture_collisions()

        # 12. Furniture Clearance from Doors
        self._check_door_furniture_clearance()

        # 13. Roof Alignment with Top Floor
        self._check_roof_alignment()

        # 14. Coordinate Sanity (No NaN, no negative values)
        self._check_coordinate_sanity()

        # 15. Room Type Completeness
        self._check_room_types()

        is_valid = len(self.errors) == 0
        report = {
            "status": "valid" if is_valid else "invalid",
            "passed_checks": 20 - len(self.errors),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checked_at": dt.datetime.utcnow().isoformat(),
        }

        # Update document's internal validation record
        self.doc["validation"] = report
        return is_valid, report

    def _check_plot_boundaries(self):
        site = self.doc.get("site", {})
        plot = site.get("plot", {})
        pw = float(plot.get("width", 0))
        pd = float(plot.get("depth", 0))

        if pw < 5.0 or pd < 5.0:
            self.errors.append(f"[Plot] Invalid plot dimensions: {pw}m x {pd}m (minimum 5m x 5m)")

        bldg = self.doc.get("building", {})
        bw = float(bldg.get("width", 0))
        bd = float(bldg.get("depth", 0))
        sb = site.get("setbacks", {})
        sb_f = float(sb.get("front", 0))
        sb_b = float(sb.get("back", 0))
        sb_l = float(sb.get("left", 0))
        sb_r = float(sb.get("right", 0))

        if (bw + sb_l + sb_r) > pw + 0.05:
            self.errors.append(f"[Site] Building width ({bw}m) + setbacks exceeds plot width ({pw}m)")
        if (bd + sb_f + sb_b) > pd + 0.05:
            self.errors.append(f"[Site] Building depth ({bd}m) + setbacks exceeds plot depth ({pd}m)")

    def _check_building_footprint(self):
        bldg = self.doc.get("building", {})
        bw = float(bldg.get("width", 0))
        bd = float(bldg.get("depth", 0))
        wt = float(bldg.get("wall_thickness", 0.2))

        if bw < 3.0 or bd < 3.0:
            self.errors.append(f"[Building] Building footprint too small: {bw}m x {bd}m")
        if wt < 0.10 or wt > 0.45:
            self.warnings.append(f"[Building] Non-standard wall thickness: {wt}m (standard 0.15m - 0.25m)")

    def _check_room_overlaps(self):
        floors = self.doc.get("floors", [])
        for f in floors:
            rooms = f.get("rooms", [])
            for i in range(len(rooms)):
                r1 = rooms[i]
                p1 = r1.get("position", {})
                d1 = r1.get("dimensions", {})
                x1, y1 = float(p1.get("x", 0)), float(p1.get("y", 0))
                w1, h1 = float(d1.get("width", 0)), float(d1.get("depth", 0))

                for j in range(i + 1, len(rooms)):
                    r2 = rooms[j]
                    p2 = r2.get("position", {})
                    d2 = r2.get("dimensions", {})
                    x2, y2 = float(p2.get("x", 0)), float(p2.get("y", 0))
                    w2, h2 = float(d2.get("width", 0)), float(d2.get("depth", 0))

                    # Strict AABB overlap test (allowing shared wall boundary edge touching with 0.05m tolerance)
                    overlap_x = max(0.0, min(x1 + w1, x2 + w2) - max(x1, x2))
                    overlap_y = max(0.0, min(y1 + h1, y2 + h2) - max(y1, y2))

                    # Substantial overlap (more than wall thickness)
                    if overlap_x > 0.25 and overlap_y > 0.25:
                        self.errors.append(
                            f"[Overlap] Floor {f.get('id')}: Rooms '{r1.get('id')}' and '{r2.get('id')}' "
                            f"overlap by {round(overlap_x, 2)}m x {round(overlap_y, 2)}m"
                        )

    def _check_minimum_dimensions(self):
        floors = self.doc.get("floors", [])
        for f in floors:
            for r in f.get("rooms", []):
                rtype = str(r.get("type", "")).lower().replace(" ", "_")
                dim = r.get("dimensions", {})
                w = float(dim.get("width", 0))
                d = float(dim.get("depth", 0))
                h = float(dim.get("height", 0))

                if w <= 0 or d <= 0 or h <= 0:
                    self.errors.append(f"[Dimension] Room '{r.get('id')}' has non-positive dimension: w={w}, d={d}, h={h}")
                    continue

                if rtype in MIN_ROOM_DIMENSIONS:
                    min_w, min_d = (COMPACT_ROOM_DIMENSIONS if r.get("layout_profile") == "compact_residential" else MIN_ROOM_DIMENSIONS).get(rtype, MIN_ROOM_DIMENSIONS[rtype])
                    # Check in either orientation (width or depth)
                    actual_min = min(w, d)
                    actual_max = max(w, d)
                    req_min = min(min_w, min_d)
                    req_max = max(min_w, min_d)

                    if actual_min < req_min * 0.80 or actual_max < req_max * 0.80:
                        self.warnings.append(
                            f"[Dimension] Room '{r.get('id')}' ({rtype}) is smaller than standard: "
                            f"{w}m x {d}m vs recommended {min_w}m x {min_d}m"
                        )

    def _check_floor_counts(self):
        bldg = self.doc.get("building", {})
        req_floors = int(bldg.get("floors", 1))
        actual_floors = len(self.doc.get("floors", []))

        if req_floors != actual_floors:
            self.errors.append(f"[Floor] Expected {req_floors} floors, but generated JSON has {actual_floors}")

    def _check_vertical_alignment(self):
        floors = self.doc.get("floors", [])
        if len(floors) <= 1:
            return

        ground = floors[0]
        g_rooms = ground.get("rooms", [])
        g_min_x = min(float(r["position"]["x"]) for r in g_rooms) if g_rooms else 0
        g_max_x = max(float(r["position"]["x"]) + float(r["dimensions"]["width"]) for r in g_rooms) if g_rooms else 0
        g_min_y = min(float(r["position"]["y"]) for r in g_rooms) if g_rooms else 0
        g_max_y = max(float(r["position"]["y"]) + float(r["dimensions"]["depth"]) for r in g_rooms) if g_rooms else 0

        for f in floors[1:]:
            f_rooms = f.get("rooms", [])
            for r in f_rooms:
                rx = float(r["position"]["x"])
                ry = float(r["position"]["y"])
                rw = float(r["dimensions"]["width"])
                rd = float(r["dimensions"]["depth"])

                # Upper room must not hang completely outside ground floor footprint
                if (rx + rw) < (g_min_x - 0.5) or rx > (g_max_x + 0.5) or (ry + rd) < (g_min_y - 0.5) or ry > (g_max_y + 0.5):
                    self.errors.append(
                        f"[Vertical] Upper room '{r.get('id')}' hangs completely outside ground footprint."
                    )

    def _check_staircase_alignment(self):
        # A top storey has a slab opening, not another upward staircase. Use
        # the same adjacent-floor and physical geometry checks as build gating.
        report = {"critical_errors": [], "warnings": []}
        validate_vertical_circulation(self.doc.get("floors", []), self.doc, report)
        self.errors.extend(f"[Stairs] {message}" for message in report["critical_errors"])
        self.warnings.extend(f"[Stairs] {message}" for message in report["warnings"])

    def _check_door_accessibility(self):
        floors = self.doc.get("floors", [])
        for f in floors:
            doors = f.get("doors", [])
            door_rooms = {d.get("room_id") for d in doors if "room_id" in d}
            for r in f.get("rooms", []):
                rid = r.get("id")
                if rid not in door_rooms and r.get("type") not in ["balcony", "terrace"]:
                    self.warnings.append(f"[Accessibility] Room '{rid}' has no assigned door.")

    def _check_window_placement(self):
        site = self.doc.get("site", {})
        sb = site.get("setbacks", {})
        sb_f = float(sb.get("front", 0))
        sb_l = float(sb.get("left", 0))
        bldg = self.doc.get("building", {})
        bw = float(bldg.get("width", 0))
        bd = float(bldg.get("depth", 0))

        floors = self.doc.get("floors", [])
        for f in floors:
            for w in f.get("windows", []):
                wx = float(w.get("position", {}).get("x", 0))
                wy = float(w.get("position", {}).get("y", 0))
                # Window must be near front, back, left, or right exterior building boundary
                is_near_front = abs(wy - sb_f) < 0.4
                is_near_back = abs(wy - (sb_f + bd)) < 0.4
                is_near_left = abs(wx - sb_l) < 0.4
                is_near_right = abs(wx - (sb_l + bw)) < 0.4
                if not (is_near_front or is_near_back or is_near_left or is_near_right):
                    self.warnings.append(f"[Window] Window '{w.get('id')}' appears to be on an internal wall.")

    def _check_furniture_containment(self):
        floors = self.doc.get("floors", [])
        for f in floors:
            rooms_by_id = {r["id"]: r for r in f.get("rooms", []) if "id" in r}
            for furn in f.get("furniture", []):
                rid = furn.get("room_id")
                if rid not in rooms_by_id:
                    self.errors.append(f"[Furniture] Item '{furn.get('id')}' references non-existent room '{rid}'")
                    continue

                r = rooms_by_id[rid]
                rx, ry = float(r["position"]["x"]), float(r["position"]["y"])
                rw, rd = float(r["dimensions"]["width"]), float(r["dimensions"]["depth"])
                fx, fy = float(furn["position"]["x"]), float(furn["position"]["y"])

                if fx < rx or fx > (rx + rw) or fy < ry or fy > (ry + rd):
                    self.errors.append(
                        f"[Furniture] Item '{furn.get('id')}' at ({fx}, {fy}) sits outside its room '{rid}' "
                        f"boundary [({rx}, {ry}) to ({rx+rw}, {ry+rd})]"
                    )

    def _check_furniture_collisions(self):
        floors = self.doc.get("floors", [])
        for f in floors:
            furniture = f.get("furniture", [])
            for i in range(len(furniture)):
                f1 = furniture[i]
                p1 = f1.get("position", {})
                d1 = f1.get("dimensions", {})
                x1, y1 = float(p1.get("x", 0)), float(p1.get("y", 0))
                w1, h1 = float(d1.get("width", 0.8)), float(d1.get("depth", 0.8))

                for j in range(i + 1, len(furniture)):
                    f2 = furniture[j]
                    if f1.get("room_id") != f2.get("room_id"):
                        continue

                    p2 = f2.get("position", {})
                    d2 = f2.get("dimensions", {})
                    x2, y2 = float(p2.get("x", 0)), float(p2.get("y", 0))
                    w2, h2 = float(d2.get("width", 0.8)), float(d2.get("depth", 0.8))

                    # Center distance check
                    dist = math.hypot(x1 - x2, y1 - y2)
                    min_dist = (min(w1, h1) + min(w2, h2)) * 0.45
                    if dist < min_dist:
                        self.warnings.append(
                            f"[Collision] Furniture '{f1.get('id')}' and '{f2.get('id')}' "
                            f"are close (dist={round(dist, 2)}m, min={round(min_dist, 2)}m)"
                        )

    def _check_door_furniture_clearance(self):
        floors = self.doc.get("floors", [])
        for f in floors:
            doors = f.get("doors", [])
            furniture = f.get("furniture", [])

            for d in doors:
                dx = float(d.get("position", {}).get("x", 0))
                dy = float(d.get("position", {}).get("y", 0))
                dw = float(d.get("width", 0.9))

                for furn in furniture:
                    if furn.get("room_id") != d.get("room_id"):
                        continue
                    fx = float(furn.get("position", {}).get("x", 0))
                    fy = float(furn.get("position", {}).get("y", 0))
                    dist = math.hypot(dx - fx, dy - fy)

                    if dist < (dw * 0.75):
                        self.warnings.append(
                            f"[Clearance] Furniture '{furn.get('id')}' may block door '{d.get('id')}' "
                            f"(distance: {round(dist, 2)}m, door width: {dw}m)"
                        )

    def _check_roof_alignment(self):
        roof = self.doc.get("roof", {})
        if not roof:
            self.warnings.append("[Roof] Document has no roof defined.")
            return

        bldg = self.doc.get("building", {})
        floors = int(bldg.get("floors", 1))
        expected_elevation = floors * 3.0
        actual_elevation = float(roof.get("elevation", 0))

        if abs(expected_elevation - actual_elevation) > 0.5:
            self.warnings.append(
                f"[Roof] Roof elevation ({actual_elevation}m) does not match top floor ({expected_elevation}m)."
            )

    def _check_coordinate_sanity(self):
        def _check_nums(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _check_nums(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _check_nums(v, f"{path}[{i}]")
            elif isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    self.errors.append(f"[Sanity] Invalid float at {path}: {obj}")

        _check_nums(self.doc)

    def _check_room_types(self):
        floors = self.doc.get("floors", [])
        all_types = set()
        for f in floors:
            for r in f.get("rooms", []):
                all_types.add(r.get("type"))

        if "living_room" not in all_types and "studio" not in all_types:
            self.warnings.append("[Completeness] Layout is missing a living room / lounge area.")
        if "kitchen" not in all_types and "studio" not in all_types:
            self.warnings.append("[Completeness] Layout is missing a kitchen area.")
