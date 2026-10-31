import { clone, containsPoint, roomBox, rotatedRectangle, uid } from './cadGeometry.js';
import { hostOpening } from './wallOpenings.js';
import { normalizeEditorDesign, rebuildWalls, rehostOpenings, roomAtPoint, syncLegacyAliases } from './roomEditing.js';
import { synchronizeStairs } from './verticalCirculation.js';
export const collectionFor = type => ({
  room: 'rooms',
  wall: 'walls',
  door: 'doors',
  window: 'windows',
  furniture: 'furniture',
  stair: 'stairs',
  floor: null
})[type];
export function getEntity(floor, selection) {
  return selection?.type === 'floor' ? floor : (floor?.[collectionFor(selection?.type)] || []).find(item => item.id === selection?.id);
}
export function editDesign(design, floorIndex, mutate) {
  const next = normalizeEditorDesign(design);
  mutate(next.floors[floorIndex], next);
  synchronizeStairs(next);
  return syncLegacyAliases(next);
}
export function deleteEntities(floor, design, selections) {
  for (const selection of selections) {
    const key = collectionFor(selection.type),
      entity = getEntity(floor, selection);
    if (!entity || entity.locked) throw new Error('Unlock the selection before deleting it.');
    if (selection.type === 'wall') throw new Error('Walls define room boundaries. Merge adjacent rooms to remove a partition.');
    if (selection.type === 'room') {
      if (floor.rooms.length <= 1) throw new Error('Keep at least one room on each floor.');
      const assets = floor.furniture.filter(i => (i.room_id || i.roomId) === entity.id);
      design.deleted_furniture_ids = [...new Set([...(design.deleted_furniture_ids || []), ...assets.map(i => i.id)])];
      floor.furniture = floor.furniture.filter(i => !assets.includes(i));
      for (const openingKey of ['doors', 'windows']) floor[openingKey] = floor[openingKey].filter(o => (o.room_id || o.roomId) !== entity.id && o.connected_room_id !== entity.id);
    }
    if (selection.type === 'furniture') design.deleted_furniture_ids = [...new Set([...(design.deleted_furniture_ids || []), entity.id])];
    floor[key] = floor[key].filter(i => i.id !== selection.id);
  }
  if (selections.some(s => s.type === 'room')) {
    rebuildWalls(floor, design.building?.wall_thickness);
    rehostOpenings(floor);
  }
}
export function moveFurniture(floor, selections, delta) {
  for (const selected of selections.filter(s => s.type === 'furniture')) {
    const entity = getEntity(floor, selected);
    if (!entity || entity.locked) throw new Error('An item in the selection is locked.');
    entity.position.x += delta.x;
    entity.position.y += delta.y;
    const polygon = rotatedRectangle(entity);
    const room = floor.rooms.find(r => polygon.every(p => containsPoint(roomBox(r), p))) || roomAtPoint(floor, entity.position);
    if (room) entity.room_id = room.id;
    entity.client_edited_3d = true;
    entity.placement_hint = 'user_exact';
  }
}
export function addFurniture(floor, asset, point) {
  const room = roomAtPoint(floor, point);
  if (!room) throw new Error('Place furniture inside a room.');
  const item = {
    ...clone(asset),
    id: uid('furniture'),
    asset_id: asset.asset_id || asset.id,
    asset: asset.asset || asset.category || 'furniture',
    room_id: room.id,
    position: {
      ...point,
      z: floor.elevation || 0
    },
    dimensions: {
      width: 1,
      depth: 1,
      height: .8,
      ...asset.dimensions
    },
    rotation: 0,
    client_edited_3d: true,
    placement_hint: 'user_exact',
    locked: false
  };
  delete item.group_id;
  floor.furniture.push(item);
  return item;
}
export function arrayWindows(floor, id, count) {
  const original = floor.windows.find(w => w.id === id),
    wall = floor.walls.find(w => w.id === original?.wall_id);
  if (!wall || count < 2 || count > 12) throw new Error('Select a hosted window and choose 2–12 windows.');
  const length = Math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y);
  if (count * original.width + (count + 1) * .1 > length) throw new Error('These windows do not fit on this wall.');
  const gap = (length - count * original.width) / (count + 1);
  const others = [...floor.doors, ...floor.windows.filter(w => w.id !== id)].filter(o => o.wall_id === wall.id);
  if (others.length) throw new Error('Use a wall without other openings for an equal-spaced array.');
  floor.windows = floor.windows.filter(w => w.id !== id);
  for (let i = 0; i < count; i++) {
    const t = (gap + original.width / 2 + i * (gap + original.width)) / length;
    floor.windows.push(hostOpening(floor, {
      ...clone(original),
      id: i === 0 ? original.id : uid('window')
    }, {
      x: wall.start.x + (wall.end.x - wall.start.x) * t,
      y: wall.start.y + (wall.end.y - wall.start.y) * t
    }, {
      transfer: false
    }));
  }
}
export function alignFurniture(floor, ids, alignment) {
  const items = ids.map(id => floor.furniture.find(i => i.id === id)).filter(Boolean);
  if (items.length < 2 || items.some(i => i.locked)) throw new Error('Select at least two unlocked furniture items.');
  const bounds = items.map(i => {
    const points = rotatedRectangle(i);
    return {
      item: i,
      left: Math.min(...points.map(p => p.x)),
      right: Math.max(...points.map(p => p.x))
    };
  });
  const left = Math.min(...bounds.map(b => b.left)),
    right = Math.max(...bounds.map(b => b.right));
  if (alignment === 'distribute') {
    if (items.length < 3) throw new Error('Select at least three items to distribute.');
    bounds.sort((a, b) => a.left - b.left);
    const gap = (right - left - bounds.reduce((sum, b) => sum + b.right - b.left, 0)) / (bounds.length - 1);
    let cursor = left;
    for (const b of bounds) {
      b.item.position.x += cursor - b.left;
      cursor += b.right - b.left + gap;
    }
  } else for (const b of bounds) b.item.position.x += alignment === 'left' ? left - b.left : alignment === 'right' ? right - b.right : (left + right - b.left - b.right) / 2;
  items.forEach(i => {
    i.client_edited_3d = true;
  });
}
