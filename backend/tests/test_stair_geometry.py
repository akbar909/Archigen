"""Regression coverage for stair geometry and generation-gating clearance."""

import copy
import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.architectural_vertical import validate_vertical_circulation
from utils.architectural_validator import ArchitecturalValidator
from utils.stair_geometry import default_risers, minimum_stair_dimensions, stair_approach_box, stair_metrics


def two_storey_fixture():
    floors = []
    for level in range(2):
        floors.append({"id": f"floor_{level}", "level": level, "elevation": level * 3,
                       "rooms": [{"id": f"lobby_{level}", "type": "stair_lobby", "position": {"x": 0, "y": 0},
                                  "dimensions": {"width": 4, "depth": 7, "height": 3}}],
                       "stairs": [], "stair_openings": [], "furniture": [], "doors": [], "walls": []})
    stair = {"id": "stair_0_1", "type": "u_shaped", "position": {"x": .4, "y": 1.2, "z": 0},
             "dimensions": {"width": 2.2, "depth": 3.4, "height": 3},
             "clear_width": 1, "landing_depth": 1, "steps": 18, "risers": 18, "headroom": 2.1,
             "access_depth": 1, "connects": {"lower_floor": "floor_0", "upper_floor": "floor_1"}}
    floors[0]["stairs"].append(stair)
    opening = {"id": "void_1", "serves_stair_id": stair["id"], "position": {"x": .4, "y": 1.2, "z": 3},
               "dimensions": {"width": 2.2, "depth": 3.4, "height": .2}}
    floors[1]["stair_openings"].append(opening)
    return {"floors": floors}


def validate(design):
    report = {"critical_errors": [], "warnings": []}
    validate_vertical_circulation(design["floors"], design, report)
    return report["critical_errors"]


