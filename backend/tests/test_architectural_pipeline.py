import copy
import json
import math
import os
import sys
import unittest


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils.architectural_preflight import (
    OPENING_GAP,
    WALL_MARGIN,
    _repair_furniture,
    _repair_openings,
    validate_and_repair_design,
)
from utils.architectural_refinement import apply_targeted_refinement
from utils.blender_service import adapt_gemini_to_blender_layout
from utils.layout_engine import ArchitecturalLayoutEngine
from utils.gemini_layout import _normalize_design, infer_layout_constraints


def footprint(item):
    dimensions = item["dimensions"]
    angle = math.radians(float(item.get("rotation", 0)) % 180)
    width = abs(math.cos(angle)) * dimensions["width"] + abs(math.sin(angle)) * dimensions["depth"]
    depth = abs(math.sin(angle)) * dimensions["width"] + abs(math.cos(angle)) * dimensions["depth"]
    return width, depth


class ArchitecturalPipelineTests(unittest.TestCase):
    def make_design(self, rooms, plot=(14, 18), floors=1):
        requirements = {
            "project_name": "Pipeline Test",
            "plot": {"width": plot[0], "depth": plot[1]},
            "floors": floors,
            "rooms": [{"id": f"requested_{index}", "type": room_type} for index, room_type in enumerate(rooms, 1)],
        }
        return ArchitecturalLayoutEngine(unit="meters").generate_layout(requirements)

    def assert_pipeline_valid(self, design):
        canonical, report = validate_and_repair_design(design, repair=True)
        self.assertEqual([], report["critical_errors"], report)
        room_map = {room["id"]: room for floor in canonical["floors"] for room in floor["rooms"]}
        expected_ids = []
        for floor in canonical["floors"]:
            wall_ids = {wall["id"] for wall in floor["walls"]}
            for opening in floor["doors"] + floor["windows"]:
                self.assertIn(opening["room_id"], room_map)
                self.assertIn(opening["wall_id"], wall_ids)
            for item in floor["furniture"]:
                expected_ids.append(item["id"])
                room = room_map[item["room_id"]]
                x0, y0 = room["position"]["x"], room["position"]["y"]
                x1 = x0 + room["dimensions"]["width"]
                y1 = y0 + room["dimensions"]["depth"]
                width, depth = footprint(item)
                self.assertGreaterEqual(item["position"]["x"] - width / 2, x0 - 1e-6)
                self.assertLessEqual(item["position"]["x"] + width / 2, x1 + 1e-6)
                self.assertGreaterEqual(item["position"]["y"] - depth / 2, y0 - 1e-6)
                self.assertLessEqual(item["position"]["y"] + depth / 2, y1 + 1e-6)

        adapted = adapt_gemini_to_blender_layout(canonical, project_id="test", version_num=1)
        actual_ids = [
            item["instance_id"]
            for room in adapted["rooms"]
            for item in room["furniture_requirements"]
        ]
        self.assertCountEqual(expected_ids, actual_ids)
        self.assertEqual(len(expected_ids), adapted["expected_inventory"]["furniture_count"])
        self.assertEqual(len(expected_ids), len(set(actual_ids)))
        return canonical, adapted

    def test_required_layout_scenarios(self):
        scenarios = {
            "small_one_bed_one_bath": (["bedroom", "bathroom"], (11, 12), 1),
            "multiple_bedrooms_bathrooms": (["living_room", "kitchen", "bedroom", "bedroom", "bedroom", "bathroom", "bathroom"], (18, 22), 1),
            "narrow_corridor_and_doors": (["foyer", "corridor", "living_room", "kitchen", "bedroom", "bathroom"], (12, 22), 1),
            "varied_furniture_orientations": (["living_room", "dining_room", "kitchen", "home_office", "bedroom", "bathroom"], (17, 20), 1),
            "multi_floor_stairs": (["living_room", "kitchen", "bedroom", "bedroom", "master_bedroom", "bathroom", "master_bathroom"], (16, 20), 2),
        }
        for name, (rooms, plot, floors) in scenarios.items():
            with self.subTest(name=name):
                canonical, adapted = self.assert_pipeline_valid(self.make_design(rooms, plot, floors))
                if floors > 1:
                    elevations = {room["bounds"]["z"] for room in adapted["rooms"]}
                    self.assertGreater(len(elevations), 1)
                    self.assertTrue(all(floor.get("stairs") for floor in canonical["floors"]))

    def test_door_and_window_on_same_wall_are_separated(self):
        design = self.make_design(["bedroom", "bathroom"], (12, 14), 1)
        floor = design["floors"][0]
        door = floor["doors"][0]
        room = next(room for room in floor["rooms"] if room["id"] == door["room_id"])
        window = copy.deepcopy(door)
        window.update({"id": "test_same_wall_window", "type": "window", "width": 1.0, "height": 1.1, "sill_height": 0.9})
        floor["windows"].append(window)
        canonical, _ = self.assert_pipeline_valid(design)
        repaired_floor = canonical["floors"][0]
        repaired_door = next(item for item in repaired_floor["doors"] if item["id"] == door["id"])
        repaired_window = next(item for item in repaired_floor["windows"] if item["id"] == window["id"])
        self.assertEqual(repaired_door["wall_id"], repaired_window["wall_id"])
        door_axis = repaired_door["position"]["x"] if repaired_door["wall_side"] in ("south", "north") else repaired_door["position"]["y"]
        window_axis = repaired_window["position"]["x"] if repaired_window["wall_side"] in ("south", "north") else repaired_window["position"]["y"]
        self.assertGreaterEqual(abs(door_axis - window_axis), (repaired_door["width"] + repaired_window["width"]) / 2)
        self.assertIn(room["id"], repaired_door["room_id"])

    def test_crowded_front_wall_shrinks_window_before_blocking_approval(self):
        room = {
            "id": "living_01",
            "position": {"x": 0, "y": 0, "z": 0},
            "dimensions": {"width": 3.6, "depth": 4.0, "height": 3.0},
        }
        floor = {
            "id": "ground_floor",
            "walls": [{
                "id": "wall_ext_002",
                "start": {"x": 0, "y": 0},
                "end": {"x": 3.6, "y": 0},
                "connected_rooms": ["living_01"],
            }],
            "doors": [{
                "id": "door_main_01",
                "type": "main_entrance",
                "room_id": "living_01",
                "wall_side": "south",
                "wall_id": "wall_ext_002",
                "position": {"x": 2.9, "y": 0, "z": 0},
                "width": 1.1,
                "height": 2.1,
            }],
            "windows": [{
                "id": "win_living_01_south",
                "type": "window",
                "room_id": "living_01",
                "wall_side": "south",
                "wall_id": "wall_ext_002",
                "position": {"x": 1.2, "y": 0, "z": 0.9},
                "width": 2.4,
                "height": 1.2,
                "sill_height": 0.9,
            }],
        }
        report = {"critical_errors": [], "warnings": [], "repairs": []}

        _repair_openings(floor, {room["id"]: room}, report)

        self.assertEqual([], report["critical_errors"], report)
        self.assertAlmostEqual(1.1, floor["doors"][0]["width"])
        self.assertLess(floor["windows"][0]["width"], 2.4)
        used_width = (
            floor["doors"][0]["width"]
            + floor["windows"][0]["width"]
            + OPENING_GAP
            + 2 * WALL_MARGIN
        )
        self.assertLessEqual(used_width, 3.6 + 1e-6)

    def test_kitchen_sink_may_be_integrated_into_island(self):
        room = {
            "id": "kitchen_01",
            "position": {"x": 0, "y": 0, "z": 0},
            "dimensions": {"width": 2.6, "depth": 2.61, "height": 3.0},
        }
        floor = {
            "id": "ground_floor",
            "doors": [],
            "furniture": [
                {
                    "id": "island_kitchen_01",
                    "category": "kitchen_island",
                    "room_id": "kitchen_01",
                    "position": {"x": 1.3, "y": 1.3, "z": 0},
                    "dimensions": {"width": 1.8, "depth": 0.9, "height": 0.9},
                    "rotation": 0,
                },
                {
                    "id": "sink_kitchen_01",
                    "category": "kitchen_sink",
                    "room_id": "kitchen_01",
                    "position": {"x": 1.3, "y": 1.3, "z": 0},
                    "dimensions": {"width": 0.8, "depth": 0.55, "height": 0.3},
                    "rotation": 0,
                },
            ],
        }
        report = {"critical_errors": [], "warnings": [], "repairs": []}

        _repair_furniture(floor, {room["id"]: room}, report)

        self.assertEqual([], report["critical_errors"], report)
        self.assertEqual(2, len(floor["furniture"]))
        self.assertEqual(
            floor["furniture"][0]["position"],
            floor["furniture"][1]["position"],
        )

    def test_same_input_is_deterministic(self):
        first = self.make_design(["living_room", "kitchen", "bedroom", "bathroom"], (14, 18), 1)
        second = self.make_design(["living_room", "kitchen", "bedroom", "bathroom"], (14, 18), 1)
        first, _ = validate_and_repair_design(first, repair=True)
        second, _ = validate_and_repair_design(second, repair=True)
        for value in (first, second):
            value.pop("validation", None)
            value.pop("generation_validation", None)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_exact_user_room_program_overrides_gemini_extras(self):
        prompt = "create a one bedroom , one bathroom , kitchen and car parking and main gate entrance"
        constraints = infer_layout_constraints(prompt)
        self.assertEqual(
            {"bedroom": 1, "bathroom": 1, "kitchen": 1, "garage": 1},
            constraints["room_counts"],
        )
        self.assertEqual(0, constraints["attached_baths"])
        self.assertTrue(constraints["replace_room_program"])
        self.assertTrue(constraints["main_gate"])

        # Simulate Gemini returning its former unwanted defaults. The
        # deterministic normalizer must still honor the user's exact inventory.
        raw = {
            "style": "modern",
            "house": {"width": 14, "length": 18, "floors": 1},
            "rooms": [
                {"id": "bed_1", "type": "Bedroom"},
                {"id": "master_1", "type": "Master Bedroom"},
                {"id": "bath_1", "type": "Bathroom"},
                {"id": "kitchen_1", "type": "Kitchen"},
                {"id": "living_1", "type": "Living Room"},
                {"id": "garage_1", "type": "Garage"},
            ],
            "doors": [],
            "windows": [],
            "furniture": [],
        }

        design = _normalize_design(raw, prompt)
        self.assertCountEqual(
            ["bedroom", "bathroom", "kitchen", "garage"],
            [room["type"] for room in design["rooms"]],
        )
        self.assertEqual([], design["validation"]["critical_errors"])
        self.assertIn("gate", design["exterior"])

    def test_previous_design_json_does_not_change_current_prompt_counts(self):
        prompt = "create one bedroom, one bathroom and one kitchen"
        polluted_prompt = (
            f"{prompt}\nCurrent design JSON:\n"
            '{"rooms":[{"type":"Master Bedroom"},{"type":"Bedroom"}]}'
        )
        constraints = infer_layout_constraints(polluted_prompt)
        self.assertEqual(1, constraints["room_counts"]["bedroom"])
        self.assertEqual(1, constraints["room_counts"]["bathroom"])
        self.assertEqual(1, constraints["room_counts"]["kitchen"])
        self.assertTrue(constraints["replace_room_program"])

    def test_production_normalizer_preserves_metric_plot_and_requested_connections(self):
        raw = {
            "style": "modern",
            "site": {"plot": {"width": 11, "depth": 12}},
            "house": {"width": 11, "length": 12, "floors": 1},
            "rooms": [
                {"id": "living", "type": "living_room", "name": "Living Room"},
                {"id": "kitchen", "type": "kitchen", "name": "Kitchen"},
                {"id": "bedroom", "type": "bedroom", "name": "Bedroom"},
                {"id": "bathroom", "type": "bathroom", "name": "Bathroom"},
            ],
            "doors": [], "windows": [], "furniture": [],
        }
        refinement = (
            "Bathroom door must be with bedroom, not in kitchen, and kitchen door "
            "must be connected with living room."
        )
        constraints = infer_layout_constraints(refinement)
        self.assertIn(["bathroom", "bedroom"], constraints["connections"])
        self.assertIn(["kitchen", "living_room"], constraints["connections"])

        design = _normalize_design(raw, refinement)
        self.assertEqual({"width": 11.0, "depth": 12.0}, design["site"]["plot"])
        self.assertEqual([], design["validation"]["critical_errors"])
        connected = {
            frozenset(door.get("connected_room_ids", []))
            for door in design["floors"][0]["doors"]
            if door.get("type") == "interior_door"
        }
        self.assertIn(frozenset(("bedroom", "bathroom")), connected)
        self.assertIn(frozenset(("living", "kitchen")), connected)
        self.assertNotIn(frozenset(("kitchen", "bathroom")), connected)

    def test_window_refinement_changes_only_requested_bedroom_window(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom"],
            (11, 12),
            1,
        )
        base, report = validate_and_repair_design(base, repair=True)
        self.assertEqual([], report["critical_errors"], report)
        base["layout_approved"] = True
        base["approved_at"] = "2026-10-11T00:00:00Z"
        base["glb_url"] = "s3://old-version/house.glb"
        original = copy.deepcopy(base)

        refined, refinement = apply_targeted_refinement(
            base,
            "room one window from bedroom which is back side of bed",
        )

        self.assertTrue(refinement["handled"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertIsNotNone(refined)
        self.assertEqual(original, base, "refinement mutated the stored base version")
        self.assertFalse(refined["layout_approved"])
        self.assertNotIn("approved_at", refined)
        self.assertNotIn("glb_url", refined)

        base_floor = base["floors"][0]
        refined_floor = refined["floors"][0]
        bedroom = next(room for room in base_floor["rooms"] if room["type"] == "bedroom")
        base_windows = [
            window for window in base_floor["windows"]
            if window["room_id"] == bedroom["id"]
        ]
        refined_windows = [
            window for window in refined_floor["windows"]
            if window["room_id"] == bedroom["id"]
        ]
        self.assertEqual({"north", "west"}, {window["wall_side"] for window in base_windows})
        self.assertEqual(["west"], [window["wall_side"] for window in refined_windows])
        self.assertEqual(len(base_floor["windows"]) - 1, len(refined_floor["windows"]))

        for key in ("site", "building", "roof"):
            self.assertEqual(base[key], refined[key], f"unrelated {key} data changed")
        for key in ("rooms", "walls", "doors", "furniture", "stairs"):
            self.assertEqual(base_floor.get(key), refined_floor.get(key), f"unrelated {key} changed")

        adapted = adapt_gemini_to_blender_layout(refined, project_id="refinement-test", version_num=2)
        self.assertEqual(
            {window["id"] for window in refined_floor["windows"]},
            set(adapted["expected_inventory"]["window_ids"]),
        )


if __name__ == "__main__":
    unittest.main()
