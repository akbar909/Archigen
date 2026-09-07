import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Environment, Html, OrbitControls, useGLTF } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import {
  Bath,
  Bed,
  Briefcase,
  DoorOpen,
  Footprints,
  Grid3X3,
  Home,
  Info,
  Layers,
  Maximize2,
  Minimize2,
  Moon,
  MousePointer,
  RotateCcw,
  Sofa,
  Sparkles,
  Sun,
  Tag,
  UtensilsCrossed,
  Waves,
} from 'lucide-react'

import { buildFurniture, makeFloorTexture } from '../utils/furnitureBuilder'

const ROOM_THEMES = {
  living: { color: '#eab308', icon: Sofa, label: 'Living Room' },
  bed: { color: '#3b82f6', icon: Bed, label: 'Bedroom' },
  bath: { color: '#06b6d4', icon: Bath, label: 'Bathroom' },
  wash: { color: '#06b6d4', icon: Bath, label: 'Washroom' },
  kitchen: { color: '#f97316', icon: UtensilsCrossed, label: 'Kitchen' },
  dining: { color: '#a855f7', icon: UtensilsCrossed, label: 'Dining Room' },
  office: { color: '#6366f1', icon: Briefcase, label: 'Office' },
  hall: { color: '#8b5cf6', icon: DoorOpen, label: 'Hallway' },
  default: { color: '#94a3b8', icon: Home, label: 'Room' },
}

function getRoomMeta(type = '') {
  const t = String(type).toLowerCase()
  for (const [key, meta] of Object.entries(ROOM_THEMES)) {
    if (t.includes(key)) return meta
  }
  return ROOM_THEMES.default
}

function makeSurfaceTexture(pattern = 'plain', kind = 'wall') {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 256
  const ctx = canvas.getContext('2d')

  if (pattern === 'brick') {
    ctx.fillStyle = kind === 'ceiling' ? '#efece4' : '#8b3a3a'
    ctx.fillRect(0, 0, 256, 256)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)'
    ctx.lineWidth = 2.5
    for (let y = 0; y < 16; y += 1) {
      const offset = y % 2 === 0 ? 0 : 16
      for (let x = -1; x < 9; x += 1) {
        ctx.strokeRect(x * 32 + offset, y * 16, 32, 16)
      }
    }
  } else if (pattern === 'wood_panel') {
    ctx.fillStyle = '#6b4728'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 8; i += 1) {
      ctx.fillStyle = i % 2 === 0 ? '#79512f' : '#613e21'
      ctx.fillRect(i * 32, 0, 30, 256)
    }
  } else if (pattern === 'concrete') {
    ctx.fillStyle = '#94a3b8'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 2000; i += 1) {
      const s = 140 + Math.random() * 50
      ctx.fillStyle = `rgba(${s},${s},${s},0.15)`
      ctx.fillRect(Math.random() * 256, Math.random() * 256, 1, 1)
    }
  } else {
    ctx.fillStyle = kind === 'ceiling' ? '#fafafa' : '#f4f4f0'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 800; i += 1) {
      const s = 235 + Math.random() * 20
      ctx.fillStyle = `rgba(${s},${s},${s},0.08)`
      ctx.fillRect(Math.random() * 256, Math.random() * 256, 1, 1)
    }
  }

  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(2, 2)
  texture.needsUpdate = true
  return texture
}

// ── Solid Architectural Wall with Cap & Baseboard ───────────────────
function ArchitecturalWall({ width, height, thickness, position, isAccent, accentMat, defaultMat, wallCapMat, baseboardMat }) {
  const mat = isAccent && accentMat ? accentMat : defaultMat

  return (
    <group position={position}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, thickness]} />
        <primitive object={mat} attach="material" />
      </mesh>
      <mesh position={[0, height / 2 + 0.02, 0]} castShadow>
        <boxGeometry args={[width, 0.04, thickness + 0.02]} />
        <primitive object={wallCapMat} attach="material" />
      </mesh>
      <mesh position={[0, -height / 2 + 0.06, 0]}>
        <boxGeometry args={[width, 0.12, thickness + 0.02]} />
        <primitive object={baseboardMat} attach="material" />
      </mesh>
    </group>
  )
}

