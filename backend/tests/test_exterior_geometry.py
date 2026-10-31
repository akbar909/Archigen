import importlib.util
import sys
import unittest
from pathlib import Path


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


if __name__ == '__main__':
    unittest.main()
