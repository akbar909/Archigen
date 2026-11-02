import { clone, containsPoint, distance, EPS, roomBox, round, uid } from './cadGeometry.js';
import { hostOpening, roomEdges } from './wallOpenings.js';
export function rebuildWalls(floor, thickness = .2) {
  const edges = (floor.rooms || []).flatMap(room => roomEdges(room).map(e => ({
      ...e,
      room
    }))),
    segments = new Map();
  for (const edge of edges) {
    const horizontal = Math.abs(edge.start.y - edge.end.y) < EPS;
    const axis = horizontal ? 'x' : 'y',
      fixed = horizontal ? 'y' : 'x';
    const cuts = [...new Set([edge.start[axis], edge.end[axis], ...edges.filter(e => Math.abs(e.start[fixed] - edge.start[fixed]) < EPS && Math.abs(e.end[fixed] - edge.start[fixed]) < EPS).flatMap(e => [e.start[axis], e.end[axis]]).filter(v => v > edge.start[axis] && v < edge.end[axis])].map(round))].sort((a, b) => a - b);
    for (let i = 0; i < cuts.length - 1; i++) {
      if (cuts[i + 1] - cuts[i] < EPS) continue;
      const start = {
          [axis]: cuts[i],
          [fixed]: edge.start[fixed]
        },
        end = {
          [axis]: cuts[i + 1],
          [fixed]: edge.start[fixed]
        };
      const key = `${round(start.x)},${round(start.y)}:${round(end.x)},${round(end.y)}`;
      if (!segments.has(key)) {
        const previous = (floor.walls || []).find(w => distance(w.start, start) < EPS && distance(w.end, end) < EPS);
        segments.set(key, {
          ...previous,
          id: previous?.id || `${floor.id}_wall_${key}`,
          start,
          end,
          room_ids: [],
          connected_rooms: [],
          thickness: previous?.thickness || thickness,
          load_bearing: previous?.load_bearing
        });
      }
      segments.get(key).room_ids.push(edge.room.id);
    }
  }
  floor.walls = [...segments.values()].map(w => ({
    ...w,
    type: w.room_ids.length > 1 ? 'interior' : 'exterior',
    load_bearing: w.load_bearing ?? w.room_ids.length === 1,
    connected_rooms: [...w.room_ids],
    thickness: w.type === 'interior' ? w.thickness : w.room_ids.length > 1 ? .12 : w.thickness
  }));
  return floor;
}
export function rehostOpenings(floor) {
  for (const key of ['doors', 'windows']) floor[key] = (floor[key] || []).map(opening => {
    const walls = floor.walls.filter(w => (w.room_ids || []).includes(opening.room_id || opening.roomId));
    try {
      return hostOpening({
        ...floor,
        walls: walls.length ? walls : floor.walls
      }, opening, opening.position, { preserveConnections: key === 'doors' });
    } catch {
      return opening;
    } // Invalid apertures remain visible and are reported, never silently removed.
  });
}
export function normalizeEditorDesign(input) {
  const design = clone(input);
  if (!design.floors?.length) design.floors = [{
    id: 'floor_0',
    level: 0,
    elevation: 0,
    floor_height: 3,
    rooms: design.rooms || [],
    walls: design.walls || [],
    doors: design.doors || [],
    windows: design.windows || [],
    furniture: design.furniture || [],
    stairs: []
  }];
  for (const floor of design.floors) {
    for (const key of ['rooms', 'walls', 'doors', 'windows', 'furniture', 'stairs', 'stair_openings']) floor[key] ||= [];
    for (const room of floor.rooms) {
      room.position = {
        z: floor.elevation || 0,
        ...room.position
      };
      room.dimensions = {
        width: room.width || 4,
        depth: room.length || 4,
        height: floor.floor_height || 3,
        ...room.dimensions
      };
      // Collapse legacy nested assets into the canonical floor collection.
      for (const key of ['furniture', 'doors', 'windows']) {
        for (const item of room[key] || []) if (!floor[key].some(i => i.id === item.id)) floor[key].push({
          ...item,
          room_id: item.room_id || room.id
        });
      }
    }
    floor.walls = floor.walls.map(wall => ({ ...wall, start: wall.start || wall.from, end: wall.end || wall.to, room_ids: wall.room_ids || wall.connected_rooms || [] }));
    if (floor.walls.some(wall => !wall.start || !wall.end)) floor.walls = [];
    floor.walls = floor.walls.filter(wall => distance(wall.start, wall.end) > EPS);
    for (const item of floor.furniture) {
      item.position = { x: 0, y: 0, z: floor.elevation || 0, ...item.position };
      const dimensions = item.dimensions || {};
      item.dimensions = { ...dimensions, width: Number(dimensions.width ?? dimensions.w) || .8, depth: Number(dimensions.depth ?? dimensions.d) || .8, height: Number(dimensions.height ?? dimensions.h) || .8 };
      item.rotation = Number(item.rotation ?? item.rotation_y) || 0;
    }
    if (!floor.walls.length) {
      rebuildWalls(floor, design.building?.wall_thickness);
      rehostOpenings(floor);
    }
    for (const door of floor.doors) {
      door.hinge_side ||= String(door.swing || 'inward_right').includes('right') ? 'right' : 'left';
      door.swing_direction ||= String(door.swing || '').includes('outward') ? 'outward' : 'inward';
    }
  }
  return design;
}
export function syncLegacyAliases(design) {
  // Legacy projections must follow edits and deletions rather than resurrect stale entities.
  for (const floor of design.floors) for (const door of floor.doors) door.swing = `${door.swing_direction || 'inward'}_${door.hinge_side || 'right'}`;
  for (const floor of design.floors) for (const room of floor.rooms) {
    if ('width' in room) room.width = room.dimensions.width;
    if ('length' in room) room.length = room.dimensions.depth;
    for (const key of ['furniture', 'doors', 'windows']) if (Array.isArray(room[key])) room[key] = clone(floor[key].filter(i => (i.room_id || i.roomId) === room.id));
  }
  for (const key of ['rooms', 'walls', 'doors', 'windows', 'furniture', 'stairs']) {
    if (Array.isArray(design[key])) design[key] = clone(design.floors.flatMap(f => f[key] || []));
  }
  return design;
}
export function transformRoom(floor, id, nextBox, thickness = .2) {
  const room = floor.rooms.find(r => r.id === id);
  if (!room || room.locked) throw new Error('This room is locked.');
  if (floor.walls.some(w => w.locked && (w.room_ids || w.connected_rooms || []).includes(id))) throw new Error('A wall belonging to this room is locked.');
  const before = roomBox(room),
    after = {
      ...before,
      ...nextBox
    };
  if (after.width < 1 || after.depth < 1) throw new Error('Rooms need a width and depth of at least 1 m.');
  const dx = after.x - before.x,
    dy = after.y - before.y;
  room.position.x = round(after.x);
  room.position.y = round(after.y);
  room.dimensions.width = round(after.width);
  room.dimensions.depth = round(after.depth);
  for (const item of floor.furniture) if ((item.room_id || item.roomId) === id) {
    item.position.x = round(item.position.x + dx);
    item.position.y = round(item.position.y + dy);
    item.client_edited_3d = true;
  }
  for (const opening of [...floor.doors, ...floor.windows]) if ((opening.room_id || opening.roomId) === id) {
    const side = opening.wall_side || 'south',
      p = opening.position;
    const tx = (p.x - before.x) / before.width,
      ty = (p.y - before.y) / before.depth;
    p.x = round(after.x + tx * after.width);
    p.y = round(after.y + ty * after.depth);
    if (side === 'south') p.y = after.y;
    if (side === 'north') p.y = after.y + after.depth;
    if (side === 'west') p.x = after.x;
    if (side === 'east') p.x = after.x + after.width;
  }
  rebuildWalls(floor, thickness);
  rehostOpenings(floor);
  return floor;
}
export function moveWall(floor, wallId, point, thickness) {
  const wall = floor.walls.find(w => w.id === wallId);
  if (!wall) return;
  if (wall.locked) throw new Error('Unlock this wall before moving it.');
  const horizontal = Math.abs(wall.end.y - wall.start.y) < EPS;
  const affected = (wall.room_ids || wall.connected_rooms || []).map(id => floor.rooms.find(r => r.id === id)).filter(Boolean);
  if (affected.some(r => r.locked)) throw new Error('A connected room is locked.');
  const changes = affected.map(room => {
    const b = roomBox(room),
      edge = roomEdges(room).find(e => distance(e.start, wall.start) + distance(e.end, wall.end) < .01) || roomEdges(room).find(e => horizontal ? Math.abs(e.start.y - wall.start.y) < EPS : Math.abs(e.start.x - wall.start.x) < EPS);
    const next = {
      ...b
    };
    if (edge?.side === 'south') {
      next.y = point.y;
      next.depth = b.top - point.y;
    }
    if (edge?.side === 'north') next.depth = point.y - b.y;
    if (edge?.side === 'west') {
      next.x = point.x;
      next.width = b.right - point.x;
    }
    if (edge?.side === 'east') next.width = point.x - b.x;
    return {
      room,
      next
    };
  });
  if (changes.some(c => c.next.width < 1 || c.next.depth < 1)) throw new Error('Moving this wall would make a room smaller than 1 m.');
  for (const {
    room,
    next
  } of changes) transformRoom(floor, room.id, next, thickness);
}
export function splitRoom(floor, roomId, axis = 'x', coordinate) {
  const room = floor.rooms.find(r => r.id === roomId);
  if (!room || room.locked) throw new Error('Select an unlocked room to split.');
  const b = roomBox(room),
    size = axis === 'x' ? b.width : b.depth,
    start = b[axis];
  const cut = coordinate ?? start + size / 2;
  if (cut - start < 1 || start + size - cut < 1) throw new Error('Each resulting room must be at least 1 m wide and deep.');
  const first = clone(room),
    second = clone(room);
  second.id = uid('room');
  first.name = `${room.name || room.type} A`;
  second.name = `${room.name || room.type} B`;
  const dim = axis === 'x' ? 'width' : 'depth';
  first.dimensions[dim] = round(cut - start);
  second.position[axis] = cut;
  second.dimensions[dim] = round(start + size - cut);
  floor.rooms.splice(floor.rooms.indexOf(room), 1, first, second);
  for (const key of ['furniture', 'doors', 'windows']) for (const item of floor[key]) if ((item.room_id || item.roomId) === roomId) {
    item.room_id = item.position[axis] > cut ? second.id : first.id;
    item.roomId = item.room_id;
  }
  for (const opening of [...floor.doors,...floor.windows]) {
    const child=opening.position[axis]>cut?second:first;
    if (opening.connected_room_id===roomId) opening.connected_room_id=child.id;
    if (opening.connected_room_ids) opening.connected_room_ids=opening.connected_room_ids.map(id=>id===roomId?child.id:id);
  }
  rebuildWalls(floor);
  rehostOpenings(floor);
  return [first.id, second.id];
}
export function mergeRooms(floor, ids) {
  const rooms = ids.map(id => floor.rooms.find(r => r.id === id)).filter(Boolean);
  if (rooms.length !== 2 || rooms.some(r => r.locked)) throw new Error('Select exactly two unlocked adjacent rooms.');
  const [a, b] = rooms.map(roomBox),
    x = Math.min(a.x, b.x),
    y = Math.min(a.y, b.y),
    right = Math.max(a.right, b.right),
    top = Math.max(a.top, b.top);
  const adjacent = (Math.abs(a.right - b.x) < EPS || Math.abs(b.right - a.x) < EPS) && Math.abs(a.y - b.y) < EPS && Math.abs(a.depth - b.depth) < EPS || (Math.abs(a.top - b.y) < EPS || Math.abs(b.top - a.y) < EPS) && Math.abs(a.x - b.x) < EPS && Math.abs(a.width - b.width) < EPS;
  if (!adjacent) throw new Error('These rooms must share a full edge and form a rectangle to merge.');
  if (rooms.some(r => /bath|kitchen|garage/.test(r.type)) && rooms[0].type !== rooms[1].type) throw new Error('Wet rooms and garages can only merge with rooms of the same type.');
  const merged = rooms[0];
  const removedWalls = new Set(floor.walls.filter(w => (w.room_ids || w.connected_rooms || []).length > 1 && (w.room_ids || w.connected_rooms).every(id => ids.includes(id))).map(w => w.id));
  if (floor.walls.some(w => removedWalls.has(w.id) && w.locked)) throw new Error('Unlock the shared wall before merging.');
  for (const key of ['doors', 'windows']) floor[key] = floor[key].filter(o => !removedWalls.has(o.wall_id));
  merged.position.x = x;
  merged.position.y = y;
  merged.dimensions.width = right - x;
  merged.dimensions.depth = top - y;
  floor.rooms = floor.rooms.filter(r => r.id !== rooms[1].id);
  for (const key of ['furniture', 'doors', 'windows']) {
    if (key === 'doors') floor.doors = floor.doors.filter(d => !(ids.includes(d.room_id) && ids.includes(d.connected_room_id)));
    for (const item of floor[key]) {
      if (ids.includes(item.room_id)) item.room_id = merged.id;
      if (ids.includes(item.connected_room_id)) item.connected_room_id = merged.id;
      if (item.connected_room_ids) item.connected_room_ids=[...new Set(item.connected_room_ids.map(id=>ids.includes(id)?merged.id:id))];
      if (item.roomId && ids.includes(item.roomId)) item.roomId=merged.id;
    }
  }
  rebuildWalls(floor);
  rehostOpenings(floor);
  return merged.id;
}
export const roomAtPoint = (floor, point) => floor.rooms.find(r => containsPoint(roomBox(r), point));
