import * as THREE from 'three'
import { doorType } from './assetCompatibility.js'
import { prepareAssetModel } from './assetModel.js'
import { isVisibleInHierarchy } from './sceneEditing.js'

export const openingKey = (type, id) => `${type}:${id}`

const array = (value) => Array.isArray(value) ? value : []
const number = (value) => value == null || value === '' ? NaN : Number(value)
const token = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9_]/g, '')

export function canonicalOpenings(design) {
  const floors = array(design?.floors)
  const owners = [...floors, design || {}, ...array(design?.rooms), ...floors.flatMap((floor) => array(floor.rooms))]
  const walls = owners.flatMap((owner) => array(owner.walls))
  const result = new Map()
  for (const owner of owners) {
    for (const type of ['door', 'window']) {
      for (const item of array(owner[`${type}s`])) {
        if (item?.id == null) continue
        const key = openingKey(type, item.id)
        if (result.has(key)) continue
        const width = number(item.width ?? item.dimensions?.width)
        const height = number(item.height ?? item.dimensions?.height)
        const p = item.position || {}
        const x = number(Array.isArray(p) ? p[0] : p.x)
        const y = number(Array.isArray(p) ? p[1] : p.y)
        let base = number(Array.isArray(p) ? p[2] : p.z)
        if (!Number.isFinite(base)) {
          const floorZ = number(owner.elevation ?? owner.position?.z)
          const sill = type === 'door' ? 0 : number(item.sill_height)
          if (Number.isFinite(floorZ) && Number.isFinite(sill)) base = floorZ + sill
        }
        const wall = walls.find((entry) => String(entry.id) === String(item.wall_id))
        const side = String(item.wall_side || item.wall || '').toLowerCase()
        let vertical
        if (wall?.start && wall?.end) {
          vertical = Math.abs(number(wall.end.y) - number(wall.start.y)) > Math.abs(number(wall.end.x) - number(wall.start.x))
        } else if (['left', 'right', 'east', 'west'].includes(side)) vertical = true
        else if (['front', 'back', 'north', 'south'].includes(side)) vertical = false
        if (![x, y, base, width, height].every(Number.isFinite) || width <= 0 || height <= 0 || vertical === undefined) continue
        result.set(key, { type, id: String(item.id), width, height, depth: 0.22,
          position: [x, base, -y], rotation: vertical ? Math.PI / 2 : 0,
          door_type: type === 'door' ? doorType(item) : undefined, roomId: item.room_id || item.roomId, wallId: item.wall_id, wallSide: side,
          source: 'layout' })
      }
    }
  }
  return [...result.values()]
}

function openingKind(object) {
  const name = String(object.name || '')
  if (/cutter|handle|knob/i.test(name)) return null
  if (['window', 'door'].includes(object.userData?.archgen_opening_kind)) return object.userData.archgen_opening_kind
  if (/^(window(?:frame|glass)?|win_asset)(?:_|$)/i.test(name)) return 'window'
  if (/^door(?:frame)?(?:_|$)/i.test(name)) return 'door'
  return null
}

function matchLayoutOpening(object, definitions) {
  const type = openingKind(object)
  if (!type) return null
  const candidates = definitions.filter((entry) => entry.type === type)
  const metadataId = object.userData?.archgen_opening_id
  if (metadataId != null) return candidates.find((entry) => entry.id === String(metadataId)) || null
  const name = token(object.name)
  const named = candidates.filter((entry) => {
    const id = token(entry.id)
    return name === id || name === `${type}_${id}`
      || new RegExp(`^${type}(?:frame|glass)?_l\\d+_${id}$`).test(name)
  })
  if (named.length === 1) return named[0]
  // Old imported wrappers use asset names instead of opening IDs. Match only
  // one nearby layout aperture; never infer size from a swung-open door leaf.
  const box = new THREE.Box3().setFromObject(object, true)
  if (box.isEmpty()) return null
  const center = box.getCenter(new THREE.Vector3())
  const pivot = object.getWorldPosition(new THREE.Vector3())
  const nearby = candidates.filter((entry) => {
    const [x, base, z] = entry.position
    const close = (point) => Math.hypot(point.x - x, point.z - z) <= 0.3
      && point.y >= base - 0.15 && point.y <= base + entry.height + 0.15
    return close(pivot) || close(center)
  })
  return nearby.length === 1 ? nearby[0] : null
}

