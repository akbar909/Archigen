"""Door approaches use actual imported geometry and preserve explicit edits."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'blender' / 'scripts'))
from place_furniture import (_door_clearance_zones, _find_clear_position,
                             _rectangles_overlap, doorways_overlapping_height,
                             reconcile_evaluated_footprint)


class BlenderDoorClearanceTests(unittest.TestCase):
    def test_reported_actual_footprints_are_repaired_without_removing_the_approach(self):
        cases = [
            ((5.08,5.14,6.08,5.33), (4.3,4.35,5.77,5.5), {'x':4.3,'y':4.35,'width':2.6,'depth':2.1}),
            ((5.69,6.89,7.09,8.43), (4.31,6.12,5.91,7.27), {'x':4.31,'y':6.12,'width':3.3,'depth':2.5}),
            ((4.42,7.27,4.89,7.74), (3.93,7.51,5.35,8.66), {'x':3.93,'y':6.12,'width':3.3,'depth':2.54}),
        ]
        for footprint, zone, bounds in cases:
            with self.subTest(footprint=footprint):
                self.assertTrue(_rectangles_overlap(footprint, zone, .01))
                dx, dy, repaired = reconcile_evaluated_footprint(footprint,bounds,[zone])
                self.assertFalse(_rectangles_overlap(repaired,zone,.01))
                self.assertNotEqual((0,0),(dx,dy))
                self.assertGreaterEqual(repaired[0],bounds['x'])
                self.assertGreaterEqual(repaired[1],bounds['y'])

    def test_invalid_exact_position_rejects_without_moving_and_valid_exact_is_unchanged(self):
        bounds = {'x':0,'y':0,'width':4,'depth':4}
        footprint = (.5,.2,1.5,1.2)
        with self.assertRaisesRegex(RuntimeError,'exact furniture placement blocks a door approach'):
            reconcile_evaluated_footprint(footprint,bounds,[(0,0,2,1.15)],user_exact=True)
        valid=(2,2,3,3)
        self.assertEqual((0,0,valid),reconcile_evaluated_footprint(valid,bounds,[(0,0,2,1.15)],user_exact=True))

    def test_shared_door_reserves_the_correct_approach_on_both_sides(self):
        door={'position':[4,2,0], 'width':.9,'height':2.1,
              'room_id':'left','connected_room_ids':['left','right'],'wall_side':'east'}
        left={'id':'left','bounds':{'x':0,'y':0,'width':4,'depth':4,'z':0}}
        right={'id':'right','bounds':{'x':4,'y':0,'width':4,'depth':4,'z':0}}
        self.assertEqual([(2.85,1.2,4,2.8)],_door_clearance_zones(left,[door]))
        self.assertEqual([(4,1.2,5.15,2.8)],_door_clearance_zones(right,[door]))

    def test_high_cabinet_and_garage_overhead_do_not_block_a_pedestrian_approach(self):
        door={'position':[1,0,0],'height':2.1,'width':1,'room_id':'room'}
        garage={**door,'type':'garage_door','swing':'overhead'}
        self.assertEqual([],doorways_overlapping_height([door],2.2,2.8))
        self.assertEqual([door],doorways_overlapping_height([door],1.2,2.3))
        self.assertEqual([],doorways_overlapping_height([garage],0,3))
        room={'id':'room','bounds':{'x':0,'y':0,'width':4,'depth':4,'z':0}}
        self.assertEqual([],_door_clearance_zones(room,[garage]))

    def test_wall_mounted_repair_slides_along_wall_without_detaching_it(self):
        footprint=(.2,.05,1.2,.35)
        bounds={'x':0,'y':0,'width':4,'depth':3}
        dx,dy,repaired=reconcile_evaluated_footprint(footprint,bounds,[(0,0,1.6,1.15)],fixed_axis='y')
        self.assertGreater(dx,0)
        self.assertAlmostEqual(0,dy)
        self.assertFalse(_rectangles_overlap(repaired,(0,0,1.6,1.15),.01))

    def test_no_fit_and_oversized_actual_models_raise_instead_of_reporting_a_clear_position(self):
        with self.assertRaisesRegex(RuntimeError,'larger than its room'):
            reconcile_evaluated_footprint((0,0,5,5),{'width':2,'depth':2},[])
        with self.assertRaisesRegex(RuntimeError,'door-approach clearance'):
            _find_clear_position([1,1,0],1,1,0,{'width':2,'depth':2},[(0,0,2,2)],[])

    def test_actual_blender_offset_geometry_is_reconciled_and_exact_positions_are_preserved(self):
        binary=os.environ.get('BLENDER_BIN') or r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
        if not os.path.isfile(binary):
            self.skipTest('Blender integration binary is not available')
        code=textwrap.dedent('''
            import bpy,sys
            sys.path.insert(0,SCRIPT_PATH)
            from place_furniture import _reconcile_evaluated_placement,_door_clearance_zones,_rectangles_overlap
            room={'id':'test_room','type':'bedroom','height':3,'bounds':{'x':0,'y':0,'width':4,'depth':4,'z':0}}
            doors=[{'id':'door','position':[1,0,0],'room_id':'test_room','width':.9,'height':2.1}]
            def model(name):
                root=bpy.data.objects.new(name,None)
                bpy.context.scene.collection.objects.link(root)
                root.location=(1,1,0)
                bpy.ops.mesh.primitive_cube_add(size=1)
                mesh=bpy.context.object
                mesh.parent=root
                mesh.location=(.45,0,.4)
                mesh.scale=(1.4,1.2,.8)
                return root
            root=model('offset_model')
            req={'id':'offset_bed','placement_hint':'exact'}
            footprint=_reconcile_evaluated_placement(root,req,room,doors,[])
            assert all(not _rectangles_overlap(footprint,zone,.01) for zone in _door_clearance_zones(room,doors))
            assert tuple(root.location)!=(1,1,0)
            root=model('user_exact_model')
            before=tuple(root.location)
            try:
                _reconcile_evaluated_placement(root,{'id':'exact_bed','placement_hint':'user_exact'},room,doors,[])
            except RuntimeError as exc:
                assert 'blocks a door approach' in str(exc)
            else:
                raise AssertionError('Unsafe exact placement must fail')
            assert tuple(root.location)==before
            print('DOOR_CLEARANCE_REGRESSION_PASS')
        ''').replace('SCRIPT_PATH',repr(str(ROOT/'blender'/'scripts')))
        completed=subprocess.run([binary,'--background','--factory-startup','--python-exit-code','1','--python-expr',code],
                                 capture_output=True,text=True,timeout=120)
        self.assertEqual(0,completed.returncode,completed.stdout[-3000:]+'\n'+completed.stderr[-3000:])
        self.assertIn('DOOR_CLEARANCE_REGRESSION_PASS',completed.stdout)


if __name__ == '__main__':
    unittest.main()
