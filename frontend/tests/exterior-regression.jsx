import React from 'react'
import { createRoot } from 'react-dom/client'
import * as THREE from 'three'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import Viewer3D from '../src/components/viewer3d'
import { useProjectStore } from '../src/store'
import { apiClient, setUnauthorizedHandler } from '../src/services/apiClient'
import '../src/index.css'

apiClient.defaults.baseURL = '/api'
setUnauthorizedHandler(() => {})
const scene = new THREE.Scene()
const wall = new THREE.Mesh(new THREE.BoxGeometry(0.15, 1.8, 8), new THREE.MeshStandardMaterial())
wall.name = 'Exterior_Boundary_Wall_1'
wall.position.set(0, 0.9, -4)
const ground = new THREE.Mesh(new THREE.BoxGeometry(50, 0.16, 50), new THREE.MeshStandardMaterial())
ground.name = 'Lush_Garden_Ground'; ground.position.set(4, -0.3, -4)
scene.add(wall, ground)
const buffer = await new GLTFExporter().parseAsync(scene, { binary: true })
const room = { id: 'room', type: 'living_room', name: 'Living room', position: { x: 1, y: 1, z: 0 }, dimensions: { width: 6, depth: 6, height: 3 } }
const design = { rooms: [room], furniture: [], floors: [{ id: 'floor', level: 0, rooms: [room], furniture: [] }],
  site: { plot: { width: 8, depth: 8 } }, exterior: { assets: [] }, layout_approved: true,
  glb_url: URL.createObjectURL(new Blob([buffer], { type: 'model/gltf-binary' })) }
useProjectStore.setState({ design, persistedDesign: structuredClone(design), activeProjectId: 'exterior_test', activeVersionId: 'v1', isDirty: false })
window.exteriorDesign = () => structuredClone(useProjectStore.getState().design)
function App() {
  const current = useProjectStore((state) => state.design)
  return <div style={{ width: '100vw', height: '100vh' }}><Viewer3D design={current} /></div>
}
createRoot(document.getElementById('root')).render(<App />)
