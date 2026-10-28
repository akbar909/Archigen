"""Headless regression check for furniture proportions and exact wall placement."""
import json
import math
import os
import sys
import tempfile

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from import_asset import load_model, get_bounding_dimensions
from place_furniture import FurnitureCatalog, place_furniture_item, populate_room_furniture


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


for asset_id in ('nightstand_03', 'dining_table_001', 'cafe_wall_pictures_03'):
    clear_scene()
    with open(os.path.join(ROOT, 'metadata', asset_id + '.json'), encoding='utf-8') as handle:
        meta = json.load(handle)
    baseline = load_model(os.path.join(ROOT, meta['model_file']))
    native = get_bounding_dimensions(baseline)
    if meta.get('mounting', {}).get('front_axis') in ('+x', '-x'):
        native = (native[1], native[0], native[2])
    clear_scene()
    placed = place_furniture_item(meta, [2, 2, 0.22], base_blender_dir=ROOT)
    bpy.context.view_layer.update()
    actual = get_bounding_dimensions(placed)
    ratios = [actual[i] / native[i] for i in range(3)]
    assert max(ratios) - min(ratios) < 0.0001, (asset_id, ratios)
    print('PROPORTIONS_OK', asset_id, [round(value, 3) for value in actual])

clear_scene()
room = {'id': 'dining', 'type': 'dining_room',
        'bounds': {'x': 5, 'y': 8, 'width': 5, 'depth': 4},
        'furniture_requirements': [{
            'id': 'wall_art_dining', 'category': 'wall_decor', 'preferred_id': 'cafe_wall_pictures_03',
            'position': [6.5, 8.15, 0.22], 'rotation_deg': 180, 'wall_mounted': True,
            'mount_height': 1.2, 'placement_hint': 'wall_exact', 'canonical_yaw_offset_deg': 90,
            'dimensions': {'width': 1, 'depth': 0.03, 'height': 0.6},
        }]}
objects = populate_room_furniture(room, FurnitureCatalog(ROOT), ROOT)
assert len(objects) == 1
obj = objects[0]
assert abs(obj.location.x - 6.5) < 0.001 and abs(obj.location.y - 8.15) < 0.001, tuple(obj.location)
assert obj['archgen_room_id'] == 'dining'
assert abs(math.degrees(obj.rotation_euler.z) - 180) < 0.001
print('WALL_ATTACHMENT_OK', obj['archgen_room_id'], tuple(obj.location))

for floor_z in (0, 3.4):
    clear_scene()
    fixture_room = {'id': 'ceiling_room', 'type': 'bedroom', 'height': 3.4,
                    'bounds': {'x': 0, 'y': 0, 'z': floor_z, 'width': 6, 'depth': 6},
                    'furniture_requirements': []}
    for asset_id in ('ceiling_fan_02', 'ceiling_lamp_02'):
        fixture_room['furniture_requirements'].append({
            'id': asset_id, 'preferred_id': asset_id, 'category': 'ceiling_light',
            'ceiling_mounted': True, 'ceiling_clearance': 0.06,
            'placement_hint': 'user_exact', 'position': [2, 2, floor_z],
            'dimensions': {'width': 1.2, 'depth': 1.2, 'height': 0.6},
        })
    fixtures = populate_room_furniture(fixture_room, FurnitureCatalog(ROOT), ROOT)
    for fixture in fixtures:
        points = [part.matrix_world @ Vector(corner) for part in fixture.children_recursive
                  if part.type == 'MESH' for corner in part.bound_box]
        assert abs(max(point.z for point in points) - (floor_z + 3.4 - 0.06)) < 0.002
        assert min(point.z for point in points) > floor_z + 2
    # Check the downloaded model too, after GLB export and reimport.
    with tempfile.TemporaryDirectory(prefix='archigen-ceiling-') as directory:
        model_path = os.path.join(directory, 'ceiling.glb')
        bpy.ops.export_scene.gltf(filepath=model_path, export_format='GLB', export_extras=True)
        clear_scene()
        bpy.ops.import_scene.gltf(filepath=model_path)
        bpy.context.view_layer.update()
        roots = [node for node in bpy.context.scene.objects if node.get('archgen_ceiling_mounted')]
        assert len(roots) == 2
        for fixture in roots:
            points = [part.matrix_world @ Vector(corner) for part in fixture.children_recursive
                      if part.type == 'MESH' for corner in part.bound_box]
            assert abs(max(point.z for point in points) - (floor_z + 3.4 - 0.06)) < 0.002
        print('CEILING_EXPORT_REOPEN_OK', floor_z, len(roots))
