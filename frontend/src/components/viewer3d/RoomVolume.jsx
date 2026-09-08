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

// ── Room Volume with Multi-Floor & Contiguous Wall Integration ───────
export default function RoomVolume({ room, viewMode, isSelected, isNightMode, furniture }) {
  const width = Math.max(Number(room.width) || 1, 1)
  const length = Math.max(Number(room.length) || 1, 1)
  const fullHeight = Math.max(Number(room.height) || 3.0, 2.4)

  const wallHeight = viewMode === 'dollhouse' ? 1.45 : fullHeight
  const position = room.position || { x: 0, y: 0, z: 0 }
  const x = Number(position.x) || 0
  const y = Number(position.y) || 0
  const z = Number(position.z) || 0

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
    if (Array.isArray(furniture) && furniture.length > 0) return furniture
    return Array.isArray(room?.furniture) ? room.furniture : []
  }, [furniture, room?.furniture])

  const furnitureGroup = useMemo(
    () => buildFurniture(furnitureList),
    [furnitureList]
  )

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
      <ArchitecturalWall
        width={width} height={wallHeight} thickness={wallThickness}
        position={[0, wallHeight / 2, -length / 2 + wallThickness / 2]}
        isAccent={accentSide === 'back'} accentMat={accentWallMat}
        defaultMat={defaultWallMat} wallCapMat={wallCapMat} baseboardMat={baseboardMat}
      />

      {/* Front Wall: Floor-to-Ceiling Glass for Living & Master, Solid Wall for others */}
      {isLiving || isMasterSuite ? (
        <FloorToCeilingGlass width={width} height={wallHeight}
          position={[0, wallHeight / 2, length / 2 - wallThickness / 2]}
        />
      ) : (
        <ArchitecturalWall
          width={width} height={wallHeight} thickness={wallThickness}
          position={[0, wallHeight / 2, length / 2 - wallThickness / 2]}
          isAccent={accentSide === 'front'} accentMat={accentWallMat}
          defaultMat={defaultWallMat} wallCapMat={wallCapMat} baseboardMat={baseboardMat}
        />
      )}

      {/* Left Wall */}
      <ArchitecturalWall
        width={wallThickness} height={wallHeight} thickness={length}
        position={[-width / 2 + wallThickness / 2, wallHeight / 2, 0]}
        isAccent={accentSide === 'left'} accentMat={accentWallMat}
        defaultMat={defaultWallMat} wallCapMat={wallCapMat} baseboardMat={baseboardMat}
      />

      {/* Right Wall */}
      <ArchitecturalWall
        width={wallThickness} height={wallHeight} thickness={length}
        position={[width / 2 - wallThickness / 2, wallHeight / 2, 0]}
        isAccent={accentSide === 'right'} accentMat={accentWallMat}
        defaultMat={defaultWallMat} wallCapMat={wallCapMat} baseboardMat={baseboardMat}
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
