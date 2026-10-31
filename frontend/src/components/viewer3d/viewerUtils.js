export function modelIdentity(url) {
  if (!url) return null
  try {
    const parsed = new URL(url, window.location.origin)
    return `${parsed.origin}${parsed.pathname}`
  } catch {
    return String(url).split('?')[0]
  }
}

export function objectFloorLevel(item) {
  const direct = item?.floor_level ?? item?.floor
  if (direct !== undefined && direct !== null && direct !== '') {
    const parsed = Number(direct)
    if (Number.isFinite(parsed)) return parsed
  }
  const z = Number(item?.position?.z ?? item?.bounds?.z)
  return Number.isFinite(z) ? Math.max(0, Math.round(z / 3)) : 0
}

function normalizeKey(str) {
  if (!str) return ''
  return String(str)
    .toLowerCase()
    .replace(/^floor(?:_l\d+)?_?/i, '')
    .replace(/^room_?/i, '')
    .replace(/[_\s-]+/g, '_')
    .replace(/_0+(\d+)/g, '_$1')
    .replace(/(\D)0+(\d+)/g, '$1$2')
    .replace(/\.00\d+$/, '')
    .trim()
}

function getRoomCategory(str) {
  const s = String(str || '').toLowerCase()
  if (s.includes('master') && s.includes('bed')) return 'master_bedroom'
  if (s.includes('master') && s.includes('bath')) return 'master_bathroom'
  if (s.includes('bed')) return 'bedroom'
  if (s.includes('bath') || s.includes('powder') || s.includes('toilet') || s.includes('wash') || s.includes('ensuite')) return 'bathroom'
  if (s.includes('liv') || s.includes('lounge') || s.includes('great')) return 'living'
  if (s.includes('kit')) return 'kitchen'
  if (s.includes('din')) return 'dining'
  if (s.includes('off') || s.includes('study')) return 'office'
  if (s.includes('gar')) return 'garage'
  if (s.includes('balc') || s.includes('terr')) return 'balcony'
  if (s.includes('foyer') || s.includes('entry')) return 'foyer'
  if (s.includes('hall') || s.includes('corr')) return 'hallway'
  return s
}

function extractNumber(str) {
  const m = String(str || '').match(/\d+/)
  return m ? parseInt(m[0], 10) : null
}

