"""Regression coverage for prose requests with floor-specific room lists."""

import os
import sys
import unittest
from collections import Counter


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils.floor_room_program import parse_floor_room_counts
from utils.gemini_prompt import build_generation_prompt, infer_layout_constraints
from utils.architectural_preflight import validate_and_repair_design
from utils.layout_engine import ArchitecturalLayoutEngine


DOUBLE_STOREY_PROMPT = """Design a modern double storey home on a 25 \u00d7 40 ft plot, with the entrance facing north.

Ground floor: a living room, compact dining area, kitchen, 1 shared bathroom, and a small guest bedroom.

First floor: 2 bedrooms, 1 shared bathroom, a small family lounge, and a front balcony.

Include a compact U-shaped staircase with a landing and at least 3 ft clear width. Align the staircase and its opening between floors, provide clear access on both levels, and keep furniture away from the stairs. Align bathrooms vertically where practical.

Use practical room sizes, minimal corridors, exterior windows, and appropriately scaled furniture. Ensure every room is accessible without passing through another bedroom. Avoid overlapping rooms, furniture, and door swings."""


class PromptFloorProgramTests(unittest.TestCase):
    def test_double_storey_request_retains_plot_orientation_and_all_rooms(self):
        constraints = infer_layout_constraints(DOUBLE_STOREY_PROMPT)
        self.assertEqual({"width": 7.62, "depth": 12.192}, constraints["plot"])
        self.assertEqual("north", constraints["orientation"])
        self.assertEqual(2, constraints["floors_count"])
        self.assertTrue(constraints["floors_explicit"])
        self.assertTrue(constraints["replace_room_program"])
        self.assertEqual({
            0: {"living_room": 1, "dining_room": 1, "kitchen": 1, "bathroom": 1, "bedroom": 1},
            1: {"bedroom": 2, "bathroom": 1, "living_room": 1, "balcony": 1},
        }, constraints["floor_room_counts"])
        self.assertEqual({
            "bedroom": 3, "bathroom": 2, "kitchen": 1,
            "living_room": 2, "dining_room": 1, "balcony": 1,
        }, constraints["room_counts"])
        self.assertEqual(0, constraints["attached_baths"])
        generated_prompt = build_generation_prompt(DOUBLE_STOREY_PROMPT)
        self.assertIn("STRICT PER-FLOOR PROGRAM:", generated_prompt)
        self.assertIn("first floor: 2 bedroom", generated_prompt)

    def test_legacy_floor_assignment_clauses_remain_supported(self):
        self.assertEqual({0: {"bedroom": 1}, 1: {"bedroom": 2}},
                         parse_floor_room_counts("1 bedroom on ground floor and 2 on first floor"))

    def test_floor_list_does_not_count_following_privacy_instructions(self):
        prompt = "Ground floor: a kitchen and a bathroom. Keep access independent of another bedroom."
        self.assertEqual({0: {"kitchen": 1, "bathroom": 1}}, parse_floor_room_counts(prompt))

    def test_explicit_sizes_do_not_override_plot_with_room_dimensions(self):
        prompt = "Design a home on a 25 ft x 40 ft plot, north-facing entrance. A bedroom is 3 x 4 m."
        constraints = infer_layout_constraints(prompt)
        self.assertEqual({"width": 7.62, "depth": 12.192}, constraints["plot"])
        self.assertEqual("north", constraints["orientation"])

    def test_room_dimensions_alone_are_not_assumed_to_be_the_plot(self):
        constraints = infer_layout_constraints("Design a 3 x 4 m bedroom with a west window.")
        self.assertNotIn("plot", constraints)
        self.assertNotIn("orientation", constraints)

    def test_nearby_room_size_cannot_replace_the_explicit_plot(self):
        constraints = infer_layout_constraints("A 3 x 4 m bedroom on a 25 x 40 ft plot, entrance facing east.")
        self.assertEqual({"width": 7.62, "depth": 12.192}, constraints["plot"])
        self.assertEqual("east", constraints["orientation"])

    def test_compact_plot_keeps_program_setbacks_and_shared_stair_access(self):
        # Simulate an LLM response with its former oversized plot and one-floor
        # default. The actual instruction must still constrain the solver.
        seed = {
            "style": "modern", "site": {"plot": {"width": 30, "depth": 40}},
            "house": {"floors": 1}, "rooms": [{"id": "unsolicited_ensuite", "type": "bathroom",
                 "access": "ensuite_only", "ensuite_for_room_id": "missing_owner"},
                 {"id": "aaa_public", "type": "living_room"}, {"id": "zzz_guest", "type": "bedroom"}],
        }
        engine = ArchitecturalLayoutEngine(unit="meters")
        design = engine.solve_or_refine_design(seed, DOUBLE_STOREY_PROMPT)
        design, report = validate_and_repair_design(design)
        self.assertEqual([], report["critical_errors"], report)
        self.assertEqual({"width": 7.62, "depth": 12.19}, design["site"]["plot"])
        self.assertEqual({"front": 2.19, "back": 1.46, "left": .76, "right": .76}, design["site"]["setbacks"])
        self.assertEqual(8.54, design["building"]["depth"])
        self.assertEqual(2, len(design["floors"]))
        expected = infer_layout_constraints(DOUBLE_STOREY_PROMPT)["floor_room_counts"]
        for level, floor in enumerate(design["floors"]):
            rooms = {r["id"]: r for r in floor["rooms"]}
            self.assertEqual(expected[level], dict(Counter(r["type"] for r in rooms.values() if r["type"] != "stair_lobby")))
            self.assertFalse(any(r["type"] in {"hallway", "corridor"} for r in rooms.values()))
            graph = {rid: set() for rid in rooms}
            for door in floor["doors"]:
                ids = [rid for rid in door["connected_room_ids"] if rid in rooms]
                for rid in ids:
                    graph[rid].update(other for other in ids if other != rid)
            start = (next(d["room_id"] for d in floor["doors"] if d["type"] == "main_entrance") if level == 0
                     else next(r["id"] for r in rooms.values() if r["type"] == "stair_lobby"))
            reached, pending = {start}, [start]
            while pending:
                for rid in graph[pending.pop()] - reached:
                    reached.add(rid)
                    if not any(token in rooms[rid]["type"] for token in ("bed", "bath")):
                        pending.append(rid)
            self.assertEqual(set(rooms), reached, "Private rooms must not become passages")
        baths = [next(r for r in f["rooms"] if r["type"] == "bathroom") for f in design["floors"]]
        self.assertTrue(all(bath["access"] == "shared" and not bath.get("ensuite_for_room_id") for bath in baths))
        self.assertEqual(baths[0]["dimensions"], baths[1]["dimensions"])
        self.assertEqual(baths[0]["position"]["x"], baths[1]["position"]["x"])
        self.assertEqual(baths[0]["position"]["y"], baths[1]["position"]["y"])
        balcony = next(r for r in design["floors"][1]["rooms"] if r["type"] == "balcony")
        self.assertAlmostEqual(12.19-1.46, balcony["position"]["y"]+balcony["dimensions"]["depth"])
        self.assertTrue(balcony["open_air"])
        guards = [w for w in design["floors"][1]["walls"] if w.get("role") == "balcony_guard"]
        self.assertTrue(guards)
        self.assertTrue(all(w["height"] == 1.10 for w in guards))
        self.assertFalse(any(w["room_id"] == balcony["id"] for w in design["floors"][1]["windows"]))
        stair = design["floors"][0]["stairs"][0]
        from utils.stair_geometry import stair_metrics
        self.assertEqual("x", stair["run_axis"])
        self.assertEqual([], stair_metrics(stair)["errors"])
        self.assertGreaterEqual(stair_metrics(stair)["tread_depth"], .25)
        self.assertGreaterEqual(stair["clear_width"], 3*.3048)
        opening = design["floors"][1]["stair_openings"][0]
        self.assertEqual("x", opening["run_axis"])
        self.assertEqual(stair["position"]["x"], opening["position"]["x"])
        self.assertEqual(stair["position"]["y"], opening["position"]["y"])

    def test_compact_planner_does_not_reduce_explicit_setbacks_to_force_a_fit(self):
        constraints = infer_layout_constraints(DOUBLE_STOREY_PROMPT)
        constraints["setbacks"] = {"front": 3.5, "back": 2.5, "left": .76, "right": .76}
        with self.assertRaisesRegex(ValueError, "only 6.19 m is available"):
            ArchitecturalLayoutEngine(unit="meters").solve_or_refine_design(
                {"style": "modern", "rooms": []}, DOUBLE_STOREY_PROMPT, constraints_override=constraints)

    def test_larger_plot_solves_the_same_complete_floor_program(self):
        prompt = DOUBLE_STOREY_PROMPT.replace("25 \u00d7 40 ft", "40 x 60 ft")
        engine = ArchitecturalLayoutEngine(unit="meters")
        design = engine.solve_or_refine_design({"style": "modern", "rooms": []}, prompt)
        design, report = validate_and_repair_design(design, repair=True)
        self.assertEqual([], report["critical_errors"], report)
        self.assertEqual({"width": 12.19, "depth": 18.29}, design["site"]["plot"])
        self.assertEqual("north", design["site"]["road"]["side"])
        main_door = next(door for door in design["floors"][0]["doors"] if door["type"] == "main_entrance")
        self.assertEqual("north", main_door["wall_side"])
        self.assertEqual(2, len(design["floors"]))
        expected = infer_layout_constraints(prompt)["floor_room_counts"]
        for level, floor in enumerate(design["floors"]):
            self.assertEqual(expected[level], dict(Counter(
                room["type"] for room in floor["rooms"] if room["type"] not in {"stair_lobby", "hallway"}
            )))
            rooms = {room["id"]: room for room in floor["rooms"]}
            graph = {room_id: set() for room_id in rooms}
            for door in floor["doors"]:
                pair = [room_id for room_id in door.get("connected_room_ids", []) if room_id in rooms]
                for room_id in pair:
                    graph[room_id].update(value for value in pair if value != room_id)
            start = (next(door["room_id"] for door in floor["doors"] if door["type"] == "main_entrance")
                     if level == 0 else next(room["id"] for room in floor["rooms"] if room["type"] == "stair_lobby"))
            reached, pending = {start}, [start]
            while pending:
                for neighbor in graph[pending.pop()] - reached:
                    reached.add(neighbor)
                    if not any(token in rooms[neighbor]["type"] for token in ("bed", "bath")):
                        pending.append(neighbor)
            self.assertEqual(set(rooms), reached, "A room requires passage through another bedroom or bathroom")
        stair = design["floors"][0]["stairs"][0]
        opening = design["floors"][1]["stair_openings"][0]
        self.assertEqual(stair["id"], opening["serves_stair_id"])
        self.assertEqual(stair["position"]["x"], opening["position"]["x"])
        self.assertEqual(stair["position"]["y"], opening["position"]["y"])

    def test_actual_entrance_gate_driveway_and_path_follow_each_frontage(self):
        for side in ("north", "south", "east", "west"):
            with self.subTest(side=side):
                design = ArchitecturalLayoutEngine(unit="meters").generate_layout({
                    "plot": {"width": 12, "depth": 16}, "floors": 1,
                    "orientation": side, "strict_room_program": True,
                    "rooms": [{"id": "living", "type": "living_room"}],
                })
                design, report = validate_and_repair_design(design, repair=True)
                self.assertEqual([], report["critical_errors"], report)
                door = next(door for door in design["doors"] if door["type"] == "main_entrance")
                self.assertEqual(side, door["wall_side"])
                gate = design["exterior"]["gate"]
                vertical = side in {"east", "west"}
                boundary_axis = "x" if vertical else "y"
                along_axis = "y" if vertical else "x"
                boundary = 12 if side == "east" else 16 if side == "north" else 0
                self.assertEqual(boundary, gate["position"][boundary_axis])
                path = design["exterior"]["entrance_path"]
                self.assertEqual(boundary, path["start"][boundary_axis])
                self.assertAlmostEqual(gate["position"][along_axis] + gate["width"] / 2,
                                       path["start"][along_axis], places=2)
                for axis in ("x", "y"):
                    self.assertAlmostEqual(door["position"][axis], path["end"][axis], places=2)
                driveway = design["exterior"]["driveway"]
                outer_edge = driveway["position"][boundary_axis]
                if side in {"north", "east"}:
                    outer_edge += driveway["depth" if boundary_axis == "y" else "width"]
                self.assertAlmostEqual(boundary, outer_edge)

    def test_private_bedroom_is_not_used_as_north_entrance_for_a_home(self):
        engine = ArchitecturalLayoutEngine(unit="meters")
        rooms = [
            {"id": "living", "type": "living_room", "position": {"x": 0, "y": 0, "z": 0},
             "dimensions": {"width": 4, "depth": 4}},
            {"id": "bed", "type": "bedroom", "position": {"x": 0, "y": 4, "z": 0},
             "dimensions": {"width": 4, "depth": 4}},
        ]
        walls = engine._compute_floor_walls(rooms, .2, 0, 0, 4, 8)
        with self.assertRaisesRegex(ValueError, "no usable north-facing entrance"):
            engine._generate_doors(rooms, walls, True, entrance_side="north")


if __name__ == "__main__":
    unittest.main()
