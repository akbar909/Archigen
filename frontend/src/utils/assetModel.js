import * as THREE from 'three'
import { clone as cloneSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { cleanOpeningScene } from './openingGeometry.js'
import { assetYawOffset } from './wallMount.js'

export function canApplyAccentColor(root) {
  let supported = 0
  let unsupported = false
  root?.traverse((mesh) => {
    if (!mesh.isMesh || !mesh.material || !mesh.visible) return
    for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      if (!material.color || material.map || material.vertexColors || material.isShaderMaterial
        || material.transmission > 0 || material.transparent) unsupported = true
      else supported++
    }
  })
  return supported > 0 && !unsupported
}

export function objectDimensions(object) {
  object.updateWorldMatrix(true, true)
  const quaternion = object.getWorldQuaternion(new THREE.Quaternion())
  const inverse = new THREE.Matrix4().makeRotationFromQuaternion(quaternion.invert())
  const bounds = new THREE.Box3()
  object.traverse((child) => {
    if (!child.isMesh || !child.geometry) return
    child.geometry.computeBoundingBox()
    const matrix = new THREE.Matrix4().multiplyMatrices(inverse, child.matrixWorld)
    bounds.union(child.geometry.boundingBox.clone().applyMatrix4(matrix))
  })
  const size = bounds.getSize(new THREE.Vector3())
  return { width: size.x, height: size.y, depth: size.z }
}

// Preserve the authored proportions and skeletons. Never stretch each axis
// independently: collections such as a table with chairs share one scale.
export function prepareAssetModel(scene, item) {
  const object = new THREE.Group()
  const clone = cloneSkeleton(cleanOpeningScene(scene, item))
  const yaw = assetYawOffset(item)
  clone.rotation.y += THREE.MathUtils.degToRad(yaw)
  clone.rotation.x += THREE.MathUtils.degToRad(Number(item.canonical_pitch_offset_deg) || 0)
  object.add(clone)
  object.updateMatrixWorld(true)
  const bounds = new THREE.Box3().setFromObject(object, true)
  const size = bounds.getSize(new THREE.Vector3())
  const center = bounds.getCenter(new THREE.Vector3())
  clone.position.sub(new THREE.Vector3(center.x, bounds.min.y, center.z))
  const dims = item.dimensions || {}
  const factor = Math.min(
    (Number(dims.width) || 1) / Math.max(size.x, 0.001),
    (Number(dims.height) || 1) / Math.max(size.y, 0.001),
    (Number(dims.depth) || 1) / Math.max(size.z, 0.001),
  )
  const isRug = /rug|carpet/.test(String(item.category || item.asset || item.name || '').toLowerCase())
  const tintable = canApplyAccentColor(clone)
  clone.traverse((child) => {
    if (!child.isMesh || !child.material) return
    child.castShadow = true
    child.receiveShadow = true
    const materials = (Array.isArray(child.material) ? child.material : [child.material]).map((source) => {
      const material = source.clone()
      if (item.wall_mounted || isRug) material.side = THREE.DoubleSide
      if (isRug) {
        material.polygonOffset = true
        material.polygonOffsetFactor = -2
        material.polygonOffsetUnits = -2
      }
      if (item.color && tintable) material.color.set(item.color)
      return material
    })
    child.material = Array.isArray(child.material) ? materials : materials[0]
  })
  return { object, scale: [factor, factor, factor],
    dimensions: { width: size.x * factor, height: size.y * factor, depth: size.z * factor } }
}
