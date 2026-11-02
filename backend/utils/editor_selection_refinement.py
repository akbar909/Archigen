"""Resolve editor instructions against a server-verified selected entity."""
import copy
import math
import re

from utils.architectural_schema_v3 import MIN_ROOM_DIMENSIONS
from utils.stair_geometry import stair_metrics

COLLECTIONS = {'room': 'rooms', 'furniture': 'furniture', 'door': 'doors', 'window': 'windows', 'wall': 'walls', 'stair': 'stairs'}


def resolve_selection(design, selection):
    if not isinstance(selection, dict) or selection.get('type') not in COLLECTIONS:
        return None
    matches = [(floor, entity) for floor in design.get('floors', [])
               if not selection.get('floor_id') or str(floor.get('id')) == str(selection['floor_id'])
               for entity in floor.get(COLLECTIONS[selection['type']], [])
               if str(entity.get('id')) == str(selection.get('id'))]
    return matches[0] if len(matches) == 1 else None


def length_amount(text, default, design):
    match = re.search(r"(?<!\w)(\d+(?:\.\d+)?|\.\d+)\s*(mm|cm|ft|feet|foot|inches|in|meters?|metres?|m)\b", text, re.I)
    if match:
        return float(match[1]) * {'mm': .001, 'cm': .01, 'ft': .3048, 'feet': .3048, 'foot': .3048, 'inches': .0254, 'in': .0254}.get(match[2].lower(), 1)
    match = re.search(r'\b(?:by|to|of)\s+(\d+(?:\.\d+)?)\b', text)
    if match:
        return float(match[1]) * (.3048 if design.get('project', {}).get('display_unit') == 'ft' else 1)
    return default


def _transpose(design):
    """Transpose the entire XY document to reuse the shared-wall width solver."""
    sides = {'north':'east', 'east':'north', 'south':'west', 'west':'south'}
    visited = set()
    def walk(value):
        if isinstance(value, (dict,list)):
            if id(value) in visited: return
            visited.add(id(value))
        if isinstance(value, list):
            for item in value: walk(item)
        elif isinstance(value, dict):
            if all(isinstance(value.get(k), (int, float)) for k in ('x','y')):
                value['x'], value['y'] = value['y'], value['x']
            if all(isinstance(value.get(k), (int, float)) for k in ('width','depth')):
                value['width'], value['depth'] = value['depth'], value['width']
            if all(isinstance(value.get(k), (int, float)) for k in ('width','length')) and 'depth' not in value:
                value['width'], value['length'] = value['length'], value['width']
            for key in ('rotation', 'rotation_y'):
                if isinstance(value.get(key), (int, float)): value[key] = -value[key]
            for key in ('wall_side', 'side', 'orientation'):
                if value.get(key) in sides: value[key] = sides[value[key]]
            if all(k in value for k in ('front','back','left','right')):
                value['front'], value['left'] = value['left'], value['front']
                value['back'], value['right'] = value['right'], value['back']
            for item in value.values(): walk(item)
    walk(design)
    return design


