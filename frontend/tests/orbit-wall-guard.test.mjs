import test from 'node:test'
import assert from 'node:assert/strict'
import * as THREE from 'three'
import { stopCameraBeforeWall } from '../src/utils/orbitWallCollision.js'

test('dollhouse zoom stops before room and boundary walls', () => {
  for (const name of ['Wall_room_1', 'Exterior_Boundary_Wall_1']) {
    const wall = new THREE.Mesh(new THREE.BoxGeometry(0.2, 2, 8), new THREE.MeshBasicMaterial())
    wall.name = name
    wall.updateMatrixWorld(true)
    const safe = stopCameraBeforeWall(new THREE.Vector3(-2, 1, 0), new THREE.Vector3(2, 1, 0), [wall])
    assert.ok(safe.x < -0.1, `${name} blocks scroll-through`)
  }
})

test('orbit movement remains unchanged when it does not cross a wall', () => {
  const wall = new THREE.Mesh(new THREE.BoxGeometry(0.2, 2, 8), new THREE.MeshBasicMaterial())
  wall.updateMatrixWorld(true)
  const desired = new THREE.Vector3(-1, 1, 1)
  assert.deepEqual(stopCameraBeforeWall(new THREE.Vector3(-2, 1, 1), desired, [wall]).toArray(), desired.toArray())
})
