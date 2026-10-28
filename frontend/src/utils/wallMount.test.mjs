import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import * as THREE from 'three'
import { assetYawOffset, snapToWallPlane, wallMountNormal, wallMountRotation } from './wallMount.js'
import { alignWallFurniture } from './designEditing.js'

const metadata = new URL('../../../blender/metadata/', import.meta.url)
const axes = { '+x': [1, 0, 0], '-x': [-1, 0, 0], '+z': [0, 0, 1], '-z': [0, 0, -1] }
for (const filename of fs.readdirSync(metadata).filter((name) => name.endsWith('.json'))) {
  const record = JSON.parse(fs.readFileSync(new URL(filename, metadata)))
  if (record.mounting?.surface !== 'wall') continue
  test(`${record.id}: decorated front faces into the room on all four walls`, () => {
    for (const side of ['front', 'back', 'left', 'right']) {
      const facing = new THREE.Vector3(...axes[record.mounting.front_axis])
        .applyAxisAngle(new THREE.Vector3(0, 1, 0), assetYawOffset(record) * Math.PI / 180)
        .applyAxisAngle(new THREE.Vector3(0, 1, 0), -wallMountRotation(side) * Math.PI / 180)
      const normal = wallMountNormal(side)
      assert.ok(facing.distanceTo(new THREE.Vector3(normal.x, 0, normal.z)) < 0.00001, side)
    }
  })
}

test('surface normals support non-cardinal walls and mounting planes stay flush during movement', () => {
  const normal = { x: 0.6, y: 0, z: 0.8 }
  const rotation = wallMountRotation('right', normal)
  const facing = new THREE.Vector3(0, 0, 1).applyAxisAngle(new THREE.Vector3(0, 1, 0), -rotation * Math.PI / 180)
  assert.ok(facing.distanceTo(new THREE.Vector3(0.6, 0, 0.8)) < 0.00001)
  const item = { wall_side: 'right', wall_normal: normal, wall_anchor: { x: 4, y: 2 }, dimensions: { depth: 0.4 } }
  const snapped = snapToWallPlane({ x: 20, y: 10, z: 0 }, item)
  assert.ok(Math.abs((snapped.x - 4) * 0.6 - (snapped.y - 2) * 0.8 - 0.212) < 0.00001)
})

test('legacy wall metadata is corrected once while preserving user height and later resizing', () => {
  const room = { position: { x: 0, y: 0 }, dimensions: { width: 5, depth: 4 } }
  const old = { wall_mounted: true, wall_side: 'right', rotation: 0, dimensions: { width: 1, depth: 0.3, height: 1.2 }, position: { x: 4.7, y: 2, z: 0 } }
  const asset = { dimensions: { width: 0.4, depth: 0.6, height: 1 }, mounting: { orientation_version: 1 } }
  const corrected = alignWallFurniture(old, room, asset)
  assert.equal(corrected.rotation, 90)
  assert.equal(corrected.dimensions.height, 1.2)
  assert.equal(corrected.dimensions.width, 0.48)
  assert.equal(old.rotation, 0)
  const resized = { ...corrected, dimensions: { width: 0.2, depth: 0.3, height: 0.5 } }
  assert.deepEqual(alignWallFurniture(resized, room, asset).dimensions, resized.dimensions)
})
