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
