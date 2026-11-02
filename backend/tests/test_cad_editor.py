"""The 2D editor's schema, draft refinement and persistence contracts."""
import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bson import ObjectId
from flask import Flask, request
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routes.chat import refine_layout_draft, update_layout_for_version
from utils.architectural_schema_v3 import validate_schema_v3
from utils.architectural_refinement import apply_layout_refinement
from utils.architectural_preflight import validate_and_repair_design
from utils.blender_service import adapt_gemini_to_blender_layout


def frontend_fixture():
    root = Path(__file__).resolve().parents[2]
    command = "import {cadFixture} from './frontend/tests/cad-fixture.mjs'; console.log(JSON.stringify(cadFixture()))"
    result = subprocess.run(['node', '--input-type=module', '-e', command], cwd=root, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


class CadEditorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = frontend_fixture()

    def setUp(self):
        self.design = copy.deepcopy(self.fixture)
        self.project_id, self.version_id, self.user_id = ObjectId(), ObjectId(), ObjectId()
        self.version = {'_id': self.version_id, 'project_id': self.project_id, 'user_id': self.user_id, 'design': self.design}
        self.app = Flask(__name__)

    def test_frontend_json_passes_schema_preflight_and_blender_adapter(self):
        valid, errors = validate_schema_v3(self.design)
        self.assertTrue(valid, errors)
        repaired, report = validate_and_repair_design(self.design)
        self.assertEqual([], report['critical_errors'])
        exported = adapt_gemini_to_blender_layout(repaired)
        self.assertEqual(2, len(exported['rooms']))
        self.assertEqual({'sofa', 'bed'}, {item['id'] for room in exported['rooms'] for item in room['furniture_requirements']})

    def test_editor_properties_are_typed_without_requiring_them_on_old_documents(self):
        self.design['floors'][0]['furniture'][0].update(locked=False, group_id=None, flip_x=True)
        self.assertTrue(validate_schema_v3(self.design)[0])
        self.design['floors'][0]['furniture'][0]['locked'] = 'false'
        self.assertFalse(validate_schema_v3(self.design)[0])
        self.design['floors'][0]['windows'][0]['width'] = -1
        self.assertFalse(validate_schema_v3(self.design)[0])

    def test_opening_refinement_moves_on_host_and_updates_offsets(self):
        before = copy.deepcopy(self.design)
        edited, report = apply_layout_refinement(self.design, 'slide living_window 1 ft north')
        self.assertIsNotNone(edited, report)
        window = edited['floors'][0]['windows'][0]
        self.assertAlmostEqual(5.3048, window['position']['y'], places=3)
        self.assertEqual(before['floors'][0]['windows'][0]['wall_id'], window['wall_id'])
        self.assertEqual(before, self.design, 'Draft input must remain immutable')

    def test_compound_opening_edit_is_atomic_and_unsupported_clauses_reject(self):
        edited, report = apply_layout_refinement(self.design, 'slide living_window 1 ft north and flip main_door')
        self.assertIsNotNone(edited, report)
        self.assertEqual('outward', edited['floors'][0]['doors'][0]['swing_direction'])
        edited, report = apply_layout_refinement(self.design, 'slide living_window 100 ft north')
        self.assertIsNone(edited)
        self.assertTrue(report['errors'])

    def test_refinement_endpoint_checks_owner_and_never_writes_a_version(self):
        collection = Mock()
        collection.find_one.return_value = self.version
        with self.app.test_request_context(json={'design': self.design, 'prompt': 'slide living_window 1 ft north'}):
            request.user = {'_id': self.user_id}
            with patch('routes.chat.versions_collection', return_value=collection):
                response = refine_layout_draft.__wrapped__(str(self.project_id), str(self.version_id))
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.get_json()['success'])
        collection.find_one.assert_called_once_with({'_id': self.version_id, 'project_id': self.project_id, 'user_id': self.user_id})
        collection.update_one.assert_not_called()
        collection.insert_one.assert_not_called()

    def test_refinement_endpoint_rejects_missing_version_and_invalid_payload(self):
        collection = Mock()
        collection.find_one.return_value = None
        with self.app.test_request_context(json={'prompt': 'flip main_door'}):
            request.user = {'_id': self.user_id}
            with patch('routes.chat.versions_collection', return_value=collection):
                _, status = refine_layout_draft.__wrapped__(str(self.project_id), str(self.version_id))
        self.assertEqual(404, status)

    def test_fix_main_gate_endpoint_uses_selected_entrance_without_saving(self):
        collection = Mock()
        collection.find_one.return_value = self.version
        self.design['floors'][0]['doors'][0]['connected_room_ids'] = ['living','exterior']
        with self.app.test_request_context(json={'design':self.design, 'prompt':'fix main gate',
                                                'selection':{'type':'door','id':'main_door','floor_id':'floor_0'}}):
            request.user = {'_id':self.user_id}
            with patch('routes.chat.versions_collection', return_value=collection):
                response = refine_layout_draft.__wrapped__(str(self.project_id), str(self.version_id))
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertIn('repaired', payload['report']['changes'][0])
        self.assertEqual(['living','exterior'], payload['design']['floors'][0]['doors'][0]['connected_room_ids'])
        collection.update_one.assert_not_called()

    def test_selected_room_understands_wider_without_repeating_its_name(self):
        self.design['floors'][0]['rooms'][1]['type'] = 'living_room'
        edited, report = apply_layout_refinement(self.design, 'make room wider', {'type':'room','id':'living','floor_id':'floor_0'})
        self.assertIsNotNone(edited, report)
        rooms = {room['id']:room for room in edited['floors'][0]['rooms']}
        self.assertAlmostEqual(5.5, rooms['living']['dimensions']['width'])
        self.assertEqual('Bedroom', rooms['bedroom']['name'])
        self.assertTrue(validate_schema_v3(edited)[0])

    def test_selected_furniture_uses_exact_identifier_for_generic_instruction(self):
        # Leave room for the rotated bed's approach clearance on its shared door.
        self.design['floors'][0]['furniture'][1]['position']['y'] = 5.3
        edited, report = apply_layout_refinement(self.design, 'rotate it 45 degrees', {'type':'furniture','id':'bed','floor_id':'floor_0'})
        self.assertIsNotNone(edited, report)
        items={item['id']:item for item in edited['floors'][0]['furniture']}
        self.assertEqual(45, items['bed']['rotation'])
        self.assertEqual(0, items['sofa']['rotation'])

    def test_selected_window_accepts_pronoun_and_direction(self):
        edited, report = apply_layout_refinement(self.design,'move it up 25 cm',{'type':'window','id':'living_window','floor_id':'floor_0'})
        self.assertIsNotNone(edited,report)
        self.assertAlmostEqual(5.25,edited['floors'][0]['windows'][0]['position']['y'])

    def test_generated_exterior_endpoint_survives_preflight_without_shared_wall_error(self):
        door = self.design['floors'][0]['doors'][0]
        door.update(connected_room_ids=['living', 'exterior'], connected_room_id='exterior')
        repaired, report = validate_and_repair_design(self.design)
        self.assertEqual([], report['critical_errors'])
        entrance = repaired['floors'][0]['doors'][0]
        self.assertEqual(['living', 'exterior'], entrance['connected_room_ids'])
        self.assertIsNone(entrance['connected_room_id'])
        self.assertAlmostEqual(entrance['offset'], entrance['wall_offset'])

    def test_selected_fix_main_gate_repairs_host_and_jamb_preserving_exterior(self):
        floor = self.design['floors'][0]
        door = floor['doors'][0]
        door.update(wall_id='stale_wall', connected_room_ids=['living', 'exterior'])
        door['position'].update(x=1.01, y=.98)
        before = copy.deepcopy(self.design)
        edited, report = apply_layout_refinement(self.design, 'fix this main gate',
                                                {'type':'door','id':door['id'],'floor_id':'floor_0'})
        self.assertIsNotNone(edited, report)
        repaired = edited['floors'][0]['doors'][0]
        wall = next(wall for wall in edited['floors'][0]['walls'] if wall['id'] == repaired['wall_id'])
        self.assertEqual(['living'], wall['room_ids'])
        self.assertEqual(['living', 'exterior'], repaired['connected_room_ids'])
        self.assertGreaterEqual(repaired['offset'], repaired['width'] / 2 + .119)
        self.assertIn('repaired', report['changes'][0])
        self.assertTrue(validate_schema_v3(edited)[0])
        self.assertEqual(before, self.design)

    def test_fix_selected_door_preserves_real_internal_connections(self):
        floor = self.design['floors'][0]
        door = floor['doors'][1]
        door.update(wall_id=floor['doors'][0]['wall_id'])
        door['position'].update(x=3, y=1)
        edited, report = apply_layout_refinement(self.design, 'repair this door',
                                                {'type':'door','id':door['id'],'floor_id':'floor_0'})
        self.assertIsNotNone(edited, report)
        repaired = edited['floors'][0]['doors'][1]
        self.assertEqual({'living','bedroom'}, set(repaired['connected_room_ids']))
        self.assertAlmostEqual(6, repaired['position']['x'])
        floor['rooms'][1]['position']['x'] = 12
        floor['walls'] = [wall for wall in floor['walls'] if len(wall['room_ids']) == 1]
        edited, report = apply_layout_refinement(self.design, 'fix it',
                                                {'type':'door','id':door['id'],'floor_id':'floor_0'})
        self.assertIsNone(edited)
        self.assertIn('shared wall', report['errors'][0])

    def test_entrance_repair_avoids_overlapping_windows_and_respects_locks(self):
        floor = self.design['floors'][0]
        door = floor['doors'][0]
        floor['windows'][0].update(wall_id=door['wall_id'], wall_side='south', position={'x':3,'y':1,'z':.9})
        edited, report = apply_layout_refinement(self.design, 'fix main gate',
                                                {'type':'door','id':door['id'],'floor_id':'floor_0'})
        self.assertIsNotNone(edited, report)
        entrance = edited['floors'][0]['doors'][0]
        window = edited['floors'][0]['windows'][0]
        self.assertGreaterEqual(abs(entrance['position']['x'] - window['position']['x']), (entrance['width']+window['width']) / 2 + .119)
        for wall in floor['walls']:
            wall['locked'] = True
        edited, report = apply_layout_refinement(self.design, 'fix it',
                                                {'type':'door','id':door['id'],'floor_id':'floor_0'})
        self.assertIsNone(edited)
        self.assertIn('unlocked exterior wall', report['errors'][0])

    def test_selection_must_exist_in_the_supplied_floor(self):
        edited, report=apply_layout_refinement(self.design,'make it wider',{'type':'room','id':'living','floor_id':'another_floor'})
        self.assertIsNone(edited)
        self.assertIn('Select the element again',report['errors'][0])

    def test_selected_room_can_grow_in_depth_using_the_same_topology_solver(self):
        from utils.refinement_resize import _rebuild_floor_walls
        floor=self.design['floors'][0]
        floor['rooms'][1]['position'].update(x=1,y=9)
        floor['furniture'][1]['position'].update(x=3.5,y=13)
        floor['windows'][1]['position'].update(x=6,y=13)
        floor['doors'][1]['position'].update(x=3,y=9)
        floor['doors'][1]['wall_side']='north'
        self.design['building']['width']=5;self.design['building']['depth']=16
        self.design['site']['plot']['depth']=20
        _rebuild_floor_walls(self.design,floor)
        edited,report=apply_layout_refinement(self.design,'make it deeper by 0.5 m',{'type':'room','id':'living','floor_id':'floor_0'})
        self.assertIsNotNone(edited,report)
        target=next(room for room in edited['floors'][0]['rooms'] if room['id']=='living')
        self.assertAlmostEqual(8.5,target['dimensions']['depth'])
        self.assertAlmostEqual(5,target['dimensions']['width'])
        self.assertFalse(any('_editor_min_width' in room for room in edited['floors'][0]['rooms']))

    def test_user_placed_interior_door_keeps_its_offset_during_save(self):
        door=self.design['floors'][0]['doors'][1]
        door['position']['y']=6
        door['client_edited_2d']=True
        repaired,report=validate_and_repair_design(self.design)
        self.assertEqual([],report['critical_errors'])
        saved=next(item for item in repaired['floors'][0]['doors'] if item['id']==door['id'])
        self.assertAlmostEqual(6,saved['position']['y'])
        self.assertEqual({'living','bedroom'},set(saved['connected_room_ids']))

    def test_user_exact_door_approach_conflict_is_reported_before_blender(self):
        floor = self.design['floors'][0]
        item = floor['furniture'][0]
        item.update(client_edited_3d=True, placement_hint='user_exact')
        item['position'].update(x=3,y=1.8)
        before = copy.deepcopy(item['position'])
        repaired, report = validate_and_repair_design(self.design)
        self.assertTrue(any('blocks a door approach' in error for error in report['critical_errors']))
        saved = next(value for value in repaired['floors'][0]['furniture'] if value['id']==item['id'])
        self.assertEqual(before, saved['position'])

    def test_high_wall_furniture_clears_door_height_and_zero_walls_are_removed(self):
        floor = self.design['floors'][0]
        item = floor['furniture'][0]
        item.update(client_edited_3d=True, placement_hint='wall_exact', wall_mounted=True, mount_height=2.4)
        item['position'].update(x=3,y=1.8)
        item['dimensions']['height']=.3
        floor['walls'].append({'id':'collapsed_wall','start':{'x':3.93,'y':6.12},'end':{'x':3.93,'y':6.12},'connected_rooms':['living']})
        repaired, report = validate_and_repair_design(self.design)
        self.assertEqual([],report['critical_errors'])
        self.assertFalse(any(wall['id']=='collapsed_wall' for wall in repaired['floors'][0]['walls']))
        self.assertTrue(any('zero-length wall' in repair for repair in report['repairs']))

    def test_selected_stair_move_keeps_upper_opening_and_core_at_upper_elevation(self):
        root=Path(__file__).resolve().parents[2]
        source="""
import {cadFixture} from './frontend/tests/cad-fixture.mjs';
import {duplicateFloor,synchronizeStairs} from './frontend/src/utils/verticalCirculation.js';
let d=cadFixture();d.floors[0].furniture[0].position.y=7.8;
duplicateFloor(d,0);
d.floors[0].stairs.push({id:'test_stair',type:'u_shaped',position:{x:1.2,y:3.2,z:0},dimensions:{width:2.2,depth:3.8,height:3}});
synchronizeStairs(d);
d.floors[0].stair_core=structuredClone(d.floors[0].stairs[0]);
d.floors[1].stair_core=structuredClone(d.floors[1].stair_openings[0]);
console.log(JSON.stringify(d));
"""
        result=subprocess.run(['node','--input-type=module','-e',source],cwd=root,capture_output=True,text=True,check=True)
        design=json.loads(result.stdout)
        edited,report=apply_layout_refinement(design,'move it right 25 cm',{'type':'stair','id':'test_stair','floor_id':'floor_0'})
        self.assertIsNotNone(edited,report)
        stair=edited['floors'][0]['stairs'][0]
        opening=edited['floors'][1]['stair_openings'][0]
        self.assertAlmostEqual(1.45,stair['position']['x'])
        self.assertEqual(stair['position']['x'],opening['position']['x'])
        self.assertEqual(3,opening['position']['z'])
        self.assertEqual(3,edited['floors'][1]['stair_core']['position']['z'])

    def test_save_rejects_invalid_schema_before_database_write(self):
        self.design['floors'][0]['rooms'][0]['dimensions']['width'] = .2
        collection = Mock(); collection.find_one.return_value = self.version
        with self.app.test_request_context(json={'design': self.design}):
            request.user = {'_id': self.user_id}
            with patch('routes.chat.versions_collection', return_value=collection):
                _, status = update_layout_for_version.__wrapped__(str(self.project_id), str(self.version_id))
        self.assertEqual(400, status); collection.update_one.assert_not_called()


if __name__ == '__main__':
    unittest.main()
