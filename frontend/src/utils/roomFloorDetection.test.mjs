import assert from 'node:assert/strict'
import test from 'node:test'
import * as THREE from 'three'
import { roomFloorMeshInfo } from './roomFloorDetection.js'

const mesh = (name, data = {}) => { const object = new THREE.Mesh(); object.name = name; object.userData = data; return object }

test('real generated stair lobby slab names remain room floors on both levels', () => {
  for (const level of [0, 1]) {
    const id = `stair_lobby_l${level}`, name = `Floor_L${level}_${id}`
    assert.deepEqual(roomFloorMeshInfo(mesh(name, { archgen_room_id: id })), { effectiveName: name, roomId: id })
    assert.ok(roomFloorMeshInfo(mesh(name)), 'legacy lobby slabs remain detectable without extras')
  }
})

test('room names containing ground or garden do not override stable room metadata', () => {
  for (const id of ['ground_floor_kitchen', 'garden_room']) assert.equal(roomFloorMeshInfo(mesh(`Floor_L0_${id}`, { archgen_room_id: id })).roomId, id)
})

test('material primitives inherit the room slab identity from their parent', () => {
  const group = new THREE.Group(); group.name = 'Floor_L1_stair_lobby_l1'; group.userData.archgen_room_id = 'stair_lobby_l1'
  const child = mesh('material_0'); group.add(child)
  assert.equal(roomFloorMeshInfo(child).roomId, 'stair_lobby_l1')
})

test('site slabs, stair treads and opening helpers cannot become rooms', () => {
  for (const name of ['Floor_Foundation', 'Floor_Podium', 'Floor_Garden_Ground', 'Floor_intermediate_slab', 'Floor_Stair_LowerTread'])
    assert.equal(roomFloorMeshInfo(mesh(name)), null, name)
  assert.equal(roomFloorMeshInfo(mesh('Floor_L1_stair_lobby_cutter', { archgen_room_id: 'stair_lobby' })), null)
  assert.equal(roomFloorMeshInfo(mesh('Floor_L1_stair_lobby', { archgen_room_id: 'stair_lobby', archgen_stair_opening: true })), null)
  assert.equal(roomFloorMeshInfo(mesh('Floor_stair', { archgen_stair_component: 'tread' })), null)
})
