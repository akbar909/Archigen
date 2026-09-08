import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Environment, Html, OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Sparkles } from 'lucide-react'

import { useProjectStore } from '../../store'
import RoomVolume from './RoomVolume'
import {
  LandscapeGround,
  ArchitecturalPodium,
  PatioDeck,
  SwimmingPool,
} from './EnvironmentElements'
import {
  CharacterAvatar,
  CameraController,
  OpeningMarker,
  RoomCalloutTag,
} from './CharacterAvatar'
import { BlenderErrorBoundary, BlenderHouseModel, BlenderLoadingFallback } from './BlenderModel'
import ViewerOverlay from './ViewerOverlay'

// ── Main Professional Viewer3D Component ─────────────────────────────
export default function Viewer3D({ design }) {
  const { regenerate3D, isGenerating3D, activeProjectId, activeVersionId } = useProjectStore()

  const glbUrl = design?.glb_url || design?.model_url || null
  // Default to interactive procedural CAD view for guaranteed instant rendering
  const [viewSource, setViewSource] = useState('procedural')

  const handleBlenderError = (err) => {
    console.warn('[Viewer3D] Switching viewSource to procedural due to model load error:', err)
    setViewSource('procedural')
  }

  const [viewMode, setViewMode] = useState('dollhouse')
  const [isNightMode, setIsNightMode] = useState(false)
  const [selectedRoomId, setSelectedRoomId] = useState('overview')

  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showCallouts, setShowCallouts] = useState(true)

  const containerRef = useRef(null)
  const controlsRef = useRef(null)
  const targetPos = useRef(new THREE.Vector3(0, 1.0, 0))
  const targetCamPos = useRef(new THREE.Vector3(22, 22, 28))

  const rooms = useMemo(() => (Array.isArray(design?.rooms) ? design.rooms : []), [design?.rooms])
  const doors = useMemo(() => (Array.isArray(design?.doors) ? design.doors : []), [design?.doors])
  const windows = useMemo(() => (Array.isArray(design?.windows) ? design.windows : []), [design?.windows])

  // House bounding box for initial & overview framing
  const houseBounds = useMemo(() => {
    if (rooms.length === 0) return { cx: 0, cz: 0, w: 24, l: 24, maxDim: 22, maxZ: 6 }
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity

    rooms.forEach((r) => {
      const rx = Number(r.position?.x) || 0
      const rz = Number(r.position?.z) || 0
      const rw = (Number(r.width) || 8) / 2
      const rl = (Number(r.length) || 8) / 2
      minX = Math.min(minX, rx - rw)
      maxX = Math.max(maxX, rx + rw)
      minZ = Math.min(minZ, rz - rl)
      maxZ = Math.max(maxZ, rz + rl)
    })

    const w = maxX - minX
    const l = maxZ - minZ
    const cx = (minX + maxX) / 2
    const cz = (minZ + maxZ) / 2
    const maxDim = Math.max(w, l + 12, 24)
    return { cx, cz, w, l, maxDim, minX, maxX, minZ, maxZ }
  }, [rooms])

  // Find active room bounds
  const currentRoom = useMemo(() => {
    return rooms.find((r) => r.id === selectedRoomId) || rooms[0] || null
  }, [rooms, selectedRoomId])

  // Character movement state
  const [charPos, setCharPos] = useState({ x: 0, y: 0.1, z: 0 })
  const [charRot, setCharRot] = useState(0)
  const [isMoving, setIsMoving] = useState(false)
  const [walkCycle, setWalkCycle] = useState(0)
  const keysRef = useRef({ w: false, a: false, s: false, d: false })

  // Mouse look state & angles
  const [isMouseLookLocked, setIsMouseLookLocked] = useState(false)
  const isMouseLockedRef = useRef(false)
  const yawRef = useRef(0)
  const pitchRef = useRef(0)

  // Toggle pointer lock for mouse look
  const toggleMouseLook = () => {
    if (viewMode !== 'walkthrough') return
    if (!document.pointerLockElement) {
      containerRef.current?.requestPointerLock?.()
    } else {
      document.exitPointerLock?.()
    }
  }

  // Pointer lock change listener
  useEffect(() => {
    const handlePointerLockChange = () => {
      const isLocked = document.pointerLockElement === containerRef.current
      setIsMouseLookLocked(isLocked)
      isMouseLockedRef.current = isLocked
      if (controlsRef.current) {
        controlsRef.current.enableRotate = !isLocked
      }
    }
    document.addEventListener('pointerlockchange', handlePointerLockChange)
    return () => document.removeEventListener('pointerlockchange', handlePointerLockChange)
  }, [])

  // Mouse move handler for look direction
  useEffect(() => {
    const onMouseMove = (e) => {
      if (!isMouseLockedRef.current || viewMode !== 'walkthrough') return

      const sensitivity = 0.0003
      yawRef.current += e.movementX * sensitivity
      pitchRef.current -= e.movementY * sensitivity

      const maxPitch = Math.PI / 2.15
      pitchRef.current = Math.max(-maxPitch, Math.min(maxPitch, pitchRef.current))

      if (controlsRef.current?.object) {
        const cam = controlsRef.current.object
        const cosPitch = Math.cos(pitchRef.current)
        const sinPitch = Math.sin(pitchRef.current)
        const cosYaw = Math.cos(yawRef.current)
        const sinYaw = Math.sin(yawRef.current)

        const lookDir = new THREE.Vector3(
          sinYaw * cosPitch,
          sinPitch,
          -cosYaw * cosPitch
        )

        controlsRef.current.target.copy(cam.position).add(lookDir.multiplyScalar(2.0))
        targetPos.current.copy(controlsRef.current.target)
      }
    }

    window.addEventListener('mousemove', onMouseMove)
    return () => window.removeEventListener('mousemove', onMouseMove)
  }, [viewMode])

  // Initialize and auto-frame complete house
  useEffect(() => {
    if (rooms.length > 0) {
      const first = rooms[0]
      const fx = Number(first.position?.x) || 0
      const fz = Number(first.position?.z) || 0
      setCharPos({ x: fx, y: 0.1, z: fz })
      setSelectedRoomId('overview')

      const { cx, cz, maxDim } = houseBounds
      targetPos.current.set(cx, 1.0, cz + 2.0)
      targetCamPos.current.set(cx + maxDim * 0.95, maxDim * 1.05, cz + maxDim * 1.15)
    }
  }, [design, rooms, houseBounds])

  // Keyboard navigation & Ctrl key for mouse toggle
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Control') {
        e.preventDefault()
        toggleMouseLook()
        return
      }

      const k = e.key.toLowerCase()
      if (['w', 'arrowup'].includes(k)) keysRef.current.w = true
      if (['s', 'arrowdown'].includes(k)) keysRef.current.s = true
      if (['a', 'arrowleft'].includes(k)) keysRef.current.a = true
      if (['d', 'arrowright'].includes(k)) keysRef.current.d = true
    }
    const onKeyUp = (e) => {
      const k = e.key.toLowerCase()
      if (['w', 'arrowup'].includes(k)) keysRef.current.w = false
      if (['s', 'arrowdown'].includes(k)) keysRef.current.s = false
      if (['a', 'arrowleft'].includes(k)) keysRef.current.a = false
      if (['d', 'arrowright'].includes(k)) keysRef.current.d = false
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [viewMode])

  // Movement loop with non-inverted natural WASD strafe & forward/back
  useEffect(() => {
    let animId
    const speed = 0.14

    const update = () => {
      const { w, a, s, d } = keysRef.current

      if (w || s || a || d) {
        setIsMoving(true)
        setWalkCycle((c) => c + 0.28)

        if (viewMode === 'walkthrough' && controlsRef.current?.object) {
          const cam = controlsRef.current.object

          const forward = new THREE.Vector3()
          cam.getWorldDirection(forward)
          forward.y = 0
          forward.normalize()

          const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize()

          const move = new THREE.Vector3(0, 0, 0)
          if (w) move.add(forward)
          if (s) move.sub(forward)
          if (d) move.add(right)
          if (a) move.sub(right)

          if (move.lengthSq() > 0) {
            move.normalize().multiplyScalar(speed)

            const curCamX = cam.position.x
            const curCamZ = cam.position.z
            const nextCamX = curCamX + move.x
            const nextCamZ = curCamZ + move.z

            const targetRoom = rooms.find((r) => {
              const rx = Number(r.position?.x) || 0
              const rz = Number(r.position?.z) || 0
              const rw = (Number(r.width) || 8) / 2 - 0.35
              const rl = (Number(r.length) || 8) / 2 - 0.35
              return nextCamX >= rx - rw && nextCamX <= rx + rw && nextCamZ >= rz - rl && nextCamZ <= rz + rl
            })

            if (targetRoom || rooms.length === 0) {
              cam.position.add(move)
              controlsRef.current.target.add(move)
              targetCamPos.current.copy(cam.position)
              targetPos.current.copy(controlsRef.current.target)

              setCharPos({ x: cam.position.x, y: 0.1, z: cam.position.z })
            }
          }
        } else {
          let moveX = 0
          let moveZ = 0
          if (w) moveZ -= speed
          if (s) moveZ += speed
          if (a) moveX -= speed
          if (d) moveX += speed

          if (moveX !== 0 || moveZ !== 0) {
            const targetRot = Math.atan2(moveX, moveZ) + Math.PI
            setCharRot(targetRot)

            setCharPos((prev) => {
              const nextX = prev.x + moveX
              const nextZ = prev.z + moveZ

              const targetRoom = rooms.find((r) => {
                const rx = Number(r.position?.x) || 0
                const rz = Number(r.position?.z) || 0
                const rw = (Number(r.width) || 8) / 2 - 0.45
                const rl = (Number(r.length) || 8) / 2 - 0.45
                return nextX >= rx - rw && nextX <= rx + rw && nextZ >= rz - rl && nextZ <= rz + rl
              })

              if (targetRoom || rooms.length === 0) {
                targetPos.current.set(nextX, 1.0, nextZ)
                return { x: nextX, y: 0.1, z: nextZ }
              }
              return prev
            })
          }
        }
      } else {
        setIsMoving(false)
      }

      animId = requestAnimationFrame(update)
    }

    animId = requestAnimationFrame(update)
    return () => cancelAnimationFrame(animId)
  }, [rooms, viewMode, currentRoom])

  // Select room camera jump
  const handleSelectRoom = (room) => {
    setSelectedRoomId(room.id)
    const rx = Number(room.position?.x) || 0
    const ry = Number(room.position?.y) || 0
    const rz = Number(room.position?.z) || 0
    setCharPos({ x: rx, y: ry + 0.1, z: rz })

    if (viewMode === 'walkthrough') {
      yawRef.current = 0
      pitchRef.current = 0
      targetCamPos.current.set(rx, ry + 1.65, rz + 0.2)
      targetPos.current.set(rx, ry + 1.6, rz - 2.0)
      if (controlsRef.current) {
        controlsRef.current.object.position.set(rx, ry + 1.65, rz + 0.2)
        controlsRef.current.target.set(rx, ry + 1.6, rz - 2.0)
        controlsRef.current.update()
      }
    } else if (viewMode === 'plan') {
      targetPos.current.set(rx, ry, rz)
      targetCamPos.current.set(rx, ry + 22, rz + 0.01)
    } else {
      targetPos.current.set(rx, ry + 1.0, rz)
      targetCamPos.current.set(rx + 8, ry + 9, rz + 9)
    }
  }

  // View mode switcher
  const handleModeChange = (mode) => {
    if (mode !== 'walkthrough' && document.pointerLockElement) {
      document.exitPointerLock?.()
    }
    setViewMode(mode)
    const { cx, cz, maxDim } = houseBounds

    if (mode === 'plan') {
      targetPos.current.set(cx, 0, cz + 2.0)
      targetCamPos.current.set(cx, maxDim * 1.8, cz + 2.01)
      if (controlsRef.current) {
        controlsRef.current.maxDistance = 120
      }
    } else if (mode === 'dollhouse') {
      targetPos.current.set(cx, 1.0, cz + 2.0)
      targetCamPos.current.set(cx + maxDim * 0.95, maxDim * 1.05, cz + maxDim * 1.15)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 95
      }
    } else if (mode === 'walkthrough') {
      yawRef.current = 0
      pitchRef.current = 0
      const cur = currentRoom || rooms[0]
      const rx = Number(cur?.position?.x) || charPos.x
      const ry = Number(cur?.position?.y) || 0
      const rz = Number(cur?.position?.z) || charPos.z
      setCharPos({ x: rx, y: ry + 0.1, z: rz })

      targetCamPos.current.set(rx, ry + 1.65, rz + 0.2)
      targetPos.current.set(rx, ry + 1.6, rz - 2.0)

      if (controlsRef.current) {
        controlsRef.current.object.position.set(rx, ry + 1.65, rz + 0.2)
        controlsRef.current.target.set(rx, ry + 1.6, rz - 2.0)
        controlsRef.current.minDistance = 0.1
        controlsRef.current.maxDistance = 6.0
        controlsRef.current.update()
      }
    }
  }

  // Fullscreen handler
  const toggleFullscreen = () => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {})
      setIsFullscreen(true)
    } else {
      document.exitFullscreen().catch(() => {})
      setIsFullscreen(false)
    }
  }

  // Reset Camera to complete house view
  const handleResetCamera = () => {
    setSelectedRoomId('overview')
    const { cx, cz, maxDim } = houseBounds
    targetPos.current.set(cx, 1.0, cz + 2.0)
    targetCamPos.current.set(cx + maxDim * 0.95, maxDim * 1.05, cz + maxDim * 1.15)
  }

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: 0,
        borderRadius: isFullscreen ? 0 : 'var(--radius-lg)',
        overflow: 'hidden',
        background: isNightMode ? '#070a10' : '#0b0f17',
        boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      }}
    >
      <Canvas
        shadows
        dpr={[1, 1.75]}
        camera={{ position: [22, 22, 28], fov: 44, near: 0.1, far: 350 }}
        gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
      >
        <color attach="background" args={[isNightMode ? '#060911' : '#0a0e17']} />

        <ambientLight intensity={isNightMode ? 0.35 : 0.75} color={isNightMode ? '#1e293b' : '#f8fafc'} />
        <hemisphereLight
          intensity={isNightMode ? 0.3 : 0.6}
          groundColor="#090d16"
          color={isNightMode ? '#334155' : '#e0f2fe'}
        />

        <directionalLight
          position={[28, 42, 24]}
          intensity={isNightMode ? 0.5 : 2.0}
          color={isNightMode ? '#93c5fd' : '#fffbeb'}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-left={-45}
          shadow-camera-right={45}
          shadow-camera-top={45}
          shadow-camera-bottom={-45}
          shadow-bias={-0.00005}
          shadow-normalBias={0.03}
        />

        {/* ── Architectural Landscape Grounds (Villa staging for multi-room homes in 3D views) ── */}
        {viewMode !== 'plan' && (
          <>
            <ArchitecturalPodium bounds={houseBounds} />
            {rooms.length > 1 && (
              <>
                <LandscapeGround bounds={houseBounds} />
                <PatioDeck
                  position={[0, 0.0, (houseBounds.maxZ || 4.0) + 2.5]}
                  width={Math.max(houseBounds.w || 14, 15)}
                  length={4.5}
                />
                <SwimmingPool
                  position={[2.5, -0.15, (houseBounds.maxZ || 4.0) + 7.8]}
                  width={10.5}
                  length={4.8}
                  depth={1.5}
                  isNightMode={isNightMode}
                />
              </>
            )}
          </>
        )}

        {/* ── Architectural House Model: Blender GLB or Procedural CAD ── */}
        {viewSource === 'blender' && glbUrl ? (
          <BlenderErrorBoundary key={glbUrl} onError={handleBlenderError}>
            <Suspense fallback={<BlenderLoadingFallback onFallbackToCad={() => setViewSource('procedural')} />}>
              <BlenderHouseModel url={glbUrl} />
            </Suspense>
          </BlenderErrorBoundary>
        ) : (
          <>
            {/* Contiguous Architectural Rooms */}
            {rooms.map((room, idx) => {
              const topLevelFurniture = Array.isArray(design?.furniture)
                ? design.furniture.filter((f) => f.roomId === room.id)
                : []
              const roomFurniture = topLevelFurniture.length > 0 ? topLevelFurniture : room.furniture

              return (
                <RoomVolume
                  key={room.id || `room-${idx}`}
                  room={room}
                  furniture={roomFurniture}
                  viewMode={viewMode}
                  isSelected={selectedRoomId === room.id}
                  isNightMode={isNightMode}
                />
              )
            })}

            {/* Floating Architectural Callout Pins */}
            {showCallouts && viewMode !== 'walkthrough' && rooms.map((room) => (
              <RoomCalloutTag
                key={`tag-${room.id || room.type}`}
                room={room}
                isSelected={selectedRoomId === room.id}
                onClick={() => handleSelectRoom(room)}
              />
            ))}

            {doors.map((door, idx) => (
              <OpeningMarker key={door.id || `door-${idx}`} item={door} kind="door" />
            ))}
            {windows.map((win, idx) => (
              <OpeningMarker key={win.id || `win-${idx}`} item={win} kind="window" />
            ))}
          </>
        )}

        {/* Walkthrough Avatar (Hidden in first-person walkthrough to avoid blocking camera) */}
        <CharacterAvatar
          position={charPos}
          rotation={charRot}
          isMoving={isMoving}
          walkCycle={walkCycle}
          isVisible={viewMode !== 'walkthrough'}
        />

        <CameraController controlsRef={controlsRef} targetPos={targetPos} targetCamPos={targetCamPos} viewMode={viewMode} />

        <OrbitControls
          ref={controlsRef}
          enableDamping
          dampingFactor={0.08}
          minDistance={viewMode === 'walkthrough' ? 0.1 : 2}
          maxDistance={viewMode === 'walkthrough' ? 4.5 : 95}
          maxPolarAngle={viewMode === 'plan' ? 0.05 : Math.PI / 2.05}
        />
        <Environment preset={isNightMode ? 'night' : 'city'} />
      </Canvas>

      <ViewerOverlay
        viewMode={viewMode}
        onModeChange={handleModeChange}
        viewSource={viewSource}
        onViewSourceChange={setViewSource}
        glbUrl={glbUrl}
        isGenerating3D={isGenerating3D}
        onRegenerate3D={() => regenerate3D(activeProjectId, activeVersionId)}
        showCallouts={showCallouts}
        onToggleCallouts={() => setShowCallouts(!showCallouts)}
        isMouseLookLocked={isMouseLookLocked}
        onToggleMouseLook={toggleMouseLook}
        isNightMode={isNightMode}
        onToggleNightMode={() => setIsNightMode(!isNightMode)}
        onResetCamera={handleResetCamera}
        isFullscreen={isFullscreen}
        onToggleFullscreen={toggleFullscreen}
        rooms={rooms}
        doors={doors}
        windows={windows}
        design={design}
        selectedRoomId={selectedRoomId}
        onSelectRoom={handleSelectRoom}
      />
    </div>
  )
}
