import test from 'node:test'
import assert from 'node:assert/strict'
import * as THREE from 'three'
import { assetSurface, compatibleOpening, placeOnSupport, tabletopSupports } from '../src/utils/assetCompatibility.js'
import { archedWindowScene, cleanOpeningScene } from '../src/utils/openingGeometry.js'
import { isAssetRecommendedForRoom } from '../src/utils/roomAssetLibrary.js'
import { updateFurnitureById, removeFurnitureById } from '../src/utils/designEditing.js'

test('opening menus isolate garage, boundary, entrance and interior doors', () => {
  const names = ['interior_door_01', 'roller_garager_door_01', 'Gate', 'entrance_door_01']
  const types = ['interior', 'garage', 'main_gate', 'entrance']
  for (let i = 0; i < types.length; i++) {
    assert.deepEqual(names.filter((id) => compatibleOpening({ id, group: 'door', model_path: '/model.glb' },
      { type: 'door', door_type: types[i] })), [names[i]])
  }
  assert.equal(compatibleOpening({ id: 'Gate', group: 'door', model_path: '/gate.glb' }, { type: 'window' }), false)
})

test('floor context excludes ceiling fixtures; bathroom recommendations reject fans and chandeliers', () => {
  const room = { type: 'bathroom' }
  for (const id of ['ceiling_fan_02', 'chandelier_02']) {
    const asset = { id, group: 'ceiling_asset' }
    assert.equal(assetSurface(asset), 'ceiling')
    assert.equal(isAssetRecommendedForRoom(asset, room), false)
  }
  assert.equal(isAssetRecommendedForRoom({ id: 'ceiling_lamp_02', group: 'ceiling_asset' }, room), true)
  assert.equal(assetSurface({ mounting: { surface: 'tabletop' } }), 'tabletop')
})

test('tabletop placement survives serialization, table movement and deletion without stale support', () => {
  const table = { id: 'table', category: 'side_table', room_id: 'room', position: { x: 2, y: 3, z: 3.4 }, dimensions: { width: 1, depth: 0.7, height: 0.8 } }
  const clock = { id: 'clock', room_id: 'room', dimensions: { width: 0.18, depth: 0.12, height: 0.22 }, position: { x: 0, y: 0, z: 0 } }
  assert.equal(placeOnSupport(clock, null), null)
  assert.equal(placeOnSupport({ ...clock, dimensions: { width: 2, depth: 2 } }, table), null)
  const placed = placeOnSupport(clock, table)
  assert.ok(Math.abs(placed.position.z - 4.202) < 1e-8)
  const design = JSON.parse(JSON.stringify({ rooms: [{ id: 'room', position: { z: 3.4 }, furniture: [table, placed] }] }))
  assert.equal(tabletopSupports(design.rooms[0]).length, 1)
  updateFurnitureById(design, 'table', { position: { x: 5, y: 6, z: 3.4 } })
  const savedClock = design.rooms[0].furniture[1]
  assert.equal(savedClock.position.x, 5)
  assert.equal(savedClock.position.y, 6)
  removeFurnitureById(design, 'table')
  assert.equal(savedClock.support_id, undefined)
  assert.equal(savedClock.position.z, 3.4)
})

test('window cleanup removes wall and duplicate variant without mutating cached scene', () => {
  const scene = new THREE.Group()
  for (const name of ['Wall001', 'Wall.001', 'Wing_01', 'Wing_01001', 'Frame', 'Frame001']) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial())
    mesh.name = name; scene.add(mesh)
  }
  const clean = cleanOpeningScene(scene, { asset_id: 'standard_window_01' })
  assert.deepEqual(clean.children.map((n) => n.name), ['Wing_01', 'Frame'])
  assert.equal(scene.children.length, 6)
  const arch = archedWindowScene()
  assert.ok(arch.getObjectByName('Arch_wall_infill'))
  const size = new THREE.Box3().setFromObject(arch).getSize(new THREE.Vector3())
  assert.ok(Math.abs(size.x - 1) < 1e-6 && Math.abs(size.y - 1) < 1e-6)
})
