import { snapToWallPlane, wallMountRotation, mountedWallNormal, mountedWallFace } from './wallMount.js'
import { placeOnSupport } from './assetCompatibility.js'
import { clampExteriorPosition } from './exteriorEditing.js'

const asArray = (value) => (Array.isArray(value) ? value : [])

export function furnitureCategory(item) {
  const raw = String(item?.category || item?.asset || item?.type || '').toLowerCase()
  const aliases = {
    chair: 'dining_chair',
    office_chair: 'dining_chair',
    king_bed: 'bed',
    queen_bed: 'bed',
    single_bed: 'bed',
    bed_double: 'bed',
    bed_single: 'bed',
    sofa_3seater: 'sofa',
    sofa_sectional: 'sofa',
    kitchen_counter: 'kitchen_island',
    sink: raw.includes('bath') ? 'bathroom_sink' : 'kitchen_sink',
    bathroom_vanity: 'bathroom_sink',
  }
  return aliases[raw] || raw
}

export function furnitureDimensions(item) {
  const dims = item?.dimensions || {}
  return {
    width: Math.max(0.005, Number(dims.width ?? dims.w) || 1),
    depth: Math.max(0.005, Number(dims.depth ?? dims.d) || 1),
    height: Math.max(0.005, Number(dims.height ?? dims.h) || 0.8),
  }
}

export function findFurnitureById(design, furnitureId) {
  if (!design || !furnitureId) return null
  const collections = [design.furniture, design.exterior?.assets]
  asArray(design.floors).forEach((floor) => collections.push(floor?.furniture))
  asArray(design.rooms).forEach((room) => collections.push(room?.furniture))
  asArray(design.floors).forEach((floor) => {
    asArray(floor?.rooms).forEach((room) => collections.push(room?.furniture))
  })
  for (const collection of collections) {
    const found = asArray(collection).find((item) => item?.id === furnitureId)
    if (found) return found
  }
  return null
}

export function findRoomById(design, roomId) {
  if (!design || !roomId) return null
  const topLevel = asArray(design.rooms).find((room) => room?.id === roomId)
  if (topLevel) return topLevel
  for (const floor of asArray(design.floors)) {
    const room = asArray(floor?.rooms).find((item) => item?.id === roomId)
    if (room) return room
  }
  return null
}

function visitFurniture(design, callback) {
  const collections = [design.furniture, design.exterior?.assets]
  asArray(design.floors).forEach((floor) => collections.push(floor?.furniture))
  asArray(design.rooms).forEach((room) => collections.push(room?.furniture))
  asArray(design.floors).forEach((floor) => {
    asArray(floor?.rooms).forEach((room) => collections.push(room?.furniture))
  })
  collections.forEach((collection) => {
    asArray(collection).forEach(callback)
  })
}

export function updateFurnitureById(design, furnitureId, patchOrUpdater) {
  if (!design || !furnitureId) return design
  visitFurniture(design, (item) => {
    if (item?.id !== furnitureId) return
    const patch = typeof patchOrUpdater === 'function' ? patchOrUpdater(item) : patchOrUpdater
    if (patch && typeof patch === 'object') Object.assign(item, patch)
  })
  visitFurniture(design, (item) => {
    if (!item.support_id) return
    const support = findFurnitureById(design, item.support_id)
    const placed = placeOnSupport(item, support)
    if (placed) Object.assign(item, placed, { client_edited_3d: true })
    else {
      delete item.support_id
      item.position = { ...item.position, z: Number(findRoomById(design, item.room_id)?.position?.z) || 0 }
      item.client_edited_3d = true
    }
  })
  return design
}

export function removeFurnitureById(design, furnitureId) {
  if (!design || !furnitureId) return design
  // Keep tabletop objects when their supporting table is removed.
  visitFurniture(design, (item) => {
    if (item.support_id !== furnitureId) return
    delete item.support_id
    item.position = { ...item.position, z: Number(findRoomById(design, item.room_id)?.position?.z) || 0 }
    item.client_edited_3d = true
  })
  // Reused house GLBs still contain their original meshes. Persist a tombstone
  // so reopening this version also hides and disables the embedded object.
  design.deleted_furniture_ids = [...new Set([
    ...asArray(design.deleted_furniture_ids).map(String), String(furnitureId),
  ])]
  const remove = (owner, key) => {
    if (Array.isArray(owner?.[key])) {
      owner[key] = owner[key].filter((item) => item?.id !== furnitureId)
    }
  }
  remove(design, 'furniture')
  remove(design.exterior, 'assets')
  asArray(design.floors).forEach((floor) => {
    remove(floor, 'furniture')
    asArray(floor?.rooms).forEach((room) => remove(room, 'furniture'))
  })
  asArray(design.rooms).forEach((room) => remove(room, 'furniture'))
  return design
}

