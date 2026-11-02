// A slab named "stair_lobby" is still a room floor, not a stair component.
export function roomFloorMeshInfo(object) {
  if (!object?.isMesh) return null
  const parent = object.parent
  const name = String(object.name || ''), parentName = String(parent?.name || '')
  const effectiveName = /^floor/i.test(name) ? name : /^floor/i.test(parentName) ? parentName : name
  if (!/^floor/i.test(effectiveName)) return null
  const data = object.userData || {}, inherited = parent?.userData || {}
  const lower = effectiveName.toLowerCase()
  if (data.archgen_stair_component || inherited.archgen_stair_component
    || data.archgen_stair_opening || inherited.archgen_stair_opening || /cutter/i.test(effectiveName)) return null
  const roomId = data.archgen_room_id || inherited.archgen_room_id || ''
  // Stable room metadata takes precedence over words in its display name.
  if (!roomId && (/podium|foundation|lawn|garden|ground|intermediate/.test(lower)
    || lower.includes('stair') && !/stair[_\s-]*lobby/.test(lower))) return null
  return { effectiveName, roomId: String(roomId) }
}
