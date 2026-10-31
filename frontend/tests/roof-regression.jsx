/* eslint-disable react-refresh/only-export-components */
import { createRoot } from 'react-dom/client'
import * as THREE from 'three'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import Viewer3D from '../src/components/viewer3d'
import { useProjectStore } from '../src/store'
import { apiClient, setUnauthorizedHandler } from '../src/services/apiClient'
import '../src/index.css'

apiClient.defaults.baseURL = '/api'
setUnauthorizedHandler(() => {})
const variant = new URLSearchParams(location.search).get('shape')
const scene = new THREE.Scene()
const parent = new THREE.Group()
parent.position.set(14, variant === 'large' ? 18 : 4, -20)
if (variant === 'sloped') {
  parent.rotation.set(0.3, 0.8, -0.1)
  parent.scale.set(1.4, 0.8, 1.1)
}
const roof = new THREE.Mesh(new THREE.BoxGeometry(variant === 'large' ? 45 : 12, 0.3, variant === 'large' ? 32 : 8),
  new THREE.MeshStandardMaterial({ color: '#7da4ac', side: THREE.DoubleSide }))
roof.name = 'Roof_L0_focus_test'
parent.add(roof)
scene.add(parent)
scene.updateMatrixWorld(true)
const bounds = new THREE.Box3().setFromObject(roof)
const dimensions = bounds.getSize(new THREE.Vector3())
const center = bounds.getCenter(new THREE.Vector3())
const floor = new THREE.Mesh(new THREE.BoxGeometry(dimensions.x + 2, 0.15, dimensions.z + 2), new THREE.MeshStandardMaterial({ color: '#ded9ca' }))
floor.position.set(center.x, 0, center.z)
floor.name = 'Floor_L0_focus_room'
floor.userData.archgen_room_id = 'focus_room'
scene.add(floor)
const room = { id: 'focus_room', name: 'Roof test room', type: 'living_room',
  position: { x: bounds.min.x - 1, y: -bounds.max.z - 1, z: 0 },
  dimensions: { width: dimensions.x + 2, depth: dimensions.z + 2, height: bounds.max.y + 1 } }
const rooms = variant === 'shared' ? [
  { id: 'living', name: 'Living room', type: 'living_room', position: { x: bounds.min.x, y: -bounds.max.z, z: 0 },
    dimensions: { width: 4, depth: dimensions.z, height: bounds.max.y } },
  { id: 'bedroom', name: 'Bedroom', type: 'bedroom', position: { x: bounds.min.x + 4, y: -bounds.max.z, z: 0 },
    dimensions: { width: dimensions.x - 4, depth: dimensions.z, height: bounds.max.y } },
] : [room]
if (variant === 'shared') {
  scene.remove(floor)
  for (const entry of rooms) {
    const slab = new THREE.Mesh(new THREE.BoxGeometry(entry.dimensions.width, 0.15, entry.dimensions.depth), floor.material)
    slab.position.set(entry.position.x + entry.dimensions.width / 2, 0, -(entry.position.y + entry.dimensions.depth / 2))
    slab.name = `Floor_L0_${entry.id}`
    slab.userData.archgen_room_id = entry.id
    scene.add(slab)
  }
  const divider = new THREE.Mesh(new THREE.BoxGeometry(0.15, 3.8, dimensions.z), floor.material)
  divider.position.set(bounds.min.x + 4, 1.9, center.z)
  divider.name = 'Wall_L0_room_divider'
  scene.add(divider)
}
window.roofRooms = rooms
const buffer = await new GLTFExporter().parseAsync(scene, { binary: true })
const design = { rooms, furniture: [], floors: [{ id: 'floor_0', level: 0, rooms }], layout_approved: true,
  glb_url: URL.createObjectURL(new Blob([buffer], { type: 'model/gltf-binary' })) }
useProjectStore.setState({ design, persistedDesign: structuredClone(design), activeProjectId: 'roof_test', activeVersionId: 'v1', isDirty: false })
function App() {
  const current = useProjectStore((state) => state.design)
  return <div style={{ width: '100vw', height: '100vh' }}><Viewer3D design={current} /></div>
}
createRoot(document.getElementById('root')).render(<App />)
