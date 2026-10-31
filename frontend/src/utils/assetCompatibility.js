export function doorType(value = {}) {
  const explicit = value.door_type || value.opening_type
  if (['interior', 'garage', 'main_gate', 'entrance'].includes(explicit)) return explicit
  const text = [value.id, value.asset_id, value.s3_key, value.relative_path, value.name, value.type].join(' ').toLowerCase()
  if (/garage|garager|roller/.test(text)) return 'garage'
  if (/gate/.test(text)) return 'main_gate'
  if (/entrance|exterior|entry/.test(text)) return 'entrance'
  return 'interior'
}

export function compatibleOpening(asset, opening, room) {
  if (!asset?.model_path || asset.group !== opening?.type) return false
  if (opening.type === 'window') return true
  const type = opening.door_type || (/garage|parking/i.test(`${room?.type} ${room?.name}`)
    && opening.width >= 2 ? 'garage' : doorType(opening))
  return doorType(asset) === type
}

export function assetSurface(asset) {
  if (asset.mounting?.surface === 'tabletop' || asset.category === 'table_clock') return 'tabletop'
  if (asset.group === 'ceiling_asset') return 'ceiling'
  return 'floor'
}

export function tabletopSupports(room) {
  return (room?.furniture || []).filter((item) => !item.wall_mounted && !item.ceiling_mounted
    && /table|desk|nightstand|console/.test(String(item.category || item.asset || ''))
    && !/with_chairs|vanity/.test(String(item.asset_id || item.category || ''))
    && item.position && item.dimensions?.height > 0)
}

export function placeOnSupport(item, support) {
  if (!support?.position || ![item.dimensions?.width, item.dimensions?.depth,
    support.dimensions?.width, support.dimensions?.depth, support.dimensions?.height].every((n) => Number.isFinite(Number(n)) && Number(n) > 0)) return null
  const angle = ((Number(item.rotation) || 0) - (Number(support.rotation) || 0)) * Math.PI / 180
  const w = Math.abs(Math.cos(angle)) * item.dimensions.width + Math.abs(Math.sin(angle)) * item.dimensions.depth
  const d = Math.abs(Math.sin(angle)) * item.dimensions.width + Math.abs(Math.cos(angle)) * item.dimensions.depth
  if (w + 0.02 > support.dimensions.width || d + 0.02 > support.dimensions.depth) return null
  const oldAngle = (Number(item.support_rotation ?? support.rotation) || 0) * Math.PI / 180
  const origin = item.support_origin || support.position
  const dx = item.support_id ? item.position.x - origin.x : 0
  const dy = item.support_id ? item.position.y - origin.y : 0
  const limitX = (support.dimensions.width - w) / 2 - 0.01
  const limitY = (support.dimensions.depth - d) / 2 - 0.01
  const x = Math.max(-limitX, Math.min(limitX, Math.cos(oldAngle) * dx + Math.sin(oldAngle) * dy))
  const y = Math.max(-limitY, Math.min(limitY, -Math.sin(oldAngle) * dx + Math.cos(oldAngle) * dy))
  const turn = (Number(support.rotation) || 0) * Math.PI / 180
  return { ...item, support_id: support.id, support_origin: { ...support.position }, support_rotation: Number(support.rotation) || 0,
    position: { x: support.position.x + Math.cos(turn) * x - Math.sin(turn) * y,
    y: support.position.y + Math.sin(turn) * x + Math.cos(turn) * y,
    z: (Number(support.position.z) || 0) + Number(support.dimensions.height) + 0.002 } }
}
