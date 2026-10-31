import { boxesOverlap, containsPoint, polygonBounds, polygonsOverlap, roomBox, rotatedRectangle, SpatialHash } from './cadGeometry.js';
import { doorSectors } from './wallOpenings.js';
export function furnitureCollisions(floor) {
  const issues = [],
    items = floor.furniture || [],
    footprints = new Map(items.map(i => [i.id, rotatedRectangle(i)]));
  const spatial = new SpatialHash();
  items.forEach((item,index) => spatial.insert(index, polygonBounds(rotatedRectangle(item, .6))));
  const nonBlocking = item => item.ceiling_mounted || item.wall_mounted || /rug|carpet|curtain/.test(item.category || item.asset || '');
  const add = (code, item, message, severity = 'error', other) => issues.push({
    code,
    severity,
    entity: {
      type: 'furniture',
      id: item.id
    },
    message,
    relatedId: other?.id
  });
  for (let i = 0; i < items.length; i++) {
    const item = items[i],
      polygon = footprints.get(item.id),
      room = floor.rooms.find(r => r.id === (item.room_id || item.roomId));
    if (!room || polygon.some(p => !containsPoint(roomBox(room), p))) add('outside-room', item, `${item.name || item.category || 'Furniture'} extends outside its room.`);
    for (const j of spatial.query(polygonBounds(polygon))) {
      if (j <= i) continue;
      const other = items[j];
      if (item.support_id === other.id || other.support_id === item.id || nonBlocking(item) || nonBlocking(other)) continue;
      const z1 = Number(item.position?.z) || 0,
        z2 = Number(other.position?.z) || 0;
      if (z1 + Number(item.dimensions?.height || 1) <= z2 || z2 + Number(other.dimensions?.height || 1) <= z1) continue;
      if (polygonsOverlap(polygon, footprints.get(other.id))) add('furniture-overlap', item, `${item.name || item.category || 'Furniture'} overlaps ${other.name || other.category || 'furniture'}.`, 'error', other);else if (/bed|table/.test(item.category || item.asset || '') && polygonsOverlap(rotatedRectangle(item, .3), rotatedRectangle(other, .3))) add('clearance', item, `Allow 0.60 m walking space near ${item.name || item.category}.`, 'warning', other);
    }
    if (nonBlocking(item)) continue;
    for (const door of floor.doors || []) {
      if (/sliding|garage/.test(door.type || '')) continue;
      if (doorSectors(door).some(sector => polygonsOverlap(polygon, sector))) add('door-swing', item, `${item.name || item.category || 'Furniture'} blocks door ${door.id}'s swing.`, 'error', door);
    }
    for (const opening of floor.stair_openings || []) if (boxesOverlap(polygonBounds(polygon), roomBox(opening))) add('blocked-shaft', item, `${item.name || item.category || 'Furniture'} blocks a stair opening.`);
  }
  return issues;
}