// ── Floor-to-Ceiling Panoramic Glass Sliding Wall ───────────────────
function FloorToCeilingGlass({ width = 4.5, height = 2.8, position = [0, 1.4, 0] }) {
  return (
    <group position={position}>
      {/* Matte black aluminum outer frame */}
      <mesh castShadow position={[0, 0, 0]}>
        <boxGeometry args={[width, height, 0.08]} />
        <meshStandardMaterial color="#0f172a" roughness={0.3} metalness={0.8} />
      </mesh>
      {/* Large Glass Panels */}
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
      {/* Center Mullion Divider */}
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
      {/* Tempered Glass Railing */}
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
      {/* Stainless Steel Handrail Top */}
      <mesh position={[0, 1.02, 0]} castShadow>
        <boxGeometry args={[width + 0.04, 0.05, 0.05]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.9} roughness={0.2} />
      </mesh>
      {/* Stainless Steel Stanchions */}
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
function RoomVolume({ room, viewMode, isSelected, isNightMode }) {
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

  const pbrMaterial = room?.pbr_material || {}
  const accentWall = pbrMaterial?.accent_wall || null
  const accentSide = accentWall?.side ? String(accentWall.side).toLowerCase() : null

  const floorPattern = pbrMaterial?.floor?.pattern || (isUpperFloor ? 'wood_planks' : 'marble_tile')
  const floorTexture = useMemo(() => makeFloorTexture(floorPattern), [floorPattern])
  const wallTexture = useMemo(() => makeSurfaceTexture(pbrMaterial?.walls?.pattern || 'plain', 'wall'), [pbrMaterial?.walls?.pattern])
  const accentTexture = useMemo(
    () => (accentWall ? makeSurfaceTexture(accentWall.pattern || 'brick', 'wall') : wallTexture),
    [accentWall, wallTexture]
  )
  const ceilingTexture = useMemo(() => makeSurfaceTexture(pbrMaterial?.ceiling?.pattern || 'plain', 'ceiling'), [pbrMaterial?.ceiling?.pattern])

  floorTexture.colorSpace = THREE.SRGBColorSpace
  wallTexture.colorSpace = THREE.SRGBColorSpace
  accentTexture.colorSpace = THREE.SRGBColorSpace
  ceilingTexture.colorSpace = THREE.SRGBColorSpace

  const defaultWallMat = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: pbrMaterial?.walls?.color || '#f4f4f0',
      roughness: 0.85,
      metalness: 0.0,
      map: wallTexture,
    })
  }, [pbrMaterial?.walls?.color, wallTexture])

  const accentWallMat = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: accentWall?.color || '#8b3a3a',
      roughness: 0.85,
      metalness: 0.0,
      map: accentTexture,
    })
  }, [accentWall?.color, accentTexture])

  const wallCapMat = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#2e3846',
      roughness: 0.5,
      metalness: 0.2,
    })
  }, [])

  const baseboardMat = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#e2e8f0',
      roughness: 0.6,
      metalness: 0.05,
    })
  }, [])

  const floorMat = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: pbrMaterial?.floor?.color || '#ffffff',
      roughness: Number(pbrMaterial?.floor?.roughness) || 0.4,
      metalness: Number(pbrMaterial?.floor?.metalness) || 0.08,
      map: floorTexture,
    })
  }, [pbrMaterial?.floor, floorTexture])

  const furnitureGroup = useMemo(
    () => buildFurniture(Array.isArray(room?.furniture) ? room.furniture : []),
    [room?.furniture]
  )

  const lights = Array.isArray(room?.lights) ? room.lights : []
  const hasCeiling = viewMode === 'walkthrough'

  return (
    <group position={[x, centerY, z]}>
      {/* Floor Slab */}
      <mesh receiveShadow position={[0, 0, 0]}>
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
        width={width}
        height={wallHeight}
        thickness={wallThickness}
        position={[0, wallHeight / 2, -length / 2 + wallThickness / 2]}
        isAccent={accentSide === 'back'}
        accentMat={accentWallMat}
        defaultMat={defaultWallMat}
        wallCapMat={wallCapMat}
        baseboardMat={baseboardMat}
      />

      {/* Front Wall: Floor-to-Ceiling Glass for Living & Master, Solid Wall for others */}
      {isLiving || isMasterSuite ? (
        <FloorToCeilingGlass
          width={width}
          height={wallHeight}
          position={[0, wallHeight / 2, length / 2 - wallThickness / 2]}
        />
      ) : (
        <ArchitecturalWall
          width={width}
          height={wallHeight}
          thickness={wallThickness}
          position={[0, wallHeight / 2, length / 2 - wallThickness / 2]}
          isAccent={accentSide === 'front'}
          accentMat={accentWallMat}
          defaultMat={defaultWallMat}
          wallCapMat={wallCapMat}
          baseboardMat={baseboardMat}
        />
      )}

      {/* Left Wall */}
      <ArchitecturalWall
        width={wallThickness}
        height={wallHeight}
        thickness={length}
        position={[-width / 2 + wallThickness / 2, wallHeight / 2, 0]}
        isAccent={accentSide === 'left'}
        accentMat={accentWallMat}
        defaultMat={defaultWallMat}
        wallCapMat={wallCapMat}
        baseboardMat={baseboardMat}
      />

      {/* Right Wall */}
      <ArchitecturalWall
        width={wallThickness}
        height={wallHeight}
        thickness={length}
        position={[width / 2 - wallThickness / 2, wallHeight / 2, 0]}
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
              color={lightColor}
              intensity={intensity}
              distance={18}
              decay={2}
              castShadow
            />
          </group>
        )
      })}
    </group>
  )
}

