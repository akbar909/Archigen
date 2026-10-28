import assert from 'node:assert/strict'
import test from 'node:test'
import * as THREE from 'three'
import { createNavigationModel, isWalkablePoint, moveWithCollisions, nearestWalkablePoint, normalizeNavigationDoors, WALK_SPEED } from './navigation.js'
import { roomPlacement } from '../components/viewer3d/viewerUtils.js'
import { turnCameraInPlace } from './cameraLook.js'

const rooms = [{ id: 'a', x: 2, z: -2, w: 4, l: 4, level: 0 }, { id: 'b', x: 6, z: -2, w: 4, l: 4, level: 0 }]
const door = { id: 'shared', worldX: 4, worldZ: -2, axis: 'z', width: 1, floorLevel: 0 }

test('body clearance stops at a solid wall, including high-delta movement', () => {
  const model = createNavigationModel({ rooms })
  const point = moveWithCollisions(model, 2, -2, 10, 0, 0)
  assert.ok(point.x <= 3.661 && point.x > 3.55)
  assert.ok(isWalkablePoint(model, point.x, point.z, 0))
  assert.ok(WALK_SPEED < 4.2 && WALK_SPEED > 2)
})

test('camera cannot get close enough to reveal the inside of a wall', () => {
  const model = createNavigationModel({ rooms })
  const point = moveWithCollisions(model, 2, -2, 0, 4, 0)
  assert.ok(point.z <= -0.339 && point.z > -0.41)
  const recovered = nearestWalkablePoint(model, 2, -0.02, 0)
  assert.ok(recovered.z < -0.34)
})

test('a real doorway connects rooms but the jamb and nearby wall remain solid', () => {
  const model = createNavigationModel({ rooms, doors: [door] })
  assert.ok(Math.abs(moveWithCollisions(model, 2, -2, 4, 0, 0).x - 6) < 0.001)
  assert.ok(moveWithCollisions(model, 2, -1.4, 4, 0, 0).x < 3.67)
  assert.ok(moveWithCollisions(model, 2, -2, 10, 0, 0).x < 7.67)
})

test('diagonal movement slides along walls without cutting the corner', () => {
  const model = createNavigationModel({ rooms })
  const point = moveWithCollisions(model, 3.5, -0.5, 1, 1, 0)
  assert.ok(point.x <= 3.661 && point.z <= -0.339)
  assert.ok(isWalkablePoint(model, point.x, point.z, 0))
})

test('door on another storey does not make a hole in a ground-floor wall', () => {
  const model = createNavigationModel({ rooms: [...rooms, ...rooms.map((room) => ({ ...room, level: 1 }))],
    doors: [{ ...door, floorLevel: 1 }] })
  assert.ok(moveWithCollisions(model, 2, -2, 4, 0, 0).x < 3.67)
  assert.ok(moveWithCollisions(model, 2, -2, 4, 0, 1).x > 5.99)
})

test('main doorway opens to the entrance path without opening the rest of the wall', () => {
  const model = createNavigationModel({ rooms: [rooms[0]],
    doors: [{ worldX: 2, worldZ: 0, axis: 'x', width: 1, floorLevel: 0 }],
    exteriorAccess: (x, z, pad) => Math.abs(x - 2) <= 0.6 + pad && z >= 0 && z < 3 })
  assert.ok(moveWithCollisions(model, 2, -2, 0, 3, 0).z > 0.99)
  assert.ok(moveWithCollisions(model, 1, -2, 0, 3, 0).z < -0.33)
})

test('canonical door positions match Blender world coordinates and keep the true aperture', () => {
  const result = normalizeNavigationDoors({ doors: [{ id: 'd', position: { x: 4, y: 2, z: 3.4 }, wall_side: 'east', width: 0.9 }],
    detected: [{ id: 'd', worldX: 4.6, worldZ: -2, width: 3, floorLevel: 1 }], floorHeight: 3.4 })
  assert.equal(result.length, 1)
  assert.deepEqual(result[0], { id: 'd', worldX: 4, worldZ: -2, axis: 'z', floorLevel: 1, width: 0.9 })
  const room = roomPlacement({ id: 'a', position: { x: 0, y: 0, z: 0 }, dimensions: { width: 4, depth: 4 } }, [], 3.4, -1)
  assert.equal(room.z, -2)
})

test('canonical wall thickness and door opening are respected by the collision model', () => {
  const walls = [
    { start: { x: 0, y: 0 }, end: { x: 8, y: 0 } }, { start: { x: 0, y: 4 }, end: { x: 8, y: 4 } },
    ...[0, 4, 8].map((x) => ({ start: { x, y: 0 }, end: { x, y: 4 } })),
  ].map((wall) => ({ ...wall, thickness: 0.3, floor_level: 0 }))
  const model = createNavigationModel({ rooms, doors: [door], walls })
  assert.ok(moveWithCollisions(model, 2, -2, 4, 0, 0).x > 5.99)
  assert.ok(moveWithCollisions(model, 2, -1, 4, 0, 0).x < 3.62)
})

test('editing drag turns slowly in place, clamps pitch, and never orbits outside the room', () => {
  const camera = new THREE.PerspectiveCamera()
  camera.position.set(2, 1.65, -2)
  const before = camera.position.clone()
  const controls = { target: new THREE.Vector3() }
  const target = { current: new THREE.Vector3() }, position = { current: new THREE.Vector3() }
  for (let i = 0; i < 50; i++) turnCameraInPlace(camera, 10, 0, controls, target, position)
  const angle = camera.getWorldDirection(new THREE.Vector3()).angleTo(new THREE.Vector3(0, 0, -1))
  assert.ok(camera.getWorldDirection(new THREE.Vector3()).x < 0, 'drag right pulls the panorama right rather than reversing it')
  assert.ok(angle > 0.85 && angle < 0.95)
  for (let i = 0; i < 50; i++) turnCameraInPlace(camera, 0, 120, controls, target, position)
  assert.ok(Math.abs(new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ').x) <= 1.35001)
  assert.deepEqual(camera.position.toArray(), before.toArray())
})
