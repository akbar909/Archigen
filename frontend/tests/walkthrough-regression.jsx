import React from 'react'
import { createRoot } from 'react-dom/client'
import * as THREE from 'three'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import Viewer3D from '../src/components/viewer3d'
import { useProjectStore } from '../src/store'
import { apiClient, setUnauthorizedHandler } from '../src/services/apiClient'
import '../src/index.css'

apiClient.defaults.baseURL = '/api'; setUnauthorizedHandler(() => {})
const scene = new THREE.Scene()
function box(name, size, position, data = {}, color = '#ddd') {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), new THREE.MeshStandardMaterial({ color }))
  mesh.name = name; mesh.position.fromArray(position); mesh.userData = data; scene.add(mesh)
}
const rooms = [0, 1].map(level => ({ id: `stair_lobby_l${level}`, name: `Stair Lobby ${level}`, type: 'stair_lobby',
  floor_level: level, position: { x: 0, y: 0, z: level * 3 }, dimensions: { width: 4.6, depth: 2.6, height: 3 } }))
const stair = { id: 'stairs', type: 'u_shaped', run_axis: 'x', room_id: 'stair_lobby_l0', floor_level: 0,
  position: { x: .15, y: .2, z: 0 }, dimensions: { width: 3.25, depth: 2.2, height: 3 },
  landing_depth: 1, clear_width: 1, steps: 18, opening_clearance: .05 }
const floors = rooms.map((room, level) => {
  // Upper floor is split around the opening, as happens with boolean GLBs.
  box(`Floor_L${level}_${room.id}`, level ? [1.1, .1, 2.6] : [4.6, .1, 2.6],
    [level ? 4.05 : 2.3, level * 3 - .05, -1.3], { archgen_room_id: room.id, archgen_floor_level: level }, '#776655')
  const walls = [
    { id: `south${level}`, start: { x: 0, y: 0 }, end: { x: 4.6, y: 0 } },
    { id: `north${level}`, start: { x: 0, y: 2.6 }, end: { x: 4.6, y: 2.6 } },
    { id: `west${level}`, start: { x: 0, y: 0 }, end: { x: 0, y: 2.6 } },
    { id: `east${level}`, start: { x: 4.6, y: 0 }, end: { x: 4.6, y: 2.6 } },
  ]
  for (const w of walls) box(`Wall_${w.id}`, [Math.abs(w.end.x - w.start.x) || .2, 3, Math.abs(w.end.y - w.start.y) || .2],
    [(w.start.x + w.end.x) / 2, level * 3 + 1.5, -(w.start.y + w.end.y) / 2],
    { archgen_wall_id: w.id, archgen_connected_rooms: room.id, archgen_floor_level: level })
  return { id: `f${level}`, level, elevation: level * 3, floor_height: 3, rooms: [room], walls,
    stairs: level ? [] : [stair], stair_openings: level ? [{ ...stair, type: 'stair_void', serves_stair_id: stair.id,
      position: { ...stair.position, z: 3 }, dimensions: { width: 3.3, depth: 2.25 } }] : [] }
})
// Another detected room on each floor reproduces the previous incorrect
// fallback when a real "stair_lobby" slab was filtered out by its name.
for (const floor of floors) {
  const level = floor.level
  const bathroom = { id: `bathroom_l${level}`, name: `Bathroom ${level}`, type: 'bathroom', floor_level: level,
    position: { x: 4.6, y: 0, z: level * 3 }, dimensions: { width: 1.5, depth: 2.6, height: 3 } }
  rooms.push(bathroom); floor.rooms.push(bathroom)
  box(`Floor_L${level}_${bathroom.id}`, [1.5, .1, 2.6], [5.35, level * 3 - .05, -1.3],
    { archgen_room_id: bathroom.id, archgen_floor_level: level }, '#ddd')
}
for (let i = 0; i < 9; i++) {
  const data = { archgen_stair_id: 'stairs', archgen_floor_level: 0, archgen_upper_floor_level: 1 }
  box(`Stair_Lower_${i}`, [.275, .14, 1.02], [3.4 - (i + .5) * .25, (i + 1) / 6, -.71], data, '#a97949')
  box(`Stair_Upper_${i}`, [.275, .14, 1.02], [1.15 + (i + .5) * .25, 1.5 + (i + 1) / 6, -1.89], data, '#a97949')
}
box('Stair_Landing', [1, .18, 2.2], [.65, 1.5, -1.3], { archgen_stair_id: 'stairs' }, '#a97949')
const buffer = await new GLTFExporter().parseAsync(scene, { binary: true })
const design = { rooms, floors, furniture: [], building: { floor_height: 3, wall_thickness: .2 },
  layout_approved: true, glb_url: URL.createObjectURL(new Blob([buffer], { type: 'model/gltf-binary' })) }
useProjectStore.setState({ design, persistedDesign: structuredClone(design), activeProjectId: 'walk', activeVersionId: 'walk1', sidebarOpen: false })
window.walkDesign = () => structuredClone(useProjectStore.getState().design)
function App() { const current = useProjectStore(s => s.design); return <div style={{ width: '100vw', height: '100vh' }}><Viewer3D design={current} /></div> }
createRoot(document.getElementById('root')).render(<App />)