// ── Inground Luxury Swimming Pool ────────────────────────────────────
function SwimmingPool({ position = [2.5, -0.15, 9.5], width = 10.5, length = 4.8, depth = 1.5, isNightMode }) {
  const waterTexture = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 256
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#0891b2'
    ctx.fillRect(0, 0, 256, 256)
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'
    ctx.lineWidth = 1.5
    for (let i = 0; i < 20; i++) {
      ctx.beginPath()
      ctx.arc(Math.random() * 256, Math.random() * 256, 10 + Math.random() * 28, 0, Math.PI * 2)
      ctx.stroke()
    }
    const t = new THREE.CanvasTexture(canvas)
    t.wrapS = t.wrapT = THREE.RepeatWrapping
    t.repeat.set(3, 2)
    return t
  }, [])

  return (
    <group position={position}>
      {/* Stone Coping Rim */}
      <mesh receiveShadow position={[0, 0.08, 0]}>
        <boxGeometry args={[width + 0.9, 0.16, length + 0.9]} />
        <meshStandardMaterial color="#cbd5e1" roughness={0.7} metalness={0.05} />
      </mesh>

      {/* Sunken Basin */}
      <mesh receiveShadow position={[0, -depth / 2 + 0.05, 0]}>
        <boxGeometry args={[width, depth, length]} />
        <meshStandardMaterial color="#0e7490" roughness={0.4} metalness={0.1} />
      </mesh>

      {/* Submerged Steps */}
      {[0, 1, 2].map((step) => (
        <mesh key={step} position={[-width / 2 + 0.45 + step * 0.35, -step * 0.22 - 0.05, 0]}>
          <boxGeometry args={[0.35, 0.2, length * 0.7]} />
          <meshStandardMaterial color="#22d3ee" roughness={0.3} />
        </mesh>
      ))}

      {/* Water Surface Plane with realistic refractive physical material */}
      <mesh position={[0, -0.06, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[width - 0.05, length - 0.05]} />
        <meshPhysicalMaterial
          color="#06b6d4"
          transparent
          opacity={0.88}
          transmission={0.82}
          roughness={0.06}
          metalness={0.08}
          ior={1.333}
          map={waterTexture}
        />
      </mesh>

      {/* Underwater Pool Lights */}
      <pointLight position={[-width / 4, -0.4, 0]} intensity={isNightMode ? 3.5 : 1.2} color="#38bdf8" distance={10} />
      <pointLight position={[width / 4, -0.4, 0]} intensity={isNightMode ? 3.5 : 1.2} color="#38bdf8" distance={10} />
    </group>
  )
}

