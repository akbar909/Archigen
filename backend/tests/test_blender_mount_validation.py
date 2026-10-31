import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'blender', 'scripts'))
from generate_house_validation import furniture_mount_error, doorways_overlapping_height


class MountValidationTests(unittest.TestCase):
    def test_ceiling_lamp_is_checked_at_top_not_floor(self):
        room = {'id': 'bed', 'height': 3, 'bounds': {'z': 0}}
        root = {'archgen_ceiling_mounted': True, 'archgen_floor_clearance': 0.008}
        self.assertIsNone(furniture_mount_error(root, room, 2.624, 2.94))
        self.assertIn('ceiling', furniture_mount_error(root, room, 2.624, 3.1))
        self.assertIn('ceiling', furniture_mount_error(root, room, 0.008, 0.324))
        doors = [{'position': [1, 0, 0], 'height': 2.1}]
        self.assertEqual([], doorways_overlapping_height(doors, 2.624, 2.94))
        self.assertEqual(doors, doorways_overlapping_height(doors, 1.9, 2.94))

    def test_upper_floor_and_custom_ceiling_clearance(self):
        room = {'height': 3.4, 'bounds': {'z': 3.4}}
        root = {'archgen_ceiling_mounted': True, 'archgen_ceiling_clearance': 0.12}
        self.assertIsNone(furniture_mount_error(root, room, 6.1, 6.68))
        self.assertIsNotNone(furniture_mount_error(root, room, 6.1, 6.74))

    def test_wall_mount_preserves_height_and_room_containment(self):
        room = {'height': 3, 'bounds': {'z': 3.4}}
        root = {'archgen_wall_mounted': True, 'archgen_mount_height': 1.2, 'archgen_floor_clearance': 0.008}
        self.assertIsNone(furniture_mount_error(root, room, 4.608, 5.3))
        self.assertIsNotNone(furniture_mount_error(root, room, 3.408, 4.1))
        self.assertIsNotNone(furniture_mount_error(root, room, 4.608, 7))

    def test_floor_rule_still_rejects_floating_and_sunken_furniture(self):
        room = {'height': 3, 'bounds': {'z': 0}}
        root = {'archgen_floor_clearance': 0.008}
        self.assertIsNone(furniture_mount_error(root, room, 0.008, 1))
        self.assertIn('finished floor', furniture_mount_error(root, room, 0.2, 1.2))
        self.assertIsNotNone(furniture_mount_error(root, room, -0.2, 1.2))
        self.assertIsNotNone(furniture_mount_error(root, room, float('nan'), 1.2))

    def test_tall_door_is_not_exempted_by_standard_door_height(self):
        short = {'position': [0, 0, 0], 'height': 2.1}
        tall = {'position': [4, 0, 0], 'height': 2.8}
        upper = {'position': [0, 0, 3.4], 'height': 2.8}
        self.assertEqual([tall], doorways_overlapping_height([short, tall, upper], 2.624, 2.94))
