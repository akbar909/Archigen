"""Audit all local model metadata using the same catalog rules as the editor.

Run with backend/.venv/Scripts/python.exe blender/scripts/audit_metadata.py.
Writes a generated report; never modifies models or source metadata.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'backend'))
from utils.asset_catalog import _entry

inventory = json.loads((ROOT / 'asset-audit.json').read_text(encoding='utf-8'))
metadata = {}
issues = []
for path in sorted((ROOT / 'metadata').glob('*.json')):
    if path.name.endswith('.schema.json'):
        continue
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        issues.append({'metadata': path.name, 'error': str(error)})
        continue
    if record.get('is_template'):
        continue
    metadata[str(record.get('id') or path.stem).lower()] = record
    model_path = ROOT / str(record.get('model_file') or '')
    alternate = model_path.with_suffix('.glb')
    if not model_path.is_file() and not alternate.is_file():
        issues.append({'metadata': path.name, 'error': 'Missing source model', 'path': record.get('model_file')})
    if any(not isinstance(record.get(key), (int, float)) or record[key] <= 0 for key in ('width', 'depth', 'height')):
        issues.append({'metadata': path.name, 'error': 'Missing or invalid physical dimensions'})

models = []
wall_assets = []
for model in inventory['models']:
    asset_id = Path(model['path']).stem.lower()
    record = metadata.get(asset_id)
    if not record:
        issues.append({'path': model['path'], 'warning': 'No source metadata; catalog uses measured proportions and category defaults'})
    entry = _entry(model['path'], 'local_audit')
    row = {'path': model['path'], 'has_metadata': bool(record), 'source_dimensions': model.get('dimensions'),
           'catalog_group': (entry or {}).get('group'), 'catalog_category': (entry or {}).get('category'),
           'effective_dimensions': (entry or {}).get('dimensions'), 'mounting': (entry or {}).get('mounting', {})}
    if entry and entry['group'] in ('wall_decor', 'wall_panel', 'curtain'):
        wall_assets.append(row)
        mounting = row['mounting']
        if not mounting.get('orientation_verified') or mounting.get('front_axis') not in ('+x', '-x', '+z', '-z') or mounting.get('up_axis') != '+y':
            issues.append({'path': model['path'], 'error': 'Wall model requires a verified front and up axis'})
    models.append(row)

summary = {'models': len(models), 'metadata_records': len(metadata),
           'models_with_metadata': sum(row['has_metadata'] for row in models),
           'wall_assets': len(wall_assets), 'verified_wall_assets': sum(bool(row['mounting'].get('orientation_verified')) for row in wall_assets),
           'duplicate_content_groups': len(inventory['duplicates']), 'issues': len(issues)}
report = {'summary': summary, 'issues': issues, 'models': models}
(ROOT / 'metadata-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, indent=2))
if issues:
    print(json.dumps(issues, indent=2))