// ── Teak Wood Patio Sun Deck & Outdoor Lounge ────────────────────────
function PatioDeck({ position = [0, 0.02, 5.5], width = 14, length = 4.2 }) {
  const deckTexture = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 256
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#b45309'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 16; i++) {
      ctx.fillStyle = i % 2 === 0 ? '#92400e' : '#78350f'
      ctx.fillRect(i * 16, 0, 14, 256)
    }
    const t = new THREE.CanvasTexture(canvas)
    t.wrapS = t.wrapT = THREE.RepeatWrapping
    t.repeat.set(4, 2)
    return t
  }, [])

  return (
    <group position={position}>
      {/* Wood Decking Platform */}
      <mesh receiveShadow position={[0, 0.06, 0]}>
        <boxGeometry args={[width, 0.12, length]} />
        <meshStandardMaterial color="#92400e" roughness={0.65} map={deckTexture} />
      </mesh>

      {/* Outdoor Sectional Lounge Sofa */}
      <group position={[-width / 3.2, 0.12, -0.4]}>
        <mesh castShadow position={[0, 0.1, 0]}>
          <boxGeometry args={[2.8, 0.2, 1.8]} />
          <meshStandardMaterial color="#1e293b" roughness={0.7} />
        </mesh>
        <mesh castShadow position={[0, 0.26, 0.2]}>
          <boxGeometry args={[2.6, 0.16, 1.3]} />
          <meshStandardMaterial color="#475569" roughness={0.85} />
        </mesh>
        <mesh castShadow position={[0, 0.48, -0.65]}>
          <boxGeometry args={[2.6, 0.38, 0.25]} />
          <meshStandardMaterial color="#334155" roughness={0.85} />
        </mesh>
        <mesh castShadow position={[-1.25, 0.42, 0]}>
          <boxGeometry args={[0.22, 0.32, 1.6]} />
          <meshStandardMaterial color="#1e293b" roughness={0.7} />
        </mesh>
        <mesh castShadow position={[0, 0.16, 1.4]}>
          <boxGeometry args={[1.2, 0.22, 0.7]} />
          <meshStandardMaterial color="#78350f" roughness={0.6} />
        </mesh>
      </group>

      {/* Poolside Sun Loungers */}
      {[-0.8, 0.8].map((xOffset, idx) => (
        <group key={idx} position={[width / 3.2 + xOffset, 0.12, 0.2]}>
          <mesh castShadow position={[0, 0.1, 0]}>
            <boxGeometry args={[0.85, 0.08, 2.0]} />
            <meshStandardMaterial color="#1e293b" roughness={0.6} />
          </mesh>
          <mesh castShadow position={[0, 0.18, 0.2]}>
            <boxGeometry args={[0.78, 0.1, 1.3]} />
            <meshStandardMaterial color="#f8fafc" roughness={0.9} />
          </mesh>
          <mesh castShadow position={[0, 0.32, -0.6]} rotation={[-0.5, 0, 0]}>
            <boxGeometry args={[0.78, 0.1, 0.6]} />
            <meshStandardMaterial color="#f8fafc" roughness={0.9} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

// ── Lush Emerald Landscape & Garden Grounds ─────────────────────────
function LandscapeGround({ bounds }) {
  const lawnSize = Math.max(bounds.w * 1.8, bounds.l * 1.8 + 20, 60)

  return (
    <group position={[bounds.cx, -0.16, bounds.cz + 3.0]}>
      {/* Manicured Grass Lawn */}
      <mesh receiveShadow position={[0, 0, 0]}>
        <boxGeometry args={[lawnSize, 0.12, lawnSize]} />
        <meshStandardMaterial color="#193519" roughness={0.94} metalness={0.0} />
      </mesh>

      {/* Garden Stepping Stone Pavers */}
      {[-3, -2, -1, 0, 1, 2, 3].map((step) => (
        <mesh key={step} receiveShadow position={[bounds.w / 2 + 2.2, 0.07, step * 2.2]}>
          <boxGeometry args={[0.9, 0.04, 1.4]} />
          <meshStandardMaterial color="#94a3b8" roughness={0.7} />
        </mesh>
      ))}

      {/* Perimeter Modern Hedges */}
      <mesh position={[-lawnSize / 2 + 1.2, 0.6, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.5, 1.2, lawnSize * 0.85]} />
        <meshStandardMaterial color="#14532d" roughness={0.9} />
      </mesh>
      <mesh position={[lawnSize / 2 - 1.2, 0.6, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.5, 1.2, lawnSize * 0.85]} />
        <meshStandardMaterial color="#14532d" roughness={0.9} />
      </mesh>
    </group>
  )
}

// ── Floating Room Callout Tag (Matching User Reference Image) ────────
function RoomCalloutTag({ room, onClick, isSelected }) {
  const rx = Number(room.position?.x) || 0
  const ry = (Number(room.position?.y) || 0) + (Number(room.height) || 3.0) + 0.6
  const rz = Number(room.position?.z) || 0
  const meta = getRoomMeta(room.type)
  const IconComp = meta.icon

  return (
    <group position={[rx, ry, rz]}>
      <Html center distanceFactor={28} zIndexRange={[100, 0]}>
        <button
          type="button"
          onClick={onClick}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: isSelected ? 'rgba(16, 185, 129, 0.95)' : 'rgba(15, 23, 42, 0.88)',
            backdropFilter: 'blur(16px)',
            border: `1px solid ${isSelected ? '#10b981' : 'rgba(255, 255, 255, 0.2)'}`,
            borderRadius: 999,
            padding: '4px 12px',
            color: '#ffffff',
            fontSize: '0.75rem',
            fontWeight: 700,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            transform: isSelected ? 'scale(1.08)' : 'scale(1)',
            transition: 'all 0.2s ease',
          }}
        >
          <IconComp size={13} color={isSelected ? '#ffffff' : meta.color} />
          <span>{room.type}</span>
          <span style={{ fontSize: '0.65rem', opacity: 0.7 }}>▶</span>
        </button>
      </Html>
    </group>
  )
}

// ── Unified Architectural Foundation Podium ─────────────────────────
function ArchitecturalPodium({ bounds }) {
  return (
    <group position={[bounds.cx, -0.1, bounds.cz]}>
      <mesh receiveShadow position={[0, 0, 0]}>
        <boxGeometry args={[bounds.w + 1.2, 0.2, bounds.l + 1.2]} />
        <meshStandardMaterial color="#1e293b" roughness={0.85} metalness={0.1} />
      </mesh>
      <mesh receiveShadow position={[0, -0.04, 0]}>
        <boxGeometry args={[bounds.w + 2.2, 0.12, bounds.l + 2.2]} />
        <meshStandardMaterial color="#0f172a" roughness={0.9} metalness={0.05} />
      </mesh>
    </group>
  )
}

// ── Opening Markers (Doors & Windows) ────────────────────────────────
function OpeningMarker({ item, kind }) {
  const position = item?.position || { x: 0, y: 1.2, z: 0 }
  const x = Number(position.x) || 0
  const y = Number(position.y) || 1.2
  const z = Number(position.z) || 0
  const w = Math.max(Number(item?.dimensions?.w || item?.width) || 1.1, 0.6)
  const h = Math.max(Number(item?.dimensions?.h || item?.height) || 2.0, 1.0)
  const isDoor = kind === 'door'

  return (
    <group position={[x, y, z]}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[w, h, isDoor ? 0.14 : 0.09]} />
        <meshStandardMaterial
          color={isDoor ? '#4a3728' : '#273549'}
          roughness={0.4}
          metalness={0.2}
        />
      </mesh>

      {!isDoor ? (
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[w * 0.88, h * 0.86, 0.02]} />
          <meshStandardMaterial
            color="#93c5fd"
            roughness={0.1}
            metalness={0.9}
            transparent={true}
            opacity={0.4}
          />
        </mesh>
      ) : (
        <mesh position={[0, 0, 0]} castShadow>
          <boxGeometry args={[w * 0.92, h * 0.94, 0.05]} />
          <meshStandardMaterial color="#6b4c35" roughness={0.7} metalness={0.05} />
        </mesh>
      )}
    </group>
  )
}