export function addExteriorAsset(design, item) {
  if (!design || !item) return design
  if (!design.exterior || typeof design.exterior !== 'object') design.exterior = {}
  if (!Array.isArray(design.exterior.assets)) design.exterior.assets = []
  if (!design.exterior.assets.some((entry) => entry?.id === item.id)) {
    design.exterior.assets.push({
      ...item,
      position: { ...(item.position || {}) },
      dimensions: { ...(item.dimensions || {}) },
    })
  }
  return design
}

export function addFurnitureToRoom(design, roomId, item) {
  if (!design || !roomId || !item) return design
  if (roomId === 'exterior_ground') return addExteriorAsset(design, item)
  const cloneItem = () => ({
    ...item,
    position: { ...(item.position || {}) },
    dimensions: { ...(item.dimensions || {}) },
  })
  const pushUnique = (owner, key) => {
    if (!owner) return
    if (!Array.isArray(owner[key])) owner[key] = []
    if (!owner[key].some((entry) => entry?.id === item.id)) owner[key].push(cloneItem())
  }

  pushUnique(design, 'furniture')
  asArray(design.rooms).forEach((room) => {
    if (room?.id === roomId) pushUnique(room, 'furniture')
  })
  asArray(design.floors).forEach((floor) => {
    const ownsRoom = asArray(floor?.rooms).some((room) => room?.id === roomId)
    if (ownsRoom) pushUnique(floor, 'furniture')
    asArray(floor?.rooms).forEach((room) => {
      if (room?.id === roomId) pushUnique(room, 'furniture')
    })
  })
  return design
}

export function updateRoomById(design, roomId, updater) {
  if (!design || !roomId) return design
  const rooms = [...asArray(design.rooms)]
  asArray(design.floors).forEach((floor) => rooms.push(...asArray(floor?.rooms)))
  rooms.forEach((room) => {
    if (room?.id === roomId) updater(room)
  })
  return design
}

export function updateWallById(design, wallId, updater) {
  if (!design || !wallId) return design
  const walls = [...asArray(design.walls)]
  asArray(design.floors).forEach((floor) => walls.push(...asArray(floor?.walls)))
  walls.forEach((wall) => {
    if (String(wall?.id) === String(wallId)) updater(wall)
  })
  return design
}

