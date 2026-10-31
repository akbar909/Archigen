"""Export an edited frontend fixture and verify it in headless Blender."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from utils.architectural_schema_v3 import validate_schema_v3
from utils.architectural_preflight import validate_and_repair_design
from utils.blender_service import adapt_gemini_to_blender_layout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blender', required=True)
    args = parser.parse_args()
    source = """
import {cadFixture} from './frontend/tests/cad-fixture.mjs';
import {normalizeEditorDesign,syncLegacyAliases,transformRoom} from './frontend/src/utils/roomEditing.js';
import {duplicateFloor,synchronizeStairs} from './frontend/src/utils/verticalCirculation.js';
let d=normalizeEditorDesign(cadFixture());
transformRoom(d.floors[0],'living',{x:1,y:1,width:5,depth:8.25});
d.floors[0].furniture[0].position={x:3.5,y:7.5,z:0};
d.floors[0].furniture[0].flip_x=true;d.floors[0].furniture[0].client_edited_3d=true;
d.floors[0].furniture[1].position.y=7.5;
duplicateFloor(d,0);
for (const [type,x,y,width,depth] of [['u_shaped',1.5,1.5,2.2,3.8],['straight',5,1.5,1.1,5.9],['l_shaped',7,1.5,3.8,3.8]])
 d.floors[0].stairs.push({id:'editor_'+type,type,position:{x,y,z:0},dimensions:{width,depth,height:3}});
synchronizeStairs(d);syncLegacyAliases(d);console.log(JSON.stringify(d));
"""
    result = subprocess.run(['node', '--input-type=module', '-e', source], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    design = json.loads(result.stdout)
    valid, errors = validate_schema_v3(design)
    if not valid:
        raise AssertionError(errors)
    design, report = validate_and_repair_design(design)
    if report['critical_errors']:
        raise AssertionError(report['critical_errors'])
    layout = adapt_gemini_to_blender_layout(design)
    with tempfile.TemporaryDirectory(prefix='.archigen_cad_export_', dir=ROOT) as folder:
        folder = Path(folder)
        input_path, output_path = folder / 'layout.json', folder / 'house.glb'
        input_path.write_text(json.dumps(layout), encoding='utf8')
        env = {**os.environ, 'TEMP': str(folder), 'TMP': str(folder), 'TMPDIR': str(folder)}
        print('Blender: exporting edited rooms, hosted openings, mirrored furniture and three stair types', flush=True)
        process = subprocess.run([args.blender, '--background', '--factory-startup', '--python-exit-code', '1',
                                  '--python', str(ROOT / 'blender/scripts/generate_house.py'), '--',
                                  '--input', str(input_path), '--output', str(output_path)],
                                 capture_output=True, text=True, timeout=600, env=env)
        if process.returncode or not output_path.exists():
            raise RuntimeError(process.stdout[-6000:] + process.stderr[-3000:])
        expected = layout['expected_inventory']['furniture_count']
        if f'Verified furniture inventory: {expected}/{expected}' not in process.stdout:
            raise AssertionError(process.stdout[-6000:])
        with output_path.open('rb') as file:
            header = file.read(12)
            if header[:4] != b'glTF':
                raise AssertionError('Invalid GLB')
            length, kind = struct.unpack('<II', file.read(8))
            document = json.loads(file.read(length).decode('utf8').rstrip(' \t\r\n\x00'))
        nodes = document['nodes']
        for stair_type in ('u_shaped', 'straight', 'l_shaped'):
            if not any(node.get('extras', {}).get('archgen_stair_id') == 'editor_' + stair_type for node in nodes):
                raise AssertionError('Missing exported stair: ' + stair_type)
        if not any(node.get('extras', {}).get('archgen_flip_x') for node in nodes):
            raise AssertionError('Mirror transform metadata was lost in Blender')
        print(json.dumps({'schema': 'passed', 'preflight': 'passed', 'blender_export': 'passed',
                          'stair_types': 3, 'mirrored_furniture': 'passed',
                          'furniture_inventory': expected, 'glb_bytes': output_path.stat().st_size}), flush=True)


if __name__ == '__main__':
    main()
