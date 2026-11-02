import { clampFurniturePosition, ceilingMountedPosition } from './designEditing.js'
import { mountWallFixture } from './fixtureMounting.js'

export function placementRoom(room, detectedRooms = []) {
  const position = room.position || room.bounds || {}
  const dimensions = room.dimensions || room.bounds || {}
  const slab = detectedRooms.find((entry) => String(entry.roomId) === String(room.id))
  const floor = slab ? slab.center.y + slab.size.y / 2 : Number(position.z) || 0
  return { ...room, position: { ...position, z: floor }, dimensions: {
    ...dimensions, height: (Number(position.z) || 0) + (Number(dimensions.height) || 3) - floor,
  } }
}

export function createAssetPlacement(asset, room, id, placement = {}) {
  if (!asset?.model_path || !room?.id || !['furniture', 'floor_overlay', 'ceiling_asset'].includes(asset.group)) return null
  const p = room.position || {}, d = room.dimensions || {}
  const item = {
    id, name: asset.name, category: asset.category, asset: asset.category,
    asset_id: asset.asset_id || asset.id, model_id: asset.id, model_path: asset.model_path,
    s3_key: asset.s3_key, asset_group: asset.group, room_id: room.id,
    mounting: asset.mounting,
    canonical_yaw_offset_deg: asset.canonical_yaw_offset_deg || 0,
    canonical_pitch_offset_deg: asset.canonical_pitch_offset_deg || 0,
    dimensions: { ...asset.dimensions }, rotation: 0, rotation_y: 0,
    ceiling_mounted: asset.group === 'ceiling_asset',
    client_edited_3d: true, placement_hint: 'user_exact',
    position: { x: (Number(p.x) || 0) + (Number(d.width) || 3) / 2,
      y: (Number(p.y) || 0) + (Number(d.depth) || 3) / 2, z: Number(p.z) || 0 },
  }
  item.position = clampFurniturePosition(item, room, item.position)
  if (item.ceiling_mounted) item.position = ceilingMountedPosition(item, room)
  return mountWallFixture(item,room,asset,placement)
}

export function placementCameraView(room) {
  const p = room.position || {}, d = room.dimensions || {}
  const width = Number(d.width) || 3, depth = Number(d.depth) || 3
  const x0 = Number(p.x) || 0, y0 = Number(p.y) || 0
  const x = x0 + width / 2
  const y = y0 + depth / 2
  const floor = Number(p.z) || 0
  const marginX = Math.min(0.7, width * 0.28), marginY = Math.min(0.7, depth * 0.28)
  const candidates = [
    [x0 + marginX, y0 + marginY], [x0 + width - marginX, y0 + marginY],
    [x0 + marginX, y0 + depth - marginY], [x0 + width - marginX, y0 + depth - marginY],
    [x, y0 + marginY], [x, y0 + depth - marginY],
  ]
  const obstacles = (room.furniture || []).filter((item) => !item.wall_mounted && !item.ceiling_mounted && item.position)
  const openings = room.openings || []
  const clearance = ([cx, cy]) => {
    const furnitureClearance = obstacles.length ? Math.min(...obstacles.map((item) => {
      const dims = item.dimensions || {}, pos = item.position || {}
      const dx = Math.abs(cx - (Number(pos.x) || 0)) - (Number(dims.width) || 1) / 2
      const dy = Math.abs(cy - (Number(pos.y) || 0)) - (Number(dims.depth) || 1) / 2
      return Math.max(dx, dy)
    })) : Math.min(width, depth)
    const openingClearance = openings.length ? Math.min(...openings.map((item) => {
      const pos = item.position || {}
      return Math.hypot(cx - (Number(pos.x) || x), cy - (Number(pos.y) || y))
    })) : Math.min(width, depth)
    return furnitureClearance + openingClearance * 0.2 - Math.hypot(cx - x, cy - y) * 0.04
  }
  const camera = candidates.sort((a, b) => clearance(b) - clearance(a))[0]
  return {
    position: [camera[0], floor + Math.min(1.65, (Number(d.height) || 3) - 0.3), -camera[1]],
    target: [x, floor + 1.15, -y],
  }
}

export function adjustAssetPlacement(item, room, dx = 0, dy = 0, rotation = 0) {
  if (item.support_id) return item
  const next = { ...item, rotation: (item.rotation + rotation + 360) % 360 }
  next.rotation_y = next.rotation
  next.position = clampFurniturePosition(next, room, {
    ...item.position, x: item.position.x + dx, y: item.position.y + dy,
  })
  return next
}