export function clampFurniturePosition(item, room, nextPosition) {
  if (item.room_id === 'exterior_ground' || room?.id === 'exterior_ground') return clampExteriorPosition(item, nextPosition)
  if (!room) return nextPosition
  const roomPosition = room.position || room.bounds || {}
  const roomDimensions = room.dimensions || room.bounds || {}
  const roomX = Number(roomPosition.x) || 0
  const roomY = Number(roomPosition.y) || 0
  const roomWidth = Math.max(1, Number(roomDimensions.width ?? room.width) || 1)
  const roomDepth = Math.max(1, Number(roomDimensions.depth ?? room.length) || 1)
  const dimensions = furnitureDimensions(item)
  const angle = (Number(item?.rotation ?? item?.rotation_y) || 0) * Math.PI / 180
  const halfWidth = (Math.abs(Math.cos(angle)) * dimensions.width + Math.abs(Math.sin(angle)) * dimensions.depth) / 2
  const halfDepth = (Math.abs(Math.sin(angle)) * dimensions.width + Math.abs(Math.cos(angle)) * dimensions.depth) / 2
  const padding = 0.14
  const minX = roomX + Math.min(halfWidth + padding, roomWidth / 2)
  const maxX = roomX + roomWidth - Math.min(halfWidth + padding, roomWidth / 2)
  const minY = roomY + Math.min(halfDepth + padding, roomDepth / 2)
  const maxY = roomY + roomDepth - Math.min(halfDepth + padding, roomDepth / 2)

  const result = {
    ...nextPosition,
    x: Math.max(minX, Math.min(maxX, Number(nextPosition?.x) || 0)),
    y: Math.max(minY, Math.min(maxY, Number(nextPosition?.y) || 0)),
    z: Math.max(Number(roomPosition.z) || 0, Number(nextPosition?.z) || 0),
  }
  if (item.wall_mounted && item.wall_side) {
    const offset = dimensions.depth / 2 + 0.12
    if (item.wall_side === 'left') result.x = roomX + offset
    if (item.wall_side === 'right') result.x = roomX + roomWidth - offset
    if (item.wall_side === 'back') result.y = roomY + offset
    if (item.wall_side === 'front') result.y = roomY + roomDepth - offset
    if (item.asset_group !== 'curtain') {
      const alongX = item.wall_side === 'front' || item.wall_side === 'back'
      const key = alongX ? 'x' : 'y'
      const lo = alongX ? minX : minY
      const hi = alongX ? maxX : maxY
      const half = dimensions.width / 2
      const bottom = Number(item.mount_height) || 0
      const obstacles = (room.openings || []).filter((opening) => {
        const matches = item.wall_id && String(opening.wall_id) === String(item.wall_id)
        const sameSide = String(opening.room_id || opening.roomId || '') === String(room.id)
          && String(opening.wall_side) === item.wall_side
        const sill = Number(opening.sill_height ?? opening.position?.z) || 0
        return (matches || sameSide) && bottom < sill + (Number(opening.height) || 2.1) && bottom + dimensions.height > sill
      }).map((opening) => ({ center: Number(opening.position?.[key]), half: (Number(opening.width) || 0.9) / 2 + half + 0.1 }))
        .filter((opening) => Number.isFinite(opening.center))
      const clear = (value) => obstacles.every((o) => Math.abs(value - o.center) >= o.half - 0.001)
      if (!clear(result[key])) {
        const candidates = [lo, hi, ...obstacles.flatMap((o) => [o.center - o.half, o.center + o.half])]
          .filter((v) => v >= lo && v <= hi && clear(v))
          .sort((a, b) => Math.abs(a - result[key]) - Math.abs(b - result[key]))
        result[key] = candidates[0] ?? (Number(item.position?.[key]) || result[key])
      }
    }
  }
  return item.wall_mounted ? snapToWallPlane(result, item) : result
}

export function normalizeDegrees(value) {
  const normalized = Number(value) % 360
  return normalized < 0 ? normalized + 360 : normalized
}

export function ceilingMountedPosition(item, room) {
  const position = room?.position || room?.bounds || {}
  const dimensions = room?.dimensions || room?.bounds || {}
  const clearance = Number.isFinite(Number(item.ceiling_clearance)) ? Math.max(0, Number(item.ceiling_clearance)) : 0.06
  return {
    ...(item.position || {}),
    z: (Number(position.z) || 0) + (Number(dimensions.height) || 3) - furnitureDimensions(item).height - clearance,
  }
}

export function clampMountHeight(item, room, height) {
  const roomHeight = Number(item.boundary_bounds?.height || (room?.dimensions || room?.bounds)?.height) || 3
  return Math.max(0, Math.min(roomHeight - furnitureDimensions(item).height - 0.1, Number(height) || 0))
}
export function alignWallFurniture(item, room, catalog) {
  if (!item.wall_mounted) return item
  const mounting = catalog?.mounting || item.mounting
  let dimensions = item.dimensions
  const version = Number(mounting?.orientation_version) || 0
  if (catalog && version > (Number(item.wall_orientation_version) || 0) && catalog.dimensions?.height > 0) {
    const factor = furnitureDimensions(item).height / catalog.dimensions.height
    dimensions = Object.fromEntries(Object.entries(catalog.dimensions).map(([key, value]) => [key, value * factor]))
  }
  const normal = mountedWallNormal(item, room)
  const rotation = wallMountRotation(item.wall_side, normal, item.rotation)
  const aligned = { ...item, mounting, dimensions, rotation, rotation_y: rotation,
    wall_normal: normal, wall_face: mountedWallFace(item, room), wall_orientation_version: version }
  return room ? { ...aligned, position: clampFurniturePosition(aligned, room, item.position || {}) } : aligned
}
