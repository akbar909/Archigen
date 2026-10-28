import React from 'react'
import { createRoot } from 'react-dom/client'
import Viewer3D from '../src/components/viewer3d'
import { useProjectStore } from '../src/store'
import { apiClient, setUnauthorizedHandler } from '../src/services/apiClient'
import '../src/index.css'

apiClient.defaults.baseURL = '/api'
setUnauthorizedHandler(() => {})
const rooms = [
  { id: 'kitchen', name: 'Kitchen', type: 'kitchen', floor_level: 0, position: { x: 0, y: 0, z: 0 }, dimensions: { width: 4, depth: 4, height: 3.4 } },
  { id: 'bedroom', name: 'Bedroom', type: 'bedroom', floor_level: 0, position: { x: 6, y: 0, z: 0 }, dimensions: { width: 4, depth: 4, height: 3.4 } },
  { id: 'upper_bedroom', name: 'Upper Bedroom', type: 'bedroom', floor_level: 1, position: { x: 6, y: 6, z: 3.4 }, dimensions: { width: 4, depth: 4, height: 3.4 } },
]
const furniture = [{ id: 'existing_counter', category: 'kitchen_cabinet', room_id: 'kitchen', position: { x: 2, y: 2, z: 0 }, dimensions: { width: 1, depth: 0.6, height: 1 } }]
const design = { rooms, furniture, layout_approved: true, building: { floor_height: 3.4 },
  glb_url: `${location.origin}/asset-test/architecture/walls/designs/wall_panel_01.glb`,
  floors: [0, 1].map((level) => ({ id: `floor_${level}`, level, rooms: rooms.filter((room) => room.floor_level === level), furniture: level ? [] : furniture })),
}
useProjectStore.setState({ design, persistedDesign: structuredClone(design), activeProjectId: 'placement_test', activeVersionId: 'v1', isDirty: false })
window.placementDesign = () => structuredClone(useProjectStore.getState().design)
function App() {
  const current = useProjectStore((state) => state.design)
  return <div style={{ width: '100vw', height: '100vh' }}><Viewer3D design={current} /></div>
}
createRoot(document.getElementById('root')).render(<App />)
