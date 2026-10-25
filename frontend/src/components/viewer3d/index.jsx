import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'

import { useProjectStore } from '../../store'
import { BlenderHouseModel } from './BlenderModel'
import { getCachedModelUrl } from '../../utils/modelCache'
import ViewerStage from './ViewerStage'
import {
  isNavigationPointWalkable,
  modelIdentity,
  objectFloorLevel,
  roomPlacement,
} from './viewerUtils'



// ── Main Professional Viewer3D Component ─────────────────────────────
export default function Viewer3D({ design }) {
  const {
    regenerate3D,
    reloadSaved3D,
    isGenerating3D,
    activeProjectId,
    activeVersionId,
    showRoof,
    toggleShowRoof,
    activeFloorLevel,
    setActiveFloorLevel,
    approveFloorPlan,
    isApprovingLayout,
  } = useProjectStore()

  const rawGlbUrl = design?.glb_url || design?.model_url || null
  const [effectiveGlbUrl, setEffectiveGlbUrl] = useState(rawGlbUrl)

  // Check IndexedDB local cache first for instant model retrieval
  useEffect(() => {
    let isCancelled = false
    if (!rawGlbUrl) {
      setEffectiveGlbUrl(null)
      return
    }

    getCachedModelUrl(rawGlbUrl)
      .then((cachedBlobUrl) => {
        if (!isCancelled) {
          if (cachedBlobUrl) {
            setEffectiveGlbUrl(cachedBlobUrl)
          } else {
            setEffectiveGlbUrl(rawGlbUrl)
          }
        }
      })
      .catch(() => {
        if (!isCancelled) setEffectiveGlbUrl(rawGlbUrl)
      })

    return () => {
      isCancelled = true
    }
  }, [rawGlbUrl])

  const glbUrl = effectiveGlbUrl
  // Exclusively use Cloud Blender 3D photorealistic model
  const [viewSource, setViewSource] = useState('blender')
  const [isModelRendered, setIsModelRendered] = useState(false)
  const [modelReloadKey, setModelReloadKey] = useState(0)

  // Reset rendered flag whenever glbUrl changes or 3D is being re-synthesized
  useEffect(() => {
    setIsModelRendered(false)
  }, [glbUrl, isGenerating3D])

  const wasGeneratingRef = useRef(false)
  useEffect(() => {
    if (isGenerating3D) {
      wasGeneratingRef.current = true
    }
  }, [isGenerating3D])

  useEffect(() => {
    if (isModelRendered && wasGeneratingRef.current) {
      wasGeneratingRef.current = false
      setViewMode('dollhouse')
    }
  }, [isModelRendered])

  const handleBlenderError = (err) => {
    console.warn('[Viewer3D] Model load error:', err)
    setIsModelRendered(false)
  }

  const handleReloadSavedModel = async () => {
    BlenderHouseModel.clear(glbUrl)
    setIsModelRendered(false)
    setModelReloadKey((value) => value + 1)
    await reloadSaved3D(activeVersionId)
  }

  const isApproved = Boolean(design?.layout_approved || design?.approved_at)
  const [viewMode, setViewMode] = useState(() => (glbUrl && isApproved ? 'dollhouse' : 'plan'))
  const [planSubMode, setPlanSubMode] = useState('vector')
  const previousModelIdentityRef = useRef(null)

  // A version with a saved cloud model should open that model directly. Use
  // the path (not the temporary signature) to avoid treating URL refreshes as
  // different models.
  useEffect(() => {
    const identity = modelIdentity(glbUrl)
    if (identity && isApproved && identity !== previousModelIdentityRef.current) {
      setViewSource('blender')
      setViewMode('dollhouse')
      setPlanSubMode('3d')
    }
    previousModelIdentityRef.current = identity
  }, [activeVersionId, glbUrl, isApproved])

  // Always route unapproved designs to 2D CAD floor plan for user review & approval
  useEffect(() => {
    if (!isApproved) {
      setViewMode('plan')
      setPlanSubMode('vector')
    }
  }, [activeVersionId, isApproved])
  const [isNightMode, setIsNightMode] = useState(false)
  const [selectedRoomId, setSelectedRoomId] = useState('overview')
  const [dismissedSynthesisPrompt, setDismissedSynthesisPrompt] = useState(false)

  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showCallouts, setShowCallouts] = useState(true)

  const containerRef = useRef(null)
  const controlsRef = useRef(null)
  const targetPos = useRef(new THREE.Vector3(0, 1.0, 0))
  const targetCamPos = useRef(new THREE.Vector3(22, 22, 28))

  const rooms = useMemo(() => (Array.isArray(design?.rooms) ? design.rooms : []), [design?.rooms])
  const doors = useMemo(() => (Array.isArray(design?.doors) ? design.doors : []), [design?.doors])
  const windows = useMemo(() => (Array.isArray(design?.windows) ? design.windows : []), [design?.windows])
  const visibleRooms = useMemo(
    () => activeFloorLevel === null || activeFloorLevel === undefined
      ? rooms
      : rooms.filter((room) => objectFloorLevel(room) === activeFloorLevel),
    [rooms, activeFloorLevel],
  )
  const visibleDoors = useMemo(
    () => activeFloorLevel === null || activeFloorLevel === undefined
      ? doors
      : doors.filter((door) => objectFloorLevel(door) === activeFloorLevel),
    [doors, activeFloorLevel],
  )
  const visibleWindows = useMemo(
    () => activeFloorLevel === null || activeFloorLevel === undefined
      ? windows
      : windows.filter((window) => objectFloorLevel(window) === activeFloorLevel),
    [windows, activeFloorLevel],
  )
  const isExteriorAccessWalkable = useMemo(() => {
    const exterior = design?.exterior || {}
    const path = exterior.entrance_path || {}
    const start = path.start || {}
    const end = path.end || {}
    const ax = Number(start.x)
    const az = Number(start.y)
    const bx = Number(end.x)
    const bz = Number(end.y)
    const pathWidth = Math.max(0.8, Number(path.width) || 1.2)
    const driveway = exterior.driveway || {}
    const driveX = Number(driveway.position?.x)
    const driveZ = Number(driveway.position?.y)
    const driveWidth = Number(driveway.width)
    const driveDepth = Number(driveway.depth)

    return (x, z, pad = 0.15) => {
      if ([ax, az, bx, bz].every(Number.isFinite)) {
        const vx = bx - ax
        const vz = bz - az
        const lengthSq = vx * vx + vz * vz
        const amount = lengthSq > 0
          ? Math.max(0, Math.min(1, ((x - ax) * vx + (z - az) * vz) / lengthSq))
          : 0
        const nearestX = ax + amount * vx
        const nearestZ = az + amount * vz
        if (Math.hypot(x - nearestX, z - nearestZ) <= pathWidth / 2 + pad) return true
      }
      return (
        [driveX, driveZ, driveWidth, driveDepth].every(Number.isFinite)
        && x >= driveX - pad && x <= driveX + driveWidth + pad
        && z >= driveZ - pad && z <= driveZ + driveDepth + pad
      )
    }
  }, [design?.exterior])
  const floors = useMemo(() => {
    if (Array.isArray(design?.floors) && design.floors.length > 0) {
      return design.floors
    }
    return [{ id: 'ground_floor', level: 0, rooms }]
  }, [design?.floors, rooms])

  // Real 3D detected room floor slabs and doors from loaded GLB
  const [detectedRooms, setDetectedRooms] = useState([])
  const [detectedDoors, setDetectedDoors] = useState([])

  // Helper to get true 3D room position and bounds (from real GLB meshes if available)
  const getRoom3DPosition = (room) => {
    const floorHeight = Number(design?.building?.floor_height ?? design?.house?.floorHeight) || 3
    return roomPlacement(room, detectedRooms, floorHeight)
  }

  // Pre-cached navigation rooms for instant collision detection without per-frame recomputation
  const navigationRooms = useMemo(() => {
    const floorHeight = Number(design?.building?.floor_height ?? design?.house?.floorHeight) || 3
    return rooms.map((room) => roomPlacement(room, detectedRooms, floorHeight))
  }, [rooms, detectedRooms, design?.building?.floor_height, design?.house?.floorHeight])

  // When real GLB 3D rooms are detected, re-sync character position to active selected room
  useEffect(() => {
    if (detectedRooms.length > 0 && selectedRoomId && selectedRoomId !== 'overview') {
      const room = rooms.find((r) => r.id === selectedRoomId)
      if (room) {
        const pos = getRoom3DPosition(room)
        setCharPos({ x: pos.x, y: pos.y + 0.1, z: pos.z })
        setCharFloorLevel(pos.level)
      }
    }
  }, [detectedRooms])

  // Collect all doors across design (GLB 3D doors + top-level + per-room) for doorway passage detection
  const allDoors = useMemo(() => {
    const list = []
    if (Array.isArray(detectedDoors) && detectedDoors.length > 0) {
      list.push(...detectedDoors)
    }
    doors.forEach((door) => {
      list.push({
        ...door,
        worldX: Number(door.position?.x) || 0,
        worldZ: Number(door.position?.y ?? door.position?.z) || 0,
        floorLevel: objectFloorLevel(door),
      })
    })
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
            floorLevel: objectFloorLevel(r),
          })
        })
      }
    })
    return list
  }, [doors, rooms, detectedRooms, detectedDoors])

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
        const pos = getRoom3DPosition(r)
        const rx = pos.x
        const rz = pos.z
        const rw = pos.w / 2
        const rl = pos.l / 2
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
  const charPosRef = useRef({ x: 0, y: 0.1, z: 0 })
  const [charFloorLevel, setCharFloorLevel] = useState(0)
  const [charRot, setCharRot] = useState(0)
  const [isMoving, setIsMoving] = useState(false)
  const [walkCycle, setWalkCycle] = useState(0)
  const keysRef = useRef({ w: false, a: false, s: false, d: false })

  // Mouse look state & angles
  const [isMouseLookLocked, setIsMouseLookLocked] = useState(false)
  const isMouseLockedRef = useRef(false)
  const yawRef = useRef(0)
  const pitchRef = useRef(0)
  const eyeHeightRef = useRef(1.65)

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

      const sensitivity = 0.0022
      yawRef.current += e.movementX * sensitivity
      pitchRef.current -= e.movementY * sensitivity

      const maxPitch = Math.PI / 2.15
      pitchRef.current = Math.max(-maxPitch, Math.min(maxPitch, pitchRef.current))

      if (controlsRef.current?.object) {
        const cam = controlsRef.current.object
        cam.position.y = eyeHeightRef.current
        const cosPitch = Math.cos(pitchRef.current)
        const sinPitch = Math.sin(pitchRef.current)
        const cosYaw = Math.cos(yawRef.current)
        const sinYaw = Math.sin(yawRef.current)

        const lookDir = new THREE.Vector3(
          sinYaw * cosPitch,
          sinPitch,
          -cosYaw * cosPitch
        )

        const lookTarget = cam.position.clone().add(lookDir.multiplyScalar(2.0))
        cam.lookAt(lookTarget)
        controlsRef.current.target.copy(lookTarget)
        targetPos.current.copy(lookTarget)
        targetCamPos.current.copy(cam.position)
      }
    }

    window.addEventListener('mousemove', onMouseMove)
    return () => window.removeEventListener('mousemove', onMouseMove)
  }, [viewMode])

  // Initialize and auto-frame complete house
  useEffect(() => {
    if (rooms.length > 0) {
      const first = rooms[0]
      const firstPosition = getRoom3DPosition(first)
      setCharPos({ x: firstPosition.x, y: firstPosition.y + 0.1, z: firstPosition.z })
      setCharFloorLevel(firstPosition.level)
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

  // High-performance movement loop with delta time, wall sliding, and zero React re-renders in walkthrough
  useEffect(() => {
    let animId
    let lastTime = performance.now()
    let isMovingLocal = false

    const update = () => {
      const now = performance.now()
      const delta = Math.min((now - lastTime) / 1000, 0.08)
      lastTime = now

      const { w, a, s, d } = keysRef.current
      const hasInput = w || s || a || d

      if (hasInput) {
        if (!isMovingLocal) {
          isMovingLocal = true
          setIsMoving(true)
        }

        if (viewMode === 'walkthrough' && controlsRef.current?.object) {
          const cam = controlsRef.current.object
          const speed = 4.2 * delta // Natural walking speed: 4.2 meters/second

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

            const isWalkable = (nx, nz, pad = 0.15) => {
              return rooms.length === 0 || isNavigationPointWalkable({
                x: nx, z: nz, level: charFloorLevel, rooms: navigationRooms,
                doors: allDoors, exteriorAccess: isExteriorAccessWalkable, padding: pad,
                fromX: curCamX, fromZ: curCamZ,
              })
            }

            let finalX = curCamX
            let finalZ = curCamZ

            // 1. Direct step
            if (isWalkable(nextCamX, nextCamZ, 0.15)) {
              finalX = nextCamX
              finalZ = nextCamZ
            } else {
              // 2. Wall-slide along X axis
              if (isWalkable(nextCamX, curCamZ, 0.15)) {
                finalX = nextCamX
              }
              // 3. Wall-slide along Z axis
              if (isWalkable(curCamX, nextCamZ, 0.15)) {
                finalZ = nextCamZ
              }
            }

            if (finalX !== curCamX || finalZ !== curCamZ) {
              const dx = finalX - curCamX
              const dz = finalZ - curCamZ
              cam.position.x = finalX
              cam.position.z = finalZ
              cam.position.y = eyeHeightRef.current
              controlsRef.current.target.x += dx
              controlsRef.current.target.z += dz
              targetCamPos.current.copy(cam.position)
              targetPos.current.copy(controlsRef.current.target)

              charPosRef.current.x = finalX
              charPosRef.current.y = charFloorLevel * 3 + 0.1
              charPosRef.current.z = finalZ
            }
          }
        } else {
          // 3rd-person avatar movement (only when avatar is visible in dollhouse / topdown)
          const speed = 4.2 * delta
          setWalkCycle((c) => c + delta * 8.5)

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

              const walkable = rooms.length === 0 || isNavigationPointWalkable({
                x: nextX, z: nextZ, level: charFloorLevel, rooms: navigationRooms,
                doors: allDoors, exteriorAccess: isExteriorAccessWalkable, padding: 0.15,
                fromX: prev.x, fromZ: prev.z,
              })

              if (walkable) {
                targetPos.current.set(nextX, prev.y + 1.0, nextZ)
                charPosRef.current = { x: nextX, y: prev.y, z: nextZ }
                return { x: nextX, y: prev.y, z: nextZ }
              }
              return prev
            })
          }
        }
      } else {
        if (isMovingLocal) {
          isMovingLocal = false
          setIsMoving(false)
          // Sync charPos to React state once on movement stop so avatar is accurate
          setCharPos({ ...charPosRef.current })
        }
      }

      animId = requestAnimationFrame(update)
    }

    animId = requestAnimationFrame(update)
    return () => cancelAnimationFrame(animId)
  }, [navigationRooms, allDoors, viewMode, isExteriorAccessWalkable, charFloorLevel])

  // Select room camera jump (jumps directly into the true 3D room center)
  const handleSelectRoom = (room) => {
    setSelectedRoomId(room.id)
    const pos = getRoom3DPosition(room)
    const rx = pos.x
    const ry = pos.y
    const rz = pos.z
    setActiveFloorLevel(pos.level)
    setCharFloorLevel(pos.level)
    const p = { x: rx, y: ry + 0.1, z: rz }
    charPosRef.current = p
    setCharPos(p)

    if (viewMode === 'walkthrough') {
      yawRef.current = 0
      pitchRef.current = 0
      targetCamPos.current.set(rx, ry + 1.65, rz + 0.2)
      targetPos.current.set(rx, ry + 1.6, rz - 2.0)
      eyeHeightRef.current = ry + 1.65
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
    } else if (mode === 'front') {
      targetPos.current.set(cx, maxDim * 0.18, cz)
      targetCamPos.current.set(cx, maxDim * 0.35, cz + maxDim * 1.1)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 120
      }
    } else if (mode === 'back') {
      targetPos.current.set(cx, maxDim * 0.18, cz)
      targetCamPos.current.set(cx, maxDim * 0.35, cz - maxDim * 1.1)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 120
      }
    } else if (mode === 'roof') {
      targetPos.current.set(cx, maxDim * 0.12, cz)
      targetCamPos.current.set(cx + maxDim * 0.45, maxDim * 1.45, cz + maxDim * 0.55)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 140
      }
    } else if (mode === 'walkthrough') {
      yawRef.current = 0
      pitchRef.current = 0
      const cur = currentRoom || rooms[0]
      const pos = getRoom3DPosition(cur)
      const rx = pos.x
      const ry = pos.y
      const rz = pos.z
      const p = { x: rx, y: ry + 0.1, z: rz }
      charPosRef.current = p
      setCharPos(p)

      targetCamPos.current.set(rx, ry + 1.65, rz + 0.2)
      targetPos.current.set(rx, ry + 1.6, rz - 2.0)
      eyeHeightRef.current = ry + 1.65

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
    handleModeChange(viewMode)
  }

  return (
    <ViewerStage
      state={{
        containerRef, isFullscreen, isNightMode, viewMode, planSubMode, design,
        approveFloorPlan, activeProjectId, activeVersionId, isApprovingLayout,
        handleSelectRoom, selectedRoomId, glbUrl, viewSource, modelReloadKey,
        handleBlenderError, handleReloadSavedModel, setDetectedRooms, setDetectedDoors,
        setIsModelRendered, showRoof, activeFloorLevel, visibleRooms, visibleDoors,
        visibleWindows, dismissedSynthesisPrompt, setDismissedSynthesisPrompt,
        isGenerating3D, regenerate3D, charPos, charRot, isMoving, walkCycle,
        controlsRef, targetPos, targetCamPos, isModelRendered, handleModeChange,
        setViewSource, showCallouts, setShowCallouts, isMouseLookLocked,
        toggleMouseLook, setIsNightMode, handleResetCamera, toggleFullscreen,
        rooms, doors, windows, isApproved, toggleShowRoof, setActiveFloorLevel,
        floors, setPlanSubMode, charFloorLevel,
      }}
    />
  )
}
