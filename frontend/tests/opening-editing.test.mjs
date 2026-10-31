import test from 'node:test'
import assert from 'node:assert/strict'
import * as THREE from 'three'
import { canonicalOpenings, collectOpeningRoots, openingFromObject, prepareOpeningModel, resolveOpeningAsset, setOpeningOverride } from '../src/utils/openingEditing.js'
import { findEditableSurface } from '../src/utils/sceneEditing.js'

test('large and small assets fill both horizontal and vertical openings without moving the bottom', () => {
  for (const dimensions of [[8, 5, 0.8], [0.3, 0.4, 0.05]]) {
    for (const rotation of [0, Math.PI / 2]) {
      const source = new THREE.Group()
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(...dimensions), new THREE.MeshStandardMaterial())
      mesh.position.set(5, 7, -3)
      source.add(mesh)
      const opening = { width: 1.4, height: 1.1, depth: 0.22 }
      const model = prepareOpeningModel(source, {}, opening)
      model.object.scale.set(...model.scale)
      model.object.rotation.y = rotation
      model.object.position.set(2, 4.2, -6)
      const bounds = new THREE.Box3().setFromObject(model.object, true)
      const size = bounds.getSize(new THREE.Vector3())
      assert.ok(Math.abs(size.x - (rotation ? 0.22 : 1.4)) < 1e-6)
      assert.ok(Math.abs(size.z - (rotation ? 1.4 : 0.22)) < 1e-6)
      assert.ok(Math.abs(size.y - 1.1) < 1e-6)
      assert.ok(Math.abs(bounds.min.y - 4.2) < 1e-6)
      assert.deepEqual(mesh.position.toArray(), [5, 7, -3], 'cached source remains unchanged')
    }
  }
})

test('metadata roots and detached glass select one stable opening', () => {
  const scene = new THREE.Group()
  const root = new THREE.Group()
  root.name = 'Window_L1_window_1'
  root.userData = { archgen_opening_kind: 'window', archgen_opening_id: 'window_1',
    archgen_opening_width: 2, archgen_opening_height: 1, archgen_opening_vertical: true,
    archgen_opening_x: 4, archgen_opening_y: 5, archgen_opening_base_z: 4.4 }
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1))
  root.add(mesh)
  const glass = mesh.clone()
  glass.name = 'WindowGlass_L1_window_1'
  scene.add(root, glass)
  const roots = collectOpeningRoots(scene)
  assert.equal(roots.size, 1)
  assert.equal(roots.get('window:window_1').originals.length, 2)
  assert.equal(findEditableSurface(mesh, scene).id, 'window_1')
  assert.equal(findEditableSurface(glass, scene).id, 'window_1')
  assert.deepEqual(openingFromObject(root).position, [4, 4.4, -5])
  assert.equal(openingFromObject(root).rotation, Math.PI / 2)
  assert.equal(openingFromObject(new THREE.Group()), null)
})

test('save, refresh URLs, category isolation and restore preserve wall geometry', () => {
  const design = { windows: [{ id: 'one', width: 2, height: 1 }], walls: [{ id: 'wall' }] }
  const initial = JSON.stringify(design)
  const selection = { type: 'window', id: 'one', opening: { width: 2, height: 1 } }
  const asset = { id: 'small', group: 'window', s3_key: 'assets/windows/small.glb', model_path: '/old.glb' }
  setOpeningOverride(design, selection, asset)
  const saved = JSON.parse(JSON.stringify(design))
  assert.equal(resolveOpeningAsset(saved.opening_overrides['window:one'], [{ ...asset, model_path: '/fresh.glb' }]).model_path, '/fresh.glb')
  setOpeningOverride(design, selection, { ...asset, group: 'curtain' })
  assert.equal(design.opening_overrides['window:one'].asset_id, 'small')
  setOpeningOverride(design, selection, null)
  delete design.opening_overrides
  assert.equal(JSON.stringify(design), initial)
})

test('legacy GLB wrappers recover aperture size from the saved layout, not the open leaf bounds', () => {
  const definitions = canonicalOpenings({ floors: [{ level: 1, elevation: 3.4,
    walls: [{ id: 'east_wall', start: { x: 4, y: 0 }, end: { x: 4, y: 6 } }],
    doors: [{ id: 'bed_door', wall_id: 'east_wall', position: { x: 4, y: 2, z: 3.4 }, width: 0.9, height: 2.1 }],
    windows: [{ id: 'win', wall_side: 'north', position: { x: 2, y: 6 }, sill_height: 1, width: 1.4, height: 1.2 }],
  }] })
  assert.equal(definitions.length, 2)
  assert.deepEqual(definitions[1].position, [2, 4.4, -6])
  const scene = new THREE.Group()
  const door = new THREE.Group()
  door.name = 'door_asset_0'
  door.position.set(4, 3.4, -2)
  const leaf = new THREE.Mesh(new THREE.BoxGeometry(0.1, 2.1, 0.9))
  leaf.name = 'door_asset_0_part_01'
  leaf.position.set(0.35, 1.05, 0.3)
  leaf.userData = { archgen_opening_kind: 'door', archgen_opening_id: 'partial-child' }
  door.add(leaf)
  scene.add(door)
  const roots = collectOpeningRoots(scene, definitions)
  assert.equal(roots.size, 1)
  const entry = roots.get('door:bed_door')
  assert.deepEqual(entry.originals, [door])
  assert.equal(entry.opening.width, 0.9)
  assert.equal(entry.opening.rotation, Math.PI / 2)
  assert.equal(findEditableSurface(leaf, scene).object, door)
  assert.equal(openingFromObject(door).source, 'layout')
  door.visible = false
  assert.equal(collectOpeningRoots(scene, definitions).get('door:bed_door').visible, true)
})

test('legacy named windows include detached glass, while ambiguous or unrelated meshes are rejected', () => {
  const definitions = canonicalOpenings({ windows: [
    { id: 'win', width: 1.4, height: 1.1, wall_side: 'front', position: { x: 2, y: 4, z: 1 } },
  ] })
  const scene = new THREE.Group()
  for (const name of ['WindowFrame_L0_win', 'WindowGlass_L0_win']) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.1, 0.2))
    mesh.name = name
    mesh.position.set(2, 1.55, -4)
    scene.add(mesh)
  }
  assert.equal(collectOpeningRoots(scene, definitions).get('window:win').originals.length, 2)
  const ambiguous = scene.children[0].clone()
  ambiguous.name = 'window_asset_0'
  ambiguous.userData = {}
  const secondScene = new THREE.Group()
  secondScene.add(ambiguous)
  assert.equal(collectOpeningRoots(secondScene, [...definitions, { ...definitions[0], id: 'other' }]).size, 0)
  ambiguous.position.x = 20
  assert.equal(collectOpeningRoots(secondScene, definitions).size, 0)
})