export function collectOpeningRoots(scene, definitions = []) {
  const result = new Map()
  scene.updateWorldMatrix(true, true)
  scene.traverse((object) => { delete object.userData.__archgenResolvedOpening })
  scene.traverse((object) => {
    const embedded = openingFromObject(object)
    // Prefer the entire imported frame/leaf hierarchy over its material parts.
    for (let parent = object.parent; parent && parent !== scene.parent; parent = parent.parent) {
      if (parent.userData?.archgen_instance_id != null || parent.userData?.__archgenResolvedOpening) return
      if (!embedded && openingKind(parent)) return
      if (parent === scene) break
    }
    if (object.userData?.archgen_instance_id != null) return
    const matched = matchLayoutOpening(object, definitions)
    const opening = embedded ? { ...matched, ...embedded, door_type: embedded.door_type || matched?.door_type } : matched
    if (!opening) return
    object.userData.__archgenResolvedOpening = opening
    const key = openingKey(opening.type, opening.id)
    if (object.userData.__archgenOpeningBaseVisible === undefined) object.userData.__archgenOpeningBaseVisible = isVisibleInHierarchy(object)
    if (!result.has(key)) result.set(key, { opening, originals: [], visible: object.userData.__archgenOpeningBaseVisible })
    result.get(key).originals.push(object)
  })
  // Procedural glass was exported as a separate mesh in existing saved houses.
  scene.traverse((object) => {
    const match = String(object.name).match(/^WindowGlass_L\d+_(.+)$/)
    const entry = match && result.get(openingKey('window', match[1]))
    if (entry && !entry.originals.includes(object)) {
      entry.originals.push(object)
      object.userData.__archgenResolvedOpening = entry.opening
    }
  })
  return result
}

// Opening dimensions belong to the wall, never to the chosen catalog model.
export function openingFromObject(object) {
  const data = object?.userData || {}
  if (data.__archgenResolvedOpening) return data.__archgenResolvedOpening
  if (data.archgen_exterior_feature === 'main_gate' || object?.name === 'Exterior_Entrance_Gate') {
    const bounds = new THREE.Box3().setFromObject(object, true)
    const size = bounds.getSize(new THREE.Vector3())
    const center = bounds.getCenter(new THREE.Vector3())
    if (bounds.isEmpty()) return null
    return { type: 'door', door_type: 'main_gate', id: 'exterior_main_gate', width: Number(data.archgen_target_width) || size.x,
      height: Number(data.archgen_target_height) || size.y, depth: 0.2,
      position: [center.x, bounds.min.y, center.z], rotation: 0 }
  }
  const type = data.archgen_opening_kind
  const width = Number(data.archgen_opening_width)
  const height = Number(data.archgen_opening_height)
  const position = [data.archgen_opening_x, data.archgen_opening_base_z, -data.archgen_opening_y].map(Number)
  if (!['window', 'door'].includes(type) || data.archgen_opening_id == null
    || ![width, height].every((value) => Number.isFinite(value) && value > 0)
    || !position.every(Number.isFinite)) return null
  return { type, door_type: data.archgen_door_type ? doorType({ type: data.archgen_door_type }) : undefined, id: String(data.archgen_opening_id), width, height, depth: 0.22,
    position, rotation: [true, 1, 'true'].includes(data.archgen_opening_vertical) ? Math.PI / 2 : 0 }
}

export function prepareOpeningModel(scene, asset, opening) {
  const prepared = prepareAssetModel(scene, { ...asset, color: undefined })
  const bounds = new THREE.Box3().setFromObject(prepared.object, true)
  const size = bounds.getSize(new THREE.Vector3())
  if (![size.x, size.y, size.z].every((value) => Number.isFinite(value) && value > 0.000001)) {
    throw new Error('Opening model has invalid bounds')
  }
  // Independent axes intentionally fill the rectangular aperture exactly.
  return { object: prepared.object,
    scale: [opening.width / size.x, opening.height / size.y, opening.depth / size.z] }
}

export function setOpeningOverride(design, selection, asset) {
  if (!selection?.opening || !['window', 'door'].includes(selection.type)) return design
  if (asset && (asset.group !== selection.type || !asset.model_path)) return design
  const key = openingKey(selection.type, selection.id)
  design.opening_overrides ||= {}
  if (!asset) delete design.opening_overrides[key]
  else design.opening_overrides[key] = {
    asset_id: asset.asset_id || asset.id, s3_key: asset.s3_key, model_path: asset.model_path,
    name: asset.name, canonical_yaw_offset_deg: asset.canonical_yaw_offset_deg || 0,
    canonical_pitch_offset_deg: asset.canonical_pitch_offset_deg || 0,
  }
  return design
}

export function resolveOpeningAsset(saved, catalog = []) {
  if (!saved) return null
  if (String(saved.asset_id || '').toLowerCase() === 'arched_window_01') return { ...saved, model_path: '/models/arched_window_01.glb', canonical_yaw_offset_deg: 0, canonical_pitch_offset_deg: 0 }
  const fresh = catalog.find((asset) => asset.s3_key === saved.s3_key)
  return fresh?.model_path ? { ...saved, ...fresh } : saved
}