clear_scene()
from generate_house_structure import build_walls_from_network
wall = build_walls_from_network([{
    'id': 'shared', 'start': {'x': 0, 'y': 0}, 'end': {'x': 4, 'y': 0},
    'material_overrides': {
        'pz': {'pattern': 'brick', 'normal': {'x': 0, 'y': 0, 'z': 1}},
        'nz': {'pattern': 'wood', 'normal': {'x': 0, 'y': 0, 'z': -1}},
    },
}], [], 3)[0]
assert len(wall.data.materials) == 3
for face in wall.data.polygons:
    normal = (wall.matrix_world.to_3x3().inverted().transposed() @ face.normal).normalized()
    expected = 1 if normal.y < -0.75 else 2 if normal.y > 0.75 else 0
    assert face.material_index == expected, (tuple(normal), face.material_index, expected)
print('INDEPENDENT_WALL_FACES_OK')
clear_scene()
catalog = FurnitureCatalog(ROOT)
source_fronts = {'wall_lamp_02': Vector((0, -1, 0)), 'cafe_wall_pictures_03': Vector((1, 0, 0)),
                 'stylized_gothic_wall_torch_01': Vector((0, -1, 0))}
mounts = {
    'front': ([2, 3.7, 0.22], {'x': 0, 'y': 0, 'z': 1}, {'x': 2, 'y': 4}),
    'back': ([2, 0.3, 0.22], {'x': 0, 'y': 0, 'z': -1}, {'x': 2, 'y': 0}),
    'left': ([0.3, 2, 0.22], {'x': 1, 'y': 0, 'z': 0}, {'x': 0, 'y': 2}),
    'right': ([3.7, 2, 0.22], {'x': -1, 'y': 0, 'z': 0}, {'x': 4, 'y': 2}),
}
requirements = []
for asset_id in source_fronts:
    for side, (position, normal, anchor) in mounts.items():
        requirements.append({'id': f'{asset_id}_{side}', 'preferred_id': asset_id, 'category': 'wall_decor',
                             'position': position, 'wall_side': side, 'wall_normal': normal, 'wall_anchor': anchor,
                             'wall_mounted': True, 'mount_height': 1.2, 'placement_hint': 'wall_exact',
                             'canonical_yaw_offset_deg': 90,  # Deliberately stale legacy catalog value.
                             'dimensions': {'width': 0.8, 'depth': 0.5, 'height': 0.6}})
mounted = populate_room_furniture({'id': 'all_walls', 'type': 'bedroom', 'height': 3.4,
                                 'bounds': {'x': 0, 'y': 0, 'width': 4, 'depth': 4},
                                 'furniture_requirements': requirements}, catalog, ROOT)
assert len(mounted) == 12


def verify_mount(obj):
    asset_id = obj['archgen_model_id']
    side = obj['archgen_wall_side']
    _, normal, anchor = mounts[side]
    inward = Vector((normal['x'], -normal['z'], 0))
    correction = next((part for part in obj.children if 'AxisNormalization' in part.name), None)
    source_front = source_fronts[asset_id].copy()
    if correction:
        source_front = correction.matrix_local.to_3x3() @ source_front
    front = (obj.matrix_world.to_3x3() @ source_front).normalized()
    assert front.dot(inward) > 0.9999, (asset_id, side, tuple(front), tuple(inward))
    meshes = [part for part in obj.children_recursive if part.type == 'MESH']
    back = min((part.matrix_world @ Vector(corner)).dot(inward) for part in meshes for corner in part.bound_box)
    plane = Vector((anchor['x'], anchor['y'], 0)).dot(inward)
    assert abs(back - plane - 0.012) < 0.002, (asset_id, side, back, plane)


for obj in mounted:
    verify_mount(obj)
with tempfile.TemporaryDirectory(prefix='archigen-wall-mounts-') as directory:
    filename = os.path.join(directory, 'all-wall-mounts.glb')
    bpy.ops.export_scene.gltf(filepath=filename, export_format='GLB', export_extras=True)
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=filename)
    bpy.context.view_layer.update()
    reopened = [obj for obj in bpy.context.scene.objects if obj.get('archgen_wall_side')]
    assert len(reopened) == 12
    for obj in reopened:
        verify_mount(obj)
print('WALL_ALL_SIDES_EXPORT_REOPEN_OK', len(reopened))
print('EDITOR_ASSETS_VERIFIED')
