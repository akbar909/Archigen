"""Regressions for saved ceiling layers and deletions over a reused house GLB."""
import copy
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

from bson import ObjectId
from flask import Flask, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routes.chat import update_layout_for_version
from utils.architectural_preflight import _repair_furniture, validate_and_repair_design
from utils.blender_service import adapt_gemini_to_blender_layout
from utils.versioning import prepare_design_snapshot


def editor_design():
    room = {'id': 'bedroom', 'type': 'bedroom', 'position': {'x': 0, 'y': 0, 'z': 0},
            'dimensions': {'width': 6, 'depth': 6, 'height': 3.4}}
    furniture = [
        {'id': 'wardrobe', 'category': 'wardrobe', 'room_id': 'bedroom',
         'position': {'x': 4, 'y': 4, 'z': 0}, 'dimensions': {'width': 1, 'depth': 0.6, 'height': 2}},
        {'id': 'bed', 'category': 'bed', 'room_id': 'bedroom', 'client_edited_3d': True,
         'position': {'x': 2, 'y': 2, 'z': 0}, 'dimensions': {'width': 2, 'depth': 2, 'height': 1}},
    ]
    for asset, height in [('ceiling_fan_02', 0.4), ('ceiling_lamp_02', 0.6)]:
        furniture.append({'id': asset, 'asset_id': asset, 'category': 'ceiling_light', 'room_id': 'bedroom',
                          'ceiling_mounted': True, 'client_edited_3d': True, 'placement_hint': 'user_exact',
                          'position': {'x': 2, 'y': 2, 'z': 0},
                          'dimensions': {'width': 1, 'depth': 1, 'height': height}})
    return {'building': {'floor_height': 3.4}, 'site': {'plot': {'width': 6, 'depth': 6}},
            'deleted_furniture_ids': ['wardrobe'],
            'floors': [{'id': 'floor_0', 'level': 0, 'elevation': 0, 'rooms': [room], 'furniture': furniture}]}


class EditorPersistenceTests(unittest.TestCase):
    def test_wall_face_finishes_survive_save_and_blender_adapter(self):
        design = editor_design()
        faces = {
            'pz': {'pattern': 'brick_wall_diff_2k', 'normal': {'x': 0, 'y': 0, 'z': 1}},
            'nz': {'pattern': 'painted_plaster_wall_diff_2k', 'normal': {'x': 0, 'y': 0, 'z': -1}},
        }
        design['floors'][0]['walls'] = [{'id': 'shared', 'start': {'x': 0, 'y': 0}, 'end': {'x': 6, 'y': 0}}]
        design['wall_face_overrides'] = {'shared': faces}
        saved = prepare_design_snapshot(json.loads(json.dumps(design)))
        saved, _ = validate_and_repair_design(saved)
        exported = adapt_gemini_to_blender_layout(saved)
        self.assertEqual(faces, exported['walls'][0]['material_overrides'])
        self.assertNotIn('material_override', exported['walls'][0])

    def assert_saved_layers(self, design):
        self.assertEqual(['wardrobe'], design['deleted_furniture_ids'])
        self.assertNotIn('wardrobe', {item['id'] for item in design['furniture']})
        self.assertNotIn('wardrobe', {item['id'] for item in design['floors'][0]['rooms'][0]['furniture']})
        for item in design['furniture']:
            if item.get('ceiling_mounted'):
                self.assertAlmostEqual(3.4 - item['dimensions']['height'] - 0.06, item['position']['z'])

    def test_snapshot_and_repeated_save_preserve_ceiling_attachment_and_deletion(self):
        source = editor_design()
        design = source
        for _ in range(3):
            design = prepare_design_snapshot(json.loads(json.dumps(design)))
            design, report = validate_and_repair_design(design)
            self.assertEqual([], report['critical_errors'])
            self.assert_saved_layers(design)
        self.assertEqual(4, len(source['floors'][0]['furniture']))
        exported = adapt_gemini_to_blender_layout(design)
        self.assertNotIn('wardrobe', exported['expected_inventory']['furniture_ids'])
        for item in exported['rooms'][0]['furniture_requirements']:
            if item['ceiling_mounted']:
                self.assertGreater(item['position'][2], 2.7)
                self.assertEqual(0.06, item['ceiling_clearance'])

    def test_saved_upper_floor_fixture_stays_at_that_floor_ceiling(self):
        design = editor_design()
        floor = design['floors'][0]
        room = floor['rooms'][0]
        room['position']['z'] = 3.4
        report = {'critical_errors': [], 'warnings': [], 'repairs': []}
        _repair_furniture(floor, {'bedroom': room}, report)
        for item in floor['furniture']:
            if item.get('ceiling_mounted'):
                self.assertAlmostEqual(6.8 - item['dimensions']['height'] - 0.06, item['position']['z'])

    @patch('routes.chat.projects_collection')
    @patch('routes.chat.versions_collection')
    def test_save_api_returns_and_persists_layers_while_reusing_glb(self, versions, projects):
        user_id, project_id, version_id = ObjectId(), ObjectId(), ObjectId()
        base = {'_id': version_id, 'project_id': project_id, 'user_id': user_id,
                'glb_url': 'https://models.example/house.glb', 'design': editor_design()}
        collection = Mock()
        collection.find_one.return_value = copy.deepcopy(base)
        versions.return_value = collection
        app = Flask(__name__)
        with app.test_request_context('/layout', method='PATCH', json={'design': editor_design()}):
            request.user = {'_id': user_id}
            response = update_layout_for_version.__wrapped__(str(project_id), str(version_id))
            payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assert_saved_layers(payload['design'])
        persisted = collection.update_one.call_args.args[1]['$set']
        self.assert_saved_layers(persisted['design'])
        self.assertEqual(base['glb_url'], persisted['glb_url'])


if __name__ == '__main__':
    unittest.main()
