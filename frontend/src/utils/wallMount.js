const NORMALS = { front: [0, 0, 1], back: [0, 0, -1], left: [1, 0, 0], right: [-1, 0, 0] }

export function wallMountNormal(side, normal) {
  const length = Math.hypot(Number(normal?.x) || 0, Number(normal?.z) || 0)
  if (length > 0.01) return { x: normal.x / length, y: 0, z: normal.z / length }
  const vector = NORMALS[side]
  return vector ? { x: vector[0], y: 0, z: vector[2] } : null
}

export function interiorWallMountNormal(side, normal) {
  const expected = wallMountNormal(side)
  const candidate = wallMountNormal(side, normal)
  if (!expected || !candidate) return candidate
  // Imported window backs and double-sided wall faces can have outward normals.
  return candidate.x * expected.x + candidate.z * expected.z < 0
    ? { x: -candidate.x, y: 0, z: -candidate.z } : candidate
}

// A facade and the room behind it share a wall ID, but use opposite faces.
// Also recover older placements whose hit anchor was saved on the outside.
export function mountedWallFace(item, room) {
  if (item.wall_face) return item.wall_face
  if (item.room_id === 'exterior_ground' || room?.id === 'exterior_ground') return 'exterior'
  const anchor = item.wall_anchor, p = room?.position || room?.bounds, d = room?.dimensions || room?.bounds
  if (!anchor || !p || !d) return 'interior'
  const outside = { left: Number(p.x) - anchor.x, right: anchor.x - Number(p.x) - Number(d.width),
    back: Number(p.y) - anchor.y, front: anchor.y - Number(p.y) - Number(d.depth) }[item.wall_side]
  return outside > 0.03 ? 'exterior' : 'interior'
}

export function mountedWallNormal(item, room) {
  const inward = interiorWallMountNormal(item.wall_side, item.wall_normal)
  return mountedWallFace(item, room) === 'exterior' && room?.id !== 'exterior_ground' && item.room_id !== 'exterior_ground'
    ? inward && { x: -inward.x, y: 0, z: -inward.z }
    : room?.id === 'exterior_ground' || item.room_id === 'exterior_ground'
      ? wallMountNormal(item.wall_side, item.wall_normal) : inward
}

export function wallMountRotation(side, normal, fallback = 0) {
  const inward = wallMountNormal(side, normal)
  if (!inward) return Number(fallback) || 0
  return ((Math.atan2(inward.x, inward.z) * 180 / Math.PI) % 360 + 360) % 360
}

export function assetYawOffset(item) {
  const mounting = item.mounting
  if (mounting?.orientation_verified && mounting.up_axis === '+y') {
    return ({ '+z': 0, '-z': 180, '+x': -90, '-x': 90 })[mounting.front_axis] ?? (Number(item.canonical_yaw_offset_deg) || 0)
  }
  return Number(item.canonical_yaw_offset_deg) || 0
}

export function snapToWallPlane(position, item) {
  const n = wallMountNormal(item.wall_side, item.wall_normal)
  const anchor = item.wall_anchor
  if (!n || !anchor || !Number.isFinite(anchor.x) || !Number.isFinite(anchor.y)) return position
  const offset = (Number(item.dimensions?.depth) || 0.08) / 2 + 0.012
  const distance = (position.x - anchor.x) * n.x - (position.y - anchor.y) * n.z
  return { ...position, x: position.x + n.x * (offset - distance), y: position.y - n.z * (offset - distance) }
}