export function roomPlacement(room, detectedRooms = [], floorHeight = 3, zSign = 1) {
  if (!room) return { x: 0, y: 0, z: 0, w: 8, l: 8, level: 0 }

  const level = objectFloorLevel(room)

  // ── 1. If 3D GLB model floor meshes are available, ALWAYS prioritize them ──
  // The GLB floor mesh center is the true Three.js world position of the room.
  if (Array.isArray(detectedRooms) && detectedRooms.length > 0) {
    const sameLevel = detectedRooms.filter((c) => Number(c.level) === Number(level))
    const candidates = sameLevel.length > 0 ? sameLevel : detectedRooms

    const roomId = String(room.id || '').trim().toLowerCase()
    const roomName = String(room.name || '').trim()
    const roomType = String(room.type || '').trim()

    // Strategy A: Exact ID match (archgen_room_id or meshId)
    let match = candidates.find((c) => {
      const cRoomId = String(c.roomId || '').toLowerCase()
      const cMeshId = String(c.meshId || '').toLowerCase()
      return (cRoomId && cRoomId === roomId) || (cMeshId && cMeshId === roomId)
    })

    // Strategy B: Normalized key match
    if (!match) {
      const normId = normalizeKey(roomId)
      const normName = normalizeKey(roomName)
      match = candidates.find((c) => {
        const cKey = normalizeKey(c.roomId || c.meshId || c.name)
        return (normId && cKey === normId) || (normName && cKey === normName)
      })
    }

    // Strategy C: Room Category + Room Index/Number match (e.g. "Bedroom 2" -> bedroom #2)
    if (!match) {
      const rCat = getRoomCategory(roomName || roomType || roomId)
      const rNum = extractNumber(roomName || roomId)

      if (rCat) {
        const catCandidates = candidates.filter((c) => {
          const cCat = getRoomCategory(c.meshId || c.name || c.roomId)
          return cCat === rCat
        })

        if (catCandidates.length === 1) {
          match = catCandidates[0]
        } else if (catCandidates.length > 1) {
          if (rNum !== null) {
            match = catCandidates.find((c) => {
              const cNum = extractNumber(c.meshId || c.name || c.roomId)
              return cNum === rNum
            })
          }
          // If no number match, find closest dimension match
          if (!match) {
            const width = Number(room.dimensions?.width ?? room.bounds?.width ?? room.width)
            const depth = Number(room.dimensions?.depth ?? room.bounds?.depth ?? room.length)
            if (Number.isFinite(width) && Number.isFinite(depth)) {
              match = catCandidates.reduce((best, curr) => {
                const diffCurr = Math.abs(curr.size.x - width) + Math.abs(curr.size.z - depth)
                const diffBest = best ? Math.abs(best.size.x - width) + Math.abs(best.size.z - depth) : Infinity
                return diffCurr < diffBest ? curr : best
              }, null)
            }
          }
        }
      }
    }

    // Strategy D: Dimension and relative position correlation on same floor
    if (!match && sameLevel.length > 0) {
      const width = Number(room.dimensions?.width ?? room.bounds?.width ?? room.width)
      const depth = Number(room.dimensions?.depth ?? room.bounds?.depth ?? room.length)
      const position = room.position || room.bounds || {}
      const expectedX = (Number(position.x) || 0) + width / 2
      const expectedZ = ((Number(position.y) || 0) + depth / 2) * zSign
      if (Number.isFinite(width) && Number.isFinite(depth)) {
        match = sameLevel.reduce((best, curr) => {
          const score = (candidate) => Math.abs(candidate.size.x - width) + Math.abs(candidate.size.z - depth)
            + Math.hypot(candidate.center.x - expectedX, candidate.center.z - expectedZ) * 0.35
          const diffCurr = score(curr)
          const diffBest = best ? score(best) : Infinity
          return diffCurr < diffBest ? curr : best
        }, null)
      }
    }

    if (match) {
      return {
        id: room.id,
        x: match.center.x,
        y: Number.isFinite(match.center.y) ? match.center.y + (Number(match.size.y) || 0) / 2 : level * floorHeight,
        z: match.center.z,
        w: match.size.x,
        l: match.size.z,
        level: Number.isFinite(match.level) ? match.level : level,
      }
    }
  }

  // ── 2. Fallback when GLB model is not loaded (Pure 2D / Three.js RoomVolume) ──
  const position = room.position || room.bounds || {}
  const dimensions = room.dimensions || room.bounds || {}
  const width = Math.max(Number(dimensions.width ?? room.width) || 4, 1)
  const depth = Math.max(Number(dimensions.depth ?? room.length) || 4, 1)
  const px = Number(position.x) || 0
  const py = Number(position.y) || 0
  const pz = Number(position.z)
  const elevation = Number.isFinite(pz)
    ? pz
    : (Number.isFinite(room.elevation) ? Number(room.elevation) : level * floorHeight)

  return {
    id: room.id,
    x: px + width / 2,
    y: elevation,
    z: (py + depth / 2) * zSign,
    w: width,
    l: depth,
    level,
  }
}

/**
 * Check whether a point falls inside a rectangular room footprint (with padding).
 */
function isInsideRoom(x, z, room, padding = 0.18) {
  const halfW = Math.max(0, room.w / 2 - padding)
  const halfL = Math.max(0, room.l / 2 - padding)
  return (
    x >= room.x - halfW && x <= room.x + halfW
    && z >= room.z - halfL && z <= room.z + halfL
  )
}

/**
 * Return the room object the point is inside (same floor), or null.
 */
function findContainingRoom(x, z, level, rooms) {
  return rooms.find(
    (r) => Number(r.level) === Number(level) && isInsideRoom(x, z, r),
  ) || null
}

/**
 * Check whether a door exists near the boundary between two rooms (or a room
 * boundary leading outside). We look for any door within range of the crossing
 * point on the shared wall edge.
 */
function hasDoorOnBoundary(crossX, crossZ, level, doors, tolerance = 0.8) {
  return doors.some((door) => {
    if (Number(door.floorLevel) !== Number(level)) return false
    const dist = Math.hypot(crossX - door.worldX, crossZ - door.worldZ)
    const doorHalfWidth = Math.max(Number(door.width) || 0.9, 0.9) / 2
    return dist <= doorHalfWidth + tolerance
  })
}

/**
 * Find the crossing point where the movement segment intersects a room's
 * bounding edge. Returns {x, z} of the intersection, or null.
 */
