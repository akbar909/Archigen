import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'scripts'))
from utils.asset_catalog import _entry, _local_keys
from utils.blender_service import _aligned_wall_item, _canonical_blender_layout
from place_furniture import wall_mount_rotation


class WallMountTests(unittest.TestCase):
    def test_reviewed_front_axes_replace_bounding_box_guesses(self):
        for key, yaw in [('lighting/wall_sconces/wall_lamp_02.glb', 0),
                         ('lighting/wall_sconces/stylized_gothic_wall_torch_01.glb', 0),
                         ('decorations/wall_art/cafe_wall_pictures_03.glb', -90)]:
            entry = _entry('assets/' + key, 'test')
            self.assertEqual(yaw, entry['canonical_yaw_offset_deg'])
            self.assertTrue(entry['mounting']['orientation_verified'])

    def test_every_wall_catalog_entry_has_reviewed_axes(self):
        entries = [_entry(key, 'test') for key in _local_keys()]
        wall = [entry for entry in entries if entry and entry['group'] in ('wall_decor', 'wall_panel', 'curtain')]
        self.assertEqual(19, len(wall))
        self.assertTrue(all(entry['mounting']['orientation_verified'] for entry in wall))

    def test_standing_mirror_and_desk_clock_are_not_wall_options(self):
        for key, category in [('decorations/mirrors/mirror_a_01.glb', 'floor_mirror'),
                              ('decorations/clocks/clock_01.glb', 'table_clock')]:
            entry = _entry('assets/' + key, 'test')
            self.assertEqual(('furniture', category), (entry['group'], entry['category']))

    def test_blender_and_browser_rotations_have_opposite_sign_on_side_walls(self):
        for side, degrees in [('front', 0), ('back', 180), ('left', 90), ('right', -90)]:
            self.assertEqual(degrees, wall_mount_rotation({'wall_side': side}))
        self.assertEqual(-90, wall_mount_rotation({'wall_normal': {'x': -1, 'z': 0}}))

    def test_legacy_dimensions_and_orientation_are_reconciled_without_mutating_snapshot(self):
        item = {'id': 'lamp', 'asset_id': 'wall_lamp_02', 'wall_mounted': True, 'wall_side': 'right',
                'canonical_yaw_offset_deg': 90, 's3_key': 'assets/lighting/wall_sconces/wall_lamp_02.glb',
                'dimensions': {'width': 1, 'depth': 0.3, 'height': 1.2}, 'position': {'x': 4.7, 'y': 2, 'z': 0}, 'room_id': 'room'}
        room = {'id': 'room', 'position': {'x': 0, 'y': 0}, 'dimensions': {'width': 5, 'depth': 4}}
        before = copy.deepcopy(item)
        aligned = _aligned_wall_item(item, room)
        self.assertEqual(0, aligned['canonical_yaw_offset_deg'])
        self.assertAlmostEqual(1.2, aligned['dimensions']['height'])
        self.assertEqual(before, item)
        exported = _canonical_blender_layout({'floors': [{'rooms': [room], 'furniture': [item]}]}, 'test', 'modern')
        requirement = exported['rooms'][0]['furniture_requirements'][0]
        self.assertEqual('right', requirement['wall_side'])
        self.assertEqual(0, requirement['canonical_yaw_offset_deg'])


if __name__ == '__main__':
    unittest.main()
