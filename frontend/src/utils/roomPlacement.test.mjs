import assert from 'node:assert/strict'
import test from 'node:test'
import { roomPlacement } from '../components/viewer3d/viewerUtils.js'

const lobby = { id: 'stair_lobby_l0', name: 'Stair Lobby', type: 'stair_lobby', floor_level: 0,
  position: { x: .76, y: 2.19, z: 0 }, dimensions: { width: 4.6, depth: 2.6, height: 3 } }
const slab = (roomId, x, z, width, depth, level = 0) => ({ roomId, meshId: roomId, name: `Floor_L${level}_${roomId}`,
  level, center: { x, y: level * 3 - .05, z }, size: { x: width, y: .1, z: depth } })

test('a missing stair lobby slab uses its saved footprint instead of the closest detected bedroom', () => {
  const detected = [slab('requested_bedroom_01', 2.285, -6.21, 3.05, 2.84),
    slab('requested_bathroom_01', 6.11, -3.49, 1.5, 2.6)]
  const actual = roomPlacement(lobby, detected, 3, -1)
  assert.equal(actual.x, lobby.position.x + lobby.dimensions.width / 2)
  assert.equal(actual.z, -(lobby.position.y + lobby.dimensions.depth / 2))
  assert.equal(actual.w, 4.6)
  assert.equal(actual.l, 2.6)
  assert.equal(actual.y, 0)
})

test('explicit metadata for another room wins over a misleading name and identical dimensions', () => {
  const detected = [slab('bathroom', 6.1, -3.49, 4.6, 2.6)]
  detected[0].meshId = lobby.id
  detected[0].name = 'Floor_Stair_Lobby'
  const actual = roomPlacement(lobby, detected, 3, -1)
  assert.equal(actual.x, lobby.position.x + lobby.dimensions.width / 2)
  assert.equal(actual.z, -(lobby.position.y + lobby.dimensions.depth / 2))
})

test('an absent upper-floor slab never matches a ground-floor slab with the same room ID', () => {
  const upper = { ...lobby, floor_level: 1, position: { x: 10, y: 8, z: 3.4 } }
  const actual = roomPlacement(upper, [slab(lobby.id, 3.06, -3.49, 4.6, 2.6)], 3.4, -1)
  assert.equal(actual.level, 1)
  assert.equal(actual.y, 3.4)
  assert.equal(actual.x, 12.3)
  assert.equal(actual.z, -9.3)
})

test('an exact room slab supplies finished floor height while retaining the complete stair-lobby footprint', () => {
  const actual = roomPlacement(lobby, [slab(lobby.id, 4.9, -3.49, 1.1, 2.6)], 3, -1)
  assert.equal(actual.x, lobby.position.x + lobby.dimensions.width / 2)
  assert.equal(actual.w, 4.6)
  assert.equal(actual.l, 2.6)
  assert.equal(actual.y, 0)
})

test('unlabelled legacy floors can still match by reliable size and position evidence', () => {
  const room = { id: 'ensuite', position: { x: 8, y: 0, z: 0 }, dimensions: { width: 4, depth: 4 } }
  const detected = [slab('', 2, -2, 4, 4), slab('', 10, -2, 4, 4)]
  detected[0].name = 'Floor_A'; detected[1].name = 'Floor_B'
  const actual = roomPlacement(room, detected, 3, -1)
  assert.equal(actual.x, 10)
  assert.equal(actual.z, -2)
})

test('a distant unlabelled slab is not accepted merely because it is the closest available size', () => {
  const detected = [slab('', 20, -20, 4.6, 2.6)]
  detected[0].name = 'Floor_A'
  const actual = roomPlacement(lobby, detected, 3, -1)
  assert.equal(actual.x, lobby.position.x + lobby.dimensions.width / 2)
  assert.equal(actual.z, -(lobby.position.y + lobby.dimensions.depth / 2))
})

test('a differently numbered legacy bedroom cannot replace a missing requested bedroom', () => {
  const room = { id: 'bedroom_1', name: 'Bedroom 1', type: 'bedroom', position: { x: 0, y: 0, z: 0 }, dimensions: { width: 3, depth: 3 } }
  const detected = [slab('', 10, -10, 3, 3)]
  detected[0].meshId = 'Bedroom_2'; detected[0].name = 'Floor_Bedroom_2'
  const actual = roomPlacement(room, detected, 3, -1)
  assert.equal(actual.x, 1.5)
  assert.equal(actual.z, -1.5)
})
