"""Wardrobe source axes, canonical footprint and worker rotation stay aligned."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'blender/scripts'))
sys.path.insert(0,str(ROOT/'backend'))
from utils.asset_catalog import _entry


class WardrobeOrientationTests(unittest.TestCase):
    def test_catalog_uses_reviewed_wardrobe_front_and_proportions(self):
        path=ROOT/'blender/metadata/wardrobe_modern_01.json'
        metadata=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual('wardrobe',metadata['category'])
        self.assertEqual('-x',metadata['mounting']['front_axis'])
        self.assertEqual(90,metadata['canonical_yaw_offset_deg'])
        entry=_entry('assets/furniture/bedroom/wardrobes/wardrobe_modern_01.glb','test')
        self.assertEqual('wardrobe',entry['category'])
        self.assertEqual(90,entry['canonical_yaw_offset_deg'])
        self.assertGreater(entry['dimensions']['width'],entry['dimensions']['depth']*2)
        self.assertGreater(entry['dimensions']['height'],2)

    def test_actual_blender_wardrobe_matches_saved_footprint_and_keeps_explicit_rotation(self):
        binary=os.environ.get('ARCHIGEN_TEST_BLENDER') or r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
        if not Path(binary).is_file():self.skipTest('Local Blender unavailable')
        code=f'''
import bpy,sys,math,json
from mathutils import Vector
sys.path.insert(0,{str(ROOT/'blender/scripts')!r})
from place_furniture import FurnitureCatalog,populate_room_furniture
catalog=FurnitureCatalog({str(ROOT/'blender')!r})
for angle in (0,90,180,270,35):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    room={{'id':'bedroom','type':'bedroom','height':3,'bounds':{{'x':0,'y':0,'z':0,'width':8,'depth':8}}}}
    room['furniture_requirements']=[{{'id':'wardrobe','instance_id':'wardrobe','category':'wardrobe',
        'preferred_id':'wardrobe_modern_01','placement_hint':'wall_backed','anchor_wall':'north',
        'position':[4,4,0],'rotation_deg':angle,'dimensions':{{'width':1.56,'depth':.65,'height':2.06}}}}]
    root=populate_room_furniture(room,catalog,{str(ROOT/'blender')!r},[])[0]
    assert abs(root.get('archgen_semantic_rotation_deg')-angle)<.0001
    assert abs(root.rotation_euler.z-math.radians(angle))<.0001
    meshes=[mesh for mesh in root.children_recursive if mesh.type=='MESH']
    points=[mesh.matrix_world @ Vector(corner) for mesh in meshes for corner in mesh.bound_box]
    width=max(p.x for p in points)-min(p.x for p in points)
    depth=max(p.y for p in points)-min(p.y for p in points)
    expected_width=abs(math.cos(math.radians(angle)))*1.56+abs(math.sin(math.radians(angle)))*.65
    expected_depth=abs(math.sin(math.radians(angle)))*1.56+abs(math.cos(math.radians(angle)))*.65
    assert abs(width-expected_width)<.015,(angle,width,expected_width)
    assert abs(depth-expected_depth)<.015,(angle,depth,expected_depth)
    height=max(p.z for p in points)-min(p.z for p in points)
    assert height>2.04,(angle,height)
    mesh=meshes[0]
    handles=set(index for poly in mesh.data.polygons if poly.material_index==1 for index in poly.vertices)
    body=set(index for poly in mesh.data.polygons if poly.material_index==0 for index in poly.vertices)
    assert handles and body
    handle_points=[mesh.matrix_world @ mesh.data.vertices[index].co for index in handles]
    body_points=[mesh.matrix_world @ mesh.data.vertices[index].co for index in body]
    front=Vector((math.sin(math.radians(angle)),-math.cos(math.radians(angle)),0))
    assert min(point.dot(front) for point in handle_points) > max(point.dot(front) for point in body_points)-.01
print('WARDROBE_ORIENTATION_REGRESSION_PASS',flush=True)
'''
        with tempfile.TemporaryDirectory(prefix='archigen-wardrobe-test-') as folder:
            process=subprocess.run([binary,'--background','--factory-startup','--python-exit-code','1','--python-expr',code],
                capture_output=True,text=True,timeout=120,env={**os.environ,'TEMP':folder,'TMP':folder,'TMPDIR':folder})
        self.assertEqual(0,process.returncode,process.stdout[-7000:]+process.stderr[-3000:])
        self.assertIn('WARDROBE_ORIENTATION_REGRESSION_PASS',process.stdout)


if __name__=='__main__':unittest.main()