// ── Walkthrough Character ────────────────────────────────────────────
function CharacterAvatar({ position, rotation, isMoving, walkCycle, isVisible }) {
  if (!isVisible) return null

  const swing = isMoving ? Math.sin(walkCycle) * 0.45 : 0
  const bob = isMoving ? Math.abs(Math.sin(walkCycle * 2)) * 0.04 : 0

  return (
    <group position={[position.x, position.y + bob, position.z]} rotation={[0, rotation, 0]}>
      <mesh position={[0, 1.76, 0]} castShadow>
        <boxGeometry args={[0.34, 0.34, 0.32]} />
        <meshStandardMaterial color="#fcd34d" roughness={0.7} />
      </mesh>
      <mesh position={[0, 1.94, 0]} castShadow>
        <boxGeometry args={[0.36, 0.1, 0.34]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>
      <mesh position={[0, 1.25, 0]} castShadow>
        <boxGeometry args={[0.44, 0.62, 0.24]} />
        <meshStandardMaterial color="#10b981" roughness={0.7} />
      </mesh>

      <group position={[-0.28, 1.42, 0]} rotation={[swing, 0, 0]}>
        <mesh position={[0, -0.22, 0]} castShadow>
          <boxGeometry args={[0.13, 0.46, 0.13]} />
          <meshStandardMaterial color="#10b981" roughness={0.7} />
        </mesh>
      </group>
      <group position={[0.28, 1.42, 0]} rotation={[-swing, 0, 0]}>
        <mesh position={[0, -0.22, 0]} castShadow>
          <boxGeometry args={[0.13, 0.46, 0.13]} />
          <meshStandardMaterial color="#10b981" roughness={0.7} />
        </mesh>
      </group>

      <group position={[-0.13, 0.85, 0]} rotation={[-swing, 0, 0]}>
        <mesh position={[0, -0.32, 0]} castShadow>
          <boxGeometry args={[0.16, 0.58, 0.16]} />
          <meshStandardMaterial color="#1e293b" roughness={0.8} />
        </mesh>
        <mesh position={[0, -0.62, 0.04]} castShadow>
          <boxGeometry args={[0.17, 0.08, 0.24]} />
          <meshStandardMaterial color="#0f172a" roughness={0.5} />
        </mesh>
      </group>
      <group position={[0.13, 0.85, 0]} rotation={[swing, 0, 0]}>
        <mesh position={[0, -0.32, 0]} castShadow>
          <boxGeometry args={[0.16, 0.58, 0.16]} />
          <meshStandardMaterial color="#1e293b" roughness={0.8} />
        </mesh>
        <mesh position={[0, -0.62, 0.04]} castShadow>
          <boxGeometry args={[0.17, 0.08, 0.24]} />
          <meshStandardMaterial color="#0f172a" roughness={0.5} />
        </mesh>
      </group>
    </group>
  )
}

// ── Smooth Camera Controller ─────────────────────────────────────────
function CameraController({ controlsRef, targetPos, targetCamPos, viewMode }) {
  useFrame(() => {
    if (!controlsRef.current || !targetPos.current) return
    if (viewMode !== 'walkthrough') {
      controlsRef.current.target.lerp(targetPos.current, 0.09)
      if (targetCamPos.current) {
        controlsRef.current.object.position.lerp(targetCamPos.current, 0.09)
      }
      controlsRef.current.update()
    }
  })
  return null
}

// ── Blender Headless GLB Model Component ─────────────────────────────
function BlenderHouseModel({ url }) {
  const { scene } = useGLTF(url)
  const clonedScene = useMemo(() => {
    if (!scene) return null
    const clone = scene.clone(true)
    clone.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true
        child.receiveShadow = true
      }
    })
    return clone
  }, [scene])

  if (!clonedScene) return null
  return <primitive object={clonedScene} position={[0, 0, 0]} />
}

