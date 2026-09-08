import { useMemo } from 'react'
import * as THREE from 'three'
import { Waves } from 'lucide-react'

// ── Inground Luxury Swimming Pool ────────────────────────────────────
export function SwimmingPool({ position = [2.5, -0.15, 9.5], width = 10.5, length = 4.8, depth = 1.5, isNightMode }) {
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

      {/* Water Surface */}
      <mesh position={[0, -0.06, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[width - 0.05, length - 0.05]} />
        <meshPhysicalMaterial
          color="#06b6d4" transparent opacity={0.88}
          transmission={0.82} roughness={0.06} metalness={0.08}
          ior={1.333} map={waterTexture}
        />
      </mesh>

      {/* Underwater Pool Lights */}
      <pointLight position={[-width / 4, -0.4, 0]} intensity={isNightMode ? 3.5 : 1.2} color="#38bdf8" distance={10} />
      <pointLight position={[width / 4, -0.4, 0]} intensity={isNightMode ? 3.5 : 1.2} color="#38bdf8" distance={10} />
    </group>
  )
}

// ── Teak Wood Patio Sun Deck & Outdoor Lounge ────────────────────────
export function PatioDeck({ position = [0, 0.02, 5.5], width = 14, length = 4.2 }) {
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
export function LandscapeGround({ bounds }) {
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

// ── Unified Architectural Foundation Podium ─────────────────────────
export function ArchitecturalPodium({ bounds }) {
  return (
    <group position={[bounds.cx, -0.12, bounds.cz]}>
      <mesh receiveShadow position={[0, 0, 0]}>
        <boxGeometry args={[bounds.w + 1.2, 0.2, bounds.l + 1.2]} />
        <meshStandardMaterial color="#1e293b" roughness={0.85} metalness={0.1} />
      </mesh>
      <mesh receiveShadow position={[0, -0.05, 0]}>
        <boxGeometry args={[bounds.w + 2.2, 0.12, bounds.l + 2.2]} />
        <meshStandardMaterial color="#0f172a" roughness={0.9} metalness={0.05} />
      </mesh>
    </group>
  )
}
