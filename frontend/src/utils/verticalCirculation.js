import { clamp, clone, containsPoint, roomBox, round, uid } from './cadGeometry.js';
export function createStairPlacement(floor, point, type='u_shaped') {
  const presets={u_shaped:[2.2,3.8],straight:[1.1,5.9],l_shaped:[3.8,3.8]};
  const [width,depth]=presets[type] || presets.u_shaped;
  const room=(floor.rooms||[]).find(r=>containsPoint(roomBox(r),point));
  if (!room) throw new Error('Place stairs inside a room or stair lobby.');
  const box=roomBox(room),margin=.12;
  if (box.width<width+margin*2 || box.depth<depth+margin*2) throw new Error(`Choose a larger space: this stair needs ${width} × ${depth} m.`);
  return {id:uid('stair'),type,room_id:room.id,position:{x:round(clamp(point.x-width/2,box.x+margin,box.right-width-margin)),y:round(clamp(point.y-depth/2,box.y+margin,box.top-depth-margin)),z:floor.elevation||0},dimensions:{width,depth,height:floor.floor_height||3},direction:'up',headroom:2.1,clear_width:type==='u_shaped'?(width-.16)/2:Math.min(width,1.1),steps:18};
}
export function synchronizeStairs(design) {
  const floors = design.floors;
  let elevation = 0;
  floors.forEach((floor, index) => {
    const previous = Number(floor.elevation) || 0,
      dz = elevation - previous;
    floor.level = index;
    floor.elevation = round(elevation);
    for (const key of ['rooms', 'furniture', 'doors', 'windows', 'stairs']) for (const entity of floor[key] || []) {
      if (entity.position) entity.position.z = round((Number(entity.position.z) || 0) + dz);
    }
    elevation += Number(floor.floor_height || 3);
    // Keep imported voids; replace only voids owned by the editor's synchronization.
    floor.stair_openings = (floor.stair_openings || []).filter(o => !o.editor_managed && (!o.serves_stair_id || (floors[index - 1]?.stairs || []).some(s => s.id === o.serves_stair_id)));
  });
  floors.forEach((floor, index) => {
    const upper = floors[index + 1];
    for (const stair of floor.stairs || []) {
      if (!upper) {
        stair.target_floor_id = null;
        stair.connects = {
          lower_floor: floor.id,
          upper_floor: null
        };
        continue;
      }
      stair.target_floor_id = upper.id;
      stair.connects = {
        lower_floor: floor.id,
        upper_floor: upper.id
      };
      stair.floor_level = index;
      stair.dimensions.height = floor.floor_height;
      stair.steps = Math.ceil(floor.floor_height / .175 / 2) * 2;
      stair.risers = stair.steps;
      stair.headroom = 2.1;
      stair.clear_width = stair.type === 'u_shaped' ? (stair.dimensions.width - .16) / 2 : Math.min(stair.dimensions.width, 1.1);
      const existing = upper.stair_openings.find(o => o.serves_stair_id === stair.id);
      const opening = {
        id: existing?.id || stair.landing_opening_id || uid('shaft'),
        type: 'stair_void',
        editor_managed: true,
        serves_stair_id: stair.id,
        position: {
          ...stair.position,
          z: upper.elevation
        },
        dimensions: {
          ...stair.dimensions,
          height: upper.slab_thickness || .2
        }
      };
      stair.landing_opening_id = opening.id;
      if (existing) Object.assign(existing, opening);else upper.stair_openings.push(opening);
    }
  });
  for (const floor of floors) if (floor.stair_core) {
    const stair = floor.stairs?.[0],
      opening = floor.stair_openings?.[0],
      reference = stair || opening;
    if (reference) {
      floor.stair_core.position = clone(reference.position);
      floor.stair_core.dimensions = clone(reference.dimensions);
    } else delete floor.stair_core;
  }
  if (design.building) design.building.floors = floors.length;
  if (design.roof) design.roof.elevation = round(elevation);
  return design;
}
export function duplicateFloor(design, index) {
  if (design.floors.length >= 4) throw new Error('The architectural schema supports up to four floors.');
  const floor = clone(design.floors[index]),
    ids = new Map();
  floor.id = uid('floor');
  ids.set(design.floors[index].id, floor.id);
  floor.name = 'Copied floor';
  for (const key of ['rooms', 'walls', 'doors', 'windows', 'furniture', 'stairs', 'stair_openings']) for (const item of floor[key] || []) ids.set(item.id, uid(key.slice(0, -1)));
  for (const item of floor.furniture || []) if (item.group_id && !ids.has(item.group_id)) ids.set(item.group_id, uid('group'));
  const referenceKeys = new Set(['id', 'room_id', 'roomId', 'wall_id', 'connected_room_id', 'connected_room_ids', 'connected_rooms', 'room_ids', 'floor_id', 'serves_stair_id', 'target_floor_id', 'landing_opening_id', 'support_id', 'group_id']);
  function rewrite(value, key = '') {
    if (Array.isArray(value)) return value.map(item => rewrite(item, key));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, rewrite(v, k)]));
    return referenceKeys.has(key) && typeof value === 'string' && ids.has(value) ? ids.get(value) : value;
  }
  const copied = rewrite(floor);
  copied.stairs = [];
  copied.stair_openings = [];
  delete copied.stair_core;
  design.floors.splice(index + 1, 0, copied);
  return synchronizeStairs(design);
}
