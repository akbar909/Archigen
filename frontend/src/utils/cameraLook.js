import * as THREE from 'three'
import { LOOK_SENSITIVITY } from './navigation.js'

export function turnCameraInPlace(camera, dx, dy, controls, targetPos, targetCamPos) {
  const angles = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ')
  // Drag the scene like a panorama; pointer-lock mouse look is handled separately.
  angles.y += THREE.MathUtils.clamp(dx, -120, 120) * LOOK_SENSITIVITY
  angles.x = THREE.MathUtils.clamp(angles.x + THREE.MathUtils.clamp(dy, -120, 120) * LOOK_SENSITIVITY, -1.35, 1.35)
  camera.quaternion.setFromEuler(angles)
  const target = camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(2).add(camera.position)
  controls?.target.copy(target)
  targetPos.current.copy(target)
  targetCamPos.current.copy(camera.position)
}

// Roof/ceiling slabs need a view of the selected face, not their solid center.
// All positions/normals here are in Three.js world coordinates.
export function roofEditingView(selection, camera, viewport, offset = { x: 0, y: 0 }, fov = camera.fov, room = null) {
  if (!['roof', 'ceiling'].includes(selection?.type)) return null
  const object = selection.surfaceObject || selection.object
  if (!object) return null
  object.updateWorldMatrix(true, true)
  const points = []
  object.traverse((mesh) => {
    if (!mesh.isMesh || !mesh.geometry?.attributes.position) return
    const positions = mesh.geometry.attributes.position
    for (let i = 0; i < positions.count; i++) {
      points.push(new THREE.Vector3().fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld))
    }
  })
  const bounds = points.length ? new THREE.Box3().setFromPoints(points) : new THREE.Box3().setFromObject(object)
  if (bounds.isEmpty()) return null
  const corners = []
  for (const x of [bounds.min.x, bounds.max.x]) for (const y of [bounds.min.y, bounds.max.y]) {
    for (const z of [bounds.min.z, bounds.max.z]) corners.push(new THREE.Vector3(x, y, z))
  }
  const center = bounds.getCenter(new THREE.Vector3())
  const normal = new THREE.Vector3(selection.surfaceNormal?.x, selection.surfaceNormal?.y, selection.surfaceNormal?.z)
  if (!Number.isFinite(normal.lengthSq()) || normal.lengthSq() < 1e-8) {
    // Legacy selections have no hit normal. Infer the slab's thin local axis,
    // then transform it with the normal matrix (including non-uniform scale).
    const localBounds = object.geometry?.boundingBox || (() => {
      object.geometry?.computeBoundingBox()
      return object.geometry?.boundingBox
    })()
    const dimensions = localBounds?.getSize(new THREE.Vector3()) || bounds.getSize(new THREE.Vector3())
    const axis = ['x', 'y', 'z'].sort((a, b) => dimensions[a] - dimensions[b])[0]
    normal.set(0, 0, 0)[axis] = 1
    if (localBounds) normal.applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(object.matrixWorld))
  }
  normal.normalize()
  const ceiling = selection.type === 'ceiling'
  if ((ceiling && normal.y > 0) || (!ceiling && normal.y < 0)) normal.negate()
  if (Math.abs(normal.y) < 1e-5 && normal.dot(camera.position.clone().sub(center)) < 0) normal.negate()

  const hit = selection.hitPoint
  const surfacePoint = hit && [hit.x, hit.y, hit.z].every(Number.isFinite)
    ? new THREE.Vector3(hit.x, hit.y, hit.z)
    : (points.length ? points : corners).reduce((best, point) => point.dot(normal) > best.dot(normal) ? point : best)
  const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(normal, surfacePoint)
  const tolerance = Math.max(bounds.getSize(new THREE.Vector3()).length() * 1e-5, 1e-5)
  const facePoints = points.filter((point) => Math.abs(plane.distanceToPoint(point)) <= tolerance)
  const faceBounds = facePoints.length >= 3 ? new THREE.Box3().setFromPoints(facePoints) : bounds
  const target = plane.projectPoint(faceBounds.getCenter(new THREE.Vector3()), new THREE.Vector3())
  if (ceiling) {
    // One roof mesh can cover many rooms. Frame only this room's portion of its
    // underside; without room data, retain the clicked spot instead of aiming
    // at the whole-house center.
    const roomFace = faceBounds.clone()
    if (room && [room.x, room.z, room.w, room.l].every(Number.isFinite)) {
      roomFace.min.x = Math.max(roomFace.min.x, room.x - room.w / 2)
      roomFace.max.x = Math.min(roomFace.max.x, room.x + room.w / 2)
      roomFace.min.z = Math.max(roomFace.min.z, room.z - room.l / 2)
      roomFace.max.z = Math.min(roomFace.max.z, room.z + room.l / 2)
      if (!roomFace.isEmpty()) roomFace.getCenter(target)
      else target.copy(surfacePoint)
    } else {
      target.copy(surfacePoint)
    }
    // Solve for height at the room's X/Z so pitched ceilings do not shift the
    // target horizontally into a neighbouring room when projecting onto a plane.
    target.y = -(normal.x * target.x + normal.z * target.z + plane.constant) / normal.y
    if (room && !roomFace.isEmpty()) {
      corners.length = 0
      for (const x of [roomFace.min.x, roomFace.max.x]) for (const z of [roomFace.min.z, roomFace.max.z]) {
        corners.push(new THREE.Vector3(x, -(normal.x * x + normal.z * z + plane.constant) / normal.y, z))
      }
    }
  }
  const currentOffset = camera.position.clone().sub(target)
  const tangent = currentOffset.clone().projectOnPlane(normal)
  const tangentLength = tangent.length()
  if (tangentLength < 1e-5) {
    tangent.set(0, 0, 1).transformDirection(object.matrixWorld).projectOnPlane(normal)
    if (tangent.lengthSq() < 1e-8) tangent.set(1, 0, 0).transformDirection(object.matrixWorld).projectOnPlane(normal)
  }
  const diagonal = bounds.getSize(new THREE.Vector3()).length()
  const obliqueness = THREE.MathUtils.clamp(tangentLength / Math.max(Math.abs(currentOffset.dot(normal)), diagonal, 1e-5), 0.15, 1)
  const direction = normal.clone().addScaledVector(tangent.normalize(), obliqueness).normalize()
  if (!ceiling && direction.y <= 0) direction.y = Math.max(normal.y, 0.1)
  direction.normalize()
  const right = new THREE.Vector3().crossVectors(camera.up, direction).normalize()
  const up = new THREE.Vector3().crossVectors(direction, right).normalize()
  const width = Math.max(1, viewport.width), height = Math.max(1, viewport.height)
  const safeX = Math.max(0.05, (width - offset.x * 2 - 48) / width)
  const safeY = Math.max(0.05, (height - offset.y * 2 - 48) / height)
  const tanY = Math.tan(THREE.MathUtils.degToRad(fov / 2))
  const tanX = tanY * camera.aspect
  let distance = camera.near * 4
  for (const corner of corners) {
    const delta = corner.clone().sub(target)
    const depth = delta.dot(direction)
    distance = Math.max(distance, depth + Math.abs(delta.dot(right)) / (tanX * safeX),
      depth + Math.abs(delta.dot(up)) / (tanY * safeY), depth + camera.near * 4)
  }
  distance *= 1.05
  if (ceiling) {
    // Interior focus turns from the existing safe position. Moving toward a
    // slab center can cross walls even if the roof's face normal is correct.
    direction.copy(currentOffset).normalize()
    distance = currentOffset.length()
    right.crossVectors(camera.up, direction).normalize()
    if (right.lengthSq() < 1e-8) right.copy(tangent).cross(direction).normalize()
    up.crossVectors(direction, right).normalize()
    let tangentFov = tanY
    for (const corner of corners) {
      const delta = corner.clone().sub(target)
      const depth = Math.max(camera.near * 2, distance - delta.dot(direction))
      tangentFov = Math.max(tangentFov, Math.abs(delta.dot(up)) / (depth * safeY),
        Math.abs(delta.dot(right)) / (depth * camera.aspect * safeX))
    }
    fov = Math.min(100, THREE.MathUtils.radToDeg(2 * Math.atan(tangentFov)))
  } else {
    distance = Math.max(distance, (bounds.max.y + Math.max(camera.near * 4, diagonal * 0.05) - target.y) / direction.y)
  }
  return { target, position: ceiling ? camera.position.clone() : target.clone().addScaledVector(direction, distance), normal, bounds, fov }
}
