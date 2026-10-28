import { clampFurniturePosition, ceilingMountedPosition } from './designEditing.js'

export function placementRoom(room, detectedRooms = []) {
  const position = room.position || room.bounds || {}
  const dimensions = room.dimensions || room.bounds || {}
  const slab = detectedRooms.find((entry) => String(entry.roomId) === String(room.id))
  const floor = slab ? slab.center.y + slab.size.y / 2 : Number(position.z) || 0
  return { ...room, position: { ...position, z: floor }, dimensions: {
    ...dimensions, height: (Number(position.z) || 0) + (Number(dimensions.height) || 3) - floor,
  } }
}

export function createAssetPlacement(asset, room, id) {
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
  return item
}

export function placementCameraView(room) {
  const p = room.position || {}, d = room.dimensions || {}
  const width = Number(d.width) || 3, depth = Number(d.depth) || 3
  const x = (Number(p.x) || 0) + width / 2
  const z = -((Number(p.y) || 0) + depth / 2)
  const floor = Number(p.z) || 0
  return {
    position: [x - Math.max(0, width / 2 - 0.45), floor + Math.min(1.65, (Number(d.height) || 3) - 0.3), z + Math.max(0, depth / 2 - 0.45)],
    target: [x, floor + 0.9, z],
  }
}

export function adjustAssetPlacement(item, room, dx = 0, dy = 0, rotation = 0) {
  const next = { ...item, rotation: (item.rotation + rotation + 360) % 360 }
  next.rotation_y = next.rotation
  next.position = clampFurniturePosition(next, room, {
    ...item.position, x: item.position.x + dx, y: item.position.y + dy,
  })
  return next
}
