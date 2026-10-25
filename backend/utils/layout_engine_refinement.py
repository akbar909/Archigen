"""Gemini-output integration with the deterministic solver."""

import copy
import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

from utils.architectural_schema_v3 import (
    MIN_ROOM_DIMENSIONS,
    VALID_ORIENTATIONS,
    VALID_ROOM_TYPES,
    VALID_STYLES,
    ft_to_m,
    m_to_ft,
)

class RefinementMixin:
    def _rooms_for_explicit_program(
        self,
        raw_rooms: List[Dict[str, Any]],
        constraints: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Reconcile Gemini rooms to the exact deterministic prompt inventory."""
        requested_counts = constraints.get("room_counts", {})
        bedroom_types = {"bedroom", "master_bedroom", "guest_room"}
        bathroom_types = {"bathroom", "master_bathroom"}

        def family(room_type: str) -> str:
            normalized = self._classify_room_type(room_type)
            if normalized in bedroom_types:
                return "bedroom"
            if normalized in bathroom_types:
                return "bathroom"
            return normalized

        available = [room for room in raw_rooms if isinstance(room, dict)]
        selected: List[Dict[str, Any]] = []
        used_indices = set()
        floor_program = constraints.get("floor_room_counts", {})
        labels = {
            "bedroom": "Bedroom",
            "master_bedroom": "Master Bedroom",
            "guest_room": "Guest Room",
            "bathroom": "Bathroom",
            "kitchen": "Kitchen",
            "living_room": "Living Room",
            "dining_room": "Dining Room",
            "garage": "Garage",
            "home_office": "Home Office",
        }

        requested_specs = []
        assigned_totals: Dict[str, int] = {}
        for raw_level, floor_counts in sorted(floor_program.items(), key=lambda value: int(value[0])):
            level = int(raw_level)
            for requested_type, raw_count in floor_counts.items():
                count = max(0, int(raw_count))
                assigned_totals[requested_type] = assigned_totals.get(requested_type, 0) + count
                requested_specs.extend((requested_type, level) for _ in range(count))

        for requested_type, raw_count in requested_counts.items():
            remaining = max(0, int(raw_count) - assigned_totals.get(requested_type, 0))
            requested_specs.extend((requested_type, None) for _ in range(remaining))

        type_ordinals: Dict[str, int] = {}
        type_totals: Dict[str, int] = {}
        for requested_type, _ in requested_specs:
            type_totals[requested_type] = type_totals.get(requested_type, 0) + 1

        for requested_type, level in requested_specs:
            output_type = requested_type
            if requested_type == "bedroom":
                output_type = constraints.get("bedroom_type", "bedroom")

            candidates = [
                (index, room)
                for index, room in enumerate(available)
                if index not in used_indices
                and family(str(room.get("type", room.get("name", "")))) == requested_type
            ]
            # Prefer the exact requested bedroom kind. An unsolicited master
            # bedroom must not become a second sleeping room.
            candidates.sort(key=lambda value: (
                self._classify_room_type(str(value[1].get("type", ""))) != output_type,
                value[0],
            ))

            type_ordinals[requested_type] = type_ordinals.get(requested_type, 0) + 1
            ordinal = type_ordinals[requested_type]
            if candidates:
                source_index, source = candidates[0]
                used_indices.add(source_index)
                room = dict(source)
            else:
                room = {}

            label = labels.get(output_type, output_type.replace("_", " ").title())
            room["id"] = str(room.get("id") or f"requested_{output_type}_{ordinal:02d}")
            room["type"] = output_type
            room["name"] = label if type_totals[requested_type] == 1 else f"{label} {ordinal}"
            if level is not None:
                room["floor"] = level
                room["strict_floor"] = True
            selected.append(room)

        return selected

    def solve_or_refine_design(
        self,
        design_data: Dict[str, Any],
        prompt: str = "",
        constraints_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Takes raw Gemini design output (with arbitrary/missing coordinates) and
        produces a mathematically validated, contiguous architectural CAD model.
        """
        from utils.gemini_layout import infer_layout_constraints

        constraints = infer_layout_constraints(prompt)
        if constraints_override:
            # Structured callers (notably Home Wizard) are authoritative for
            # exact geometry and inventory. Keep inferred prose fields only as
            # fallbacks for values the structured payload did not provide.
            constraints.update(copy.deepcopy(constraints_override))

        # Extract plot dimensions or use standard architectural envelope
        plot_info = design_data.get("site", {}).get("plot", {})
        house_info = design_data.get("house", {})
        requested_plot = constraints.get("plot") if isinstance(constraints.get("plot"), dict) else {}
        pw = float(requested_plot.get("width") or plot_info.get("width") or house_info.get("width") or 14.0)
        pd = float(requested_plot.get("depth") or plot_info.get("depth") or house_info.get("length") or 18.0)

        # A floor count stated by the user must override Gemini's normalized
        # default (usually 1). Otherwise "make it three floors" is silently
        # discarded before the deterministic layout engine sees it.
        if constraints.get("floors_explicit"):
            floors_cnt = int(constraints.get("floors_count", 1))
        else:
            floors_cnt = int(house_info.get("floors") or (len(design_data.get("floors", [])) or constraints.get("floors_count", 1)))

        # Build room requirement list
        raw_rooms = design_data.get("rooms", [])
        strict_room_program = bool(
            constraints.get("replace_room_program")
            and constraints.get("room_counts")
        )
        if constraints.get("requested_rooms"):
            raw_rooms = copy.deepcopy(constraints["requested_rooms"])
            strict_room_program = True
        elif strict_room_program:
            raw_rooms = self._rooms_for_explicit_program(raw_rooms, constraints)
        style = constraints.get("style") or design_data.get("style") or house_info.get("style") or "modern"

        requirements = {
            "project_name": design_data.get("project_name", "ArchiGen Residential Home"),
            "style": style,
            "orientation": constraints.get("orientation") or design_data.get("site", {}).get("road", {}).get("side", "south"),
            "plot": {"width": pw, "depth": pd},
            "floors": floors_cnt,
            "rooms": raw_rooms if raw_rooms else [],
            "connection_preferences": constraints.get("connections", []),
            "strict_room_program": strict_room_program,
            "strict_floor_program": bool(constraints.get("floor_room_counts")),
            "roof_type": constraints.get("roof_type"),
            "setbacks": copy.deepcopy(constraints.get("setbacks") or {}),
            "max_coverage": constraints.get("max_coverage"),
        }

        # If rooms list was empty, populate from constraints
        if not requirements["rooms"]:
            for rtype, count in constraints.get("room_counts", {}).items():
                for _ in range(count):
                    requirements["rooms"].append({"type": rtype, "name": rtype.replace("_", " ").title()})

        # Run deterministic constraint engine
        solved_doc = self.generate_layout(requirements)

        # Preserve non-geometric wizard selections as canonical design
        # metadata. Renderers may adopt these fields incrementally, while the
        # saved version always reflects exactly what the user selected.
        if constraints.get("source") == "home_wizard":
            preferences = copy.deepcopy(constraints.get("design_preferences") or {})
            features = copy.deepcopy(constraints.get("features") or {})
            solved_doc["design_preferences"] = preferences
            solved_doc["features"] = features
            solved_doc["feature_configs"] = copy.deepcopy(constraints.get("feature_configs") or {})
            solved_doc["special_requirements"] = constraints.get("special_requirements", "")
            solved_doc["project"]["building_type"] = constraints.get("building_type", "house")
            solved_doc["site"]["road_access"] = constraints.get("road_access", "front")
            solved_doc["site"]["max_coverage"] = constraints.get("max_coverage")

            exterior = solved_doc.setdefault("exterior", {})
            exterior.setdefault("boundary_wall", {})["enabled"] = bool(features.get("boundary_wall"))
            gate_enabled = bool(features.get("entrance_gate"))
            exterior.setdefault("gate", {})["enabled"] = gate_enabled
            exterior.setdefault("entrance_path", {})["enabled"] = True
            ground_rooms = (solved_doc.get("floors") or [{}])[0].get("rooms", [])
            has_garage = any(room.get("type") == "garage" for room in ground_rooms)
            exterior.setdefault("driveway", {})["enabled"] = bool(features.get("car_parking")) or has_garage
            exterior.setdefault("landscape", {})["front_garden"] = bool(features.get("front_garden"))
            exterior["exterior_lighting"] = bool(features.get("exterior_lighting"))
            solved_doc.setdefault("roof", {})["solar_panels"] = bool(features.get("solar_panels"))
            solved_doc["roof"]["rooftop_terrace"] = bool(features.get("rooftop_terrace"))

        # Merge custom PBR materials from Gemini where matching
        gemini_rooms_by_type = {}
        for gr in raw_rooms:
            gt = str(gr.get("type", "")).lower()
            if gt not in gemini_rooms_by_type:
                gemini_rooms_by_type[gt] = gr

        for fl in solved_doc.get("floors", []):
            for r in fl.get("rooms", []):
                rt = str(r.get("type", "")).lower()
                matching_gr = gemini_rooms_by_type.get(rt)
                if matching_gr and "materials" in matching_gr:
                    r["materials"] = matching_gr["materials"]
                if matching_gr and "pbr_material" in matching_gr:
                    r["pbr_material"] = matching_gr["pbr_material"]

        return solved_doc
