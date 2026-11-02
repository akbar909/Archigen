"""Reported curtain, shower and door hierarchy regressions use the real assets."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'blender/scripts'))
from utils.furniture_mounting import mount_wall_fixture
from utils.blender_service import _aligned_wall_item
from generate_house_opening_models import _select_window_model_path


class InteriorAssetTests(unittest.TestCase):
    def test_arched_window_exists_but_is_only_selected_for_an_explicit_request(self):
        arched=ROOT/'blender/assets/architecture/windows/arched/arched_window_01.glb'
        standard=ROOT/'blender/assets/windows/window_standard_02.glb'
        self.assertTrue(arched.is_file())
        self.assertEqual(str(standard),_select_window_model_path([str(arched),str(standard)]))
        self.assertEqual(str(arched),_select_window_model_path([str(standard),str(arched)],'arched_window_01'))

    def test_shower_mount_migration_retains_explicit_height_and_dimensions(self):
        room={'position':{'x':0,'y':0,'z':0},'dimensions':{'width':4,'depth':4,'height':3}}
        old={'id':'shower','asset_id':'shower_set_02','category':'shower','position':{'x':3.5,'y':2,'z':0},'dimensions':{'width':1,'depth':1,'height':2.1}}
        mounted=mount_wall_fixture(old,room)
        self.assertTrue(mounted['wall_mounted'])
        self.assertEqual(.95,mounted['mount_height'])
        self.assertEqual(1.35,mounted['dimensions']['height'])
        mounted['mount_height']=1.05
        self.assertEqual(1.05,mount_wall_fixture(mounted,room)['mount_height'])
        self.assertNotIn('wall_mounted',old)

    def test_explicit_right_wall_survives_mount_normalization_after_save(self):
        room={'position':{'x':4,'y':0,'z':0},'dimensions':{'width':3,'depth':4,'height':3}}
        item={'id':'shower','asset_id':'shower_set_02','category':'shower','wall_mounted':True,
              'wall_side':'right','anchor_wall':'west','mount_height':1.05,
              'position':{'x':4.5,'y':2,'z':0},'dimensions':{'width':.527,'depth':.827,'height':1.35}}
        saved=mount_wall_fixture(item,room)
        self.assertEqual('right',saved['wall_side'])
        self.assertEqual(-1,saved['wall_normal']['x'])
        self.assertEqual(270,saved['rotation'])
        self.assertEqual('east',saved['anchor_wall'])
        self.assertGreater(saved['position']['x'],6)
        self.assertEqual(1.05,saved['mount_height'])

    def test_curtains_outward_normal_is_migrated_without_editing_source(self):
        item={'wall_mounted':True,'s3_key':'assets/decorations/curtains_blinds/curtains_04.glb',
              'room_id':'room','wall_side':'left','wall_normal':{'x':-1,'z':0},'dimensions':{'width':1.8,'depth':.071,'height':1.33},
              'position':{'x':.1,'y':2,'z':0}}
        before=copy.deepcopy(item)
        migrated=_aligned_wall_item(item,{'position':{'x':0,'y':0},'dimensions':{'width':4,'depth':4}})
        self.assertEqual(1,migrated['wall_normal']['x'])
        self.assertEqual(before,item)

    def test_real_door_panel_and_handles_move_together_and_shower_is_mounted_above_floor(self):
        binary=os.environ.get('ARCHIGEN_TEST_BLENDER') or r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
        if not Path(binary).is_file():self.skipTest('Local Blender unavailable')
        room={'id':'bathroom','type':'bathroom','height':3,'bounds':{'x':0,'y':0,'z':0,'width':4,'depth':4}}
        item=mount_wall_fixture({'id':'shower','asset_id':'shower_set_02','category':'shower',
            'position':{'x':3.5,'y':2,'z':0},'dimensions':{'width':1,'depth':1,'height':2.1}},
            {'position':{'x':0,'y':0,'z':0},'dimensions':{'width':4,'depth':4,'height':3}})
        req={**item,'preferred_id':item['asset_id'],'position':[item['position'][key] for key in ('x','y','z')],
             'rotation_deg':item['rotation'],'instance_id':'shower'}
        code=f'''
import bpy,sys,math
from mathutils import Vector
sys.path.insert(0,{str(ROOT/'blender/scripts')!r})
from generate_house_opening_models import _try_import_door_model,_try_import_window_model
from place_furniture import FurnitureCatalog,populate_room_furniture
for index,(vertical,swing) in enumerate([(False,'inward_left'),(False,'inward_right'),(True,'outward_right')]):
    root=_try_import_door_model(2,1,0,.9,2.1,index,is_vertical=vertical,swing=swing)
    assert root is not None
    parts={{mesh.get('archgen_source_object_name'):mesh for mesh in root.children_recursive if mesh.type=='MESH'}}
    panel=parts['door_frame'];handle=parts['door_handle'];casing=parts['door_casing']
    assert panel.parent==handle.parent and panel.parent!=casing.parent,'Door panel must rotate with its hardware'
    hinge=panel.parent
    before=panel.matrix_world.inverted() @ handle.matrix_world
    hinge.rotation_euler.z=0;bpy.context.view_layer.update()
    after=panel.matrix_world.inverted() @ handle.matrix_world
    assert max(abs(before[i][j]-after[i][j]) for i in range(4) for j in range(4))<.0001
window=_try_import_window_model(2,0,1.6,1.4,1.2,20)
assert window is not None and window.get('archgen_source_file')=='window_standard_02.glb'
room={room!r};room['furniture_requirements']=[{req!r}]
items=populate_room_furniture(room,FurnitureCatalog({str(ROOT/'blender')!r}),{str(ROOT/'blender')!r},[])
assert len(items)==1
meshes=[obj for obj in items[0].children_recursive if obj.type=='MESH']
points=[mesh.matrix_world @ Vector(corner) for mesh in meshes for corner in mesh.bound_box]
assert min(p.z for p in points)>.94
assert max(p.z for p in points)>2.2 and max(p.z for p in points)<2.4
assert max(p.x for p in points)<4 and min(p.x for p in points)>0
print('INTERIOR_ASSET_REGRESSIONS_PASS',flush=True)
'''
        with tempfile.TemporaryDirectory(prefix='archigen-interior-test-') as folder:
            process=subprocess.run([binary,'--background','--factory-startup','--python-exit-code','1','--python-expr',code],
                capture_output=True,text=True,timeout=120,env={**os.environ,'TEMP':folder,'TMP':folder,'TMPDIR':folder})
        self.assertEqual(0,process.returncode,process.stdout[-7000:]+process.stderr[-3000:])
        self.assertIn('INTERIOR_ASSET_REGRESSIONS_PASS',process.stdout)


if __name__=='__main__':unittest.main()
