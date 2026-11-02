import { stairMetrics, STAIR_GAP } from './stairGeometry.js'

const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
const inside = (x, y, x0, y0, w, d) => x >= x0 - 1e-5 && y >= y0 - 1e-5 && x <= x0 + w + 1e-5 && y <= y0 + d + 1e-5

export function navigationStairs(floors, rooms, stairs = []) {
  const floorStairs = floors.flatMap(f => (f.stairs || []).map(s => ({ ...s, floor_level: s.floor_level ?? f.level })))
  const definitions = floorStairs.length ? floorStairs : stairs
  return definitions.flatMap(stair => {
    if (stair.type === 'stair_void') return []
    const lowerLevel = Number(stair.floor_level ?? 0), upperLevel = lowerLevel + 1
    const lowerRoom = rooms.find(r => r.level === lowerLevel && String(r.id) === String(stair.room_id)) || rooms.find(r => r.level === lowerLevel)
    const upperRoom = rooms.find(r => r.level === upperLevel)
    if (!lowerRoom || !upperRoom) return []
    const lowerY = Number(lowerRoom.y) || 0, upperY = Number(upperRoom.y) || upperLevel * 3
    const m = stairMetrics(stair, upperY - lowerY)
    if (![m.width, m.depth, m.tread].every(v => Number.isFinite(v) && v > 0)) return []
    const upperFloor = floors.find(f => Number(f.level) === upperLevel)
    const opening = (upperFloor?.stair_openings || upperFloor?.openings || []).find(o => o.serves_stair_id === stair.id || o.stair_id === stair.id)
    return [{ ...stair, m, lowerLevel, upperLevel, lowerY, upperY, opening }]
  })
}

function localPoint(stair, x, z, sign) {
  const px = x - Number(stair.position?.x || 0), py = z * sign - Number(stair.position?.y || 0)
  return stair.m.acrossPlot ? { u: py, v: stair.m.width - px } : { u: px, v: py }
}

function localHeight(s, u, v) {
  const m = s.m, w = m.localWidth, d = m.localDepth, run = d - m.landingDepth
  const rise = s.upperY - s.lowerY
  // Small endpoint extensions bridge the slab cutout clearance, without
  // turning the whole void into a walkable floor.
  const bridge = Math.max(0.12, Number(s.opening_clearance) || 0)
  if (m.type === 'straight') {
    if (inside(u, v, 0, -bridge, w, d + 2 * bridge)) return s.lowerY + rise * clamp(v / run, 0, 1)
  } else if (m.type === 'l_shaped') {
    if (inside(u, v, 0, run, m.landingDepth, m.landingDepth)) return s.lowerY + rise / 2
    if (inside(u, v, 0, -bridge, m.clearWidth, run + bridge)) return s.lowerY + rise / 2 * clamp(v / run, 0, 1)
    if (inside(u, v, m.landingDepth, d - m.clearWidth, w - m.landingDepth + bridge, m.clearWidth))
      return s.lowerY + rise / 2 * (1 + clamp((u - m.landingDepth) / (w - m.landingDepth), 0, 1))
  } else if (m.type === 'u_shaped') {
    const fw = (w - STAIR_GAP) / 2
    if (inside(u, v, 0, run, w, m.landingDepth)) return s.lowerY + rise / 2
    if (inside(u, v, 0, -bridge, fw, run + bridge)) return s.lowerY + rise / 2 * clamp(v / run, 0, 1)
    if (inside(u, v, fw + STAIR_GAP, -bridge, fw, run + bridge)) return s.upperY - rise / 2 * clamp(v / run, 0, 1)
  }
  return null
}

export function stairSurface(s, x, z, sign, radius = 0) {
  const { u, v } = localPoint(s, x, z, sign)
  const y = localHeight(s, u, v)
  if (y == null) return null
  // Keep the body between the rails. At endpoints the adjacent floor supplies
  // support; at the turn both flights connect through the real landing.
  if (radius && [[radius, 0], [-radius, 0], [0, radius], [0, -radius]].some(([du, dv]) => {
    const sample = localHeight(s, u + du, v + dv)
    if (sample != null) return Math.abs(sample - y) > 0.55
    const end = v < radius + 0.02 || (s.m.type === 'straight' && v > s.m.localDepth - radius - 0.02)
      || (s.m.type === 'l_shaped' && u > s.m.localWidth - radius - 0.02)
    return !end || du !== 0 && s.m.type !== 'l_shaped'
  })) return null
  return { x, z, y, level: y >= s.upperY - 0.02 ? s.upperLevel : s.lowerLevel, stairId: s.id }
}

export function inStairFootprint(stair, x, z, sign, opening = false) {
  const item = opening && stair.opening ? stair.opening : stair
  const p = item.position || {}, d = item.dimensions || {}
  return inside(x, z * sign, Number(p.x || 0), Number(p.y || 0), Number(d.width), Number(d.depth))
}
