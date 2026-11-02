import { roomBox } from './cadGeometry.js';
import { openingRoomIds } from './wallOpenings.js';

// The same 1.15 m approach and 0.35 m side allowance used by backend/Blender.
export function doorApproachBox(door, room, floor, { sideAllowance = .35 } = {}) {
  if (!door.position || /garage/.test(door.type || '') || door.swing === 'overhead') return null;
  const b = roomBox(room), p = door.position;
  if (Math.abs(Number(p.z || 0) - Number(room.position?.z || floor.elevation || 0)) > .35) return null;
  const sides = [[Math.abs(p.y-b.y),'south'],[Math.abs(p.y-b.top),'north'],[Math.abs(p.x-b.x),'west'],[Math.abs(p.x-b.right),'east']].sort((a,c)=>a[0]-c[0]);
  const onBoundary = p.x >= b.x-.3 && p.x <= b.right+.3 && p.y >= b.y-.3 && p.y <= b.top+.3 && sides[0][0] <= .35;
  if (!openingRoomIds(door).includes(room.id) && !onBoundary) return null;
  const side = sides[0][1], half = Number(door.width || .9)/2+sideAllowance, depth = 1.15;
  const box = side==='south' ? {x:p.x-half,y:b.y,right:p.x+half,top:Math.min(b.top,b.y+depth)} :
    side==='north' ? {x:p.x-half,y:Math.max(b.y,b.top-depth),right:p.x+half,top:b.top} :
    side==='west' ? {x:b.x,y:p.y-half,right:Math.min(b.right,b.x+depth),top:p.y+half} :
    {x:Math.max(b.x,b.right-depth),y:p.y-half,right:b.right,top:p.y+half};
  return {x:Math.max(b.x,box.x), y:Math.max(b.y,box.y), right:Math.min(b.right,box.right), top:Math.min(b.top,box.top)};
}

export function itemOverlapsDoorHeight(item, door, room, floor) {
  const base = Number(room.position?.z || floor.elevation || 0), height = Number(item.dimensions?.height || 0);
  const bottom = item.ceiling_mounted ? base+Number(room.dimensions?.height || floor.floor_height || 3)-height-Number(item.ceiling_clearance ?? .06) :
    Number(item.position?.z ?? base) + Number(item.mount_height || 0);
  const doorBase = Number(door.position?.z ?? base);
  return bottom < doorBase+Number(door.height || 2.1) && bottom+height > doorBase;
}
