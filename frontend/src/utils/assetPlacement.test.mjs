import assert from 'node:assert/strict'
import test from 'node:test'
import { adjustAssetPlacement, createAssetPlacement, placementCameraView, placementRoom } from './assetPlacement.js'

const room = { id: 'bedroom', position: { x: 6, y: 2, z: 3.4 }, dimensions: { width: 4, depth: 5, height: 3.4 } }
const bed = { id: 'bed_01', name: 'Bed', group: 'furniture', category: 'bed', model_path: 'https://assets.example/bed.glb', dimensions: { width: 1.8, depth: 2, height: 1 } }

test('preview belongs to the selected destination and does not mutate room or catalog', () => {
  const source = JSON.stringify({ room, bed })
  const item = createAssetPlacement(bed, room, 'preview_1')
  assert.equal(item.room_id, 'bedroom')
  assert.deepEqual(item.position, { x: 8, y: 4.5, z: 3.4 })
  assert.equal(JSON.stringify({ room, bed }), source)
  assert.equal(room.furniture, undefined)
  assert.equal(createAssetPlacement({ ...bed, model_path: null }, room, 'invalid'), null)
})

test('preview rotation and movement are clamped without touching existing furniture', () => {
  const item = createAssetPlacement(bed, room, 'preview_1')
  const snapshot = JSON.stringify(item)
  const moved = adjustAssetPlacement(item, room, 100, -100, 90)
  assert.ok(moved.position.x <= 10 - 1 - 0.14)
  assert.ok(moved.position.y >= 2 + 0.9 + 0.14)
  assert.equal(moved.rotation, 90)
  assert.equal(JSON.stringify(item), snapshot)
})

test('destination camera is within room walls and on the destination storey', () => {
  const view = placementCameraView(room)
  assert.ok(view.position[0] > 6 && view.position[0] < 10)
  assert.ok(-view.position[2] > 2 && -view.position[2] < 7)
  assert.equal(view.position[1], 5.05)
  assert.deepEqual(view.target, [8, 4.55, -4.5])
})

test('room camera chooses a clear interior quadrant away from furniture and openings', () => {
  const occupied = { ...room,
    furniture: [{ position: { x: 6.7, y: 3.4 }, dimensions: { width: 1.4, depth: 1.4 } }],
    openings: [{ position: { x: 9.3, y: 3.4 } }],
  }
  const view = placementCameraView(occupied)
  assert.ok(-view.position[2] > 5)
  assert.ok(Math.hypot(view.position[0] - 6.7, -view.position[2] - 3.4) > 2)
  assert.ok(Math.hypot(view.position[0] - 9.3, -view.position[2] - 3.4) > 2)
  assert.deepEqual(view.target, [8, 4.55, -4.5])
})

test('real floor slab height is shared by preview and camera; ceiling assets stay overhead', () => {
  const normalized = placementRoom(room, [{ roomId: 'bedroom', center: { y: 3.5 }, size: { y: 0.2 } }])
  assert.equal(normalized.position.z, 3.6)
  const item = createAssetPlacement({ ...bed, group: 'ceiling_asset' }, normalized, 'fan_preview')
  assert.ok(Math.abs(item.position.z - 5.74) < 0.0001)
  assert.equal(item.ceiling_mounted, true)
  assert.equal(createAssetPlacement(bed, normalized, 'bed_preview').position.z, 3.6)
  assert.equal(placementCameraView(normalized).position[1], 5.25)
})
