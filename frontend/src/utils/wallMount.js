const NORMALS = { front: [0, 0, 1], back: [0, 0, -1], left: [1, 0, 0], right: [-1, 0, 0] }

export function wallMountNormal(side, normal) {
  const length = Math.hypot(Number(normal?.x) || 0, Number(normal?.z) || 0)
  if (length > 0.01) return { x: normal.x / length, y: 0, z: normal.z / length }
  const vector = NORMALS[side]
  return vector ? { x: vector[0], y: 0, z: vector[2] } : null
}

export function wallMountRotation(side, normal, fallback = 0) {
  const inward = wallMountNormal(side, normal)
  if (!inward) return Number(fallback) || 0
  return ((-Math.atan2(inward.x, inward.z) * 180 / Math.PI) % 360 + 360) % 360
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