def apply_selection_refinement(base_design, prompt, selection):
    # Lazy imports keep the public refinement dispatcher backward compatible.
    from utils.refinement_resize import _apply_room_resize, _rebuild_floor_walls
    from utils.refinement_furniture import _finalize_refinement
    report = {'handled': True, 'changes': [], 'errors': []}
    design = copy.deepcopy(base_design)
    resolved = resolve_selection(design, selection)
    if not resolved:
        report['errors'] = ['Select the element again; it is no longer in this floor plan.']
        return None, report
    floor, entity = resolved
    kind = selection['type']
    name = entity.get('name') or (entity.get('type', '').replace('_', ' ').title() if kind in ('door', 'window') else kind.title()) or kind.title()
    if entity.get('locked'):
        report['errors'] = [f'Unlock {name} before editing it.']
        return None, report
    text = ' '.join(prompt.lower().split())
    amount = length_amount(text, .5 if kind == 'room' else .25, design)
    increase = bool(re.search(r'\b(wider|widen|larger|bigger|expand|increase|grow|deeper|longer|taller|higher|thicker)\b', text))
    decrease = bool(re.search(r'\b(narrower|smaller|shrink|reduce|decrease|shorter|thinner|lower)\b', text))
    dimension = 'depth' if re.search(r'\b(depth|deep|deeper|longer|length)\b', text) else 'height' if re.search(r'\b(height|taller|higher|lower)\b', text) else 'width'
    if kind == 'room' and (increase or decrease or re.search(r'\b(?:width|depth|height)\b.*\bto\b', text)):
        current = float(entity['dimensions'][dimension])
        desired = amount if re.search(r'\bto\s+\d', text) else current + amount * (-1 if decrease else 1)
        if dimension in ('width', 'depth') and desired > current:
            if dimension == 'depth':
                _transpose(design)
                for storey in design['floors']:
                    for room in storey['rooms']:
                        room['_editor_min_width'] = MIN_ROOM_DIMENSIONS.get(room.get('type'), (1,1))[1]
            result, report = _apply_room_resize(design, {
                'room_type': entity.get('type', 'room'), 'room_id': entity['id'], 'floor_id': floor['id'],
                'mode': 'to' if re.search(r'\d',text) else None, 'amount': desired if re.search(r'\d',text) else None, 'axis': 'width',
            }, report)
            if result is not None and dimension == 'depth':
                _transpose(result)
                for storey in result['floors']:
                    for room in storey['rooms']: room.pop('_editor_min_width', None)
            if result is not None:
                actual = resolve_selection(result,selection)[1]['dimensions'][dimension]
                report['changes'] = [f'{name} is now {actual:.2f} m {"deep" if dimension == "depth" else "wide"}.']
            return result, report
        minimum = 2 if dimension == 'height' else MIN_ROOM_DIMENSIONS.get(entity.get('type'), (1,1))[dimension == 'depth']
        if desired < minimum or dimension == 'height' and desired > float(floor.get('floor_height', 3)):
            report['errors'] = [f'{name} cannot use that dimension. Keep its {dimension} at least {minimum:.2f} m and below the floor height.']
            return None, report
        entity['dimensions'][dimension] = round(desired,4)
        _rebuild_floor_walls(design, floor)
    elif kind == 'furniture':
        room = next((r for r in floor.get('rooms',[]) if r['id'] == (entity.get('room_id') or entity.get('roomId'))), None)
        if not room:
            report['errors'] = ['Place this furniture in a room first.']; return None, report
        if re.search(r'\b(rotate|turn)\b', text):
            angle = re.search(r'(\d+(?:\.\d+)?)\s*(?:degrees?|°)?', text)
            value = float(angle[1]) if angle else 90
            entity['rotation'] = (float(entity.get('rotation',0)) + value * (-1 if re.search(r'\b(left|counterclockwise)\b',text) else 1)) % 360
        elif re.search(r'\b(mirror|flip)\b', text):
            key = 'flip_y' if re.search(r'\b(y|vertical)\b',text) else 'flip_x'; entity[key] = not entity.get(key,False)
        elif increase or decrease:
            dims = entity.setdefault('dimensions',{})
            if re.search(r'\b(bigger|larger|smaller)\b',text) and not re.search(r'\d',text):
                for key in ('width','depth','height'): dims[key] = round(float(dims.get(key,1)) * (.9 if decrease else 1.1),4)
            else:
                dims[dimension] = round(amount if re.search(r'\bto\s+\d',text) else float(dims.get(dimension,1)) + amount * (-1 if decrease else 1),4)
                if dims[dimension] < .05: report['errors'] = ['Keep furniture dimensions above 5 cm.']; return None, report
        elif re.search(r'\b(move|slide|shift|center|centre|opposite)\b',text):
            pos, rp, rd = entity['position'], room['position'], room['dimensions']
            angle = math.radians(float(entity.get('rotation',0)))
            hw = (abs(math.cos(angle))*entity['dimensions']['width']+abs(math.sin(angle))*entity['dimensions']['depth'])/2+.1
            hd = (abs(math.sin(angle))*entity['dimensions']['width']+abs(math.cos(angle))*entity['dimensions']['depth'])/2+.1
            if re.search(r'\b(centre|center)\b',text): pos.update(x=rp['x']+rd['width']/2,y=rp['y']+rd['depth']/2)
            elif 'opposite' in text:
                side = min([(pos['x']-rp['x'],'west'),(rp['x']+rd['width']-pos['x'],'east'),(pos['y']-rp['y'],'south'),(rp['y']+rd['depth']-pos['y'],'north')])[1]
                if side in ('west','east'): pos['x'] = rp['x']+rd['width']-hw if side == 'west' else rp['x']+hw
                else: pos['y'] = rp['y']+rd['depth']-hd if side == 'south' else rp['y']+hd
            elif re.search(r'\b(left|west)\b',text): pos['x'] -= amount
            elif re.search(r'\b(right|east)\b',text): pos['x'] += amount
            elif re.search(r'\b(up|north|back)\b',text): pos['y'] += amount
            elif re.search(r'\b(down|south|front)\b',text): pos['y'] -= amount
            else: report['errors'] = [f'Tell me where to move {name}, for example “move it left 25 cm”.']; return None, report
        else:
            report['errors'] = [f'For {name}, try “rotate it 45 degrees”, “move it left”, or “make it smaller”.']; return None, report
        entity['client_edited_3d'] = True; entity['placement_hint'] = 'user_exact'
    elif kind in ('door','window'):
        if re.search(r'\b(fix|repair|resolve|rehost)\b', text):
            from utils.editor_opening_repair import repair_selected_opening
            error = repair_selected_opening(floor, entity)
            if error:
                report['errors'] = [error]
                return None, report
            report['changes'] = [f'{name} repaired on its {"exterior" if "exterior" in entity["connected_room_ids"] else "shared"} wall.']
            return _finalize_refinement(design, report)
        elif increase or decrease or re.search(r'\b(width|height|sill)\b.*\bto\b',text):
            key = 'sill_height' if 'sill' in text and kind == 'window' else dimension
            if key == 'depth': key = 'width'
            value = length_amount(text, .1,design)
            entity[key] = round(value if re.search(r'\bto\s+\d',text) else float(entity.get(key, .9)) + value * (-1 if decrease else 1),4)
            if entity[key] < 0 or key != 'sill_height' and entity[key] < .3:
                report['errors'] = ['That opening would be too small.']; return None, report
            if float(entity.get('height',2.1))+float(entity.get('sill_height',0))>float(floor.get('floor_height',3)):
                report['errors'] = ['The opening would extend above the ceiling. Reduce its height or sill.']; return None, report
        else:
            from utils.architectural_refinement import _apply_editor_opening_refinement
            instruction = f'{prompt} {kind} {entity["id"]}'
            instruction = re.sub(r'\bup\b','north',instruction,flags=re.I)
            instruction = re.sub(r'\bdown\b','south',instruction,flags=re.I)
            if re.search(r'\b(move|slide|shift)\b',text) and not re.search(r'\d',text): instruction += ' 0.25 m'
            result,opening_report=_apply_editor_opening_refinement(design,instruction)
            if not opening_report['handled']:
                return None, {'handled':True,'changes':[],'errors':[f'For {name}, try “move it right 25 cm”, “make it wider”, or “flip its hinge”.']}
            return result,opening_report
        entity['client_edited_2d'] = True
    elif kind == 'wall' and re.search(r'\b(thicker|thinner|thickness)\b',text):
        amount=length_amount(text,.02,design)
        entity['thickness'] = round(amount if re.search(r'\bto\s+\d',text) else float(entity.get('thickness',.2)) + amount * (-1 if 'thinner' in text else 1),4)
        if not .1 <= entity['thickness'] <= .5:
            report['errors'] = ['Wall thickness must stay between 10 and 50 cm.']; return None,report
    elif kind == 'stair' and (increase or decrease or re.search(r'\b(move|slide|shift)\b',text)):
        if increase or decrease:
            if dimension=='height':report['errors']=['Stair height follows the floor height. Change the floor height in Properties.'];return None,report
            entity['dimensions'][dimension]=round(float(entity['dimensions'][dimension])+amount*(-1 if decrease else 1),4)
            if entity['dimensions'][dimension] < (.9 if dimension=='width' else 2):
                report['errors']=['Keep stairs at least 0.90 m wide and 2 m deep.'];return None,report
        else:
            if re.search(r'\b(left|west)\b',text):entity['position']['x']-=amount
            elif re.search(r'\b(right|east)\b',text):entity['position']['x']+=amount
            elif re.search(r'\b(up|north|back)\b',text):entity['position']['y']+=amount
            elif re.search(r'\b(down|south|front)\b',text):entity['position']['y']-=amount
            else:report['errors']=['Choose a direction, for example “move it left 25 cm”.'];return None,report
        floor_index=design['floors'].index(floor)
        metrics = stair_metrics(entity, floor.get('floor_height', 3))
        if metrics['errors']:
            report['errors'] = [f"The stair {error}" for error in metrics['errors']];return None,report
        if floor_index+1<len(design['floors']):
            upper=design['floors'][floor_index+1]
            opening=next((o for o in upper.get('stair_openings',[]) if o.get('serves_stair_id')==entity['id']),None)
            if opening:
                opening['position']={**entity['position'],'z':upper.get('elevation',0)}
                opening['dimensions']={**entity['dimensions'],'height':upper.get('slab_thickness',.2)}
                for axis in ('width', 'depth'):
                    opening['dimensions'][axis] += float(entity.get('opening_clearance', 0))
        for storey in (floor,design['floors'][floor_index+1] if floor_index+1<len(design['floors']) else {}):
            if storey.get('stair_core'):
                storey['stair_core']['position']={**entity['position'],'z':storey.get('elevation',0)}
                storey['stair_core']['dimensions']=copy.deepcopy(entity['dimensions'])
    else:
        examples = '“make it wider” or “make it deeper by 30 cm”' if kind == 'room' else 'a move, resize or rotation'
        report['errors'] = [f'For {name}, try {examples}.']; return None, report
    report['changes'] = [f'{name} updated.']
    return _finalize_refinement(design,report)