class StairGeometryTests(unittest.TestCase):
    def test_minimum_footprints_meet_tread_landing_and_riser_targets(self):
        for kind in ("u_shaped", "l_shaped", "straight"):
            with self.subTest(kind=kind):
                minimum = minimum_stair_dimensions(kind, rise=3, clear_width=1)
                metrics = stair_metrics({"type": kind, "dimensions": minimum, **minimum}, rise=3)
                self.assertEqual([], metrics["errors"])
                self.assertAlmostEqual(.25, metrics["tread_depth"])
                self.assertLessEqual(metrics["riser_height"], .19)
        self.assertEqual(24, default_risers(4.2))
        self.assertEqual(18, default_risers(3))

    def test_short_run_cannot_be_hidden_by_claimed_tread_or_step_count(self):
        stair = two_storey_fixture()["floors"][0]["stairs"][0]
        stair["dimensions"]["depth"] = 2.8
        stair["tread"] = .3
        self.assertTrue(any("run too short" in error for error in stair_metrics(stair)["errors"]))
        stair["steps"] = stair["risers"] = 8
        errors = stair_metrics(stair)["errors"]
        self.assertTrue(any("at least 16" in error for error in errors))
        self.assertTrue(any("run too short" in error for error in errors))

    def test_reported_width_does_not_override_actual_flight_width(self):
        stair = two_storey_fixture()["floors"][0]["stairs"][0]
        stair["dimensions"]["width"] = 1.8
        self.assertTrue(any("narrower than 0.90" in error for error in stair_metrics(stair)["errors"]))
        stair["dimensions"]["width"] = 2.2
        stair["landing_depth"] = .9
        self.assertTrue(any("landing" in error for error in stair_metrics(stair)["errors"]))

    def test_actual_floor_rise_requires_enough_risers(self):
        stair = two_storey_fixture()["floors"][0]["stairs"][0]
        self.assertTrue(any("0.19" in error for error in stair_metrics(stair, rise=4.2)["errors"]))

    def test_explicit_stair_parameters_require_finite_numbers(self):
        for field in ("clear_width", "landing_depth", "rotation", "access_depth"):
            for value in ("bad", "NaN", "Infinity", float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value):
                    stair = two_storey_fixture()["floors"][0]["stairs"][0]
                    stair[field] = value
                    self.assertTrue(any(f"invalid {field}" in error for error in stair_metrics(stair)["errors"]))
            for value in (None, "0" if field == "rotation" else "1.0"):
                with self.subTest(field=field, valid_value=value):
                    stair = two_storey_fixture()["floors"][0]["stairs"][0]
                    stair[field] = value
                    if field == "clear_width" and value is None:
                        stair["landing_depth"] = stair["access_depth"] = 1.1
                    self.assertEqual([], stair_metrics(stair)["errors"])
        stair = two_storey_fixture()["floors"][0]["stairs"][0]
        stair["access_depth"] = ".8"
        self.assertTrue(any("clear floor access" in error for error in stair_metrics(stair)["errors"]))

    def test_valid_top_floor_opening_does_not_need_an_upward_stair(self):
        design = two_storey_fixture()
        self.assertEqual([], validate(design))
        validator = ArchitecturalValidator(design)
        validator._check_staircase_alignment()
        self.assertEqual([], validator.errors)

    def test_preflight_rejects_short_stair_and_private_upper_access(self):
        design = two_storey_fixture()
        design["floors"][0]["stairs"][0]["dimensions"]["depth"] = 2.8
        self.assertTrue(any("run too short" in error for error in validate(design)))
        design = two_storey_fixture()
        design["floors"][1]["rooms"][0]["type"] = "bedroom"
        self.assertTrue(any("private or service room" in error for error in validate(design)))

    def test_void_and_approach_furniture_block_without_stair_core_metadata(self):
        for point, expected in (((1.2, 2), "stair opening"), ((1.2, .6), "upper approach")):
            with self.subTest(point=point):
                design = two_storey_fixture()
                design["floors"][1]["furniture"].append({"id": "sofa", "position": {"x": point[0], "y": point[1]},
                                                         "dimensions": {"width": .5, "depth": .5, "height": .5}})
                self.assertTrue(any(expected in error.lower() for error in validate(design)))

    def test_door_swing_and_full_wall_segment_are_checked(self):
        design = two_storey_fixture()
        design["floors"][0]["doors"].append({"id": "door", "position": {"x": 1.4, "y": 1.2},
                                             "width": .9, "wall_side": "south"})
        self.assertTrue(any("swings into stair" in error.lower() for error in validate(design)))
        design = two_storey_fixture()
        design["floors"][1]["walls"].append({"id": "crossing", "start": {"x": -10, "y": 2}, "end": {"x": 1, "y": 2}})
        self.assertTrue(any("Wall 'crossing'" in error for error in validate(design)))

    def test_door_approach_is_reserved_even_when_door_swings_away(self):
        design = two_storey_fixture()
        stair = design["floors"][0]["stairs"][0]
        stair["position"]["y"] = 3
        design["floors"][1]["stair_openings"][0]["position"]["y"] = 3
        door = {"id": "north_door", "position": {"x": 1.5, "y": 7}, "width": .9,
                "wall_side": "north", "swing_direction": "outward", "room_id": "lobby_0"}
        design["floors"][0]["doors"].append(door)
        errors = validate(design)
        self.assertTrue(any("blocks the approach to door 'north_door'" in error for error in errors))
        self.assertFalse(any("swings into" in error for error in errors))

    def test_clear_side_door_does_not_need_furniture_comfort_margin(self):
        design = two_storey_fixture()
        # The door aperture ends at y=1.10, clear of the stair beginning at
        # y=1.20. Its optional 0.35 m furniture side margin would overlap.
        design["floors"][0]["doors"].append({"id": "side_door", "position": {"x": 0, "y": .65},
                                             "width": .9, "wall_side": "west", "swing_direction": "outward",
                                             "room_id": "lobby_0"})
        self.assertEqual([], validate(design))

    def test_upper_door_approach_is_checked_on_both_sides_of_shared_wall(self):
        design = two_storey_fixture()
        upper = design["floors"][1]
        upper["rooms"][0]["dimensions"]["depth"] = 5
        upper["rooms"].append({"id": "bedroom", "type": "bedroom", "position": {"x": 0, "y": 5, "z": 3},
                               "dimensions": {"width": 4, "depth": 3, "height": 3}})
        upper["doors"].append({"id": "shared_door", "position": {"x": 1.5, "y": 5, "z": 3}, "width": .9,
                               "wall_side": "south", "room_id": "bedroom", "connected_room_id": "lobby_1"})
        errors = validate(design)
        self.assertTrue(any("Stair opening 'void_1' blocks the approach to door 'shared_door'" in error for error in errors))
        self.assertFalse(any("swings into" in error for error in errors))

    def test_void_approach_uses_source_type_and_declared_access_depth(self):
        opening = {"type": "stair_void", "source_stair_type": "straight", "position": {"x": 1, "y": 2},
                   "dimensions": {"width": 1.2, "depth": 6, "height": .2}, "clear_width": 1.1, "access_depth": 1.5}
        self.assertEqual((1, 8, 2.2, 9.5), stair_approach_box(opening, upper=True))
        opening["source_stair_type"] = "l_shaped"
        self.assertEqual((2.2, 6.9, 3.7, 8), stair_approach_box(opening, upper=True))

    def test_missing_or_shifted_opening_is_rejected(self):
        design = two_storey_fixture()
        design["floors"][1]["stair_openings"][0]["position"]["x"] += .1
        self.assertTrue(any("not aligned" in error for error in validate(design)))
        design["floors"][1]["stair_openings"] = []
        self.assertTrue(any("no slab opening" in error for error in validate(design)))

    def test_generation_rejects_schema_valid_json_with_an_unsafe_stair(self):
        from utils.architectural_preflight import validate_and_repair_design
        from utils.gemini_normalization import _validate_home_design_schema
        from utils.layout_engine import ArchitecturalLayoutEngine

        design = ArchitecturalLayoutEngine(unit="meters").generate_layout({
            "plot": {"width": 18, "depth": 24}, "floors": 2,
            "rooms": [{"type": "living_room", "floor": 0},
                      {"type": "kitchen", "floor": 0},
                      {"type": "bedroom", "floor": 1}],
        })
        design, report = validate_and_repair_design(design)
        self.assertEqual([], report["critical_errors"])
        self.assertTrue(_validate_home_design_schema(design)[0])
        design["floors"][0]["stairs"][0]["dimensions"]["depth"] = 2.0
        design, report = validate_and_repair_design(design)
        valid, errors = _validate_home_design_schema(design)
        self.assertFalse(valid)
        self.assertTrue(any("run too short" in message for message in errors))

    def test_blender_honors_explicit_landing_instead_of_clamping_it(self):
        class Object(dict):
            def __init__(self):
                self.data = types.SimpleNamespace(materials=[])
                self.rotation_euler = [0, 0, 0]

        objects = []
        context = types.SimpleNamespace(active_object=None)

        def add_cube(**kwargs):
            obj = Object()
            obj.location = kwargs.get("location")
            context.active_object = obj
            objects.append(obj)

        runtime = types.ModuleType("generate_house_runtime")
        runtime.bpy = types.SimpleNamespace(context=context, ops=types.SimpleNamespace(mesh=types.SimpleNamespace(primitive_cube_add=add_cube)))
        for name in ("BLENDER_ROOT", "SCRIPT_DIR", "export_glb", "import_asset", "mathutils", "place_furniture"):
            setattr(runtime, name, None)
        materials = types.ModuleType("generate_house_materials")
        materials.apply_box_uv_mapping = None
        materials.create_pbr_material = lambda *args: None
        opening_models = types.ModuleType("generate_house_opening_models")
        opening_models._try_import_gate_model = None
        script = Path(__file__).resolve().parents[2] / "blender/scripts/generate_house_vertical.py"
        spec = importlib.util.spec_from_file_location("stair_renderer_under_test", script)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"generate_house_runtime": runtime, "generate_house_materials": materials,
                                      "generate_house_opening_models": opening_models}):
            spec.loader.exec_module(module)
        stair = copy.deepcopy(two_storey_fixture()["floors"][0]["stairs"][0])
        stair["dimensions"]["depth"] = 3.8
        stair["landing_depth"] = 1.4
        created = module.build_staircase(stair, 0, 3)
        landing = next(obj for obj in created if obj.get("archgen_stair_component") == "landing")
        treads = [obj for obj in created if obj.get("archgen_stair_component") == "tread"]
        self.assertEqual(18, len(treads))
        self.assertAlmostEqual(1.4, landing.scale[1])
        self.assertAlmostEqual(stair_metrics(stair)["tread_depth"] + .025, treads[0].scale[1])
        across = {**stair, "run_axis": "x", "dimensions": {"width": 3.8, "depth": 2.2, "height": 3}}
        turned = module.build_staircase(across, 0, 3)
        self.assertEqual(len(created), len(turned))
        sx, sy = stair["position"]["x"], stair["position"]["y"]
        for original, rotated in zip(created, turned):
            self.assertAlmostEqual(sx + 3.8 - (original.location[1] - sy), rotated.location[0])
            self.assertAlmostEqual(sy + original.location[0] - sx, rotated.location[1])
            self.assertAlmostEqual(original.location[2], rotated.location[2])
            self.assertAlmostEqual(math.pi / 2, rotated.rotation_euler[2])


if __name__ == "__main__":
    unittest.main()
