// World-space collision model shared by the walkthrough and its camera guard.
export const WALK_SPEED = 2.6
export const WALK_RADIUS = 0.24
export const LOOK_SENSITIVITY = 0.0018
const EPS = 1e-5

export function normalizeNavigationDoors({ doors = [], detected = [], rooms = [], zSign = -1, floorHeight = 3 }) {
  const result = new Map()
  const add = (door, world = false, room = null) => {
    const p = door.position || {}
    const legacyLocal = room && !door.room_id && !door.roomId && !door.wall_id && !door.wall_side
    const rp = room?.position || room?.bounds || {}, rd = room?.dimensions || room?.bounds || {}
    const x = world ? Number(door.worldX) : Number(p.x ?? p[0]) + (legacyLocal ? (Number(rp.x) || 0) + (Number(rd.width) || 4) / 2 : 0)
    const z = world ? Number(door.worldZ) : (Number(p.y ?? p.z ?? p[1]) + (legacyLocal ? (Number(rp.y) || 0) + (Number(rd.depth) || 4) / 2 : 0)) * zSign
    if (!Number.isFinite(x) || !Number.isFinite(z)) return
    const side = String(door.wall_side || door.side || '').toLowerCase()
    const axis = door.axis || (['left', 'right', 'east', 'west'].includes(side) ? 'z'
      : ['front', 'back', 'north', 'south'].includes(side) ? 'x' : null)
    const level = Number(door.floor_level ?? door.floorLevel ?? door.floor ?? room?.floor_level
      ?? Math.floor((Number(p.z) || 0) / floorHeight + 0.01))
    const id = String(door.id || `${level}:${x.toFixed(3)}:${z.toFixed(3)}`)
    if (!result.has(id)) result.set(id, { id, worldX: x, worldZ: z, axis, floorLevel: level,
      width: Number(door.width ?? door.dimensions?.width ?? door.dimensions?.w) || 0.9 })
  }
  doors.forEach((door) => add(door))
  rooms.forEach((room) => (room.doors || []).forEach((door) => add(door, false, room)))
  detected.forEach((door) => add(door, true))
  return [...result.values()]
}

export function createNavigationModel({ rooms = [], doors = [], walls = [], zSign = -1, wallThickness = 0.2,
  exteriorAccess = () => false, radius = WALK_RADIUS }) {
  const lines = []
  walls.forEach((wall) => {
    const start = wall.start || wall.from, end = wall.end || wall.to
    if (!start || !end) return
    const ax = Number(start.x), az = Number(start.y) * zSign
    const bx = Number(end.x), bz = Number(end.y) * zSign
    if (![ax, az, bx, bz].every(Number.isFinite)) return
    const axis = Math.abs(bx - ax) >= Math.abs(bz - az) ? 'x' : 'z'
    lines.push({ axis, fixed: axis === 'x' ? (az + bz) / 2 : (ax + bx) / 2,
      min: Math.min(axis === 'x' ? ax : az, axis === 'x' ? bx : bz),
      max: Math.max(axis === 'x' ? ax : az, axis === 'x' ? bx : bz),
      thickness: Number(wall.thickness) || wallThickness, level: Number(wall.floor_level ?? wall.floorLevel ?? 0) })
  })
  // Older GLBs have no canonical walls. Their detected floor footprints still
  // provide solid boundaries; only real door apertures may connect them.
  const levels = new Set(lines.map((line) => line.level))
  rooms.forEach((room) => {
    if (levels.has(Number(room.level))) return
    const x0 = room.x - room.w / 2, x1 = room.x + room.w / 2
    const z0 = room.z - room.l / 2, z1 = room.z + room.l / 2
    lines.push(
      { axis: 'x', fixed: z0, min: x0, max: x1, thickness: wallThickness, level: Number(room.level) },
      { axis: 'x', fixed: z1, min: x0, max: x1, thickness: wallThickness, level: Number(room.level) },
      { axis: 'z', fixed: x0, min: z0, max: z1, thickness: wallThickness, level: Number(room.level) },
      { axis: 'z', fixed: x1, min: z0, max: z1, thickness: wallThickness, level: Number(room.level) },
    )
  })
  const segments = []
  const passages = []
  lines.forEach((line) => {
    const apertures = doors.filter((door) => Number(door.floorLevel) === line.level
      && (!door.axis || door.axis === line.axis)
      && Math.abs((line.axis === 'x' ? door.worldZ : door.worldX) - line.fixed) <= line.thickness / 2 + 0.12)
      .map((door) => {
        const center = line.axis === 'x' ? door.worldX : door.worldZ
        return { min: Math.max(line.min, center - door.width / 2), max: Math.min(line.max, center + door.width / 2) }
      }).filter((door) => door.max > door.min).sort((a, b) => a.min - b.min)
    let cursor = line.min
    apertures.forEach((opening) => {
      if (opening.min > cursor) segments.push({ ...line, min: cursor, max: opening.min })
      passages.push({ ...line, ...opening })
      cursor = Math.max(cursor, opening.max)
    })
    if (cursor < line.max) segments.push({ ...line, min: cursor })
  })
  return { rooms, doors, segments, passages, radius, wallThickness, exteriorAccess }
}

