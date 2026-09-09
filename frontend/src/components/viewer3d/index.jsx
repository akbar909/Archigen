import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Environment, Html, OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Loader2, Sparkles } from 'lucide-react'

import { useProjectStore } from '../../store'
import {
  CharacterAvatar,
  CameraController,
} from './CharacterAvatar'
import { BlenderErrorBoundary, BlenderHouseModel, BlenderLoadingFallback } from './BlenderModel'
import ViewerOverlay from './ViewerOverlay'

// ── Main Professional Viewer3D Component ─────────────────────────────
export default function Viewer3D({ design }) {
  const { regenerate3D, isGenerating3D, activeProjectId, activeVersionId } = useProjectStore()

  const glbUrl = design?.glb_url || design?.model_url || null
  // Exclusively use Cloud Blender 3D photorealistic model
  const [viewSource, setViewSource] = useState('blender')

  const handleBlenderError = (err) => {
    console.warn('[Viewer3D] Model load error:', err)
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

  // Real 3D detected room floor slabs from loaded GLB
  const [detectedRooms, setDetectedRooms] = useState([])

  // Helper to get true 3D room position and bounds (from real GLB meshes if available)
  const getRoom3DPosition = (room) => {
    if (!room) return { x: 0, y: 0.1, z: 0, w: 8, l: 8 }
    // 1. Match by room id
    let match = detectedRooms.find((d) => d.meshId === room.id || d.name === `floor_${room.id}`)
    // 2. Match by clean type name
    if (!match && room.type) {
      const cleanType = String(room.type).toLowerCase().replace(/[\s_]+/g, '')
      match = detectedRooms.find((d) => d.name.toLowerCase().replace(/[\s_]+/g, '').includes(cleanType))
    }
    // 3. Match by index in rooms array
    if (!match) {
      const roomIdx = rooms.findIndex((r) => r.id === room.id || r.type === room.type)
      if (roomIdx >= 0 && roomIdx < detectedRooms.length) {
        match = detectedRooms[roomIdx]
      }
    }
    // 4. Match by horizontal X alignment
    if (!match && room.position) {
      const rx = Number(room.position.x) || 0
      match = detectedRooms.find((d) => Math.abs(d.center.x - rx) < 1.0)
    }

    if (match) {
      return {
        x: match.center.x,
        y: match.center.y,
        z: match.center.z,
        w: match.size.x,
        l: match.size.z,
      }
    }

    return {
      x: Number(room.position?.x) || 0,
      y: Number(room.position?.y) || 0,
      z: Number(room.position?.z) || 0,
      w: Number(room.width) || 8,
      l: Number(room.length) || 8,
    }
  }

  // Collect all doors across design (top-level + per-room) for doorway passage detection
  const allDoors = useMemo(() => {
    const list = [...doors]
    rooms.forEach((r) => {
      if (Array.isArray(r.doors)) {
        r.doors.forEach((d) => {
          const pos = getRoom3DPosition(r)
          const rx = pos.x
          const rz = pos.z
          const dpos = d.position || {}
          const dx = Number(dpos.x !== undefined ? dpos.x : (dpos[0] || 0))
          const dz = Number(dpos.z !== undefined ? dpos.z : (dpos[1] || 0))
          list.push({
            ...d,
            worldX: rx + dx,
            worldZ: rz + dz,
            width: Number(d.dimensions?.w || d.width || 1.0),
          })
        })
      }
    })
    return list
  }, [doors, rooms, detectedRooms])

  // House bounding box for initial & overview framing
  const houseBounds = useMemo(() => {
    if (rooms.length === 0 && detectedRooms.length === 0) {
      return { cx: 0, cz: 0, w: 24, l: 24, maxDim: 22, maxZ: 6 }
    }
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity

    if (detectedRooms.length > 0) {
      detectedRooms.forEach((d) => {
        const hw = d.size.x / 2
        const hl = d.size.z / 2
        minX = Math.min(minX, d.center.x - hw)
        maxX = Math.max(maxX, d.center.x + hw)
        minZ = Math.min(minZ, d.center.z - hl)
        maxZ = Math.max(maxZ, d.center.z + hl)
      })
    } else {
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
    }

    const w = maxX - minX
    const l = maxZ - minZ
    const cx = (minX + maxX) / 2
    const cz = (minZ + maxZ) / 2
    const maxDim = Math.max(w, l + 12, 24)
    return { cx, cz, w, l, maxDim, minX, maxX, minZ, maxZ }
  }, [rooms, detectedRooms])

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

            // Collision check: inside room with 0.15m clearance OR passing through doorway threshold
            const isWalkable = (nx, nz, pad = 0.15) => {
              const inRoom = (rooms.length > 0 ? rooms : detectedRooms).some((r) => {
                const pos = getRoom3DPosition(r)
                const rx = pos.x
                const rz = pos.z
                const rw = pos.w / 2 - pad
                const rl = pos.l / 2 - pad
                return nx >= rx - rw && nx <= rx + rw && nz >= rz - rl && nz <= rz + rl
              })
              if (inRoom) return true

              const nearDoor = allDoors.some((d) => {
                const dx = d.worldX !== undefined ? d.worldX : (Number(d.position?.x) || 0)
                const dz = d.worldZ !== undefined ? d.worldZ : (Number(d.position?.z) || 0)
                const dw = Math.max(Number(d.width) || 1.0, 0.9)
                const dist = Math.hypot(nx - dx, nz - dz)
                return dist <= dw * 0.8 + 0.35
              })
              return nearDoor || rooms.length === 0
            }

            if (isWalkable(nextCamX, nextCamZ, 0.15)) {
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

              // Check walkable bounds with 0.15m padding or doorway corridor
              const inRoom = (rooms.length > 0 ? rooms : detectedRooms).some((r) => {
                const pos = getRoom3DPosition(r)
                const rx = pos.x
                const rz = pos.z
                const rw = pos.w / 2 - 0.15
                const rl = pos.l / 2 - 0.15
                return nextX >= rx - rw && nextX <= rx + rw && nextZ >= rz - rl && nextZ <= rz + rl
              })
              const nearDoor = allDoors.some((d) => {
                const dx = d.worldX !== undefined ? d.worldX : (Number(d.position?.x) || 0)
                const dz = d.worldZ !== undefined ? d.worldZ : (Number(d.position?.z) || 0)
                const dw = Math.max(Number(d.width) || 1.0, 0.9)
                const dist = Math.hypot(nextX - dx, nextZ - dz)
                return dist <= dw * 0.8 + 0.35
              })

              if (inRoom || nearDoor || rooms.length === 0) {
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
  }, [rooms, allDoors, viewMode, currentRoom, detectedRooms])

  // Select room camera jump (jumps directly into the true 3D room center)
  const handleSelectRoom = (room) => {
    setSelectedRoomId(room.id)
    const pos = getRoom3DPosition(room)
    const rx = pos.x
    const ry = pos.y
    const rz = pos.z
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
      const pos = getRoom3DPosition(cur)
      const rx = pos.x
      const ry = pos.y
      const rz = pos.z
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
        gl={{
          antialias: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.1,
          outputColorSpace: THREE.SRGBColorSpace,
        }}
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

        {/* ── Photorealistic Architectural House Model: Cloud Blender GLB ── */}
        {glbUrl ? (
          <BlenderErrorBoundary
            key={glbUrl}
            onError={handleBlenderError}
            onRetry={() => regenerate3D(activeProjectId, activeVersionId)}
          >
            <Suspense fallback={<BlenderLoadingFallback />}>
              <BlenderHouseModel url={glbUrl} onRoomsDetected={setDetectedRooms} />
            </Suspense>
          </BlenderErrorBoundary>
        ) : (
          <Html center>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                padding: '28px 32px',
                background: 'rgba(15, 23, 42, 0.95)',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                borderRadius: 20,
                boxShadow: '0 25px 60px rgba(0,0,0,0.7)',
                backdropFilter: 'blur(28px)',
                width: 350,
                color: 'white',
                pointerEvents: 'auto',
              }}
            >
              {isGenerating3D ? (
                <>
                  <div
                    style={{
                      position: 'relative',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 64,
                      height: 64,
                      marginBottom: 16,
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        inset: 0,
                        borderRadius: '50%',
                        border: '2px dashed rgba(56, 189, 248, 0.5)',
                        animation: 'spin 6s linear infinite',
                      }}
                    />
                    <Loader2 size={32} color="#38bdf8" style={{ animation: 'spin 1.2s linear infinite' }} />
                  </div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: 8, color: '#f8fafc' }}>
                    Synthesizing 3D Model…
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.75)', lineHeight: 1.5, marginBottom: 16 }}>
                    Cloud Blender is constructing walls, applying PBR textures, and placing 3D furniture.
                  </div>
                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '4px 12px',
                      background: 'rgba(56, 189, 248, 0.15)',
                      borderRadius: 999,
                      border: '1px solid rgba(56, 189, 248, 0.3)',
                      fontSize: '0.75rem',
                      color: '#38bdf8',
                      fontWeight: 600,
                    }}
                  >
                    <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#38bdf8', animation: 'pulse 1.5s infinite' }} />
                    EC2 Headless Blender Worker
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontSize: '2.5rem', marginBottom: 12 }}>🏛️</div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: 8 }}>
                    3D Model Ready to Synthesize
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.72)', lineHeight: 1.5, marginBottom: 18 }}>
                    Architectural layout generated. Click below to synthesize the high-resolution 3D GLB model in Blender.
                  </div>
                  <button
                    type="button"
                    onClick={() => regenerate3D(activeProjectId, activeVersionId)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 22px',
                      background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                      border: '1px solid rgba(56, 189, 248, 0.5)',
                      borderRadius: 10,
                      color: '#ffffff',
                      fontSize: '0.88rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      boxShadow: '0 4px 16px rgba(2, 132, 199, 0.5)',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <Sparkles size={16} />
                    <span>Generate Blender 3D</span>
                  </button>
                </>
              )}
            </div>
          </Html>
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
