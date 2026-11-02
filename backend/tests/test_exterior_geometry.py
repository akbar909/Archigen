import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[2] / 'blender' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('generate_house_vertical', SCRIPTS / 'generate_house_vertical.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExteriorGeometryTests(unittest.TestCase):
    def test_entrance_path_begins_at_driveway_edge_without_large_overlap(self):
        start = module.clip_path_start_after_driveway(3, 0, 6, 6, 1, 0, 4, 3)
        self.assertIsNotNone(start)
        self.assertAlmostEqual(4.49, start[0], places=2)
        self.assertAlmostEqual(2.98, start[1], places=2)

    def test_path_inside_driveway_needs_no_second_surface(self):
        self.assertIsNone(module.clip_path_start_after_driveway(3, 0, 4, 2, 1, 0, 4, 3))

    def test_path_outside_driveway_is_unchanged(self):
        self.assertEqual((6, 3), module.clip_path_start_after_driveway(6, 3, 8, 5, 1, 0, 4, 3))

    def test_gate_gap_and_driveway_follow_north_and_east_frontages(self):
        class FakeObject(dict):
            def __init__(self, location):
                super().__init__()
                self.location = location
                self.rotation_euler = SimpleNamespace(z=0)
                self.data = SimpleNamespace(materials=[])

        for side in ("north", "east"):
            with self.subTest(side=side):
                context = SimpleNamespace(active_object=None)
                def cube_add(*, location, **kwargs):
                    context.active_object = FakeObject(location)
                fake_bpy = SimpleNamespace(context=context, ops=SimpleNamespace(mesh=SimpleNamespace(primitive_cube_add=cube_add)))
                vertical = side == "east"
                site = {"plot": {"width": 12, "depth": 16}, "road": {"side": side}}
                exterior = {
                    "boundary_wall": {"enabled": True, "height": 2, "thickness": .15},
                    "gate": {"position": {"x": 12 if vertical else 3, "y": 3 if vertical else 16},
                             "width": 3, "height": 2, "side": side, "axis": "y" if vertical else "x"},
                    "driveway": {"position": {"x": 10 if vertical else 3, "y": 3 if vertical else 14},
                                 "width": 2 if vertical else 3, "depth": 3 if vertical else 2},
                }
                with patch.object(module, "bpy", fake_bpy), \
                     patch.object(module, "create_pbr_material", return_value=None), \
                     patch.object(module, "apply_box_uv_mapping"), \
                     patch.object(module, "_try_import_gate_model", return_value=None):
                    objects = module.build_exterior_features(site, exterior, 8, 10, 6, 8)
                gate = next(obj for obj in objects if obj.name == "Exterior_Entrance_Gate")
                self.assertEqual((12, 4.5, 1) if vertical else (4.5, 16, 1), gate.location)
                self.assertAlmostEqual(module.math.pi / 2 if vertical else module.math.pi, gate.rotation_euler.z)
                drive = next(obj for obj in objects if obj.name == "Exterior_Driveway_Paving")
                self.assertEqual((11, 4.5, -.01) if vertical else (4.5, 15, -.01), drive.location)
                for wall in (obj for obj in objects if obj.name.startswith("Exterior_Boundary_Wall")):
                    x, y, _ = wall.location
                    if (vertical and x == 12) or (not vertical and y == 16):
                        center = y if vertical else x
                        span = wall.scale[1 if vertical else 0]
                        self.assertTrue(center + span / 2 <= 3 or center - span / 2 >= 6,
                                        "A boundary wall blocks the entrance gate")


if __name__ == '__main__':
    unittest.main()
