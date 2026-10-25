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
from utils.architectural_refinement import apply_targeted_refinement, is_explicit_full_redesign
from utils.blender_service import adapt_gemini_to_blender_layout
from utils.layout_engine import ArchitecturalLayoutEngine
from utils.gemini_layout import _normalize_design, infer_layout_constraints
from utils.gemini_layout import _validate_home_design_schema
from utils.gemini import generate_home_design
from utils.wizard_constraints import build_prompt_layout_constraints, build_wizard_layout_constraints


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
                    self.assertTrue(all(floor.get("stairs") for floor in canonical["floors"][:-1]))
                    self.assertFalse(canonical["floors"][-1].get("stairs"))
                    self.assertTrue(all(floor.get("stair_openings") for floor in canonical["floors"][1:]))

    def test_two_three_and_four_storey_vertical_architecture(self):
        engine = ArchitecturalLayoutEngine(unit="meters")
        for floor_count in (2, 3, 4):
            requested_rooms = [
                {"id": "living", "type": "living_room", "floor": 0},
                {"id": "kitchen", "type": "kitchen", "floor": 0},
            ]
            for level in range(1, floor_count):
                requested_rooms.extend([
                    {"id": f"bedroom_{level}", "type": "bedroom", "floor": level},
                    {"id": f"bathroom_{level}", "type": "bathroom", "floor": level},
                ])

            with self.subTest(floors=floor_count):
                design = engine.generate_layout({
                    "project_name": f"{floor_count} Storey Test",
                    "plot": {"width": 18, "depth": 24},
                    "floors": floor_count,
                    "rooms": requested_rooms,
                })
                canonical, adapted = self.assert_pipeline_valid(design)
                self.assertEqual(floor_count, len(canonical["floors"]))
                self.assertEqual(list(range(floor_count)), [floor["level"] for floor in canonical["floors"]])
                self.assertEqual(
                    [level * 3.0 for level in range(floor_count)],
                    [floor["elevation"] for floor in canonical["floors"]],
                )

                all_room_ids = []
                all_wall_ids = []
                all_opening_ids = []
                for level, floor in enumerate(canonical["floors"]):
                    all_room_ids.extend(room["id"] for room in floor["rooms"])
                    all_wall_ids.extend(wall["id"] for wall in floor["walls"])
                    all_opening_ids.extend(item["id"] for item in floor["doors"] + floor["windows"])
                    self.assertTrue(all(room["position"]["z"] == level * 3.0 for room in floor["rooms"]))
                    self.assertTrue(all(wall["floor_level"] == level for wall in floor["walls"]))
                    wall_ids = {wall["id"] for wall in floor["walls"]}
                    for opening in floor["doors"] + floor["windows"]:
                        self.assertEqual(level, opening["floor_level"])
                        self.assertIn(opening["wall_id"], wall_ids)

                    if level < floor_count - 1:
                        self.assertEqual(1, len(floor["stairs"]))
                        stair = floor["stairs"][0]
                        self.assertEqual(floor["id"], stair["connects"]["lower_floor"])
                        self.assertEqual(canonical["floors"][level + 1]["id"], stair["connects"]["upper_floor"])
                    else:
                        self.assertEqual([], floor["stairs"])
                    if level > 0:
                        self.assertEqual(1, len(floor["stair_openings"]))
                        previous_stair = canonical["floors"][level - 1]["stairs"][0]
                        opening = floor["stair_openings"][0]
                        self.assertEqual(previous_stair["id"], opening["serves_stair_id"])
                        self.assertEqual(previous_stair["position"]["x"], opening["position"]["x"])
                        self.assertEqual(previous_stair["position"]["y"], opening["position"]["y"])

                self.assertEqual(len(all_room_ids), len(set(all_room_ids)))
                self.assertEqual(len(all_wall_ids), len(set(all_wall_ids)))
                self.assertEqual(len(all_opening_ids), len(set(all_opening_ids)))
                self.assertEqual(
                    set(range(floor_count)),
                    {room["floor_level"] for room in adapted["rooms"]},
                )

    def test_two_floor_wizard_program_is_structured_exact_and_approval_safe(self):
        wizard = {
            "plot": {
                "width": "40", "length": "60", "unit": "ft", "floors": 2,
                "buildingType": "house", "orientation": "north", "roadAccess": "front",
                "coverage": "60",
                "setbacks": {"front": "10", "rear": "6", "left": "4", "right": "4"},
            },
            "design": {
                "architecturalStyle": "modern", "roofType": "flat",
                "exteriorColor": "white", "wallMaterial": "plaster",
                "interiorStyle": "contemporary", "flooringMaterial": "tile",
                "furniture": "fully_furnished", "designPriority": "balanced",
                "budget": "standard",
            },
            "rooms": [
                {"type": "living_room", "count": 1, "floor": 0, "preferredSize": "large", "preferredLocation": "front"},
                {"type": "drawing_room", "count": 1, "floor": 0, "preferredSize": "medium", "preferredLocation": "front"},
                {"type": "dining_room", "count": 1, "floor": 0},
                {"type": "kitchen", "count": 1, "floor": 0, "preferredLocation": "back"},
                {"type": "master_bedroom", "count": 1, "floor": 0, "preferredSize": "large", "preferredLocation": "back", "attachedBathroom": True},
                {"type": "bathroom", "count": 1, "floor": 0, "preferredSize": "small"},
                {"type": "garage", "count": 1, "floor": 0, "preferredLocation": "front"},
                {"type": "storage_room", "count": 1, "floor": 0, "preferredSize": "small"},
                {"type": "bedroom", "count": 3, "floor": 1, "attachedBathroom": True},
                {"type": "study_room", "count": 1, "floor": 1, "preferredLocation": "front"},
                {"type": "prayer_room", "count": 1, "floor": 1, "preferredSize": "small"},
                {"type": "laundry_room", "count": 1, "floor": 1, "preferredSize": "small", "preferredLocation": "back"},
                {"type": "balcony", "count": 1, "floor": 1, "preferredLocation": "front"},
                {"type": "terrace", "count": 1, "floor": 1, "preferredLocation": "back"},
            ],
            "features": {
                "front_garden": True, "boundary_wall": True,
                "entrance_gate": True, "car_parking": True,
                "balcony": True, "rooftop_terrace": True,
                "exterior_lighting": True, "solar_panels": True,
            },
            "featureConfigs": {"car_parking": {"parkingSpaces": 1}},
            "specialRequirements": "",
        }
        constraints = build_wizard_layout_constraints(wizard)
        design = generate_home_design(
            "Structured wizard request",
            constraints_prompt="Ground + 1 Floor",
            layout_constraints=constraints,
        )
        canonical, _adapted = self.assert_pipeline_valid(design)

        self.assertEqual(2, canonical["building"]["floors"])
        self.assertEqual([0, 1], [floor["level"] for floor in canonical["floors"]])
        self.assertEqual({"width": 12.19, "depth": 18.29}, canonical["site"]["plot"])
        self.assertEqual(
            {"front": 3.05, "back": 1.83, "left": 1.22, "right": 1.22},
            canonical["site"]["setbacks"],
        )
        self.assertEqual(60.0, canonical["site"]["max_coverage"])
        self.assertEqual("fully_furnished", canonical["design_preferences"]["furniture"])
        self.assertTrue(canonical["features"]["solar_panels"])
        self.assertEqual(11, len(canonical["floors"][0]["rooms"]))
        self.assertEqual(13, len(canonical["floors"][1]["rooms"]))
        self.assertTrue(all(
            sum(room["type"] == "hallway" for room in floor["rooms"]) == 1
            for floor in canonical["floors"]
        ))
        self.assertEqual(
            3,
            sum(room["type"] == "bedroom" for room in canonical["floors"][1]["rooms"]),
        )
        self.assertTrue(all(
            any(room["type"] == "stair_lobby" for room in floor["rooms"])
            for floor in canonical["floors"]
        ))

        # Every requested attached bathroom is a private, one-door ensuite for
        # its exact bedroom instance. It must never become a shared bathroom,
        # a bathroom bank, or a shortcut into another room.
        private_ensuites = [
            room
            for floor in canonical["floors"]
            for room in floor["rooms"]
            if room.get("access") == "ensuite_only"
        ]
        self.assertEqual(4, len(private_ensuites))
        for floor in canonical["floors"]:
            room_map = {room["id"]: room for room in floor["rooms"]}
            interior_pairs = [
                set(door.get("connected_room_ids", []))
                for door in floor["doors"]
                if "exterior" not in door.get("connected_room_ids", [])
            ]
            self.assertFalse(any(
                len(pair) == 2
                and all("bath" in room_map[room_id]["type"] for room_id in pair)
                for pair in interior_pairs
            ))
            self.assertFalse(any(
                len(pair) == 2
                and all("bedroom" in room_map[room_id]["type"] for room_id in pair)
                for pair in interior_pairs
            ))
            for destination in (
                room for room in floor["rooms"]
                if room["type"] in {"bathroom", "storage_room"}
                and room.get("access") != "ensuite_only"
            ):
                self.assertEqual(
                    1,
                    sum(destination["id"] in pair for pair in interior_pairs),
                    f"{destination['id']} must not be used as circulation",
                )
            for ensuite in (room for room in floor["rooms"] if room.get("access") == "ensuite_only"):
                owner_id = ensuite["ensuite_for_room_id"]
                owner = room_map[owner_id]
                self.assertEqual(ensuite["id"], owner.get("ensuite_id"))
                incident = [pair for pair in interior_pairs if ensuite["id"] in pair]
                self.assertEqual([{ensuite["id"], owner_id}], incident)

        # This compact kitchen cannot support professional island clearances;
        # omitting the optional island is safer than blocking plan approval.
        kitchen = next(room for room in canonical["floors"][0]["rooms"] if room["type"] == "kitchen")
        kitchen_items = [
            item for item in canonical["floors"][0]["furniture"]
            if item["room_id"] == kitchen["id"]
        ]
        self.assertFalse(any("island" in str(item.get("asset", "")) for item in kitchen_items))

    def test_complete_wizard_text_prompt_uses_exact_deterministic_program(self):
        prompt = (
            "Design a house on a 40x60 feet north-facing plot. 2 floors total (Ground + 1 Floor). "
            "Road access from front. Setbacks: front: 10ft, rear: 6ft, left: 4ft, right: 4ft. "
            "Rooms: 1 Living Room on Ground Floor (large) at front, "
            "1 Drawing Room on Ground Floor (medium) at front, "
            "1 Dining Room on Ground Floor (medium), "
            "1 Master Bedroom on Ground Floor (large) with attached bathroom at back, "
            "1 Bathroom on Ground Floor (small), 1 Garage on Ground Floor (medium) at front, "
            "1 Kitchen on Ground Floor (medium) at back, 1 Storage Room on Ground Floor (small), "
            "3 Bedroom on 1st Floor (medium) with attached bathroom, "
            "1 Study Room on 1st Floor (medium) at front, 1 Prayer Room on 1st Floor (small), "
            "1 Balcony on 1st Floor (medium) at front, 1 Laundry Room on 1st Floor (small) at back, "
            "1 Terrace on 1st Floor (medium) at back. Architectural style: Modern. Roof: flat. "
            "Exterior color: white. Wall material: plaster. Interior style: contemporary. "
            "Flooring: tile. Furniture: Fully Furnished. Design priority: Balanced. "
            "Additional features: Front Garden, Boundary Wall, Entrance Gate, Car Parking, "
            "Rooftop Terrace, Balcony, Exterior Lighting, Solar Panels, Laundry Area."
        )
        constraints = build_prompt_layout_constraints(prompt)
        self.assertIsNotNone(constraints)
        self.assertEqual("structured_prompt", constraints["source"])
        self.assertEqual(2, constraints["floors_count"])
        self.assertEqual("north", constraints["orientation"])
        self.assertEqual({"width": 12.192, "depth": 18.288}, constraints["plot"])
        self.assertEqual(
            {"front": 3.048, "back": 1.829, "left": 1.219, "right": 1.219},
            constraints["setbacks"],
        )
        self.assertEqual(3, constraints["floor_room_counts"][1]["bedroom"])
        self.assertEqual(4, constraints["attached_baths"])
        self.assertTrue(constraints["features"]["solar_panels"])

        complete_copy = prompt.replace(
            "Rooms:", "Maximum coverage: 60%. Rooms:", 1
        ).replace(
            "Additional features:", "Budget: Standard. Additional features:", 1
        )
        complete_constraints = build_prompt_layout_constraints(complete_copy)
        self.assertEqual(60.0, complete_constraints["max_coverage"])
        self.assertEqual("standard", complete_constraints["design_preferences"]["budget"])
        self.assertEqual(constraints["setbacks"], complete_constraints["setbacks"])

        # No explicit constraints object is passed here: this exercises the
        # pasted/free-text API path and must not fall through to Gemini.
        design = generate_home_design(prompt, constraints_prompt=prompt)
        canonical, _adapted = self.assert_pipeline_valid(design)
        self.assertEqual(2, canonical["building"]["floors"])
        self.assertEqual("north", canonical["site"]["road"]["side"])
        self.assertEqual(11, len(canonical["floors"][0]["rooms"]))
        self.assertEqual(13, len(canonical["floors"][1]["rooms"]))
        self.assertEqual(
            3,
            sum(room["type"] == "bedroom" for room in canonical["floors"][1]["rooms"]),
        )
        self.assertEqual(
            4,
            sum(
                room.get("access") == "ensuite_only"
                for floor in canonical["floors"]
                for room in floor["rooms"]
            ),
        )

    def test_legacy_crowded_dining_chairs_and_island_are_non_blocking(self):
        dining = {
            "id": "dining_room_01",
            "position": {"x": 0, "y": 0, "z": 0},
            "dimensions": {"width": 2.7, "depth": 3.0, "height": 3.0},
        }
        kitchen = {
            "id": "kitchen_01",
            "position": {"x": 3.0, "y": 0, "z": 0},
            "dimensions": {"width": 2.4, "depth": 2.7, "height": 3.0},
        }
        furniture = [{
            "id": "table_dining_room_01", "asset": "dining_table", "category": "dining_table",
            "room_id": dining["id"], "position": {"x": 1.35, "y": 1.5, "z": 0},
            "dimensions": {"width": 1.6, "depth": 0.85, "height": 0.76}, "rotation": 0,
        }]
        for index in range(1, 5):
            furniture.append({
                "id": f"chair_dining_room_01_{index}", "asset": "dining_chair",
                "category": "chair", "room_id": dining["id"],
                "position": {"x": 1.35, "y": 1.5, "z": 0},
                "dimensions": {"width": 0.45, "depth": 0.45, "height": 0.85}, "rotation": 0,
            })
        furniture.extend([
            {
                "id": "fridge_kitchen_01", "asset": "refrigerator", "category": "refrigerator",
                "room_id": kitchen["id"], "position": {"x": 3.55, "y": 0.55, "z": 0},
                "dimensions": {"width": 0.9, "depth": 0.8, "height": 1.82}, "rotation": 180,
            },
            {
                "id": "sink_kitchen_01", "asset": "kitchen_sink", "category": "sink",
                "room_id": kitchen["id"], "position": {"x": 4.85, "y": 0.55, "z": 0},
                "dimensions": {"width": 0.8, "depth": 0.55, "height": 0.88}, "rotation": 180,
            },
            {
                "id": "island_kitchen_01", "asset": "kitchen_island", "category": "kitchen_counter",
                "room_id": kitchen["id"], "position": {"x": 4.2, "y": 1.35, "z": 0},
                "dimensions": {"width": 1.8, "depth": 0.9, "height": 0.92}, "rotation": 0,
            },
        ])
        floor = {"id": "ground_floor", "doors": [], "furniture": furniture}
        report = {"critical_errors": [], "warnings": [], "repairs": []}

        _repair_furniture(floor, {dining["id"]: dining, kitchen["id"]: kitchen}, report)

        self.assertEqual([], report["critical_errors"], report)
        self.assertTrue(any(item["id"] == "table_dining_room_01" for item in floor["furniture"]))
        self.assertTrue(any(item["id"] == "fridge_kitchen_01" for item in floor["furniture"]))
        self.assertTrue(any(item["id"] == "sink_kitchen_01" for item in floor["furniture"]))

    def test_explicit_floor_prompt_is_authoritative(self):
        constraints = infer_layout_constraints("Make this a 3-floor family house")
        self.assertTrue(constraints["floors_explicit"])
        self.assertEqual(3, constraints["floors_count"])

        wizard_wording = infer_layout_constraints("2 floors total (Ground + 1 Floor).")
        self.assertTrue(wizard_wording["floors_explicit"])
        self.assertEqual(2, wizard_wording["floors_count"])

        inferred = infer_layout_constraints("A spacious family house with many rooms")
        self.assertFalse(inferred["floors_explicit"])

        with self.assertRaisesRegex(ValueError, "supports 1 to 4 floors"):
            ArchitecturalLayoutEngine(unit="meters").generate_layout({
                "plot": {"width": 20, "depth": 25},
                "floors": 5,
                "rooms": [{"type": "bedroom"}] * 5,
            })

    def test_narrow_bedroom_is_repaired_before_schema_validation(self):
        engine = ArchitecturalLayoutEngine(unit="meters")
        rooms = [
            engine._create_room_dict(
                "bedroom_01", "Bedroom", "bedroom",
                0.0, 0.0, 0.0, 0.54, 4.0,
                engine._default_materials("bedroom"), 0,
            ),
            engine._create_room_dict(
                "living_01", "Living Room", "living_room",
                0.54, 0.0, 0.0, 4.46, 4.0,
                engine._default_materials("living_room"), 0,
            ),
        ]

        engine._repair_schema_minimum_room_spans(rooms)

        bedroom, living = rooms
        self.assertEqual(1.5, bedroom["dimensions"]["width"])
        self.assertEqual(1.5, bedroom["width"])
        self.assertEqual(1.5, living["position"]["x"])
        self.assertEqual(3.5, living["dimensions"]["width"])

        design = {"rooms": rooms, "doors": [], "windows": [], "furniture": []}
        valid, errors = _validate_home_design_schema(design)
        self.assertTrue(valid, errors)

    def test_unrepairable_narrow_bedroom_reports_actionable_error(self):
        engine = ArchitecturalLayoutEngine(unit="meters")
        rooms = [
            engine._create_room_dict(
                "bedroom_01", "Bedroom", "bedroom",
                0.0, 0.0, 0.0, 0.54, 4.0,
                engine._default_materials("bedroom"), 0,
            ),
        ]

        with self.assertRaisesRegex(ValueError, "Bedroom is only 0.54 m"):
            engine._repair_schema_minimum_room_spans(rooms)

    def test_wall_backed_fixture_orientation_reaches_blender(self):
        design = self.make_design(["kitchen", "bedroom", "bathroom"], (15, 18), 1)
        floor = design["floors"][0]
        furniture = {item["id"]: item for item in floor["furniture"]}

        bed = next(item for item in furniture.values() if item["id"].startswith("bed_"))
        toilet = next(item for item in furniture.values() if item["id"].startswith("toilet_"))
        vanity = next(item for item in furniture.values() if item["id"].startswith("vanity_"))
        kitchen_sink = next(item for item in furniture.values() if item["id"].startswith("sink_"))

        for item in (bed, toilet, vanity):
            self.assertEqual("north", item["anchor_wall"])
            self.assertEqual(0.0, item["rotation"])
        self.assertEqual("south", kitchen_sink["anchor_wall"])
        self.assertEqual(180.0, kitchen_sink["rotation"])

        adapted = adapt_gemini_to_blender_layout(design, project_id="orientation", version_num=1)
        requirements = {
            item["instance_id"]: item
            for room in adapted["rooms"]
            for item in room["furniture_requirements"]
        }
        for source in (bed, toilet, vanity, kitchen_sink):
            self.assertEqual(source["anchor_wall"], requirements[source["id"]]["anchor_wall"])
            self.assertEqual(source["rotation"], requirements[source["id"]]["rotation_deg"])

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

    def test_shared_door_clearance_moves_furniture_in_secondary_room(self):
        room_a = {
            "id": "room_a",
            "position": {"x": 0, "y": 0, "z": 0},
            "dimensions": {"width": 4, "depth": 4, "height": 3},
        }
        room_b = {
            "id": "room_b",
            "position": {"x": 4, "y": 0, "z": 0},
            "dimensions": {"width": 4, "depth": 4, "height": 3},
        }
        floor = {
            "id": "ground_floor",
            "doors": [{
                "id": "door_shared",
                "type": "interior_door",
                "room_id": "room_a",
                "connected_room_ids": ["room_a", "room_b"],
                "wall_side": "east",
                "position": {"x": 4, "y": 2, "z": 0},
                "width": 0.9,
                "swing": "inward_right",
            }],
            "furniture": [{
                "id": "chair_room_b",
                "category": "chair",
                "room_id": "room_b",
                "position": {"x": 4.5, "y": 2, "z": 0},
                "dimensions": {"width": 0.8, "depth": 0.8, "height": 0.9},
                "rotation": 0,
            }],
        }
        report = {"critical_errors": [], "warnings": [], "repairs": []}

        _repair_furniture(floor, {"room_a": room_a, "room_b": room_b}, report)

        self.assertEqual([], report["critical_errors"], report)
        moved = floor["furniture"][0]["position"]
        self.assertFalse(4.0 <= moved["x"] <= 5.15 and 1.1 <= moved["y"] <= 2.9)
        self.assertIn("Moved furniture 'chair_room_b' inside room 'room_b'.", report["repairs"])

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

        main_door = next(door for door in design["doors"] if door["type"] == "main_entrance")
        self.assertEqual(main_door["id"], design["exterior"]["main_entrance"]["door_id"])
        self.assertEqual(main_door["position"], design["exterior"]["main_entrance"]["position"])
        self.assertEqual(
            main_door["position"]["x"],
            design["exterior"]["entrance_path"]["end"]["x"],
        )
        self.assertEqual(
            main_door["position"]["y"],
            design["exterior"]["entrance_path"]["end"]["y"],
        )

        legacy_design = copy.deepcopy(design)
        legacy_design["exterior"].pop("entrance_path")
        legacy_design["exterior"]["main_entrance"]["position"] = {"x": 0, "y": 0, "z": 0}
        repaired, report = validate_and_repair_design(legacy_design, repair=True)
        self.assertEqual([], report["critical_errors"], report)
        self.assertEqual(main_door["position"], repaired["exterior"]["main_entrance"]["position"])
        self.assertEqual(main_door["position"]["x"], repaired["exterior"]["entrance_path"]["end"]["x"])
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
            "remove the north window from the bedroom",
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

    def test_wardrobe_direction_refinement_keeps_house_and_snaps_to_wall(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        base, report = validate_and_repair_design(base, repair=True)
        self.assertEqual([], report["critical_errors"], report)
        floor = base["floors"][0]
        bedroom = next(room for room in floor["rooms"] if room["type"] == "bedroom")
        wardrobe = next(item for item in floor["furniture"] if item["category"] == "wardrobe")

        # Simulate the bad saved placement shown by the user: the correct asset
        # exists, but its transform points the wrong way and floats in the room.
        wardrobe["rotation"] = 0.0
        wardrobe["anchor_wall"] = "west"
        wardrobe["position"] = {
            "x": bedroom["position"]["x"] + bedroom["dimensions"]["width"] / 2,
            "y": bedroom["position"]["y"] + bedroom["dimensions"]["depth"] / 2,
            "z": bedroom["position"]["z"],
        }
        base["layout_approved"] = True
        base["approved_at"] = "2026-10-16T00:00:00Z"
        base["glb_url"] = "s3://old-version/house.glb"
        original = copy.deepcopy(base)

        refined, refinement = apply_targeted_refinement(
            base,
            "fix the direction of wardrobe in bedroom",
        )

        self.assertTrue(refinement["handled"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertEqual(original, base, "refinement mutated the stored base version")
        self.assertFalse(refined["layout_approved"])
        self.assertNotIn("approved_at", refined)
        self.assertNotIn("glb_url", refined)

        refined_floor = refined["floors"][0]
        corrected = next(item for item in refined_floor["furniture"] if item["id"] == wardrobe["id"])
        self.assertEqual("west", corrected["anchor_wall"])
        self.assertEqual(90.0, corrected["rotation"])
        expected_x = (
            bedroom["position"]["x"]
            + WALL_MARGIN
            + corrected["dimensions"]["depth"] / 2
        )
        self.assertAlmostEqual(expected_x, corrected["position"]["x"], places=4)

        for key in ("site", "building", "roof"):
            self.assertEqual(base[key], refined[key], f"unrelated {key} data changed")
        base_rooms = [{key: value for key, value in room.items() if key != "furniture"} for room in floor["rooms"]]
        refined_rooms = [
            {key: value for key, value in room.items() if key != "furniture"}
            for room in refined_floor["rooms"]
        ]
        self.assertEqual(base_rooms, refined_rooms, "unrelated room geometry changed")
        for key in ("walls", "doors", "windows", "stairs"):
            self.assertEqual(floor.get(key), refined_floor.get(key), f"unrelated {key} changed")
        base_other = [item for item in floor["furniture"] if item["id"] != wardrobe["id"]]
        refined_other = [item for item in refined_floor["furniture"] if item["id"] != wardrobe["id"]]
        self.assertEqual(base_other, refined_other, "unrelated furniture changed")

        adapted = adapt_gemini_to_blender_layout(refined, project_id="refinement-test", version_num=2)
        requirement = next(
            item
            for room in adapted["rooms"]
            for item in room["furniture_requirements"]
            if item["instance_id"] == wardrobe["id"]
        )
        self.assertEqual("west", requirement["anchor_wall"])
        self.assertEqual(90.0, requirement["rotation_deg"])

    def test_generic_asset_refinement_is_not_wardrobe_specific(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom"],
            (18, 20),
            1,
        )
        base, report = validate_and_repair_design(base, repair=True)
        self.assertEqual([], report["critical_errors"], report)
        original = copy.deepcopy(base)
        sofa = next(item for item in base["floors"][0]["furniture"] if item["category"] == "sofa")

        refined, refinement = apply_targeted_refinement(
            base,
            "rotate the sofa in the living room by 90 degrees",
        )

        self.assertTrue(refinement["handled"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertEqual(original, base, "generic asset refinement mutated its base version")
        corrected = next(
            item for item in refined["floors"][0]["furniture"] if item["id"] == sofa["id"]
        )
        self.assertEqual((sofa["rotation"] + 90.0) % 360.0, corrected["rotation"])
        untouched_before = [
            item for item in base["floors"][0]["furniture"] if item["id"] != sofa["id"]
        ]
        untouched_after = [
            item for item in refined["floors"][0]["furniture"] if item["id"] != sofa["id"]
        ]
        self.assertEqual(untouched_before, untouched_after)

    def test_multiple_asset_refinements_apply_atomically(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        base, validation = validate_and_repair_design(base, repair=True)
        self.assertEqual([], validation["critical_errors"], validation)
        original = copy.deepcopy(base)
        furniture = base["floors"][0]["furniture"]
        sofa = next(item for item in furniture if item["category"] == "sofa")
        refrigerator = next(item for item in furniture if item["category"] == "refrigerator")

        refined, refinement = apply_targeted_refinement(
            base,
            "Rotate the sofa in the living room by 90 degrees\n\n"
            "Move the refrigerator to the north wall",
        )

        self.assertTrue(refinement["handled"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertEqual(2, len(refinement["changes"]))
        self.assertEqual(original, base, "multi-asset refinement mutated its base version")
        updated = {item["id"]: item for item in refined["floors"][0]["furniture"]}
        self.assertEqual((sofa["rotation"] + 90.0) % 360.0, updated[sofa["id"]]["rotation"])
        self.assertEqual("north", updated[refrigerator["id"]]["anchor_wall"])
        self.assertEqual(0.0, updated[refrigerator["id"]]["rotation"])

        untouched_ids = {
            item["id"] for item in furniture
            if item["id"] not in {sofa["id"], refrigerator["id"]}
        }
        before = {item["id"]: item for item in furniture if item["id"] in untouched_ids}
        after = {
            item["id"]: item for item in refined["floors"][0]["furniture"]
            if item["id"] in untouched_ids
        }
        self.assertEqual(before, after)

    def test_set_sofa_in_center_is_targeted_and_does_not_regenerate_layout(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        base, validation = validate_and_repair_design(base, repair=True)
        self.assertEqual([], validation["critical_errors"], validation)
        original = copy.deepcopy(base)

        refined, refinement = apply_targeted_refinement(
            base,
            "set sofa in center in living room",
        )

        self.assertTrue(refinement["handled"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertEqual(1, len(refinement["changes"]))
        self.assertEqual(original, base, "center refinement mutated its base version")

        old_floor, new_floor = base["floors"][0], refined["floors"][0]
        old_room_geometry = [
            {key: value for key, value in room.items() if key != "furniture"}
            for room in old_floor["rooms"]
        ]
        new_room_geometry = [
            {key: value for key, value in room.items() if key != "furniture"}
            for room in new_floor["rooms"]
        ]
        self.assertEqual(old_room_geometry, new_room_geometry)
        for key in ("site", "building", "roof"):
            self.assertEqual(base[key], refined[key])

        living = next(room for room in new_floor["rooms"] if room["type"] == "living_room")
        sofa = next(item for item in new_floor["furniture"] if item["category"] == "sofa")
        self.assertAlmostEqual(
            living["position"]["x"] + living["dimensions"]["width"] / 2.0,
            sofa["position"]["x"],
        )
        self.assertAlmostEqual(
            living["position"]["y"] + living["dimensions"]["depth"] / 2.0,
            sofa["position"]["y"],
        )

    def test_vague_unique_style_feedback_preserves_complete_layout(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        base, validation = validate_and_repair_design(base, repair=True)
        self.assertEqual([], validation["critical_errors"], validation)
        base["layout_approved"] = True
        base["approved_at"] = "2026-10-18T00:00:00Z"
        base["glb_url"] = "s3://old-version/house.glb"
        original = copy.deepcopy(base)

        refined, refinement = apply_targeted_refinement(
            base,
            "that is not unique style",
            requested_style="modern",
        )

        self.assertTrue(refinement["handled"])
        self.assertEqual("style_only", refinement["kind"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertEqual(original, base, "style refinement mutated the stored base version")
        self.assertFalse(refined["layout_approved"])
        self.assertNotIn("approved_at", refined)
        self.assertNotIn("glb_url", refined)
        self.assertEqual("modern", refined["style"])
        self.assertEqual("modern", refined["project"]["style"])
        self.assertEqual("signature_modern", refined["exterior"]["design_concept"])

        # Every architectural/spatial collection must remain exactly stable.
        self.assertEqual(base["site"], refined["site"])
        self.assertEqual(base["roof"], refined["roof"])
        for key in ("width", "depth", "wall_thickness", "slab_thickness", "floors"):
            self.assertEqual(base["building"][key], refined["building"][key])
        for key in ("main_entrance", "gate", "entrance_path", "boundary_wall", "driveway", "landscape"):
            self.assertEqual(base["exterior"][key], refined["exterior"][key])

        for old_floor, new_floor in zip(base["floors"], refined["floors"]):
            for key in ("id", "level", "elevation", "floor_height", "walls", "doors", "windows", "stairs", "furniture", "ceiling"):
                self.assertEqual(old_floor.get(key), new_floor.get(key), f"style edit changed floor field {key}")
            self.assertEqual(len(old_floor["rooms"]), len(new_floor["rooms"]))
            for old_room, new_room in zip(old_floor["rooms"], new_floor["rooms"]):
                for key in ("id", "name", "type", "position", "dimensions", "width", "length", "height", "floor"):
                    self.assertEqual(old_room.get(key), new_room.get(key), f"style edit changed room field {key}")

        for key in ("doors", "windows", "furniture"):
            self.assertEqual(base[key], refined[key], f"style edit changed top-level {key}")
        self.assertNotEqual(
            base["floors"][0]["rooms"][0]["materials"],
            refined["floors"][0]["rooms"][0]["materials"],
        )

    def test_explicit_style_refinement_uses_prompt_and_reaches_blender(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom"],
            (12, 18),
            1,
        )
        refined, refinement = apply_targeted_refinement(
            base,
            "make the visual style industrial",
            requested_style="modern",
        )

        self.assertTrue(refinement["handled"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertEqual("industrial", refined["style"])
        self.assertEqual("industrial", refined["project"]["style"])
        self.assertEqual("brick", refined["building"]["wall_style"]["pattern"])
        self.assertEqual(base["floors"][0]["walls"], refined["floors"][0]["walls"])
        self.assertEqual(base["floors"][0]["doors"], refined["floors"][0]["doors"])

        adapted = adapt_gemini_to_blender_layout(
            refined, project_id="style-refinement", version_num=2
        )
        self.assertTrue(all(room["style"] == "industrial" for room in adapted["rooms"]))
        self.assertTrue(all(room["walls"]["pattern"] == "brick" for room in adapted["rooms"]))

    def test_varied_appearance_prompts_are_all_safe_in_place_edits(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        geometry = {
            "site": copy.deepcopy(base["site"]),
            "roof": copy.deepcopy(base["roof"]),
            "rooms": [
                (room["id"], copy.deepcopy(room["position"]), copy.deepcopy(room["dimensions"]))
                for floor in base["floors"] for room in floor["rooms"]
            ],
            "walls": copy.deepcopy(base["floors"][0]["walls"]),
            "doors": copy.deepcopy(base["floors"][0]["doors"]),
            "windows": copy.deepcopy(base["floors"][0]["windows"]),
        }

        prompts = [
            "make the facade more distinctive",
            "use a coastal aesthetic",
            "make the materials warmer and more luxurious",
            "change the bathroom tiles to grey",
            "use black aluminium frames",
            "the colors look too generic",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                refined, report = apply_targeted_refinement(
                    base, prompt, requested_style="modern"
                )
                self.assertTrue(report["handled"], report)
                self.assertEqual("style_only", report["kind"])
                self.assertEqual(geometry["site"], refined["site"])
                self.assertEqual(geometry["roof"], refined["roof"])
                self.assertEqual(geometry["walls"], refined["floors"][0]["walls"])
                self.assertEqual(geometry["doors"], refined["floors"][0]["doors"])
                self.assertEqual(geometry["windows"], refined["floors"][0]["windows"])
                self.assertEqual(
                    geometry["rooms"],
                    [
                        (room["id"], room["position"], room["dimensions"])
                        for floor in refined["floors"] for room in floor["rooms"]
                    ],
                )

    def test_mixed_style_and_geometry_request_is_not_swallowed(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        refined, refinement = apply_targeted_refinement(
            base,
            "make the style industrial and move the garage to the right",
            requested_style="industrial",
        )

        self.assertIsNone(refined)
        self.assertFalse(refinement["handled"])

    def test_minimal_style_alias_is_canonical(self):
        constraints = infer_layout_constraints("use a minimal style")
        self.assertEqual("minimalist", constraints["preferred_style"])

        design = ArchitecturalLayoutEngine(unit="meters").generate_layout({
            "style": "minimal",
            "plot": {"width": 12, "depth": 18},
            "rooms": [{"type": "living_room"}, {"type": "bedroom"}],
        })
        self.assertEqual("minimalist", design["project"]["style"])

    def test_only_explicit_full_redesign_language_authorizes_layout_rebuild(self):
        edit_prompts = [
            "that is not unique style",
            "make it warmer and more luxurious",
            "change the bathroom tiles to grey",
            "fix the entrance",
            "make the bedroom larger",
            "move the kitchen behind the living room",
            "add a bedroom",
        ]
        for prompt in edit_prompts:
            with self.subTest(prompt=prompt):
                self.assertFalse(is_explicit_full_redesign(prompt))

        redesign_prompts = [
            "redesign the entire layout",
            "regenerate the whole house",
            "start over from scratch",
            "create a brand-new floor plan",
            "rearrange all rooms",
        ]
        for prompt in redesign_prompts:
            with self.subTest(prompt=prompt):
                self.assertTrue(is_explicit_full_redesign(prompt))

    def test_fix_bedroom_repairs_active_bed_conflict_without_regeneration(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        base, clean_validation = validate_and_repair_design(base, repair=True)
        self.assertEqual([], clean_validation["critical_errors"], clean_validation)
        floor = base["floors"][0]
        bed = next(item for item in floor["furniture"] if item["category"] == "bed")
        # Simulate a generated/catalog footprint that cannot fit in the room.
        bed["dimensions"]["width"] = 5.0
        bed["dimensions"]["depth"] = 5.0
        invalid, validation = validate_and_repair_design(base, repair=True)
        self.assertTrue(any(bed["id"] in error for error in validation["critical_errors"]))
        base["generation_validation"] = validation
        original = copy.deepcopy(base)

        for prompt in ("fix the bedroom", "just fix the bedroom dont regenerate it"):
            with self.subTest(prompt=prompt):
                refined, refinement = apply_targeted_refinement(base, prompt)

                self.assertTrue(refinement["handled"], refinement)
                self.assertEqual("validation_repair", refinement["kind"])
                self.assertEqual([], refinement["errors"], refinement)
                self.assertEqual(original, base, "repair mutated its stored base version")
                self.assertEqual([], refined["generation_validation"]["critical_errors"])
                repaired_bed = next(
                    item for item in refined["floors"][0]["furniture"]
                    if item["id"] == bed["id"]
                )
                self.assertLessEqual(repaired_bed["dimensions"]["width"], 1.60)
                self.assertLessEqual(repaired_bed["dimensions"]["depth"], 2.00)

                # Site and every architectural object stay locked; only furniture
                # transforms/dimensions may change.
                self.assertEqual(base["site"], refined["site"])
                self.assertEqual(base["building"], refined["building"])
                self.assertEqual(base["roof"], refined["roof"])
                self.assertEqual(base["exterior"], refined["exterior"])
                for key in ("rooms", "walls", "doors", "windows", "stairs"):
                    if key == "rooms":
                        old = [
                            {k: v for k, v in room.items() if k not in ("furniture",)}
                            for room in base["floors"][0][key]
                        ]
                        new = [
                            {k: v for k, v in room.items() if k not in ("furniture",)}
                            for room in refined["floors"][0][key]
                        ]
                        self.assertEqual(old, new)
                    else:
                        self.assertEqual(
                            base["floors"][0][key], refined["floors"][0][key],
                            f"repair changed locked field {key}",
                        )

    def test_fix_room_without_matching_conflict_returns_actionable_error(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom"],
            (12, 18),
            1,
        )
        original = copy.deepcopy(base)

        refined, refinement = apply_targeted_refinement(base, "fix the bedroom")

        self.assertIsNone(refined)
        self.assertTrue(refinement["handled"])
        self.assertEqual("validation_repair", refinement["kind"])
        self.assertIn("No active furniture-fit conflict", refinement["errors"][0])
        self.assertEqual(original, base)

    def test_room_width_growth_is_a_local_validated_edit(self):
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        base, validation = validate_and_repair_design(base, repair=True)
        self.assertEqual([], validation["critical_errors"], validation)
        original = copy.deepcopy(base)
        old_bedroom = next(room for room in base["floors"][0]["rooms"] if room["type"] == "bedroom")

        refined, refinement = apply_targeted_refinement(base, "increase the width of bedroom")

        self.assertTrue(refinement["handled"], refinement)
        self.assertEqual("room_resize", refinement["kind"])
        self.assertEqual([], refinement["errors"], refinement)
        self.assertEqual(original, base, "room resizing mutated its stored base version")
        new_bedroom = next(room for room in refined["floors"][0]["rooms"] if room["type"] == "bedroom")
        self.assertGreater(new_bedroom["dimensions"]["width"], old_bedroom["dimensions"]["width"])
        self.assertEqual(len(base["floors"][0]["rooms"]), len(refined["floors"][0]["rooms"]))
        self.assertEqual(base["site"], refined["site"])
        self.assertEqual(base["building"], refined["building"])
        self.assertEqual([], refined["generation_validation"]["critical_errors"])

    def test_room_width_intent_accepts_varied_natural_wording(self):
        prompts = (
            "make the bedroom wider",
            "the sleeping room needs more width",
            "give the bedroom more horizontal space",
            "enlarge the bedroom by 0.3 m",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                base = self.make_design(
                    ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
                    (12, 18),
                    1,
                )
                base, validation = validate_and_repair_design(base, repair=True)
                self.assertEqual([], validation["critical_errors"], validation)
                old_width = next(
                    room for room in base["floors"][0]["rooms"] if room["type"] == "bedroom"
                )["dimensions"]["width"]
                refined, refinement = apply_targeted_refinement(base, prompt)
                self.assertIsNotNone(refined, refinement)
                self.assertEqual("room_resize", refinement["kind"])
                new_width = next(
                    room for room in refined["floors"][0]["rooms"] if room["type"] == "bedroom"
                )["dimensions"]["width"]
                self.assertGreater(new_width, old_width)

    def test_narrow_saved_bedroom_expands_into_available_side_space(self):
        """Regression for the user's 2.08 m bedroom beside a shorter bathroom."""
        engine = ArchitecturalLayoutEngine(unit="meters")
        base = self.make_design(
            ["living_room", "kitchen", "bedroom", "bathroom", "garage"],
            (12, 18),
            1,
        )
        floor = base["floors"][0]
        rooms = {room["type"]: room for room in floor["rooms"]}
        geometry = {
            "garage": (0.96, 2.27, 3.40, 5.00),
            "kitchen": (0.96, 7.27, 3.40, 3.82),
            "living_room": (4.36, 2.27, 4.28, 4.06),
            "bedroom": (4.36, 6.33, 2.08, 4.76),
            "bathroom": (6.44, 6.33, 1.79, 3.87),
        }
        for room_type, (x, y, width, depth) in geometry.items():
            room = rooms[room_type]
            room["position"].update({"x": x, "y": y})
            room["dimensions"].update({"width": width, "depth": depth})
            room["width"], room["length"] = width, depth
        base["site"]["setbacks"].update({"left": 0.96, "front": 2.27})
        base["building"].update({"width": 7.68, "depth": 8.82})
        floor["walls"] = engine._compute_floor_walls(
            floor["rooms"], 0.2, 0.96, 2.27, 7.68, 8.82,
        )
        floor["doors"] = engine._generate_doors(floor["rooms"], floor["walls"], True)
        floor["windows"] = engine._generate_windows(
            floor["rooms"], floor["walls"], 7.68, 8.82, 0.96, 2.27,
        )
        bedroom_id = rooms["bedroom"]["id"]
        floor["furniture"] = [
            item for item in floor["furniture"]
            if str(item.get("room_id")) == bedroom_id and item.get("category") in {"bed", "nightstand"}
        ]
        original_bath_width = rooms["bathroom"]["dimensions"]["width"]
        original_bath_x = rooms["bathroom"]["position"]["x"]

        refined, refinement = apply_targeted_refinement(base, "increase the width of bedroom")

        self.assertIsNotNone(refined, refinement)
        self.assertEqual([], refinement["errors"], refinement)
        updated = {room["type"]: room for room in refined["floors"][0]["rooms"]}
        self.assertGreater(updated["bedroom"]["dimensions"]["width"], 2.08)
        self.assertEqual(original_bath_width, updated["bathroom"]["dimensions"]["width"])
        self.assertGreater(updated["bathroom"]["position"]["x"], original_bath_x)
        self.assertEqual([], refined["generation_validation"]["critical_errors"])
        self.assertEqual(3, len(refined["floors"][0]["furniture"]))


if __name__ == "__main__":
    unittest.main()
