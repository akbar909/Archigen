import React, { Suspense, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Canvas, useThree } from '@react-three/fiber'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import * as THREE from 'three'
import { BlenderHouseModel } from '../src/components/viewer3d/BlenderModel'

const assets = [
  { id: 'small', group: 'window', s3_key: 'small', model_path: '/asset-test/windows/window_standard_02.glb', canonical_yaw_offset_deg: 90 },
  { id: 'large', asset_id: 'standard_window_01', group: 'window', s3_key: 'large', model_path: '/asset-test/architecture/windows/standard/standard_window_01.glb' },
  { id: 'gate', group: 'door', s3_key: 'gate', model_path: '/asset-test/architecture/doors/exterior/Gate.glb', canonical_pitch_offset_deg: 180 },
  { id: 'arched_window_01', asset_id: 'arched_window_01', group: 'window', s3_key: 'arched', model_path: '/models/arched_window_01.glb' },
]

async function fixture() {
  const scene = new THREE.Scene()
  const original = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.1, 0.22), new THREE.MeshStandardMaterial())
  original.name = 'Window_L0_test'
  original.position.set(0, 1.55, 0)
  original.userData = { archgen_opening_kind: 'window', archgen_opening_id: 'test',
    archgen_opening_width: 1.4, archgen_opening_height: 1.1,
    archgen_opening_x: 0, archgen_opening_y: 0, archgen_opening_base_z: 1 }
  const glass = original.clone()
  glass.userData = {}
  glass.name = 'WindowGlass_L0_test'
  const door = original.clone()
  door.name = 'Door_L0_gate'
  door.position.set(3, 1.05, 0)
  door.userData = { ...original.userData, archgen_opening_kind: 'door', archgen_opening_id: 'gate',
    archgen_opening_width: 0.9, archgen_opening_height: 2.1, archgen_opening_x: 3,
    archgen_opening_base_z: 0, archgen_opening_vertical: true }
  if (new URLSearchParams(location.search).has('legacy')) {
    original.userData = {}
    door.userData = {}
    door.name = 'door_asset_0'
  }
  scene.add(original, glass, door)
  const buffer = await new GLTFExporter().parseAsync(scene, { binary: true })
  return URL.createObjectURL(new Blob([buffer], { type: 'model/gltf-binary' }))
}

function Probe() {
  const { scene } = useThree()
  useEffect(() => {
    window.openingSnapshot = () => {
      const replacements = []
      const originals = []
      scene.traverse((object) => {
        if (object.userData.source === 'opening-replacement') {
          const box = new THREE.Box3().setFromObject(object, true)
          const names = []; object.traverse((node) => { if (node.isMesh) names.push(node.name) })
          replacements.push({ names, id: object.userData.entityId, size: box.getSize(new THREE.Vector3()).toArray(), min: box.min.toArray(), visible: object.visible })
        }
        if (/^(Window_L|WindowGlass_L|Door_L|door_asset_0$)/.test(object.name)) originals.push({ name: object.name, visible: object.visible })
      })
      return { replacements, originals }
    }
  }, [scene])
  return null
}

function App() {
  const [url, setUrl] = useState(null)
  const [overrides, setOverrides] = useState({})
  const [level, setLevel] = useState(0)
  const design = useMemo(() => ({ opening_overrides: overrides,
    windows: [{ id: 'test', width: 1.4, height: 1.1, position: { x: 0, y: 0, z: 1 }, wall_side: 'front' }],
    doors: [{ id: 'gate', width: 0.9, height: 2.1, position: { x: 3, y: 0, z: 0 }, wall_side: 'left' }],
  }), [overrides])
  useEffect(() => { fixture().then(setUrl); window.setOpeningAsset = (index) => setOverrides(index == null ? {} : { [index === 2 ? 'door:gate' : 'window:test']: assets[index] }); window.setOpeningFloor = setLevel }, [])
  return <Canvas camera={{ position: [0, 2, 6] }} style={{ height: 600 }}>
    <ambientLight intensity={1} /><Probe />
    {url && <Suspense fallback={null}><BlenderHouseModel url={url} design={design} uploadedAssets={assets} activeFloorLevel={level} /></Suspense>}
  </Canvas>
}
createRoot(document.getElementById('root')).render(<App />)
