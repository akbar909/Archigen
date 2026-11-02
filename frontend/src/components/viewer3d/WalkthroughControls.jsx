/* eslint-disable react/prop-types */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { nearestWalkablePosition, walkableSurface } from '../../utils/navigation'
import { turnCameraInPlace } from '../../utils/cameraLook'

export function WalkthroughDragLook({ enabled, isTransforming, controlsRef, targetPos, targetCamPos, onDragChange }) {
  const { camera, gl } = useThree()
  const transforming = useRef(isTransforming)
  transforming.current = isTransforming
  useEffect(() => {
    if (!enabled) return undefined
    const canvas = gl.domElement
    const previousTouchAction = canvas.style.touchAction
    canvas.style.touchAction = 'none'
    let pointer = null
    const touches = new Set()
    const down = (event) => {
      if (event.pointerType === 'touch') {
        touches.add(event.pointerId)
        // A second finger belongs to pinch zoom, not camera rotation.
        if (touches.size > 1) { up(); return }
      }
      if (event.button !== 0 || pointer || transforming.current) return
      pointer = { id: event.pointerId, x: event.clientX, y: event.clientY,
        startX: event.clientX, startY: event.clientY, dragging: false }
      canvas.setPointerCapture(event.pointerId)
    }
    const move = (event) => {
      if (!pointer || event.pointerId !== pointer.id || transforming.current) return
      if (event.pointerType === 'mouse' && !(event.buttons & 1)) return
      event.preventDefault()
      const dx = event.clientX - pointer.x, dy = event.clientY - pointer.y
      pointer.x = event.clientX
      pointer.y = event.clientY
      if (!pointer.dragging && Math.hypot(event.clientX - pointer.startX, event.clientY - pointer.startY) < 5) return
      if (!pointer.dragging) { pointer.dragging = true; onDragChange(true) }
      // Touch steers the view toward the finger's direction. Keep the existing
      // panorama-style mouse drag unchanged on desktop.
      const direction = event.pointerType === 'touch' ? -1 : 1
      turnCameraInPlace(camera, dx * direction, dy * direction, controlsRef.current, targetPos, targetCamPos)
    }
    const up = (event) => {
      if (event?.pointerId !== undefined) touches.delete(event.pointerId)
      if (event?.type === 'blur') touches.clear()
      if (event?.pointerId !== undefined && event.pointerId !== pointer?.id) return
      if (pointer?.dragging) onDragChange(false)
      if (pointer && canvas.hasPointerCapture(pointer.id)) canvas.releasePointerCapture(pointer.id)
      pointer = null
    }
    canvas.addEventListener('pointerdown', down)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    window.addEventListener('blur', up)
    canvas.addEventListener('lostpointercapture', up)
    return () => {
      canvas.style.touchAction = previousTouchAction
      canvas.removeEventListener('pointerdown', down)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
      window.removeEventListener('blur', up)
      canvas.removeEventListener('lostpointercapture', up)
      up()
    }
  }, [enabled, camera, gl, controlsRef, targetPos, targetCamPos, onDragChange])
  return null
}

// DOM joystick feeds the same camera-relative movement and collision loop as WASD.
export function WalkthroughJoystick({ movementRef }) {
  const pointer = useRef(null)
  const pad = useRef(null)
  const reset = useCallback(() => {
    pointer.current = null
    movementRef.current = { x: 0, y: 0 }
    pad.current?.style.setProperty('--stick-x', '0px')
    pad.current?.style.setProperty('--stick-y', '0px')
  }, [movementRef])
  useEffect(() => {
    const clear = () => { movementRef.current = { x: 0, y: 0 }; pointer.current = null }
    window.addEventListener('blur', reset)
    document.addEventListener('visibilitychange', reset)
    return () => {
      clear()
      window.removeEventListener('blur', reset)
      document.removeEventListener('visibilitychange', reset)
    }
  }, [movementRef, reset])
  const move = (event) => {
    if (pointer.current !== event.pointerId) return
    event.preventDefault()
    const rect = event.currentTarget.getBoundingClientRect()
    const radius = rect.width * 0.32
    const dx = event.clientX - rect.left - rect.width / 2
    const dy = event.clientY - rect.top - rect.height / 2
    const length = Math.hypot(dx, dy)
    const scale = Math.min(1, radius / Math.max(1, length))
    const x = dx * scale, y = dy * scale
    movementRef.current = length < radius * 0.12 ? { x: 0, y: 0 } : { x: x / radius, y: y / radius }
    pad.current.style.setProperty('--stick-x', `${x}px`)
    pad.current.style.setProperty('--stick-y', `${y}px`)
  }
  return <div className="walkthrough-touch-controls">
    <div ref={pad} className="walkthrough-joystick" role="group" aria-label="Movement joystick: drag to walk"
      onPointerDown={(event) => {
        if (pointer.current !== null) return
        pointer.current = event.pointerId
        event.currentTarget.setPointerCapture(event.pointerId)
        move(event)
      }} onPointerMove={move}
      onPointerUp={(event) => { if (event.pointerId === pointer.current) reset() }}
      onPointerCancel={(event) => { if (event.pointerId === pointer.current) reset() }}
      onLostPointerCapture={reset} onContextMenu={(event) => event.preventDefault()}>
      <span className="joystick-directions" aria-hidden="true">↕<br />↔</span><span className="joystick-thumb" />
    </div>
    <span className="walkthrough-touch-hint">Drag to look · Pinch to zoom</span>
  </div>
}