// ── Main Professional Viewer3D Component ─────────────────────────────
export default function Viewer3D({ design }) {
  const glbUrl = design?.glb_url || design?.model_url || null
  const [viewSource, setViewSource] = useState(glbUrl ? 'blender' : 'procedural')

  useEffect(() => {
    if (glbUrl) {
      setViewSource('blender')
    }
  }, [glbUrl])

  const [viewMode, setViewMode] = useState('dollhouse')
  const [isNightMode, setIsNightMode] = useState(false)
  const [selectedRoomId, setSelectedRoomId] = useState('overview')

  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showInfoPopover, setShowInfoPopover] = useState(false)
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
          shadow-bias={-0.0002}
        />

        {/* ── Architectural Landscape Grounds ── */}
        <LandscapeGround bounds={houseBounds} />
        <ArchitecturalPodium bounds={houseBounds} />

        {/* ── Teak Patio Deck & Swimming Pool ── */}
        <PatioDeck
          position={[0, 0.02, (houseBounds.maxZ || 4.0) + 2.4]}
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

        {/* ── Architectural House Model: Blender GLB or Procedural CAD ── */}
        {viewSource === 'blender' && glbUrl ? (
          <Suspense
            fallback={
              <Html center>
                <div
                  style={{
                    background: 'rgba(15, 23, 42, 0.92)',
                    border: '1px solid rgba(56, 189, 248, 0.4)',
                    backdropFilter: 'blur(12px)',
                    borderRadius: 12,
                    padding: '14px 22px',
                    color: '#38bdf8',
                    fontWeight: 600,
                    fontSize: '0.88rem',
                    boxShadow: '0 12px 36px rgba(0,0,0,0.6)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    whiteSpace: 'nowrap',
                  }}
                >
                  <Sparkles size={16} className="animate-spin" />
                  <span>Loading Photorealistic 3D Model...</span>
                </div>
              </Html>
            }
          >
            <BlenderHouseModel url={glbUrl} />
          </Suspense>
        ) : (
          <>
            {/* Contiguous Architectural Rooms */}
            {rooms.map((room, idx) => (
              <RoomVolume
                key={room.id || `room-${idx}`}
                room={room}
                viewMode={viewMode}
                isSelected={selectedRoomId === room.id}
                isNightMode={isNightMode}
              />
            ))}

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

      {/* ── Top Left: Viewport Mode Switcher & Source Toggle ── */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 14,
          display: 'flex',
          gap: 6,
          alignItems: 'center',
          zIndex: 10,
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: 4,
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 999,
            padding: 3,
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          }}
        >
          {[
            { id: 'dollhouse', icon: Home, label: 'Dollhouse 3D' },
            { id: 'walkthrough', icon: Footprints, label: 'Walkthrough' },
            { id: 'plan', icon: Grid3X3, label: 'Floor Plan' },
          ].map((mode) => {
            const IconComp = mode.icon
            const isActive = viewMode === mode.id
            return (
              <button
                key={mode.id}
                type="button"
                onClick={() => handleModeChange(mode.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '5px 12px',
                  borderRadius: 999,
                  border: 'none',
                  background: isActive ? 'var(--accent)' : 'transparent',
                  color: isActive ? '#ffffff' : 'var(--text-secondary)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <IconComp size={14} />
                <span>{mode.label}</span>
              </button>
            )
          })}
        </div>

        {/* Blender Photorealistic 3D Model Switcher */}
        {glbUrl && (
          <div
            style={{
              display: 'flex',
              background: 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(56, 189, 248, 0.35)',
              borderRadius: 999,
              padding: 3,
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            }}
          >
            <button
              type="button"
              onClick={() => setViewSource(viewSource === 'blender' ? 'procedural' : 'blender')}
              title="Toggle between Blender Photorealistic 3D Model and CAD Floor Plan"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 12px',
                borderRadius: 999,
                border: 'none',
                background: viewSource === 'blender' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                color: viewSource === 'blender' ? '#38bdf8' : 'var(--text-secondary)',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Sparkles size={13} />
              <span>{viewSource === 'blender' ? 'Blender 3D' : 'CAD View'}</span>
            </button>
          </div>
        )}
      </div>


      {/* ── Top Right: Stats Details in ! Icon + Day/Night + Tools ── */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 14,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          zIndex: 10,
        }}
      >
        {/* Toggle Floating Room Tags (Reference Image Feature) */}
        {viewMode !== 'walkthrough' && (
          <button
            type="button"
            onClick={() => setShowCallouts(!showCallouts)}
            title="Toggle Room Callout Tags"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: showCallouts ? 'rgba(16, 185, 129, 0.2)' : 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: `1px solid ${showCallouts ? '#10b981' : 'rgba(255, 255, 255, 0.12)'}`,
              borderRadius: 999,
              padding: '5px 11px',
              color: showCallouts ? '#10b981' : 'var(--text-primary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          >
            <Tag size={13} />
            <span>Tags</span>
          </button>
        )}

        {/* Mouse Look Direction Toggle Button for Walkthrough */}
        {viewMode === 'walkthrough' && (
          <button
            type="button"
            onClick={toggleMouseLook}
            title="Toggle Mouse Look Direction (or press Ctrl key)"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: isMouseLookLocked ? 'var(--accent)' : 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: `1px solid ${isMouseLookLocked ? 'var(--accent)' : 'rgba(255, 255, 255, 0.15)'}`,
              borderRadius: 999,
              padding: '5px 12px',
              color: isMouseLookLocked ? '#ffffff' : 'var(--text-primary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          >
            <MousePointer size={14} />
            <span>{isMouseLookLocked ? 'Mouse ON (Ctrl)' : 'Mouse (Ctrl)'}</span>
          </button>
        )}

        {/* Architectural Details Info Button in a Row with Day/Night */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setShowInfoPopover(!showInfoPopover)}
            title="View Architectural Details"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: showInfoPopover ? 'var(--accent)' : 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 999,
              padding: '5px 13px',
              color: showInfoPopover ? '#ffffff' : 'var(--text-primary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          >
            <Info size={14} />
            <span>{rooms.length}</span>
            <span>Rooms</span>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>•</span>
            <span>{doors.length} Doors</span>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>•</span>
            <span>{windows.length} Windows</span>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>•</span>
            <span style={{ textTransform: 'capitalize', color: '#fbbf24' }}>{design?.style || 'Modern'}</span>
          </button>

          {/* Floating Details Popover Card */}
          {showInfoPopover && (
            <div
              style={{
                position: 'absolute',
                top: 38,
                right: 0,
                width: 280,
                background: 'rgba(15, 23, 42, 0.95)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: 'var(--radius-md)',
                padding: '14px 16px',
                zIndex: 30,
                boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: 8 }}>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Design Specifications</div>
                <button
                  type="button"
                  onClick={() => setShowInfoPopover(false)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem' }}
                >
                  ✕
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Rooms</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent)' }}>{rooms.length}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Doors</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff' }}>{doors.length}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Windows</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff' }}>{windows.length}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Style</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fbbf24', textTransform: 'capitalize', marginTop: 3 }}>
                    {design?.style || 'Modern'}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 2 }}>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase' }}>
                  Room Dimensions
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 120, overflowY: 'auto' }}>
                  {rooms.map((r, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      <span>{r.type}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{r.width}m × {r.length}m</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Night / Day Toggle */}
        <button
          type="button"
          onClick={() => setIsNightMode(!isNightMode)}
          title={isNightMode ? 'Switch to Day Mode' : 'Switch to Night Glow'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 999,
            padding: '5px 12px',
            color: isNightMode ? '#fbbf24' : 'var(--text-primary)',
            fontSize: '0.78rem',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          }}
        >
          {isNightMode ? <Moon size={14} /> : <Sun size={14} />}
          <span>{isNightMode ? 'Night' : 'Day'}</span>
        </button>

        {/* Reset Camera Button */}
        <button
          type="button"
          onClick={handleResetCamera}
          title="Reset Camera to Full View"
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '50%',
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-primary)',
            cursor: 'pointer',
          }}
        >
          <RotateCcw size={14} />
        </button>

        {/* Fullscreen Button */}
        <button
          type="button"
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '50%',
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-primary)',
            cursor: 'pointer',
          }}
        >
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* ── Bottom Floating Room Navigator Strip (Lucide Icons) ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 32,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          background: 'rgba(15, 23, 42, 0.88)',
          backdropFilter: 'blur(18px)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 999,
          padding: '4px 6px',
          maxWidth: '92%',
          overflowX: 'auto',
          zIndex: 10,
          boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
        }}
      >
        <button
          type="button"
          onClick={handleResetCamera}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '5px 12px',
            borderRadius: 999,
            border: 'none',
            background: selectedRoomId === 'overview' ? 'var(--accent)' : 'rgba(255, 255, 255, 0.06)',
            color: selectedRoomId === 'overview' ? '#ffffff' : 'var(--text-secondary)',
            fontSize: '0.75rem',
            fontWeight: 600,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            transition: 'all 0.15s ease',
          }}
        >
          <Home size={13} />
          <span>Overview</span>
        </button>

        <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.15)', flexShrink: 0 }} />

        {rooms.map((room) => {
          const meta = getRoomMeta(room.type)
          const RoomIconComp = meta.icon
          const isSelected = selectedRoomId === room.id
          return (
            <button
              key={room.id || room.type}
              type="button"
              onClick={() => handleSelectRoom(room)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 11px',
                borderRadius: 999,
                border: `1px solid ${isSelected ? meta.color : 'transparent'}`,
                background: isSelected ? 'rgba(255,255,255,0.15)' : 'rgba(255, 255, 255, 0.05)',
                color: isSelected ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
            >
              <RoomIconComp size={13} color={isSelected ? meta.color : 'currentColor'} />
              <span>{room.type}</span>
            </button>
          )
        })}
      </div>

      {/* ── Center Crosshair for Mouse Look ── */}
      {viewMode === 'walkthrough' && isMouseLookLocked && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
            zIndex: 20,
            width: 7,
            height: 7,
            border: '2px solid rgba(255, 255, 255, 0.85)',
            borderRadius: '50%',
            boxShadow: '0 0 8px rgba(0,0,0,0.7)',
          }}
        />
      )}

      {/* ── Bottom Controls Guide ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'rgba(255, 255, 255, 0.45)',
          fontSize: '0.6875rem',
          fontWeight: 500,
          pointerEvents: 'none',
          whiteSpace: 'nowrap',
          zIndex: 10,
        }}
      >
        {viewMode === 'walkthrough' ? (
          <>
            <span><strong style={{ color: '#fbbf24' }}>[Ctrl]</strong> {isMouseLookLocked ? 'Release Mouse' : 'Enable Mouse Look'}</span>
            <span>•</span>
            <span><strong style={{ color: '#6ee7b7' }}>Mouse</strong> Look direction</span>
            <span>•</span>
            <span><strong style={{ color: '#6ee7b7' }}>WASD</strong> Walk</span>
          </>
        ) : (
          <>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>WASD</strong> to walk</span>
            <span>•</span>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>Left Click</strong> orbit</span>
            <span>•</span>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>Right Click</strong> pan</span>
            <span>•</span>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>Scroll</strong> zoom</span>
          </>
        )}
      </div>
    </div>
  )
}
