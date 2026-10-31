import { wallMountNormal, wallMountRotation, snapToWallPlane } from './wallMount.js'

export function clampExteriorPosition(item, position) {
  const result = { ...position }
  const bounds = item.boundary_bounds || item.placement_bounds
  if (!bounds) return result // Older outdoor placements have no measured ground bounds.
  const dims = item.dimensions || {}
  const angle = (Number(item.rotation) || 0) * Math.PI / 180
  const halfX = (Math.abs(Math.cos(angle)) * (Number(dims.width) || 1) + Math.abs(Math.sin(angle)) * (Number(dims.depth) || 1)) / 2
  const halfY = (Math.abs(Math.sin(angle)) * (Number(dims.width) || 1) + Math.abs(Math.cos(angle)) * (Number(dims.depth) || 1)) / 2
  const clamp = (value, min, max, half) => Math.max(min + Math.min(half, (max - min) / 2),
    Math.min(max - Math.min(half, (max - min) / 2), value))
  if (!item.wall_mounted || Math.abs(item.wall_normal?.z || 0) > 0.5) result.x = clamp(result.x, bounds.minX, bounds.maxX, halfX)
  if (!item.wall_mounted || Math.abs(item.wall_normal?.x || 0) > 0.5) result.y = clamp(result.y, bounds.minY, bounds.maxY, halfY)
  return item.wall_mounted ? snapToWallPlane(result, item) : result
}

export function createBoundaryDecor(asset, selection, id) {
  const bounds = selection.boundaryBounds
  const hit = selection.hitPoint
  const normal = wallMountNormal(null, selection.surfaceNormal)
  if (!bounds || !hit || !normal || Math.abs(selection.surfaceNormal?.y || 0) > 0.5 || !asset.model_path) return null
  const alongX = Math.abs(normal.z) > 0.5
  if (asset.dimensions.width > (alongX ? bounds.maxX - bounds.minX : bounds.maxY - bounds.minY)
    || asset.dimensions.height > bounds.height) return null
  const side = alongX ? (normal.z > 0 ? 'front' : 'back') : (normal.x > 0 ? 'left' : 'right')
  const item = {
    id, name: asset.name, category: asset.category, asset: asset.category,
    asset_id: asset.asset_id || asset.id, model_id: asset.id, model_path: asset.model_path, s3_key: asset.s3_key,
    asset_group: asset.group, mounting: asset.mounting,
    canonical_yaw_offset_deg: asset.canonical_yaw_offset_deg || 0, canonical_pitch_offset_deg: asset.canonical_pitch_offset_deg || 0,
    dimensions: { ...asset.dimensions }, room_id: 'exterior_ground', wall_mounted: true,
    wall_id: selection.wallId, wall_side: side, wall_normal: normal, wall_anchor: { x: hit.x, y: -hit.z },
    boundary_bounds: { ...bounds }, position: { x: hit.x, y: -hit.z, z: bounds.base },
    mount_height: Math.max(0, Math.min(bounds.height - asset.dimensions.height, hit.y - bounds.base - asset.dimensions.height / 2)),
    rotation: wallMountRotation(side, normal), rotation_y: wallMountRotation(side, normal),
    client_edited_3d: true, placement_hint: 'wall_exact',
  }
  item.position = clampExteriorPosition(item, item.position)
  return item
}
