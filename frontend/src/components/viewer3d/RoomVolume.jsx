import { useMemo } from 'react'
import * as THREE from 'three'
import { getRoomMeta, makeSurfaceTexture } from './constants'
import { buildFurniture, makeFloorTexture } from '../../utils/furnitureBuilder'

// ── Solid Architectural Wall with Cap & Baseboard ───────────────────
function ArchitecturalWall({ width, height, thickness, position, isAccent, accentMat, defaultMat, wallCapMat, baseboardMat }) {
  const mat = isAccent && accentMat ? accentMat : defaultMat

  return (
    <group position={position}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, thickness]} />
        <primitive object={mat} attach="material" />
      </mesh>
      <mesh position={[0, height / 2 + 0.015, 0]} castShadow>
        <boxGeometry args={[width, 0.03, thickness]} />
        <primitive object={wallCapMat} attach="material" />
      </mesh>
      <mesh position={[0, -height / 2 + 0.05, 0]}>
        <boxGeometry args={[width, 0.10, thickness]} />
        <primitive object={baseboardMat} attach="material" />
      </mesh>
    </group>
  )
}

// ── Floor-to-Ceiling Panoramic Glass Sliding Wall ───────────────────
function FloorToCeilingGlass({ width = 4.5, height = 2.8, position = [0, 1.4, 0] }) {
  return (
    <group position={position}>
      <mesh castShadow position={[0, 0, 0]}>
        <boxGeometry args={[width, height, 0.08]} />
        <meshStandardMaterial color="#0f172a" roughness={0.3} metalness={0.8} />
      </mesh>
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[width * 0.94, height * 0.92, 0.02]} />
        <meshPhysicalMaterial
          color="#93c5fd"
          transparent
          opacity={0.35}
          transmission={0.88}
          roughness={0.05}
          metalness={0.1}
          ior={1.5}
        />
      </mesh>
      <mesh position={[0, 0, 0.01]} castShadow>
        <boxGeometry args={[0.06, height * 0.92, 0.04]} />
        <meshStandardMaterial color="#0f172a" roughness={0.4} metalness={0.7} />
      </mesh>
    </group>
  )
}

// ── Cantilevered Balcony Glass Railing ───────────────────────────────
function BalconyGlassRailing({ width = 6.0, position = [0, 0, 0] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.5, 0]}>
        <boxGeometry args={[width, 1.0, 0.03]} />
        <meshPhysicalMaterial
          color="#93c5fd"
          transparent
          opacity={0.38}
          transmission={0.85}
          roughness={0.08}
          metalness={0.1}
        />
      </mesh>
      <mesh position={[0, 1.02, 0]} castShadow>
        <boxGeometry args={[width + 0.04, 0.05, 0.05]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.9} roughness={0.2} />
      </mesh>
      {[-width / 2 + 0.1, 0, width / 2 - 0.1].map((sx, idx) => (
        <mesh key={idx} position={[sx, 0.5, 0]} castShadow>
          <boxGeometry args={[0.04, 1.0, 0.04]} />
          <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.3} />
        </mesh>
      ))}
    </group>
  )
}