export function isWalkablePoint(model, x, z, level) {
  if (!Number.isFinite(x) || !Number.isFinite(z)) return false
  const insideRoom = model.rooms.some((room) => Number(room.level) === Number(level)
    && Math.abs(x - room.x) <= room.w / 2 + EPS && Math.abs(z - room.z) <= room.l / 2 + EPS)
  const insidePassage = model.passages.some((door) => door.level === Number(level)
    && Math.abs((door.axis === 'x' ? z : x) - door.fixed) <= door.thickness / 2 + model.radius + 0.12
    && (door.axis === 'x' ? x : z) >= door.min + model.radius - EPS
    && (door.axis === 'x' ? x : z) <= door.max - model.radius + EPS)
  if (!insideRoom && !insidePassage && !(Number(level) === 0 && model.exteriorAccess(x, z, -model.radius))) return false
  return !model.segments.some((wall) => {
    if (wall.level !== Number(level)) return false
    const tangent = wall.axis === 'x' ? x : z
    const normal = wall.axis === 'x' ? z : x
    const dx = Math.max(wall.min - tangent, 0, tangent - wall.max)
    const dz = Math.max(0, Math.abs(normal - wall.fixed) - wall.thickness / 2)
    return dx * dx + dz * dz < (model.radius - EPS) ** 2
  })
}

export function nearestWalkablePoint(model, x, z, level) {
  if (isWalkablePoint(model, x, z, level)) return { x, z }
  const margin = model.radius + model.wallThickness / 2 + 0.02
  const candidates = model.rooms.filter((room) => Number(room.level) === Number(level)).flatMap((room) => {
    const halfX = Math.max(0, room.w / 2 - margin), halfZ = Math.max(0, room.l / 2 - margin)
    return [{ x: Math.max(room.x - halfX, Math.min(room.x + halfX, x)),
      z: Math.max(room.z - halfZ, Math.min(room.z + halfZ, z)) }, { x: room.x, z: room.z }]
  }).filter((point) => isWalkablePoint(model, point.x, point.z, level))
    .sort((a, b) => (a.x - x) ** 2 + (a.z - z) ** 2 - (b.x - x) ** 2 - (b.z - z) ** 2)
  return candidates[0] || { x, z }
}

export function moveWithCollisions(model, x, z, dx, dz, level) {
  if (!model.rooms.length) return { x: x + dx, z: z + dz }
  const start = nearestWalkablePoint(model, x, z, level)
  let nextX = start.x, nextZ = start.z
  // Substeps prevent a slow frame or large input jump from tunnelling through
  // a thin wall. Sliding tests start from the already corrected position.
  const steps = Math.max(1, Math.ceil(Math.hypot(dx, dz) / 0.05))
  const sx = dx / steps, sz = dz / steps
  for (let i = 0; i < steps; i++) {
    if (isWalkablePoint(model, nextX + sx, nextZ + sz, level)) { nextX += sx; nextZ += sz }
    else {
      if (isWalkablePoint(model, nextX + sx, nextZ, level)) nextX += sx
      if (isWalkablePoint(model, nextX, nextZ + sz, level)) nextZ += sz
    }
  }
  return { x: nextX, z: nextZ }
}
