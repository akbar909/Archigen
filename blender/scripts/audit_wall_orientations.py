"""Render read-only cardinal views of every wall-mounted asset for metadata review.

Run with Blender --background --factory-startup --python this_file.py.
Columns show glTF +X, -X, +Z, -Z; no source models are modified.
"""
import json
import math
import os
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from import_asset import load_model

output = tempfile.mkdtemp(prefix='archigen-wall-orientation-')
report = json.load(open(os.path.join(ROOT, 'asset-audit.json'), encoding='utf-8'))
tokens = ('architecture/walls/designs/', 'decorations/wall_art/', 'decorations/mirrors/',
          'decorations/clocks/', 'lighting/wall_sconces/', 'decorations/curtains_blinds/')
models = [entry for entry in report['models'] if any(token in entry['path'] for token in tokens)]
size = 192
sheets = []
for index, entry in enumerate(models):
    if index % 7 == 0:
        sheets.append(np.ones((7 * size, 4 * size, 4), dtype=np.float32) * 0.12)
        sheets[-1][:, :, 3] = 1
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    root = load_model(os.path.join(ROOT, entry['path']))
    bpy.context.view_layer.update()
    meshes = [part for part in [root] + list(root.children_recursive) if part.type == 'MESH']
    points = [part.matrix_world @ Vector(corner) for part in meshes for corner in part.bound_box]
    low = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    factor = 2 / max(high - low)
    root.scale *= factor
    root.location -= (low + high) * 0.5 * factor
    bpy.context.view_layer.update()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 2.5
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (0.16, 0.16, 0.16)
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    for column, (axis, direction) in enumerate((('+x', (1, 0, 0)), ('-x', (-1, 0, 0)), ('+z', (0, -1, 0)), ('-z', (0, 1, 0)))):
        camera.location = Vector(direction) * 5
        camera.rotation_euler = (-camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(output, f'{index:02d}_{axis}.png')
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = np.array(image.pixels[:], dtype=np.float32).reshape(size, size, 4)
        row = 6 - index % 7
        sheets[-1][row * size:(row + 1) * size, column * size:(column + 1) * size] = pixels
        bpy.data.images.remove(image)
    print('WALL_AUDIT_ROW', index // 7, index % 7, entry['path'], flush=True)
for index, pixels in enumerate(sheets):
    image = bpy.data.images.new(f'wall-orientations-{index}', width=4 * size, height=7 * size)
    image.pixels.foreach_set(pixels.ravel())
    image.filepath_raw = os.path.join(output, f'sheet-{index}.png')
    image.file_format = 'PNG'
    image.save()
with open(os.path.join(output, 'index.json'), 'w', encoding='utf-8') as handle:
    json.dump({'columns': ['+x', '-x', '+z', '-z'], 'models': models}, handle, indent=2)
print('WALL_ORIENTATION_AUDIT_OUTPUT', output, flush=True)
