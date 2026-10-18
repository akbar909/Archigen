import os
import sys
import unittest


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils.architectural_preflight import _boxes_overlap, _rotated_footprint, validate_and_repair_design
from utils.architectural_refinement import apply_targeted_refinement
from utils.layout_engine import ArchitecturalLayoutEngine
from utils.room_program_refinement import parse_room_program_mutations


class RoomProgramRefinementTests(unittest.TestCase):
    def make_three_floor_design(self):
        rooms = [
            {"id": "living", "type": "living_room", "floor": 0},
            {"id": "kitchen", "type": "kitchen", "floor": 0},
            {"id": "dining", "type": "dining_room", "floor": 0},
            {"id": "bath0", "type": "bathroom", "floor": 0},
            {"id": "garage", "type": "garage", "floor": 0},
            {"id": "bed1", "type": "bedroom", "floor": 1},
            {"id": "bed2", "type": "bedroom", "floor": 1},
            {"id": "office", "type": "home_office", "floor": 2},
        ]
        design = ArchitecturalLayoutEngine(unit="meters").generate_layout({
            "plot": {"width": 18, "depth": 24},
            "floors": 3,
            "rooms": rooms,
            "strict_room_program": True,
        })
        canonical, report = validate_and_repair_design(design, repair=True)
        self.assertEqual([], report["critical_errors"], report)
        return canonical

    def test_stair_core_is_part_of_furniture_repair(self):
        design = self.make_three_floor_design()
        floor = design["floors"][0]
        core = floor["stair_core"]
        cpos, cdim = core["position"], core["dimensions"]
        core_box = (
            cpos["x"], cpos["y"],
            cpos["x"] + cdim["width"], cpos["y"] + cdim["depth"],
        )
        for item in floor["furniture"]:
            width, depth = _rotated_footprint(item)
            position = item["position"]
            item_box = (
                position["x"] - width / 2, position["y"] - depth / 2,
                position["x"] + width / 2, position["y"] + depth / 2,
            )
            self.assertFalse(_boxes_overlap(core_box, item_box, 0.12), item["id"])

    def test_add_bedroom_to_ground_floor_reflows_program(self):
        base = self.make_three_floor_design()
        original_ground_count = len(base["floors"][0]["rooms"])

        refined, report = apply_targeted_refinement(base, "add one bedroom in ground floor")

        self.assertTrue(report["handled"])
        self.assertEqual([], report["errors"], report)
        self.assertEqual("room_program_reflow", report["scope"])
        self.assertFalse(report["layout_preserved"])
        self.assertEqual(3, len(refined["floors"]))
        self.assertEqual(original_ground_count + 1, len(refined["floors"][0]["rooms"]))
        self.assertEqual(
            1,
            sum(room["type"] == "bedroom" for room in refined["floors"][0]["rooms"]),
        )
        self.assertEqual([], refined["generation_validation"]["critical_errors"])

    def test_locator_room_is_not_mistaken_for_room_addition(self):
        self.assertEqual([], parse_room_program_mutations("add one window in the bedroom", 3))


if __name__ == "__main__":
    unittest.main()
