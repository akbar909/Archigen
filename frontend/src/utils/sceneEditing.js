import * as THREE from 'three'

const raycasts = new WeakMap()
const noRaycast = () => {}

export function editorViewportOffset(canvas, drawer) {
  if (!drawer || !canvas.width || !canvas.height) return { x: 0, y: 0 }
  const bottomSheet = drawer.width > canvas.width * 0.85 && drawer.top > canvas.top + canvas.height * 0.15
  return bottomSheet
    ? { x: 0, y: Math.min(canvas.height * 0.7, Math.max(0, canvas.bottom - drawer.top + 12)) / 2 }
    : { x: Math.min(canvas.width * 0.7, Math.max(0, canvas.right - drawer.left + 16)) / 2, y: 0 }
}

export function setSubtreePickable(root, enabled) {
  root.traverse((object) => {
    if (!object.isMesh) return
    if (!raycasts.has(object)) raycasts.set(object, object.raycast)
    object.raycast = enabled ? raycasts.get(object) : noRaycast
  })
}

export function isVisibleInHierarchy(object) {
  for (let node = object; node; node = node.parent) if (!node.visible) return false
  return true
}

export function findEditableSurface(hitObject, sceneRoot) {
  // Child primitives may carry incomplete extras. Use the resolved opening
  // wrapper first so selection and replacement target the same whole object.
  for (let node = hitObject; node && node !== sceneRoot.parent; node = node.parent) {
    const opening = node.userData?.__archgenResolvedOpening
    if (opening) return { type: opening.type, id: opening.id, object: node }
    if (node === sceneRoot) break
  }
  let fallback = null
  for (let node = hitObject; node && node !== sceneRoot.parent; node = node.parent) {
    const name = String(node.name || '').toLowerCase()
    const wallId = node.userData?.archgen_wall_id
    const roomId = node.userData?.archgen_room_id
    const openingKind = node.userData?.archgen_opening_kind
    const resolvedOpening = node.userData?.__archgenResolvedOpening
    if (node.userData?.archgen_exterior_feature === 'boundary_wall' || /^exterior_boundary_wall_\d+$/i.test(node.name)) {
      return { type: 'wall', id: String(wallId || node.name), object: node, exterior: true, roomId: 'exterior_ground' }
    }
    if (resolvedOpening) return { type: resolvedOpening.type, id: resolvedOpening.id, object: node }
    if (node.userData?.archgen_exterior_feature === 'main_gate' || node.name === 'Exterior_Entrance_Gate') {
      return { type: 'door', id: 'exterior_main_gate', object: node }
    }
    if (['window', 'door'].includes(openingKind) && node.userData.archgen_opening_id != null) {
      return { type: openingKind, id: String(node.userData.archgen_opening_id), object: node }
    }
    // A GLB wall can be a group containing several material primitives.
    // Prefer its stable metadata root over a similarly named child mesh.
    if (wallId) return { type: 'wall', id: String(wallId), object: node }
    if (roomId && name.startsWith('floor')) return { type: 'floor', id: String(roomId), roomId: String(roomId), object: node }
    if (name.startsWith('window_')) fallback = { type: 'window', id: node.name, object: node }
    else if (/^door(?:_|frame_)/.test(name)) fallback = { type: 'door', id: node.name, object: node }
    else if (name.startsWith('wall_')) fallback = { type: 'wall', id: node.name, object: node }
    else if (name.startsWith('roof_') || name.startsWith('ceiling_')) fallback = { type: 'roof', id: node.name, object: node }
    else if (name.startsWith('floor_') && !/foundation|podium|intermediate|ground|garden|stair/.test(name)) fallback = { type: 'floor', id: node.name, object: node }
    else if (/garden_ground|landscape_ground|lawn/.test(name) || name === 'ground') fallback = { type: 'ground', id: node.name, object: node }
    if (node === sceneRoot) break
  }
  return fallback
}

