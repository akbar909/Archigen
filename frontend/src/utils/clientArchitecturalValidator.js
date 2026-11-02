import { boxesOverlap, distance, projectToSegment, roomBox, rotatedRectangle, polygonsOverlap, containsPoint } from './cadGeometry.js';
import { doorSectors, openingRoomIds, isExteriorOpening } from './wallOpenings.js';
import { furnitureCollisions } from './furnitureCollision.js';
import { inaccessibleRooms } from './spatialGraph.js';
import { doorApproachBox } from './doorClearance.js';
import { MAX_STAIR_RISER, MIN_STAIR_TREAD, STAIR_TYPES, stairAccessBox, stairMetrics } from './stairGeometry.js';

const CIRCULATION_ROOM = /^(stair_lobby|hallway|corridor|foyer|living_room|dining_room)$/;
const boxPolygon = box => [{ x: box.x, y: box.y }, { x: box.right, y: box.y }, { x: box.right, y: box.top }, { x: box.x, y: box.top }];
const blocksStairs = item => !item.ceiling_mounted && !item.wall_mounted && !/rug|carpet|curtain/.test(item.category || item.asset || '');
// Project design standards, mirrored from architectural_schema_v3.py (not a code certification).
export const MIN_ROOM_DIMENSIONS = {
  living_room: [3.6, 3.6],
  bedroom: [3.6, 3.6],
  master_bedroom: [3.8, 3.8],
  guest_room: [2.8, 3],
  kitchen: [3, 3],
  dining_room: [3, 3.2],
  bathroom: [1.5, 2],
  master_bathroom: [1.8, 2.4],
  powder_room: [1.2, 1.4],
  home_office: [2.4, 2.7],
  hallway: [1, 1.5],
  corridor: [1, 2],
  foyer: [1.5, 1.8],
  laundry: [1.5, 1.8],
  garage: [3.2, 4.9],
  balcony: [1.5, 2.4],
  pantry: [1.2, 1.5],
  closet: [1.2, 1.5],
  drawing_room: [3.2, 3.2],
  prayer_room: [2, 2.4],
  storage_room: [1.5, 1.8],
  servant_room: [2.7, 3],
  garden: [2, 2.4],
  terrace: [1.5, 2.4],
  stair_lobby: [2.7, 4]
};
const COMPACT_ROOM_DIMENSIONS = { living_room:[2.8,3], dining_room:[1.8,2], kitchen:[2.4,2.4], bedroom:[2.8,2.8], bathroom:[1.5,2], balcony:[2,1.5], stair_lobby:[4.6,2.6] };
export function validateClientDesign(design) {
  const issues = [],
    ids = new Set();
  for (const [floorIndex, floor] of (design?.floors || []).entries()) {
    const add = (code, type, item, message, severity = 'error') => issues.push({
      code,
      severity,
      floorIndex,
      entity: {
        type,
        id: item.id
      },
      message
    });
    for (const type of ['rooms', 'walls', 'doors', 'windows', 'furniture', 'stairs']) for (const item of floor[type] || []) {
      if (ids.has(item.id)) add('duplicate-id', type.replace(/s$/, ''), item, `Duplicate identifier: ${item.id}.`);
      ids.add(item.id);
    }
    const rooms = floor.rooms || [];
    for (let i = 0; i < rooms.length; i++) {
      const room = rooms[i],
        b = roomBox(room),
        name = room.name || room.type,
        min = (room.layout_profile === 'compact_residential' ? COMPACT_ROOM_DIMENSIONS[room.type] : null) || MIN_ROOM_DIMENSIONS[room.type] || [1, 1];
      if (b.width < min[0] || b.depth < min[1]) add('room-minimum', 'room', room, `${name}: recommended minimum ${min[0]} × ${min[1]} m.`, 'warning');
      const plot = design.site?.plot;
      if (plot && (b.x < 0 || b.y < 0 || b.right > plot.width + .001 || b.top > plot.depth + .001)) add('site-boundary', 'room', room, `${name} extends beyond the plot.`);
      for (let j = i + 1; j < rooms.length; j++) if (boxesOverlap(b, roomBox(rooms[j]))) add('room-overlap', 'room', room, `${name} overlaps ${rooms[j].name || rooms[j].type}.`);
      if (/bedroom|living_room|home_office|guest_room/.test(room.type) && !(floor.windows || []).some(w => (w.room_id || w.roomId) === room.id && floor.walls?.find(a => a.id === w.wall_id)?.type === 'exterior')) add('daylight', 'room', room, `${name} has no exterior window.`, 'warning');
    }
    const openings = [...(floor.doors || []).map(o => ({
      ...o,
      kind: 'door'
    })), ...(floor.windows || []).map(o => ({
      ...o,
      kind: 'window'
    }))];
    for (let i = 0; i < openings.length; i++) {
      const o = openings[i],
        wall = floor.walls?.find(w => w.id === o.wall_id);
      if (!wall || !o.position || projectToSegment(o.position, wall.start, wall.end).distance > .05) add('unhosted', o.kind, o, `${o.kind} ${o.id} is not hosted on a wall.`);else {
        const p = projectToSegment(o.position, wall.start, wall.end);
        if (Math.min(p.t, 1 - p.t) * p.length < Number(o.width) / 2 + .099) add('jamb-clearance', o.kind, o, `${o.kind} ${o.id} needs 0.10 m jamb clearance.`);
      }
      if (!(Number(o.width) > 0) || !(Number(o.height) > 0) || Number(o.height) + Number(o.sill_height || 0) > Number(floor.floor_height || 3)) add('opening-height', o.kind, o, `${o.kind} ${o.id} has invalid dimensions or extends above the ceiling.`);
      if (o.kind === 'door' && o.width < .8) add('door-width', o.kind, o, `Door ${o.id} is narrower than the 0.80 m design target.`, 'warning');
      for (let j = i + 1; j < openings.length; j++) {
        const other = openings[j];
        const sameWall = wall && other.wall_id === wall.id;
        const colocated = wall && other.position && projectToSegment(other.position, wall.start, wall.end).distance < .02;
        if ((sameWall || colocated) && distance(o.position, other.position) < (Number(o.width) + Number(other.width)) / 2 + .1) add('aperture-overlap', o.kind, o, `Openings ${o.id} and ${other.id} overlap or lack spacing.`);
      }
      const intended = openingRoomIds(o);
      if (o.kind === 'door' && isExteriorOpening(o) && wall && (wall.room_ids || wall.connected_rooms || []).length !== 1) {
        add('connection', 'door', o, 'The entrance needs an exterior wall opening to outside.');
      }
      if (o.kind === 'door' && intended.length > 1 && intended.some(id => !(wall?.room_ids || wall?.connected_rooms || []).includes(id))) {
        add('connection', 'door', o, `Door to ${rooms.find(r => r.id === intended.find(id => id !== o.room_id))?.name || 'the next room'} needs a shared wall.`);
      }
      if (o.kind === 'door' && o.connected_room_id && o.connected_room_id !== 'exterior') {
        const room = rooms.find(r => r.id === (o.room_id || o.roomId)),
          other = rooms.find(r => r.id === o.connected_room_id);
        if (!other || !(wall?.room_ids || wall?.connected_rooms || []).includes(other.id)) add('connection', 'door', o, `Door ${o.id} references a room outside its wall.`);
        if (room?.access === 'ensuite_only' && other && !/master_bedroom|hallway|corridor/.test(other.type)) add('privacy', 'door', o, 'An ensuite should connect to the master bedroom or hallway.', 'warning');
      }
    }
    for (const room of inaccessibleRooms(floor)) add('inaccessible', 'room', room, `${room.name || room.type} has no doorway path to the entrance.`, 'warning');
    for (const issue of furnitureCollisions(floor)) issues.push({
      ...issue,
      floorIndex
    });
    if (floorIndex < design.floors.length - 1 && !floor.stairs?.length) add('missing-stair', 'floor', floor, 'This floor has no stair to the next storey.');
    for (const stair of floor.stairs || []) {
      const metrics = stairMetrics(stair, floor.floor_height || stair.dimensions?.height || 3);
      if (!['x', 'y'].includes(stair.run_axis || 'y') || (stair.run_axis === 'x' && metrics.type !== 'u_shaped')) add('stair-type', 'stair', stair, 'Choose a valid direction for this stair configuration.');
      const box = roomBox(stair), polygon = boxPolygon(box);
      if (!STAIR_TYPES.includes(metrics.type)) add('stair-type', 'stair', stair, 'Choose a supported straight, L-shaped or U-shaped stair.');
      if (![metrics.width, metrics.depth, metrics.riserHeight].every(value => Number.isFinite(value) && value > 0)) add('stair-dimensions', 'stair', stair, 'Stair dimensions and storey height must be positive finite numbers.');
      if (Number(stair.rotation || 0) % 360 !== 0) add('stair-rotation', 'stair', stair, 'Stair rotation is not supported by the 3D builder. Use the aligned stair footprint.');
      if (!Number.isInteger(metrics.requestedRisers) || metrics.requestedRisers < 16 || metrics.requestedRisers % 2 || (stair.steps != null && stair.risers != null && Number(stair.steps) !== Number(stair.risers))) add('stair-risers', 'stair', stair, 'Use a matching, even riser count of at least 16 for the stair flights.');
      if (metrics.riserHeight > MAX_STAIR_RISER + .000001) add('stair-rise', 'stair', stair, `The ${Math.round(metrics.riserHeight * 100)} cm risers exceed the 19 cm design target. Add risers and increase the footprint.`);
      if (!Number.isFinite(Number(stair.headroom ?? 2.1)) || Number(stair.headroom ?? 2.1) < 2) add('stair-headroom', 'stair', stair, 'Stairs need at least 2.00 m clear headroom.');
      if (!Number.isFinite(metrics.clearWidth) || metrics.clearWidth < .9 || Number(stair.clear_width ?? metrics.clearWidth) > metrics.availableWidth + .000001) add('stair-width', 'stair', stair, 'The stair footprint must provide the specified clear width, at least 0.90 m per flight.');
      if (!Number.isFinite(metrics.landingDepth) || metrics.landingDepth + .000001 < Math.max(.9, metrics.requestedClearWidth)) add('stair-landing', 'stair', stair, 'Make the stair landing at least as deep as the clear flight width (minimum 0.90 m).');
      if (stair.access_depth != null && (!Number.isFinite(Number(stair.access_depth)) || Number(stair.access_depth) + .000001 < metrics.clearWidth)) add('stair-access', 'stair', stair, 'Make the stair approach at least as deep as the clear flight width.');
      if (!Number.isFinite(metrics.tread) || metrics.tread < MIN_STAIR_TREAD - .000001) add('stair-tread', 'stair', stair, `The stair run is too short. Allow at least 25 cm per tread; this footprint needs at least ${metrics.acrossPlot ? `${metrics.minimumWidth.toFixed(2)} m width` : `${metrics.minimumDepth.toFixed(2)} m depth`}${metrics.type === 'l_shaped' ? ` and ${metrics.minimumWidth.toFixed(2)} m width` : ''}.`);
      if(!(floor.rooms||[]).some(r=>polygon.every(p=>containsPoint(roomBox(r),p)))) add('stair-boundary','stair',stair,'Keep the stair inside a room or stair lobby.');
      for(const door of floor.doors||[]) if(!/sliding|garage/.test(door.type||'')&&doorSectors(door).some(sector=>polygonsOverlap(polygon,sector))) add('stair-door','stair',stair,'Move the stair clear of the door swing.');
      for (const door of floor.doors || []) if ((floor.rooms || []).some(room => {
        const approach = doorApproachBox(door, room, floor, { sideAllowance: 0 });
        return approach && boxesOverlap(box, approach);
      })) add('stair-door-approach', 'stair', stair, 'Move the stair clear of the doorway approach.');
      for (const item of floor.furniture || []) if (blocksStairs(item) && polygonsOverlap(polygon,rotatedRectangle(item))) add('stair-furniture','stair',stair,`Move ${item.name || 'furniture'} out of the stair area.`);
      const upper = design.floors[floorIndex + 1],
        opening = upper?.stair_openings?.find(o => o.serves_stair_id === stair.id);
      if (!upper || !opening) add('missing-shaft', 'stair', stair, 'Stair has no matching upper-floor opening.');else {
        const b = roomBox(opening),
          s = roomBox(stair);
        if (Math.abs(b.x - s.x) > .05 || Math.abs(b.y - s.y) > .05 || b.width < s.width || b.depth < s.depth) add('shaft-alignment', 'stair', stair, 'Stair and upper-floor opening are misaligned.');
        for (const room of upper.rooms || []) if (!CIRCULATION_ROOM.test(room.type) && boxesOverlap(b, roomBox(room))) add('shaft-room', 'stair', stair, `Upper-floor ${room.name || room.type} covers the stair shaft. Reserve a stair lobby with independent access.`);
        const openingPolygon = boxPolygon(b);
        for (const door of upper.doors || []) {
          if (!/sliding|garage/.test(door.type || '') && doorSectors(door).some(sector => polygonsOverlap(openingPolygon, sector))) add('shaft-door', 'stair', stair, 'Keep the upper-floor door swing clear of the stair opening.');
          if ((upper.rooms || []).some(room => {
            const approach = doorApproachBox(door, room, upper, { sideAllowance: 0 });
            return approach && boxesOverlap(b, approach);
          })) add('shaft-door-approach', 'stair', stair, 'Keep the upper-floor doorway approach clear of the stair opening.');
        }
        for (const wall of upper.walls || []) {
          const mid = {
            x: (wall.start.x + wall.end.x) / 2,
            y: (wall.start.y + wall.end.y) / 2
          };
          if (mid.x > b.x + .05 && mid.x < b.right - .05 && mid.y > b.y + .05 && mid.y < b.top - .05) add('shaft-wall', 'stair', stair, 'An upper-floor wall crosses the stair shaft.');
        }
      }
      for (const [accessFloor, destination] of Number(stair.access_depth) > 0 ? [[floor, false], ...(upper ? [[upper, true]] : [])] : []) {
        const access = stairAccessBox(stair, destination), accessPolygon = boxPolygon(access), level = destination ? 'upper' : 'lower';
        if (!(accessFloor.rooms || []).some(room => CIRCULATION_ROOM.test(room.type) && accessPolygon.every(point => containsPoint(roomBox(room), point)))) add('stair-access', 'stair', stair, `Provide a clear ${metrics.clearWidth.toFixed(2)} m ${level}-floor stair approach from a lounge, hallway or stair lobby.`);
        for (const item of accessFloor.furniture || []) if (blocksStairs(item) && polygonsOverlap(accessPolygon, rotatedRectangle(item))) add('stair-access-furniture', 'stair', stair, `Move ${item.name || item.category || 'furniture'} out of the ${level}-floor stair approach.`);
        if ((accessFloor.doors || []).some(door => !/sliding|garage/.test(door.type || '') && doorSectors(door).some(sector => polygonsOverlap(accessPolygon, sector)))) add('stair-access-door', 'stair', stair, `Keep door swings clear of the ${level}-floor stair approach.`);
      }
    }
  }
  return issues;
}
