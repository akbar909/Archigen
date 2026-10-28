import assert from 'node:assert/strict'
import test from 'node:test'
import * as THREE from 'three'
import { clampFurniturePosition, clampMountHeight, ceilingMountedPosition, removeFurnitureById } from './designEditing.js'
import { prepareAssetModel, objectDimensions } from './assetModel.js'

test('wardrobe deletion survives JSON save/reload and leaves the source version intact', () => {
  const wardrobe = { id: 'wardrobe', category: 'wardrobe' }
  const source = { furniture: [wardrobe], rooms: [{ id: 'bedroom', furniture: [wardrobe] }],
    floors: [{ furniture: [wardrobe], rooms: [{ id: 'bedroom', furniture: [wardrobe] }] }] }
  const draft = structuredClone(source)
  removeFurnitureById(draft, 'wardrobe')
  removeFurnitureById(draft, 'wardrobe')
  const saved = JSON.parse(JSON.stringify(draft))
  assert.deepEqual(saved.deleted_furniture_ids, ['wardrobe'])
  assert.equal(saved.furniture.length, 0)
  assert.equal(saved.rooms[0].furniture.length, 0)
  assert.equal(saved.floors[0].furniture.length, 0)
  assert.equal(saved.floors[0].rooms[0].furniture.length, 0)
  assert.equal(source.furniture.length, 1)
  assert.equal(source.deleted_furniture_ids, undefined)
})

test('saved fixture with legacy floor Z is rendered below the correct room ceiling', () => {
  const fixture = { ceiling_mounted: true, position: { x: 2, y: 3, z: 0 }, dimensions: { height: 0.4 } }
  const room = { position: { z: 3.4 }, dimensions: { height: 3.4 } }
  const position = ceilingMountedPosition(fixture, room)
  assert.ok(Math.abs(position.z - 6.34) < 0.00001)
  assert.equal(position.x, 2)
  assert.equal(position.y, 3)
  assert.equal(fixture.position.z, 0)
})

test('curtain height nudges stay above the floor and below the ceiling', () => {
  const curtain = { dimensions: { width: 1.5, height: 2.2, depth: 0.1 } }
  const room = { dimensions: { height: 3 } }
  assert.equal(clampMountHeight(curtain, room, 0.1 + 0.1), 0.2)
  assert.equal(clampMountHeight(curtain, room, -0.1), 0)
  assert.ok(Math.abs(clampMountHeight(curtain, room, 10) - 0.7) < 0.0001)
})

test('rotated furniture remains inside room bounds throughout dragging', () => {
  const room = { bounds: { x: 10, y: 12, width: 4, depth: 4 } }
  const item = { dimensions: { width: 1, depth: 0.6, height: 0.7 }, rotation: 45 }
  const pos = clampFurniturePosition(item, room, { x: 99, y: -20 })
  const half = (1 + 0.6) / Math.sqrt(2) / 2
  assert.ok(pos.x + half <= 14 - 0.139)
  assert.ok(pos.y - half >= 12 + 0.139)
})

test('wall decor slides along its own wall and avoids a window', () => {
  const room = { id: 'dining', bounds: { x: 5, y: 8, width: 5, depth: 4 },
    openings: [{ wall_id: 'dining:north', position: { x: 7.5 }, width: 1.5, height: 2 }] }
  const item = { wall_mounted: true, wall_side: 'back', wall_id: 'dining:north',
    mount_height: 1, rotation: 180, dimensions: { width: 0.8, depth: 0.08, height: 0.6 } }
  const pos = clampFurniturePosition(item, room, { x: 7.5, y: -100 })
  assert.equal(pos.y, 8.16)
  assert.ok(Math.abs(pos.x - 7.5) >= 1.25 - 0.001)
})

test('replacement model retains authored proportions and measured size', () => {
  const scene = new THREE.Group()
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(4, 2, 1), new THREE.MeshStandardMaterial()))
  const normalized = prepareAssetModel(scene, { dimensions: { width: 2, height: 2, depth: 2 } })
  const root = new THREE.Group()
  root.add(normalized.object)
  root.scale.fromArray(normalized.scale)
  const dims = objectDimensions(root)
  assert.equal(dims.width, 2)
  assert.equal(dims.height, 1)
  assert.equal(dims.depth, 0.5)
  assert.equal(scene.children[0].scale.x, 1)
})