export function WalkthroughLens({ enabled, editing, interactive = true }) {
  const { camera, size, gl } = useThree()
  const original = useRef(null)
  const zoomTarget = useRef(null)
  const [touch, setTouch] = useState(() => window.matchMedia('(any-pointer: coarse)').matches)
  useEffect(() => {
    const query = window.matchMedia('(any-pointer: coarse)')
    const change = () => setTouch(query.matches)
    query.addEventListener('change', change)
    return () => query.removeEventListener('change', change)
  }, [])
  useEffect(() => {
    zoomTarget.current = null
    if (editing) return
    // A moderate vertical FOV gives portrait phones room context without an
    // extreme horizontal angle in landscape. Restore the exterior lens on exit.
    if (enabled) {
      original.current ??= { fov: camera.fov, near: camera.near }
      camera.fov = touch && size.width < size.height ? 78 : 64
      camera.near = touch ? 0.03 : original.current.near
      camera.updateProjectionMatrix()
    } else if (original.current) {
      Object.assign(camera, original.current)
      original.current = null
      camera.updateProjectionMatrix()
    }
  }, [camera, enabled, editing, touch, size.width, size.height])
  useEffect(() => {
    if (!enabled || !interactive) return undefined
    const canvas = gl.domElement
    let pinchDistance = null
    const zoom = (scale) => {
      // Change the lens only: never dolly through furniture or room boundaries.
      canvas.dispatchEvent(new Event('viewer-lens-change'))
      const fov = zoomTarget.current ?? camera.fov
      zoomTarget.current = Math.max(40, Math.min(90,
        2 * Math.atan(Math.tan(fov * Math.PI / 360) * scale) * 180 / Math.PI))
    }
    const wheel = (event) => {
      event.preventDefault()
      const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size.height : 1)
      zoom(Math.exp(Math.max(-200, Math.min(200, pixels)) * 0.002))
    }
    // Only fingers starting on the canvas count; the joystick is independent.
    const distance = (event) => event.targetTouches.length === 2
      ? Math.hypot(event.targetTouches[0].clientX - event.targetTouches[1].clientX,
        event.targetTouches[0].clientY - event.targetTouches[1].clientY) : null
    const start = (event) => { pinchDistance = distance(event) }
    const move = (event) => {
      const next = distance(event)
      if (next && pinchDistance) {
        event.preventDefault()
        zoom(pinchDistance / next)
      }
      pinchDistance = next
    }
    const reset = () => { pinchDistance = null; zoomTarget.current = null }
    canvas.addEventListener('wheel', wheel, { passive: false })
    canvas.addEventListener('touchstart', start, { passive: true })
    canvas.addEventListener('touchmove', move, { passive: false })
    canvas.addEventListener('touchend', start)
    canvas.addEventListener('touchcancel', reset)
    window.addEventListener('blur', reset)
    return () => {
      reset()
      canvas.removeEventListener('wheel', wheel)
      canvas.removeEventListener('touchstart', start)
      canvas.removeEventListener('touchmove', move)
      canvas.removeEventListener('touchend', start)
      canvas.removeEventListener('touchcancel', reset)
      window.removeEventListener('blur', reset)
    }
  }, [enabled, interactive, camera, gl, size.height, editing])
  useFrame((_, delta) => {
    if (zoomTarget.current === null) return
    camera.fov += (zoomTarget.current - camera.fov) * (1 - Math.exp(-16 * delta))
    if (Math.abs(camera.fov - zoomTarget.current) < 0.01) {
      camera.fov = zoomTarget.current
      zoomTarget.current = null
    }
    camera.updateProjectionMatrix()
  })
  return null
}

export function WalkthroughCameraGuard({ enabled, navigation, level, controlsRef, targetPos, targetCamPos }) {
  const { camera } = useThree()
  useFrame(() => {
    if (!enabled || !navigation?.rooms.length) return
    const height = camera.position.y - 1.65
    if (walkableSurface(navigation, camera.position.x, camera.position.z, level, height)) return
    const safe = nearestWalkablePosition(navigation, camera.position.x, camera.position.z, level, height)
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