// ── Wall with Door or Window Cutout ──────────────────────────────────
function WallWithOpening({
  length,
  height,
  thickness,
  position,
  rotation = [0, 0, 0],
  opening = null,
  isAccent,
  accentMat,
  defaultMat,
  wallCapMat,
  baseboardMat,
}) {
  const mat = isAccent && accentMat ? accentMat : defaultMat

  if (!opening) {
    return (
      <group position={position} rotation={rotation}>
        <ArchitecturalWall
          width={length}
          height={height}
          thickness={thickness}
          position={[0, 0, 0]}
          isAccent={isAccent}
          accentMat={accentMat}
          defaultMat={defaultMat}
          wallCapMat={wallCapMat}
          baseboardMat={baseboardMat}
        />
      </group>
    )
  }

  const isDoor = opening.type === 'door' || opening.type === 'main_entrance' || opening.type === 'interior_door'
  const opW = Math.min(Math.max(Number(opening.width) || (isDoor ? 0.95 : 1.4), 0.7), Math.max(length - 0.4, 0.6))
  const opH = Math.min(Number(opening.height) || (isDoor ? 2.1 : 1.3), height - 0.1)
  const sillH = isDoor ? 0 : Math.max(Number(opening.sill_height) || 0.85, 0.2)

  const sideW = Math.max((length - opW) / 2, 0.05)
  const headerH = Math.max(height - (sillH + opH), 0.05)

  return (
    <group position={position} rotation={rotation}>
      {/* Left Wall Segment */}
      <mesh position={[-(opW / 2 + sideW / 2), 0, 0]} castShadow receiveShadow>
        <boxGeometry args={[sideW, height, thickness]} />
        <primitive object={mat} attach="material" />
      </mesh>
      {/* Left Wall Cap */}
      <mesh position={[-(opW / 2 + sideW / 2), height / 2 + 0.015, 0]} castShadow>
        <boxGeometry args={[sideW, 0.03, thickness]} />
        <primitive object={wallCapMat} attach="material" />
      </mesh>
      {/* Left Baseboard */}
      <mesh position={[-(opW / 2 + sideW / 2), -height / 2 + 0.05, 0]}>
        <boxGeometry args={[sideW, 0.10, thickness]} />
        <primitive object={baseboardMat} attach="material" />
      </mesh>

      {/* Right Wall Segment */}
      <mesh position={[(opW / 2 + sideW / 2), 0, 0]} castShadow receiveShadow>
        <boxGeometry args={[sideW, height, thickness]} />
        <primitive object={mat} attach="material" />
      </mesh>
      {/* Right Wall Cap */}
      <mesh position={[(opW / 2 + sideW / 2), height / 2 + 0.015, 0]} castShadow>
        <boxGeometry args={[sideW, 0.03, thickness]} />
        <primitive object={wallCapMat} attach="material" />
      </mesh>
      {/* Right Baseboard */}
      <mesh position={[(opW / 2 + sideW / 2), -height / 2 + 0.05, 0]}>
        <boxGeometry args={[sideW, 0.10, thickness]} />
        <primitive object={baseboardMat} attach="material" />
      </mesh>

      {/* Header Segment Above Opening */}
      {headerH > 0.08 && (
        <mesh position={[0, height / 2 - headerH / 2, 0]} castShadow receiveShadow>
          <boxGeometry args={[opW, headerH, thickness]} />
          <primitive object={mat} attach="material" />
        </mesh>
      )}
      {/* Header Wall Cap */}
      <mesh position={[0, height / 2 + 0.015, 0]} castShadow>
        <boxGeometry args={[opW, 0.03, thickness]} />
        <primitive object={wallCapMat} attach="material" />
      </mesh>

      {/* Bottom Parapet under Window (for windows only) */}
      {!isDoor && sillH > 0.08 && (
        <>
          <mesh position={[0, -height / 2 + sillH / 2, 0]} castShadow receiveShadow>
            <boxGeometry args={[opW, sillH, thickness]} />
            <primitive object={mat} attach="material" />
          </mesh>
          <mesh position={[0, -height / 2 + 0.05, 0]}>
            <boxGeometry args={[opW, 0.10, thickness]} />
            <primitive object={baseboardMat} attach="material" />
          </mesh>
        </>
      )}

      {/* 3D Architectural Frame & Core */}
      {isDoor ? (
        <group position={[0, -height / 2 + opH / 2, 0]}>
          <mesh castShadow>
            <boxGeometry args={[opW + 0.04, opH + 0.02, thickness + 0.02]} />
            <meshStandardMaterial color="#2d1d13" roughness={0.6} metalness={0.2} />
          </mesh>
          <mesh position={[opW * 0.15, 0, 0.06]} rotation={[0, 0.40, 0]} castShadow>
            <boxGeometry args={[opW * 0.90, opH * 0.96, 0.045]} />
            <meshStandardMaterial color="#6b4c35" roughness={0.7} metalness={0.1} />
          </mesh>
        </group>
      ) : (
        <group position={[0, -height / 2 + sillH + opH / 2, 0]}>
          <mesh castShadow>
            <boxGeometry args={[opW, opH, thickness * 0.8]} />
            <meshStandardMaterial color="#1e293b" roughness={0.4} metalness={0.8} />
          </mesh>
          <mesh>
            <boxGeometry args={[opW * 0.92, opH * 0.90, 0.02]} />
            <meshPhysicalMaterial
              color="#93c5fd"
              transparent
              opacity={0.35}
              transmission={0.88}
              roughness={0.06}
              metalness={0.1}
              ior={1.5}
            />
          </mesh>
          <mesh position={[0, 0, 0.01]} castShadow>
            <boxGeometry args={[0.035, opH * 0.90, 0.03]} />
            <meshStandardMaterial color="#334155" roughness={0.5} metalness={0.7} />
          </mesh>
        </group>
      )}
    </group>
  )
}

