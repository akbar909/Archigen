/* eslint-disable react/prop-types */
import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { editorViewportOffset } from '../../utils/sceneEditing'

export default function EditorCameraFraming({
  selection,
  enabled,
  controlsRef,
  targetPos,
  targetCamPos,
  viewMode = 'dollhouse',
  isTransforming = false,
  isCameraDragging = false,
}) {
  const { camera, gl, size } = useThree()
  const animation = useRef(null)
  const savedFov = useRef(null)
  const offset = useRef({ x: 0, y: 0 })
  const desiredOffset = useRef({ x: 0, y: 0 })
  const lastTrackedTarget = useRef(new THREE.Vector3())
  const active = enabled && Boolean(selection?.object)

  useEffect(() => {
    if (!active) {
      camera.clearViewOffset()
      if (savedFov.current !== null) camera.fov = savedFov.current
      savedFov.current = null
      camera.updateProjectionMatrix()
      animation.current = null
      offset.current = { x: 0, y: 0 }
      return undefined
    }
    if (savedFov.current === null) savedFov.current = camera.fov
    const canvas = gl.domElement
    const drawer = canvas.closest('.viewer-container')?.querySelector('.interior-editor-drawer')
      || canvas.parentElement?.parentElement?.querySelector('.interior-editor-drawer')
    const update = () => {
      desiredOffset.current = editorViewportOffset(canvas.getBoundingClientRect(), drawer?.getBoundingClientRect())
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(canvas)
    if (drawer) observer.observe(drawer)
    const frame = requestAnimationFrame(update)
    return () => { observer.disconnect(); cancelAnimationFrame(frame) }
  }, [active, camera, gl, size.width, size.height])

  useEffect(() => {
    if (!active || !selection?.object) return
    selection.object.updateWorldMatrix(true, true)
    const bounds = new THREE.Box3().setFromObject(selection.object)
    if (bounds.isEmpty()) return
    const target = selection.type === 'furniture' || !selection.hitPoint
      ? bounds.getCenter(new THREE.Vector3())
      : new THREE.Vector3(selection.hitPoint.x, selection.hitPoint.y, selection.hitPoint.z)

    const distance = camera.position.distanceTo(target)
    if (distance < 0.05) return
    const start = camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(distance).add(camera.position)
    let targetFov = savedFov.current ?? camera.fov
    if (selection.type === 'furniture') {
      const radius = bounds.getBoundingSphere(new THREE.Sphere()).radius
      const safeWidth = Math.max(80, size.width - desiredOffset.current.x * 2 - 48)
      const safeHeight = Math.max(80, size.height - desiredOffset.current.y * 2 - 48)
      const fraction = Math.min(safeHeight / size.height, safeWidth / size.width * camera.aspect)
      const angle = Math.asin(Math.min(0.95, radius / distance))
      targetFov = Math.max(targetFov, Math.min(100, THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(angle) / fraction))))
    }
    animation.current = { start, target, startFov: camera.fov, targetFov, elapsed: 0 }
    targetCamPos.current.copy(camera.position)
    targetPos.current.copy(target)
    lastTrackedTarget.current.copy(target)
  }, [
    active,
    selection?.id,
    selection?.object,
    selection?.type,
    selection?.hitPoint,
    viewMode,
    camera,
    targetPos,
    targetCamPos,
    controlsRef,
    size.width,
    size.height,
  ])

  useEffect(() => () => {
    camera.clearViewOffset()
    if (savedFov.current !== null) camera.fov = savedFov.current
    camera.updateProjectionMatrix()
  }, [camera])

  useFrame((_, delta) => {
    if (!active) return
    const blend = 1 - Math.exp(-12 * delta)
    offset.current.x = THREE.MathUtils.lerp(offset.current.x, desiredOffset.current.x, blend)
    offset.current.y = THREE.MathUtils.lerp(offset.current.y, desiredOffset.current.y, blend)
    camera.setViewOffset(size.width, size.height, offset.current.x, offset.current.y, size.width, size.height)
    if (isTransforming || isCameraDragging) {
      animation.current = null
      return
    }

    // Continuously follow moving object by updating the look direction and orbit target
    // NEVER mutate camera.position so camera can never penetrate walls or go outside the room
    // Do not turn camera during active gizmo mouse-drag to keep mouse movement at steady 1:1 speed
    if (selection?.object && !isTransforming) {
      selection.object.updateWorldMatrix(true, false)
      const currentBounds = new THREE.Box3().setFromObject(selection.object)
      if (!currentBounds.isEmpty()) {
        const currentCenter = currentBounds.getCenter(new THREE.Vector3())
        if (currentCenter.distanceToSquared(lastTrackedTarget.current) > 0.0001) {
          lastTrackedTarget.current.copy(currentCenter)
          targetPos.current.copy(currentCenter)
          const distance = camera.position.distanceTo(currentCenter)
          const start = camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(distance).add(camera.position)
          animation.current = { start, target: currentCenter, startFov: camera.fov, targetFov: camera.fov, elapsed: 0 }
        }
      }
    }

    const current = animation.current
    if (!current) return
    current.elapsed = Math.min(1, current.elapsed + delta / 0.35)
    const t = current.elapsed * current.elapsed * (3 - 2 * current.elapsed)
    const look = current.start.clone().lerp(current.target, t)
    camera.fov = THREE.MathUtils.lerp(current.startFov, current.targetFov, t)
    camera.updateProjectionMatrix()
    camera.lookAt(look)
    controlsRef.current?.target.copy(look)
    if (current.elapsed === 1) animation.current = null
  })
  return null
}
