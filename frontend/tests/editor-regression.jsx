import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Canvas, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import EditorCameraFraming from '../src/components/viewer3d/EditorCameraFraming'
import InteriorEditorDrawer from '../src/components/viewer3d/InteriorEditorDrawer'
import { applySurfaceTexture } from '../src/utils/sceneEditing'
import { WalkthroughDragLook, WalkthroughCameraGuard } from '../src/components/viewer3d/WalkthroughControls'
import { createNavigationModel } from '../src/utils/navigation'
import SelectionClickGuard from '../src/components/viewer3d/SelectionClickGuard'
import { isSelectionClick } from '../src/utils/selectionGesture'
import '../src/index.css'
import { apiClient, setUnauthorizedHandler } from '../src/services/apiClient'

apiClient.defaults.baseURL = '/api'
setUnauthorizedHandler(() => {})

const textureFiles = {
  walls: ['brick_wall_diff_2k', 'painted_plaster_wall_diff_2k', 'plaster_wall_diff_2k', 'wood_panel_diff_2k'],
  floors: ['dark_wooden_planks_diff_2k', 'marble_01_diff_2k', 'marble_mosaic_tiles_diff_2k'],
  grounds: ['concrete_pavers_diff_2k', 'leafy_grass_diff_1k'],
}
const navigation = createNavigationModel({ rooms: [{ id: 'test', x: 0, z: 0, w: 12, l: 12, level: 0 }] })

function Scene({ item }) {
  const { camera, gl } = useThree()
  const targetPos = useRef(new THREE.Vector3())
  const targetCamPos = useRef(camera.position.clone())
  const controls = useRef({ target: new THREE.Vector3() })
  const [dragging, setDragging] = useState(false)
  const [transforming, setTransforming] = useState(false)
  const [selection, setSelection] = useState(null)
  const object = useRef(null)
  const wall = useRef(null)
  useEffect(() => {
    window.editorCameraState = () => ({ position: camera.position.toArray(), direction: camera.getWorldDirection(new THREE.Vector3()).toArray() })
    window.editorSetTransforming = setTransforming
    setSelection({ type: 'furniture', id: 'curtain', object: object.current })
    let cancelled = false
    async function verify() {
      const results = []
      for (const [folder, names] of Object.entries(textureFiles)) {
        for (const name of names) {
          const root = new THREE.Group()
          const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 0.1), new THREE.MeshStandardMaterial())
          mesh.geometry.deleteAttribute('uv')
          root.add(mesh)
          const count = await applySurfaceTexture(root, `/asset-test/textures/${folder}/${name}.jpg`)
          results.push({ name, count, loaded: mesh.material.map.image.width > 0, uv: !!mesh.geometry.attributes.uv })
          if (folder === 'walls') await applySurfaceTexture(wall.current, `/asset-test/textures/${folder}/${name}.jpg`)
        }
      }
      if (cancelled) return
      // Allow camera framing and the drawer entry animation to settle.
      await new Promise((resolve) => setTimeout(resolve, 900))
      const canvas = gl.domElement.getBoundingClientRect()
      const drawer = document.querySelector('.interior-editor-drawer').getBoundingClientRect()
      const center = new THREE.Box3().setFromObject(object.current).getCenter(new THREE.Vector3()).project(camera)
      const x = canvas.left + (center.x + 1) * canvas.width / 2
      const y = canvas.top + (1 - center.y) * canvas.height / 2
      window.editorResults = { textures: results, selectionVisible: x < drawer.left || y < drawer.top,
        position: camera.position.toArray(), projection: { x, y }, drawer: { left: drawer.left, top: drawer.top } }
    }
    verify().catch((error) => { window.editorResults = { error: error.stack } })
    return () => { cancelled = true }
  }, [camera, gl])
  return <>
    <SelectionClickGuard isTransforming={transforming} />
    <ambientLight intensity={2} />
    <directionalLight position={[0, 4, 4]} intensity={3} />
    <mesh ref={wall} position={[0, 1.5, -0.15]} onClick={(event) => {
      if (isSelectionClick(event)) window.editorSceneSelectionCount = (window.editorSceneSelectionCount || 0) + 1
    }}><boxGeometry args={[8, 4, 0.1]} /><meshStandardMaterial /></mesh>
    <group ref={object} position={[2, item.mount_height + 0.5, 0]}>
      <mesh><cylinderGeometry args={[0.3, 0.3, 0.06, 48]} /><meshStandardMaterial color="#f6eee4" /></mesh>
    </group>
    <EditorCameraFraming selection={selection} enabled controlsRef={controls} targetPos={targetPos} targetCamPos={targetCamPos}
      viewMode="walkthrough" isCameraDragging={dragging} isTransforming={transforming} />
    <WalkthroughDragLook enabled isTransforming={transforming} controlsRef={controls} targetPos={targetPos}
      targetCamPos={targetCamPos} onDragChange={setDragging} />
    <WalkthroughCameraGuard enabled navigation={navigation} level={0} controlsRef={controls} targetPos={targetPos} targetCamPos={targetCamPos} />
  </>
}

function App() {
  const [selectionType, setSelectionType] = useState('furniture')
  const [libraryRoom, setLibraryRoom] = useState('bedroom')
  const [tintable, setTintable] = useState(false)
  const [item, setItem] = useState({ id: 'curtain', name: 'Curtains', category: 'curtain', wall_mounted: true,
    asset_group: 'curtain', mount_height: 1, position: { x: 2, y: 0, z: 0 }, dimensions: { width: 1.4, height: 1, depth: 0.1 } })
  useEffect(() => { window.editorHeight = item.mount_height }, [item.mount_height])
  useEffect(() => { window.editorSelectSurface = setSelectionType; window.editorSetTintable = setTintable }, [])
  return <div className="viewer-container" style={{ height: '100vh', width: '100vw', position: 'relative', background: '#111' }}>
    <Canvas camera={{ position: [0, 1.65, 4], fov: 44 }} gl={{ preserveDrawingBuffer: true }}><Scene item={item} /></Canvas>
    <div className="viewer-editor-actions">
      <button type="button" className="viewer-edit-toggle active">Done editing</button>
      <button type="button" className="viewer-add-assets" onClick={() => setSelectionType('library')}>+ Add assets</button>
    </div>
    <InteriorEditorDrawer selection={{ type: selectionType, id: selectionType === 'furniture' ? 'curtain' : 'surface', roomId: libraryRoom,
      opening: ['window', 'door'].includes(selectionType) ? { type: selectionType, door_type: 'main_gate', width: 1.4, height: 1.1 } : null }} furniture={item} room={{ id: libraryRoom, name: libraryRoom }} transformMode="translate"
      onSwapOpening={(asset) => { window.editorOpening = asset?.id || 'original' }}
      canAccentColor={tintable}
      rooms={[{ id: 'bedroom', name: 'Bedroom' }, { id: 'kitchen', name: 'Kitchen' }, { id: 'bathroom', name: 'Bathroom' }]}
      onLibraryRoomChange={setLibraryRoom}
      onAddModelAsNew={(asset) => { window.editorAddedAsset = { id: asset.id, roomId: libraryRoom } }}
      onAddWallDecor={(asset) => { window.editorAddedCeilingAsset = asset.id }}
      onNudge={(_, __, height = 0) => setItem((current) => ({ ...current, mount_height: current.mount_height + height }))}
      onClose={() => {}} onRotate={() => {}} onResize={() => {}} onTransformModeChange={() => {}} />
  </div>
}
createRoot(document.getElementById('root')).render(<App />)
