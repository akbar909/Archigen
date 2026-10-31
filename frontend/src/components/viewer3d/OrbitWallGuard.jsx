/* eslint-disable react/prop-types */
import { useLayoutEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { stopCameraBeforeWall } from '../../utils/orbitWallCollision'

const isWallMesh = (object) => {
  for (let node = object; node; node = node.parent) {
    if (node.userData?.archgen_wall_id || node.userData?.archgen_exterior_feature === 'boundary_wall'
      || /(?:^|_)wall(?:_|\.|$)|exterior_boundary_wall/i.test(String(node.name || ''))) return true
  }
  return false
}

export default function OrbitWallGuard({ enabled, controlsRef, targetCamPos }) {
  const { camera, scene } = useThree()
  const previous = useRef(camera.position.clone())
  const walls = useRef([])
  const refresh = useRef(0)
  const wasEnabled = useRef(false)

  useLayoutEffect(() => {
    previous.current.copy(camera.position)
    refresh.current = 0
  }, [enabled, camera])

  useFrame(() => {
    if (!enabled || !wasEnabled.current) {
      wasEnabled.current = enabled
      previous.current.copy(camera.position)
      return
    }
    if (refresh.current-- <= 0) {
      const meshes = []
      scene.traverse((object) => { if (object.isMesh && object.visible && isWallMesh(object)) meshes.push(object) })
      walls.current = meshes
      refresh.current = meshes.length ? 60 : 1
    }
    const safe = stopCameraBeforeWall(previous.current, camera.position, walls.current)
    if (!safe.equals(camera.position)) {
      camera.position.copy(safe)
      targetCamPos.current.copy(safe)
      controlsRef.current?.update()
    }
    previous.current.copy(camera.position)
  })
  return null
}
