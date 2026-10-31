import * as THREE from 'three'

export function stopCameraBeforeWall(previous, desired, wallMeshes, clearance = 0.12) {
  const movement = desired.clone().sub(previous)
  const distance = movement.length()
  if (distance < 0.0001 || !wallMeshes.length) return desired.clone()
  const direction = movement.normalize()
  const raycaster = new THREE.Raycaster(previous, direction, 0.001, distance)
  const hit = raycaster.intersectObjects(wallMeshes, false)[0]
  if (!hit) return desired.clone()
  return hit.point.clone().addScaledVector(direction, -clearance)
}
