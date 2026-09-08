import * as THREE from 'three'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { getRoomMeta } from './constants'

// ── Floating Room Callout Tag ─────────────────────────────────────────
export function RoomCalloutTag({ room, onClick, isSelected }) {
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

// ── Opening Markers (Doors & Windows) ────────────────────────────────
export function OpeningMarker({ item, kind }) {
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
export function CharacterAvatar({ position, rotation, isMoving, walkCycle, isVisible }) {
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
export function CameraController({ controlsRef, targetPos, targetCamPos, viewMode }) {
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
