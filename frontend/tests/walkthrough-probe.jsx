import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'

export default function WalkProbe({ controlsRef, targetPos, targetCamPos, touchMoveRef, onSelectRoom, onModeChange, level, selection }) {
  const { camera, scene, gl } = useThree()
  const destination = useRef(null)
  useEffect(() => {
    window.walkState = () => ({ position: camera.position.toArray(), direction: camera.getWorldDirection(new THREE.Vector3()).toArray(), level, selection: selection && { type: selection.type, wallFace: selection.wallFace, normal: selection.surfaceNormal } })
    window.walkSelect = index => onSelectRoom(window.walkDesign().rooms[index])
    window.walkMode = onModeChange
    window.walkToward = (x, z) => { destination.current = { x, z }; window.walkArrived = false }
    window.walkPanelBounds = () => {
      let root
      scene.traverse(n => { if (n.userData?.entityId && n.visible) root = n })
      if (!root) return null
      const b = new THREE.Box3().setFromObject(root, true)
      return { min: b.min.toArray(), max: b.max.toArray() }
    }
    window.walkFacade = () => {
      const p = new THREE.Vector3(2.3, 4.5, .1)
      camera.position.set(2.3, 4.5, 6); camera.lookAt(p); camera.updateMatrixWorld(true)
      controlsRef.current.target.copy(p); targetPos.current.copy(p); targetCamPos.current.copy(camera.position)
      const projected = p.project(camera), r = gl.domElement.getBoundingClientRect()
      return { x: r.left + (projected.x + 1) * r.width / 2, y: r.top + (1 - projected.y) * r.height / 2 }
    }
  }, [camera, level, selection, onSelectRoom, onModeChange, scene, gl, controlsRef, targetPos, targetCamPos])
  useFrame(() => {
    const target = destination.current
    if (!target) return
    const distance = Math.hypot(target.x - camera.position.x, target.z - camera.position.z)
    if (distance < .035) { touchMoveRef.current = { x: 0, y: 0 }; destination.current = null; window.walkArrived = true; return }
    const look = new THREE.Vector3(target.x, camera.position.y, target.z)
    camera.lookAt(look); controlsRef.current.target.copy(look); targetPos.current.copy(look)
    touchMoveRef.current = { x: 0, y: -Math.min(.6, distance * 2) }
  })
  return null
}
