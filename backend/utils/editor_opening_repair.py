"""Repair one selected opening without inventing or dropping room connections."""
import math

from utils.architectural_preflight import _infer_side, WALL_MARGIN, OPENING_GAP
from utils.opening_connections import opening_room_ids, is_exterior_opening


def repair_selected_opening(floor, opening):
    owner = opening.get('room_id') or opening.get('roomId')
    room = next((room for room in floor.get('rooms', []) if room['id'] == owner), None)
    if not room:
        return 'This opening needs a room before it can be repaired.'
    intended = set(opening_room_ids(opening))
    exterior = is_exterior_opening(opening)
    width = float(opening.get('width', .9))
    margin = width / 2 + WALL_MARGIN
    original = opening.get('position') or room['position']
    candidates = []
    for wall in floor.get('walls', []):
        ids = list(wall.get('room_ids') or wall.get('connected_rooms') or [])
        if wall.get('locked') or owner not in ids or not intended.issubset(set(ids)):
            continue
        if exterior and len(ids) != 1:
            continue
        start, end = wall.get('start') or wall.get('from'), wall.get('end') or wall.get('to')
        if not start or not end:
            continue
        dx, dy = end['x'] - start['x'], end['y'] - start['y']
        length = math.hypot(dx, dy)
        if length < 2 * margin:
            continue
        ux, uy = dx / length, dy / length
        projected = (original['x'] - start['x']) * ux + (original['y'] - start['y']) * uy
        blocked = []
        for other in floor.get('doors', []) + floor.get('windows', []):
            if other.get('id') == opening.get('id') or not other.get('position'):
                continue
            position = other['position']
            offset = (position['x'] - start['x']) * ux + (position['y'] - start['y']) * uy
            separation = abs((position['x'] - start['x']) * uy - (position['y'] - start['y']) * ux)
            if separation <= .05 and 0 <= offset <= length:
                clearance = (width + float(other.get('width', .9))) / 2 + OPENING_GAP
                blocked.append((offset - clearance, offset + clearance))
        offsets = [max(margin, min(length - margin, projected)), margin, length - margin]
        offsets += [edge for interval in blocked for edge in interval]
        for offset in offsets:
            if offset < margin - 1e-6 or offset > length - margin + 1e-6:
                continue
            if any(a + 1e-6 < offset < b - 1e-6 for a, b in blocked):
                continue
            position = {'x': round(start['x'] + ux * offset, 4),
                        'y': round(start['y'] + uy * offset, 4),
                        'z': float(floor.get('elevation', 0)) + float(opening.get('sill_height', 0))}
            score = math.hypot(position['x'] - original['x'], position['y'] - original['y'])
            candidates.append((score, wall['id'] != opening.get('wall_id'), wall, ids, position, offset, length))
    if not candidates:
        return ('The entrance needs an unlocked exterior wall of its room with enough free space. '
                'Move another opening or reduce the door width.' if exterior else
                'These rooms need a shared wall with enough free space for this door. Move the rooms together or choose another connection.')
    _, _, wall, ids, position, offset, length = min(candidates, key=lambda value: value[:2])
    opening.update(wall_id=wall['id'], room_id=owner, roomId=owner, position=position,
                   wall_side=_infer_side(room, {'position': position}),
                   offset=round(offset, 4), wall_offset=round(offset, 4), t=round(offset / length, 6),
                   connected_room_ids=ids + (['exterior'] if exterior else []),
                   connected_rooms=ids + (['exterior'] if exterior else []),
                   connected_room_id=next((value for value in ids if value != owner), None),
                   client_edited_2d=True)
    return None
