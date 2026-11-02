"""Distinguish room connections from the exterior circulation endpoint."""


def opening_room_ids(opening):
    values = [opening.get('room_id') or opening.get('roomId')]
    values += list(opening.get('connected_room_ids') or opening.get('connected_rooms') or [])
    values.append(opening.get('connected_room_id'))
    return list(dict.fromkeys(str(value) for value in values if value and value != 'exterior'))


def is_exterior_opening(opening):
    return (opening.get('type') in ('main_entrance', 'garage_door')
            or opening.get('connected_room_id') == 'exterior'
            or 'exterior' in (opening.get('connected_room_ids') or opening.get('connected_rooms') or []))
