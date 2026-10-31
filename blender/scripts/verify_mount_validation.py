"""Run with Blender --background --python-exit-code 1 --python this_file.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from generate_house_validation import validate_generated_scene
from place_furniture import FurnitureCatalog, populate_room_furniture


def main():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    catalog = FurnitureCatalog(base)
    rooms, expected, doors = [], [], []
    for level, elevation in enumerate([0, 3.4]):
        room_id = f'room_{level}'
        requirements = [
            {'id': f'ceiling_{level}', 'preferred_id': 'ceiling_lamp_01', 'category': 'ceiling_light',
             'ceiling_mounted': True, 'ceiling_clearance': 0.06 if level == 0 else 0.12,
             'position': [1, 0.6, elevation], 'dimensions': {'width': 0.45, 'depth': 0.45, 'height': 0.5}},
            {'id': f'wall_{level}', 'preferred_id': 'wall_lamp_02', 'category': 'wall_decor',
             'wall_mounted': True, 'mount_height': 1.4, 'position': [3, 3, elevation],
             'dimensions': {'width': 0.4, 'depth': 0.4, 'height': 0.4}},
            {'id': f'floor_{level}', 'preferred_id': 'nightstand_01', 'category': 'nightstand',
             'position': [4, 4, elevation], 'dimensions': {'width': 0.5, 'depth': 0.5, 'height': 0.6}},
        ]
        for item in requirements:
            item['placement_hint'] = 'user_exact'
        room = {'id': room_id, 'type': 'bedroom', 'height': 3, 'floor_level': level,
                'bounds': {'x': 0, 'y': 0, 'z': elevation, 'width': 6, 'depth': 6},
                'furniture_requirements': requirements}
        bpy.ops.mesh.primitive_cube_add(size=1, location=(3, 3, elevation - 0.05))
        floor = bpy.context.object
        floor.name = f'Floor_{room_id}'
        floor.scale = (6, 6, 0.1)
        floor['archgen_room_id'] = room_id
        door = {'id': f'door_{level}', 'room_id': room_id, 'position': [1, 0, elevation], 'width': 0.9, 'height': 2.1}
        doors.append(door)
        populate_room_furniture(room, catalog, base, [door])
        rooms.append(room)
        expected.extend(item['id'] for item in requirements)
    layout = {'doors': doors, 'site': {'plot': {'width': 6, 'depth': 6}}}
    validate_generated_scene(layout, rooms, expected)
    ceiling = next(obj for obj in bpy.context.scene.objects if obj.get('archgen_instance_id') == 'ceiling_0')
    ceiling.location.z -= 0.2
    try:
        validate_generated_scene(layout, rooms, expected)
    except RuntimeError as error:
        assert 'not attached to its ceiling' in str(error), str(error)
    else:
        raise AssertionError('Misattached ceiling lamp was accepted')
    print('MOUNT_VALIDATION_PASS: real ceiling, wall and floor assets on two floors; invalid mount rejected')


if __name__ == '__main__':
    main()
