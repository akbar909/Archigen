/* eslint-disable react/prop-types */
import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { nearestWalkablePoint } from '../../utils/navigation'
import { turnCameraInPlace } from '../../utils/cameraLook'

export function WalkthroughDragLook({ enabled, isTransforming, controlsRef, targetPos, targetCamPos, onDragChange }) {
  const { camera, gl } = useThree()
  const transforming = useRef(isTransforming)
  transforming.current = isTransforming
  useEffect(() => {
    if (!enabled) return undefined
    const canvas = gl.domElement
    let pointer = null
    const down = (event) => {
      if (event.button !== 0) return
      pointer = { id: event.pointerId, x: event.clientX, y: event.clientY,
        startX: event.clientX, startY: event.clientY, dragging: false }
    }
    const move = (event) => {
      if (!pointer || event.pointerId !== pointer.id || transforming.current || !(event.buttons & 1)) return
      const dx = event.clientX - pointer.x, dy = event.clientY - pointer.y
      pointer.x = event.clientX
      pointer.y = event.clientY
      if (!pointer.dragging && Math.hypot(event.clientX - pointer.startX, event.clientY - pointer.startY) < 5) return
      if (!pointer.dragging) { pointer.dragging = true; onDragChange(true) }
      turnCameraInPlace(camera, dx, dy, controlsRef.current, targetPos, targetCamPos)
    }
    const up = () => { if (pointer?.dragging) onDragChange(false); pointer = null }
    canvas.addEventListener('pointerdown', down)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    window.addEventListener('blur', up)
    return () => {
      canvas.removeEventListener('pointerdown', down)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
      window.removeEventListener('blur', up)
      up()
    }
  }, [enabled, camera, gl, controlsRef, targetPos, targetCamPos, onDragChange])
  return null
}

export function WalkthroughCameraGuard({ enabled, navigation, level, controlsRef, targetPos, targetCamPos }) {
  const { camera } = useThree()
  useFrame(() => {
    if (!enabled || !navigation?.rooms.length) return
    const safe = nearestWalkablePoint(navigation, camera.position.x, camera.position.z, level)
    const dx = safe.x - camera.position.x, dz = safe.z - camera.position.z
    if (Math.abs(dx) + Math.abs(dz) < 0.00001) return
    camera.position.x = safe.x
    camera.position.z = safe.z
    if (controlsRef.current) { controlsRef.current.target.x += dx; controlsRef.current.target.z += dz }
    targetPos.current.x += dx
    targetPos.current.z += dz
    targetCamPos.current.copy(camera.position)
  })
  return null
}