export function mapSurfaceUVs(mesh, tileSize) {
  if (mesh.userData.__surfaceUvTile === tileSize) return
  let geometry = mesh.geometry.clone()
  if (geometry.index) geometry = geometry.toNonIndexed()
  if (!geometry.attributes.normal) geometry.computeVertexNormals()
  const positions = geometry.attributes.position
  const normals = geometry.attributes.normal
  const uv = new Float32Array(positions.count * 2)
  const point = new THREE.Vector3()
  const normal = new THREE.Vector3()
  const normalMatrix = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld)
  for (let i = 0; i < positions.count; i++) {
    point.fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld)
    normal.fromBufferAttribute(normals, i).applyNormalMatrix(normalMatrix)
    const ax = Math.abs(normal.x), ay = Math.abs(normal.y), az = Math.abs(normal.z)
    uv[i * 2] = (ay >= ax && ay >= az ? point.x : ax >= az ? point.z : point.x) / tileSize
    uv[i * 2 + 1] = (ay >= ax && ay >= az ? -point.z : point.y) / tileSize
  }
  geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2))
  mesh.geometry = geometry
  mesh.userData.__surfaceUvTile = tileSize
}

export function surfaceFaceKey(normal) {
  const axis = ['x', 'y', 'z'].sort((a, b) => Math.abs(normal[b]) - Math.abs(normal[a]))[0]
  return `${normal[axis] >= 0 ? 'p' : 'n'}${axis}`
}

export function installSurfaceTexture(root, texture, tileSize = 1.8, faceNormal = null) {
  root.updateWorldMatrix(true, true)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.flipY = false
  texture.channel = 0
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(1, 1)
  texture.needsUpdate = true
  let count = 0
  root.traverse((mesh) => {
    if (!mesh.isMesh || !mesh.material || !mesh.geometry?.attributes.position) return
    mapSurfaceUVs(mesh, tileSize)
    const originals = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    const makeMaterial = (source) => {
      const material = source.clone()
      material.map = texture
      material.color?.set('#ffffff')
      material.vertexColors = false
      // The previous finish's baked lighting/normal maps must not mask the new finish.
      material.normalMap = material.bumpMap = material.aoMap = material.lightMap = null
      material.roughnessMap = material.metalnessMap = null
      material.metalness = 0
      material.roughness = 0.8
      material.needsUpdate = true
      return material
    }
    if (faceNormal) {
      const geometry = mesh.geometry
      const key = surfaceFaceKey(faceNormal)
      const materials = [...originals]
      let index = materials.findIndex((material) => material.userData?.surfaceFaceKey === key)
      const material = makeMaterial(originals[0])
      material.userData.surfaceFaceKey = key
      if (index < 0) { index = materials.length; materials.push(material) }
      else materials[index] = material
      const groups = [...geometry.groups]
      const normalMatrix = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld)
      const desired = new THREE.Vector3(faceNormal.x, faceNormal.y, faceNormal.z).normalize()
      const normal = new THREE.Vector3()
      geometry.clearGroups()
      for (let i = 0; i < geometry.attributes.position.count; i += 3) {
        normal.fromBufferAttribute(geometry.attributes.normal, i).applyNormalMatrix(normalMatrix)
        const originalIndex = groups.find((group) => i >= group.start && i < group.start + group.count)?.materialIndex || 0
        const previous = originalIndex < originals.length ? originalIndex : 0
        geometry.addGroup(i, 3, normal.dot(desired) > 0.75 ? index : previous)
      }
      mesh.material = materials
    } else {
      const materials = originals.map(makeMaterial)
      mesh.material = Array.isArray(mesh.material) ? materials : materials[0]
    }
    count++
  })
  return count
}

const textureCache = new Map()

export async function applySurfaceTexture(root, url, tileSize = 1.8, faceNormal = null) {
  if (!root || !url) return 0
  const key = faceNormal ? surfaceFaceKey(faceNormal) : 'all'
  const requests = root.userData.__finishRequests ||= {}
  const applied = root.userData.__finishApplied ||= {}
  requests[key] = url
  if (applied[key] === `${url}:${tileSize}`) return 1
  let texture = textureCache.get(url)
  if (!texture) {
    texture = await new THREE.TextureLoader().loadAsync(url)
    textureCache.set(url, texture)
  }
  if (requests[key] !== url) return 0
  const count = installSurfaceTexture(root, texture, tileSize, faceNormal)
  applied[key] = `${url}:${tileSize}`
  root.userData.__appliedFinishUrl = url
  root.userData.__finishTileSize = tileSize
  return count
}
