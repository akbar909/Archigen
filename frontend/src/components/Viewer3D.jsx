import { Environment, OrbitControls, Text } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'

const ROOM_COLORS = {
  bedroom: '#4f87ff',
  bathroom: '#36c7a5',
  kitchen: '#ff8f5a',
  living: '#e3b645',
  dining: '#b084f4',
  office: '#7ea7c9',
}

function roomColor(type = '') {
  const key = String(type).toLowerCase()
  if (key.includes('living')) return ROOM_COLORS.living
  if (key.includes('bed')) return ROOM_COLORS.bedroom
  if (key.includes('bath')) return ROOM_COLORS.bathroom
  if (key.includes('kitchen')) return ROOM_COLORS.kitchen
  if (key.includes('dining')) return ROOM_COLORS.dining
  if (key.includes('office')) return ROOM_COLORS.office
  return '#8f9bb3'
}

function RoomVolume({ room }) {
  const width = Math.max(Number(room.width) || 1, 0.5)
  const length = Math.max(Number(room.length) || 1, 0.5)
  const height = Math.max(Number(room.height) || 3, 2.2)
  const position = room.position || { x: 0, y: 0, z: 0 }
  const x = Number(position.x) || 0
  const y = Number(position.y) || 0
  const z = Number(position.z) || 0

  const wallThickness = 0.1
  const slabThickness = 0.08
  const centerY = y + slabThickness / 2
  const roomType = room.type || 'Room'
  const color = roomColor(roomType)

  return (
    <group position={[x, centerY, z]}>
      <mesh receiveShadow>
        <boxGeometry args={[width, slabThickness, length]} />
        <meshStandardMaterial color={color} roughness={0.8} metalness={0.05} />
      </mesh>

      <mesh position={[0, height / 2, -length / 2 + wallThickness / 2]} castShadow receiveShadow>
        <boxGeometry args={[width, height, wallThickness]} />
        <meshStandardMaterial color="#cfd6e6" roughness={0.55} />
      </mesh>
      <mesh position={[0, height / 2, length / 2 - wallThickness / 2]} castShadow receiveShadow>
        <boxGeometry args={[width, height, wallThickness]} />
        <meshStandardMaterial color="#cfd6e6" roughness={0.55} />
      </mesh>
      <mesh position={[-width / 2 + wallThickness / 2, height / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[wallThickness, height, length]} />
        <meshStandardMaterial color="#d6dcea" roughness={0.55} />
      </mesh>
      <mesh position={[width / 2 - wallThickness / 2, height / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[wallThickness, height, length]} />
        <meshStandardMaterial color="#d6dcea" roughness={0.55} />
      </mesh>

      <Text
        position={[0, 0.14, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={Math.max(Math.min(width, length) * 0.12, 0.22)}
        maxWidth={Math.max(width * 0.8, 0.6)}
        color="#0f172a"
        anchorX="center"
        anchorY="middle"
      >
        {roomType}
      </Text>
    </group>
  )
}

function OpeningMarker({ item, kind }) {
  const p = item?.position || { x: 0, y: 0, z: 0 }
  const x = Number(p.x) || 0
  const y = Number(p.y) || 0
  const z = Number(p.z) || 0
  const w = Math.max(Number(item?.width) || 0.9, 0.5)
  const h = Math.max(Number(item?.height) || 2.1, 1.5)
  const isDoor = kind === 'door'

  return (
    <mesh position={[x, y + h / 2, z]} castShadow>
      <boxGeometry args={[w, h, isDoor ? 0.05 : 0.04]} />
      <meshStandardMaterial color={isDoor ? '#e59f5b' : '#77b5ff'} emissive={isDoor ? '#271505' : '#10233f'} />
    </mesh>
  )
}

function BaseSite({ span = 60 }) {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.02, 0]}>
        <planeGeometry args={[span, span]} />
        <meshStandardMaterial color="#101827" roughness={0.92} metalness={0.02} />
      </mesh>
      <gridHelper args={[span, 60, '#334155', '#182233']} position={[0, 0.001, 0]} />
    </group>
  )
}

export default function Viewer3D({ design }) {
  const rooms = Array.isArray(design?.rooms) ? design.rooms : []
  const doors = Array.isArray(design?.doors) ? design.doors : []
  const windows = Array.isArray(design?.windows) ? design.windows : []

  return (
    <div style={{ height: 'clamp(280px, 58vw, 420px)', width: '100%', position: 'relative', overflow: 'hidden' }}>
      <Canvas shadows dpr={[1, 1.5]} camera={{ position: [14, 11, 16], fov: 42, near: 0.1, far: 200 }}>
        <color attach="background" args={[0.055, 0.08, 0.13]} />

        <hemisphereLight intensity={0.4} groundColor="#0a0f18" color="#dbeafe" />
        <ambientLight intensity={0.2} />
        <directionalLight
          position={[14, 18, 12]}
          intensity={1.15}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-left={-30}
          shadow-camera-right={30}
          shadow-camera-top={30}
          shadow-camera-bottom={-30}
        />

        <BaseSite />

        {rooms.map((room, idx) => (
          <RoomVolume key={room.id || `${room.type || 'room'}-${idx}`} room={room} />
        ))}

        {doors.map((door, idx) => (
          <OpeningMarker key={`door-${door.id || idx}`} item={door} kind="door" />
        ))}
        {windows.map((windowItem, idx) => (
          <OpeningMarker key={`window-${windowItem.id || idx}`} item={windowItem} kind="window" />
        ))}

        <OrbitControls enablePan enableZoom enableRotate minDistance={8} maxDistance={60} maxPolarAngle={Math.PI / 2.05} />
        <Environment preset="studio" />
      </Canvas>

      <div style={{
        position: 'absolute', top: 10, left: 10,
        background: 'rgba(13,13,13,0.76)',
        backdropFilter: 'blur(8px)',
        color: 'var(--text-secondary)',
        fontSize: '0.75rem',
        fontWeight: 500,
        padding: '4px 10px',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border)'
      }}>
        {rooms.length > 0 ? `${rooms.length} room${rooms.length !== 1 ? 's' : ''} loaded` : 'Awaiting design'}
      </div>
    </div>
  )
}
