/* eslint-disable react/prop-types */
import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { editorViewportOffset } from '../../utils/sceneEditing'
import { roofEditingView } from '../../utils/cameraLook'

export default function EditorCameraFraming({
  selection,
  ceilingRoom = null,
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
  const refocusRoof = useRef(null)
  const lastTrackedTarget = useRef(new THREE.Vector3())
  const active = enabled && Boolean(selection?.object)
  const roofSelected = ['roof', 'ceiling'].includes(selection?.type)

  useEffect(() => {
    // A deliberate zoom takes over from automatic selection framing.
    const stop = () => { animation.current = null }
    const canvas = gl.domElement
    canvas.addEventListener('viewer-lens-change', stop)
    return () => canvas.removeEventListener('viewer-lens-change', stop)
  }, [gl])

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
      const next = editorViewportOffset(canvas.getBoundingClientRect(), drawer?.getBoundingClientRect())
      const changed = Math.abs(next.x - desiredOffset.current.x) + Math.abs(next.y - desiredOffset.current.y) > 1
      desiredOffset.current = next
      if (changed) refocusRoof.current?.()
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
    if (roofSelected) {
      const focus = () => {
        const view = roofEditingView({ type: selection.type, object: selection.object, surfaceObject: selection.surfaceObject,
          surfaceNormal: selection.surfaceNormal, hitPoint: selection.hitPoint }, camera,
          { width: size.width, height: size.height }, desiredOffset.current, savedFov.current ?? camera.fov, ceilingRoom)
        if (!view) return
        const controls = controlsRef.current
        if (controls) {
          // Clear accumulated orbit damping before taking ownership of this focus.
          const damping = controls.enableDamping
          controls.enableDamping = false
          controls.update?.()
          controls.enableDamping = damping
        }
        const startPosition = camera.position.clone()
        const distance = Math.max(camera.near * 4, startPosition.distanceTo(view.target))
        animation.current = {
          start: camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(distance).add(startPosition),
          target: view.target,
          startPosition,
          endPosition: view.position,
          // Rise clear of an exterior slab before moving across its footprint.
          abovePosition: selection.type === 'roof' ? new THREE.Vector3(startPosition.x,
            Math.max(startPosition.y, view.position.y, view.bounds.max.y + camera.near * 4), startPosition.z) : null,
          startFov: camera.fov, targetFov: view.fov, elapsed: 0,
        }
        targetPos.current.copy(view.target)
        targetCamPos.current.copy(view.position)
      }
      refocusRoof.current = focus
      focus()
      return () => { refocusRoof.current = null }
    }
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
    selection?.surfaceNormal,
    selection?.surfaceObject,
    roofSelected,
    ceilingRoom,
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

    // Existing furniture/surface tracking turns in place. Roof focus owns its
    // position and face target so tracking cannot replace them with a slab center.
    // Do not turn camera during active gizmo mouse-drag to keep mouse movement at steady 1:1 speed
    if (!roofSelected && selection?.object && !isTransforming) {
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
    current.elapsed = Math.min(1, current.elapsed + delta / (current.endPosition ? 0.65 : 0.35))
    const t = current.elapsed * current.elapsed * (3 - 2 * current.elapsed)
    if (current.endPosition) {
      if (current.abovePosition) {
        const firstLeg = current.elapsed < 0.35
        const amount = firstLeg ? current.elapsed / 0.35 : (current.elapsed - 0.35) / 0.65
        const smooth = amount * amount * (3 - 2 * amount)
        camera.position.lerpVectors(firstLeg ? current.startPosition : current.abovePosition,
          firstLeg ? current.abovePosition : current.endPosition, smooth)
      } else {
        camera.position.lerpVectors(current.startPosition, current.endPosition, t)
      }
    }
    const look = current.start.clone().lerp(current.target, t)
    camera.fov = THREE.MathUtils.lerp(current.startFov, current.targetFov, t)
    camera.updateProjectionMatrix()
    camera.lookAt(look)
    controlsRef.current?.target.copy(look)
    if (current.endPosition) {
      targetCamPos.current.copy(camera.position)
      targetPos.current.copy(look)
    }
    if (current.elapsed === 1) animation.current = null
  })
  return null
}