// ── Room Volume with Multi-Floor & Contiguous Wall Integration ───────
export default function RoomVolume({ room, viewMode, isSelected, isNightMode, furniture, doors = [], windows = [] }) {
  const width = Math.max(Number(room.dimensions?.width ?? room.width) || 1, 1)
  const length = Math.max(Number(room.dimensions?.depth ?? room.length) || 1, 1)
  const fullHeight = Math.max(Number(room.dimensions?.height ?? room.height) || 3.0, 2.4)

  const wallHeight = viewMode === 'dollhouse' ? 1.45 : fullHeight
  const position = room.position || { x: 0, y: 0, z: 0 }
  const isCanonical = Boolean(room.dimensions)
  const x = (Number(position.x) || 0) + (isCanonical ? width / 2 : 0)
  const y = Number(isCanonical ? position.z : position.y) || 0
  const z = (Number(isCanonical ? position.y : position.z) || 0) + (isCanonical ? length / 2 : 0)

  const isUpperFloor = y >= 2.5 || Number(room.floor) === 1
  const wallThickness = 0.14
  const slabThickness = 0.14
  const centerY = y + slabThickness / 2
  const roomType = String(room.type || 'Room').toLowerCase()
  const isLiving = roomType.includes('living') || roomType.includes('lounge') || roomType.includes('great')
  const isMasterSuite = isUpperFloor && roomType.includes('bed')

  const meta = getRoomMeta(room.type)

  const materials = room?.materials || {}
  const pbrMaterial = room?.pbr_material || {}
  const accentWall = pbrMaterial?.accent_wall || (materials?.accent_wall ? { pattern: materials.accent_wall } : null)
  const accentSide = accentWall?.side ? String(accentWall.side).toLowerCase() : null

  const floorPattern = materials?.floor || pbrMaterial?.floor?.pattern || (isUpperFloor ? 'wood_planks' : 'marble_tile')
  const floorTexture = useMemo(() => makeFloorTexture(floorPattern), [floorPattern])
  const wallTexture = useMemo(() => makeSurfaceTexture(materials?.walls || pbrMaterial?.walls?.pattern || 'plain', 'wall'), [materials?.walls, pbrMaterial?.walls?.pattern])
  const accentTexture = useMemo(
    () => (accentWall ? makeSurfaceTexture(accentWall.pattern || 'brick', 'wall') : wallTexture),
    [accentWall, wallTexture]
  )
  const ceilingTexture = useMemo(() => makeSurfaceTexture(materials?.ceiling || pbrMaterial?.ceiling?.pattern || 'plain', 'ceiling'), [materials?.ceiling, pbrMaterial?.ceiling?.pattern])

  floorTexture.colorSpace = THREE.SRGBColorSpace
  wallTexture.colorSpace = THREE.SRGBColorSpace
  accentTexture.colorSpace = THREE.SRGBColorSpace
  ceilingTexture.colorSpace = THREE.SRGBColorSpace

  const defaultWallMat = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({
      color: pbrMaterial?.walls?.color || '#f4f4f0',
      roughness: 0.85,
      metalness: 0.0,
      map: wallTexture,
    })
    mat.polygonOffset = true
    mat.polygonOffsetFactor = 1
    mat.polygonOffsetUnits = 1
    return mat
  }, [pbrMaterial?.walls?.color, wallTexture])

  const accentWallMat = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({
      color: accentWall?.color || '#8b3a3a',
      roughness: 0.85,
      metalness: 0.0,
      map: accentTexture,
    })
    mat.polygonOffset = true
    mat.polygonOffsetFactor = 1
    mat.polygonOffsetUnits = 1
    return mat
  }, [accentWall?.color, accentTexture])

  const wallCapMat = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({
      color: '#2e3846',
      roughness: 0.5,
      metalness: 0.2,
    })
    mat.polygonOffset = true
    mat.polygonOffsetFactor = 0.5
    mat.polygonOffsetUnits = 0.5
    return mat
  }, [])

  const baseboardMat = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({
      color: '#e2e8f0',
      roughness: 0.6,
      metalness: 0.05,
    })
    mat.polygonOffset = true
    mat.polygonOffsetFactor = 0.5
    mat.polygonOffsetUnits = 0.5
    return mat
  }, [])

  const floorMat = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({
      color: pbrMaterial?.floor?.color || '#ffffff',
      roughness: Number(pbrMaterial?.floor?.roughness) || 0.4,
      metalness: Number(pbrMaterial?.floor?.metalness) || 0.08,
      map: floorTexture,
    })
    mat.polygonOffset = true
    mat.polygonOffsetFactor = -1
    mat.polygonOffsetUnits = -1
    return mat
  }, [pbrMaterial?.floor, floorTexture])

  const furnitureList = useMemo(() => {
    const items = Array.isArray(furniture) && furniture.length > 0 ? furniture : (Array.isArray(room?.furniture) ? room.furniture : [])
    if (!isCanonical) return items
    return items.map((item) => ({
      ...item,
      position: {
        x: (Number(item.position?.x) || x) - x,
        y: Math.max(0, (Number(item.position?.z) || y) - y),
        z: (Number(item.position?.y) || z) - z,
      },
      rotation_y: -(Number(item.rotation ?? item.rotation_y) || 0),
    }))
  }, [furniture, room?.furniture, isCanonical, x, y, z])

  const furnitureGroup = useMemo(
    () => buildFurniture(furnitureList),
    [furnitureList]
  )

  const roomDoors = useMemo(() => {
    const list = Array.isArray(doors) && doors.length > 0 ? doors.filter((d) => (d.roomId || d.room_id) === room.id) : []
    return list.length > 0 ? list : (Array.isArray(room.doors) ? room.doors : [])
  }, [doors, room.doors, room.id])

  const roomWindows = useMemo(() => {
    const list = Array.isArray(windows) && windows.length > 0 ? windows.filter((w) => (w.roomId || w.room_id) === room.id) : []
    return list.length > 0 ? list : (Array.isArray(room.windows) ? room.windows : [])
  }, [windows, room.windows, room.id])

  // Resolve openings per wall side
  const backOpening = useMemo(() => {
    const d = roomDoors.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/back|north/))
    if (d) return { ...d, type: 'door' }
    const w = roomWindows.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/back|north/))
    if (w) return { ...w, type: 'window' }
    return null
  }, [roomDoors, roomWindows])

  const frontOpening = useMemo(() => {
    const d = roomDoors.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/front|south/))
    if (d) return { ...d, type: 'door' }
    const w = roomWindows.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/front|south/))
    if (w) return { ...w, type: 'window' }
    return null
  }, [roomDoors, roomWindows])

  const leftOpening = useMemo(() => {
    const d = roomDoors.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/left|west/))
    if (d) return { ...d, type: 'door' }
    const w = roomWindows.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/left|west/))
    if (w) return { ...w, type: 'window' }
    return null
  }, [roomDoors, roomWindows])

  const rightOpening = useMemo(() => {
    const d = roomDoors.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/right|east/))
    if (d) return { ...d, type: 'door' }
    const w = roomWindows.find((item) => String(item.wall_side || item.wall || '').toLowerCase().match(/right|east/))
    if (w) return { ...w, type: 'window' }
    return null
  }, [roomDoors, roomWindows])

  const lights = Array.isArray(room?.lights) ? room.lights : []
  const hasCeiling = viewMode === 'walkthrough'

  return (
    <group position={[x, centerY, z]}>
      {/* Floor Slab */}
      <mesh receiveShadow position={[0, 0.004, 0]}>
        <boxGeometry args={[width, slabThickness, length]} />
        <primitive object={floorMat} attach="material" />
      </mesh>

      {/* Structural Upper Floor Under-Slab */}
      {isUpperFloor && (
        <mesh receiveShadow position={[0, -0.1, 0]}>
          <boxGeometry args={[width + 0.08, 0.18, length + 0.08]} />
          <meshStandardMaterial color="#1e293b" roughness={0.8} />
        </mesh>
      )}

      {/* Cantilevered Balcony Slab & Railing (For Upper Floor Master Suite) */}
      {isMasterSuite && (
        <group position={[0, 0, length / 2 + 1.2]}>
          <mesh receiveShadow position={[0, 0, 0]}>
            <boxGeometry args={[width, slabThickness, 2.4]} />
            <meshStandardMaterial color="#78350f" roughness={0.7} />
          </mesh>
          <mesh receiveShadow position={[0, -0.1, 0]}>
            <boxGeometry args={[width + 0.04, 0.16, 2.44]} />
            <meshStandardMaterial color="#1e293b" roughness={0.8} />
          </mesh>
          <BalconyGlassRailing width={width} position={[0, slabThickness / 2, 1.2]} />
          <BalconyGlassRailing width={2.4} position={[-width / 2, slabThickness / 2, 0]} />
          <BalconyGlassRailing width={2.4} position={[width / 2, slabThickness / 2, 0]} />
        </group>
      )}

      {isSelected && (
        <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[width + 0.1, length + 0.1]} />
          <meshBasicMaterial color={meta.color} wireframe transparent opacity={0.35} />
        </mesh>
      )}

      {/* Back Wall */}
      <WallWithOpening
        length={width}
        height={wallHeight}
        thickness={wallThickness}
        position={[0, wallHeight / 2, -length / 2 + wallThickness / 2]}
        opening={backOpening}
        isAccent={accentSide === 'back'}
        accentMat={accentWallMat}
        defaultMat={defaultWallMat}
        wallCapMat={wallCapMat}
        baseboardMat={baseboardMat}
      />

      {/* Front Wall */}
      {isLiving || isMasterSuite ? (
        <FloorToCeilingGlass
          width={width}
          height={wallHeight}
          position={[0, wallHeight / 2, length / 2 - wallThickness / 2]}
        />
      ) : (
        <WallWithOpening
          length={width}
          height={wallHeight}
          thickness={wallThickness}
          position={[0, wallHeight / 2, length / 2 - wallThickness / 2]}
          opening={frontOpening}
          isAccent={accentSide === 'front'}
          accentMat={accentWallMat}
          defaultMat={defaultWallMat}
          wallCapMat={wallCapMat}
          baseboardMat={baseboardMat}
        />
      )}

      {/* Left Wall */}
      <WallWithOpening
        length={length}
        height={wallHeight}
        thickness={wallThickness}
        position={[-width / 2 + wallThickness / 2, wallHeight / 2, 0]}
        rotation={[0, Math.PI / 2, 0]}
        opening={leftOpening}
        isAccent={accentSide === 'left'}
        accentMat={accentWallMat}
        defaultMat={defaultWallMat}
        wallCapMat={wallCapMat}
        baseboardMat={baseboardMat}
      />

      {/* Right Wall */}
      <WallWithOpening
        length={length}
        height={wallHeight}
        thickness={wallThickness}
        position={[width / 2 - wallThickness / 2, wallHeight / 2, 0]}
        rotation={[0, Math.PI / 2, 0]}
        opening={rightOpening}
        isAccent={accentSide === 'right'}
        accentMat={accentWallMat}
        defaultMat={defaultWallMat}
        wallCapMat={wallCapMat}
        baseboardMat={baseboardMat}
      />

      {hasCeiling && (
        <mesh position={[0, fullHeight, 0]} receiveShadow>
          <boxGeometry args={[width, 0.08, length]} />
          <meshStandardMaterial color="#fcfcfc" roughness={0.9} map={ceilingTexture} />
        </mesh>
      )}

      <primitive object={furnitureGroup} />

      {lights.map((l, i) => {
        const lx = Number(l?.position?.x) || 0
        const ly = Math.min(Number(l?.position?.y) || fullHeight - 0.2, wallHeight - 0.2)
        const lz = Number(l?.position?.z) || 0
        const intensity = isNightMode ? 2.8 : Number(l?.intensity) || 1.6
        const lightColor = isNightMode ? '#fbbf24' : l?.color || '#ffedd5'

        return (
          <group key={i} position={[lx, ly, lz]}>
            <mesh>
              <cylinderGeometry args={[0.15, 0.15, 0.04, 16]} />
              <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.2} />
            </mesh>
            <mesh position={[0, -0.02, 0]}>
              <circleGeometry args={[0.12, 16]} />
              <meshBasicMaterial color={lightColor} />
            </mesh>
            <pointLight
              color={lightColor} intensity={intensity}
              distance={18} decay={2} castShadow
            />
          </group>
        )
      })}
    </group>
  )
}