function findEdgeCrossing(fromX, fromZ, toX, toZ, room) {
  const halfW = room.w / 2
  const halfL = room.l / 2
  const left = room.x - halfW
  const right = room.x + halfW
  const top = room.z - halfL
  const bottom = room.z + halfL

  const dx = toX - fromX
  const dz = toZ - fromZ

  // Check all 4 edges and return the closest intersection
  let bestT = Infinity
  let bestPoint = null

  const edges = [
    { axis: 'x', val: left, min: top, max: bottom },    // left wall
    { axis: 'x', val: right, min: top, max: bottom },   // right wall
    { axis: 'z', val: top, min: left, max: right },      // top wall
    { axis: 'z', val: bottom, min: left, max: right },   // bottom wall
  ]

  for (const edge of edges) {
    if (edge.axis === 'x' && Math.abs(dx) > 0.0001) {
      const t = (edge.val - fromX) / dx
      if (t >= 0 && t <= 1) {
        const iz = fromZ + t * dz
        if (iz >= edge.min - 0.1 && iz <= edge.max + 0.1 && t < bestT) {
          bestT = t
          bestPoint = { x: edge.val, z: iz }
        }
      }
    } else if (edge.axis === 'z' && Math.abs(dz) > 0.0001) {
      const t = (edge.val - fromZ) / dz
      if (t >= 0 && t <= 1) {
        const ix = fromX + t * dx
        if (ix >= edge.min - 0.1 && ix <= edge.max + 0.1 && t < bestT) {
          bestT = t
          bestPoint = { x: ix, z: edge.val }
        }
      }
    }
  }

  return bestPoint
}

export function isNavigationPointWalkable({
  x,
  z,
  level,
  rooms,
  doors,
  exteriorAccess,
  padding = 0.18,
  fromX,
  fromZ,
}) {
  const sameFloorRooms = rooms.filter((r) => Number(r.level) === Number(level))

  // Find which rooms the origin and destination are in
  const originRoom = (fromX !== undefined && fromZ !== undefined)
    ? findContainingRoom(fromX, fromZ, level, sameFloorRooms)
    : null
  const targetRoom = findContainingRoom(x, z, level, sameFloorRooms)

  // --- Case 1: Target inside a room ---
  if (targetRoom) {
    // Same room → always allowed (no wall crossing)
    if (originRoom && originRoom === targetRoom) return true

    // Different room or coming from outside → check for door on boundary
    if (originRoom) {
      // Moving between two rooms: find where we cross the origin room's boundary
      const crossing = findEdgeCrossing(fromX, fromZ, x, z, originRoom)
      if (crossing && hasDoorOnBoundary(crossing.x, crossing.z, level, doors)) {
        return true
      }
      // Also check the target room boundary crossing
      const crossing2 = findEdgeCrossing(fromX, fromZ, x, z, targetRoom)
      if (crossing2 && hasDoorOnBoundary(crossing2.x, crossing2.z, level, doors)) {
        return true
      }
      return false // Wall block — no door found on boundary
    }

    // Coming from outside into a room — check if there's a door near the entry
    if (fromX !== undefined && fromZ !== undefined) {
      const crossing = findEdgeCrossing(fromX, fromZ, x, z, targetRoom)
      if (crossing && hasDoorOnBoundary(crossing.x, crossing.z, level, doors)) {
        return true
      }
    }
    // Fallback: allow if we're near a door (teleport/initial placement)
    const nearDoor = doors.some((d) => {
      if (Number(d.floorLevel) !== Number(level)) return false
      const w = Math.max(Number(d.width) || 0.9, 0.9)
      return Math.hypot(x - d.worldX, z - d.worldZ) <= w / 2 + padding + 0.3
    })
    return nearDoor || !originRoom // Allow if no origin (initial placement)
  }

  // --- Case 2: Target is outside all rooms ---
  // If we were in a room, we need a door to exit
  if (originRoom && fromX !== undefined && fromZ !== undefined) {
    const crossing = findEdgeCrossing(fromX, fromZ, x, z, originRoom)
    if (!crossing || !hasDoorOnBoundary(crossing.x, crossing.z, level, doors)) {
      return false // No door on this edge → wall blocks us
    }
  }

  // Outside → check door passages for walkable zone
  const insideDoorPassage = doors.some((door) => {
    if (Number(door.floorLevel) !== Number(level)) return false
    const width = Math.max(Number(door.width) || 0.9, 0.9)
    return Math.hypot(x - door.worldX, z - door.worldZ) <= width / 2 + padding + 0.2
  })
  if (insideDoorPassage) return true

  return Number(level) === 0 && exteriorAccess(x, z, padding)
}

