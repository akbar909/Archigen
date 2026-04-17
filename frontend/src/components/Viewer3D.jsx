import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment } from '@react-three/drei'

function Room({ room, idx }) {
  const width = Number(room.width) || 1
  const length = Number(room.length) || 1
  const height = Number(room.height) || 3
  const position = room.position || { x: 0, y: 0, z: 0 }
  const x = Number(position.x) || 0
  const y = Number(position.y) || 0
  const z = Number(position.z) || 0

  const colorMap = {
    Bedroom: '#60a5fa',
    Bathroom: '#34d399',
    'Living Room': '#fbbf24',
    Kitchen: '#f87171',
  }
  const color = colorMap[room.type] || '#c084fc'

  // Position rooms on floor plane with y = height/2 to rest on ground
  return (
    <mesh position={[x, height / 2 + y, z]} castShadow receiveShadow>
      <boxGeometry args={[width, height, length]} />
      <meshStandardMaterial color={color} opacity={0.9} transparent />
    </mesh>
  )
}

function Floor({ size = 40 }) {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[size, size]} />
      <meshStandardMaterial color="#0f172a" roughness={0.9} />
    </mesh>
  )
}

export default function Viewer3D({ design }) {
  const rooms = Array.isArray(design?.rooms) ? design.rooms : []

  return (
    <div className="glass-card h-[420px] md:h-full relative overflow-hidden">
      <Canvas shadows camera={{ position: [12, 10, 14], fov: 45 }}>
        <color attach="background" args={[0.05, 0.07, 0.12]} />
        <ambientLight intensity={0.4} />
        <directionalLight
          position={[10, 12, 6]}
          intensity={1.1}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
        />
        <Floor />
        {rooms.map((room, idx) => (
          <Room key={room.id || idx} room={room} idx={idx} />
        ))}
        <gridHelper args={[40, 20, '#475569', '#1e293b']} />
        <OrbitControls enablePan enableZoom enableRotate />
        <Environment preset="city" />
      </Canvas>
      <div className="absolute top-2 left-2 bg-slate-900/70 text-xs text-slate-200 px-3 py-2 rounded-lg border border-slate-700">
        {rooms.length > 0 ? `${rooms.length} rooms loaded` : 'Awaiting design'}
      </div>
    </div>
  )
}
