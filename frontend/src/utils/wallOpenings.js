import { clamp, distance, projectToSegment, roomBox, round } from './cadGeometry.js';
// "exterior" is a circulation endpoint, never a room hosted by a wall.
export function openingRoomIds(opening) {
  return [...new Set([opening.room_id || opening.roomId,
    ...(opening.connected_room_ids?.length ? opening.connected_room_ids : opening.connected_rooms || []), opening.connected_room_id]
    .filter(id => id && id !== 'exterior'))];
}
export function isExteriorOpening(opening) {
  return ['main_entrance', 'garage_door'].includes(opening.type) ||
    opening.connected_room_id === 'exterior' ||
    (opening.connected_room_ids?.length ? opening.connected_room_ids : opening.connected_rooms || []).includes('exterior');
}
export function roomEdges(room) {
  const b = roomBox(room);
  return [{
    side: 'south',
    start: {
      x: b.x,
      y: b.y
    },
    end: {
      x: b.right,
      y: b.y
    }
  }, {
    side: 'north',
    start: {
      x: b.x,
      y: b.top
    },
    end: {
      x: b.right,
      y: b.top
    }
  }, {
    side: 'west',
    start: {
      x: b.x,
      y: b.y
    },
    end: {
      x: b.x,
      y: b.top
    }
  }, {
    side: 'east',
    start: {
      x: b.right,
      y: b.y
    },
    end: {
      x: b.right,
      y: b.top
    }
  }];
}
export function openingSide(room, wall) {
  return roomEdges(room).sort((a, b) => projectToSegment(wall.start, a.start, a.end).distance + projectToSegment(wall.end, a.start, a.end).distance - projectToSegment(wall.start, b.start, b.end).distance - projectToSegment(wall.end, b.start, b.end).distance)[0]?.side || 'south';
}
export function hostOpening(floor, opening, point, {
  transfer = true,
  preserveConnections = false
} = {}) {
  const roomIds = wall => wall.room_ids?.length ? wall.room_ids : wall.connected_rooms || [];
  const owner = opening.room_id || opening.roomId;
  const intended = openingRoomIds(opening);
  const exterior = isExteriorOpening(opening);
  const candidates = (floor.walls || []).filter(w => distance(w.start, w.end) >= Number(opening.width) + .2)
    .filter(w => transfer || w.id === opening.wall_id)
    .filter(w => !exterior || (roomIds(w).length === 1 && roomIds(w).includes(owner)))
    .filter(w => !preserveConnections || (intended.length > 1 ? intended.every(id => roomIds(w).includes(id)) : roomIds(w).includes(owner)))
    .map(wall => ({
    wall,
    projection: projectToSegment(point, wall.start, wall.end)
  })).sort((a, b) => a.projection.distance - b.projection.distance);
  if (!candidates.length) throw new Error(exterior ? 'The entrance needs an exterior wall of its room with space for the door and jambs.' : 'No suitable shared wall has space for this opening and its jamb clearances.');
  const {
      wall,
      projection
    } = candidates[0],
    length = projection.length;
  const margin = (Number(opening.width) / 2 + .1) / length,
    t = clamp(projection.t, margin, 1 - margin);
  const ids = roomIds(wall);
  const room = (floor.rooms || []).find(r => r.id === opening.room_id && ids.includes(r.id)) || (floor.rooms || []).find(r => ids.includes(r.id));
  if (!room) throw new Error('The opening needs a wall belonging to a room.');
  const x = round(wall.start.x + (wall.end.x - wall.start.x) * t),
    y = round(wall.start.y + (wall.end.y - wall.start.y) * t);
  return {
    ...opening,
    wall_id: wall.id,
    room_id: room.id,
    roomId: room.id,
    connected_room_id: ids.find(id => id !== room.id) || null,
    connected_room_ids: exterior ? [...ids, 'exterior'] : [...ids],
    connected_rooms: exterior ? [...ids, 'exterior'] : [...ids],
    client_edited_2d: true,
    wall_side: openingSide(room, wall),
    wall_offset: round(t * length),
    offset: round(t * length),
    t: round(t),
    position: {
      x,
      y,
      z: Number(floor.elevation || 0) + Number(opening.sill_height || 0)
    }
  };
}
export function doorSector(door) {
  const width = Number(door.width) || .85,
    side = door.wall_side || 'south',
    right = door.hinge_side === 'right';
  const vertical = ['west', 'east'].includes(side),
    outward = door.swing_direction === 'outward';
  const p = door.position,
    tangent = vertical ? {
      x: 0,
      y: 1
    } : {
      x: 1,
      y: 0
    };
  const normal = {
    south: {
      x: 0,
      y: 1
    },
    north: {
      x: 0,
      y: -1
    },
    west: {
      x: 1,
      y: 0
    },
    east: {
      x: -1,
      y: 0
    }
  }[side] || {
    x: 0,
    y: 1
  };
  const hinge = {
    x: p.x + tangent.x * width / 2 * (right ? 1 : -1),
    y: p.y + tangent.y * width / 2 * (right ? 1 : -1)
  };
  const closed = {
    x: tangent.x * (right ? -1 : 1),
    y: tangent.y * (right ? -1 : 1)
  };
  const open = {
    x: normal.x * (outward ? -1 : 1),
    y: normal.y * (outward ? -1 : 1)
  };
  return [hinge, ...Array.from({
    length: 25
  }, (_, i) => {
    const a = i / 24 * Math.PI / 2;
    return {
      x: hinge.x + width * (closed.x * Math.cos(a) + open.x * Math.sin(a)),
      y: hinge.y + width * (closed.y * Math.cos(a) + open.y * Math.sin(a))
    };
  })];
}

export function doorSectors(door) {
  if (!/double/.test(door.type || '')) return [doorSector(door)];
  const vertical = ['east','west'].includes(door.wall_side);
  return [-1,1].map(sign => doorSector({ ...door, width:door.width / 2,
    hinge_side:sign < 0 ? 'left' : 'right',
    position:{ ...door.position, x:door.position.x + (vertical ? 0 : sign * door.width / 4), y:door.position.y + (vertical ? sign * door.width / 4 : 0) } }));
}
