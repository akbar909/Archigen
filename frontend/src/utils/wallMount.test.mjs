import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import * as THREE from 'three'
import { assetYawOffset, snapToWallPlane, wallMountNormal, wallMountRotation, interiorWallMountNormal } from './wallMount.js'
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
        .applyAxisAngle(new THREE.Vector3(0, 1, 0), wallMountRotation(side) * Math.PI / 180)
      const normal = wallMountNormal(side)
      assert.ok(facing.distanceTo(new THREE.Vector3(normal.x, 0, normal.z)) < 0.00001, side)
    }
  })
}

test('surface normals support non-cardinal walls and mounting planes stay flush during movement', () => {
  const normal = { x: 0.6, y: 0, z: 0.8 }
  const rotation = wallMountRotation('right', normal)
  const facing = new THREE.Vector3(0, 0, 1).applyAxisAngle(new THREE.Vector3(0, 1, 0), rotation * Math.PI / 180)
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
  assert.equal(corrected.rotation, 270)
  assert.equal(corrected.dimensions.height, 1.2)
  assert.equal(corrected.dimensions.width, 0.48)
  assert.equal(old.rotation, 0)
  const resized = { ...corrected, dimensions: { width: 0.2, depth: 0.3, height: 0.5 } }
  assert.deepEqual(alignWallFurniture(resized, room, asset).dimensions, resized.dimensions)
})

test('Curtains 04 stays inside even when the imported window has a reversed face normal',()=>{
  const room={id:'living',position:{x:0,y:0},dimensions:{width:4,depth:4,height:3}}
  for(const side of ['front','back','left','right']) {
    const inward=wallMountNormal(side)
    const reversed={x:-inward.x,y:0,z:-inward.z}
    assert.deepEqual(interiorWallMountNormal(side,reversed),inward)
    const item={asset_id:'curtains_04',wall_mounted:true,wall_side:side,wall_normal:reversed,
      wall_anchor:{x:side==='right'?4:side==='left'?0:2,y:side==='front'?4:side==='back'?0:2},
      position:{x:2,y:2,z:0},dimensions:{width:1.8,height:1.33,depth:.071},asset_group:'curtain'}
    const aligned=alignWallFurniture(item,room)
    const distance=(aligned.position.x-item.wall_anchor.x)*inward.x-(aligned.position.y-item.wall_anchor.y)*inward.z
    assert.ok(distance > item.dimensions.depth/2,`${side}: ${distance}`)
  }
})

test('facade panels stay outside all four walls after moving, aligning and reloading', () => {
  const room = { id: 'upper', position: { x: 2, y: 3, z: 3 }, dimensions: { width: 5, depth: 4, height: 3 } }
  for (const side of ['front', 'back', 'left', 'right']) {
    const inward = wallMountNormal(side), outward = { x: -inward.x, y: 0, z: -inward.z }
    const anchor = { x: side === 'left' ? 1.9 : side === 'right' ? 7.1 : 4,
      y: side === 'back' ? 2.9 : side === 'front' ? 7.1 : 5 }
    const item = { wall_mounted: true, room_id: room.id, wall_side: side, wall_face: 'exterior',
      wall_normal: outward, wall_anchor: anchor, position: { x: 4, y: 5, z: 3 },
      dimensions: { width: 1, depth: .1, height: 1 }, mount_height: 1 }
    const aligned = alignWallFurniture(item, room)
    assert.deepEqual(aligned.wall_normal, outward)
    const distance = (aligned.position.x - anchor.x) * outward.x - (aligned.position.y - anchor.y) * outward.z
    assert.ok(distance > .05, `${side}: panel must clear the outside face`)
    assert.equal(JSON.stringify(alignWallFurniture(JSON.parse(JSON.stringify(aligned)), room)), JSON.stringify(aligned))
    // Older saves kept the outside hit anchor but mistakenly pointed inward.
    const legacy = { ...item, wall_face: undefined, wall_normal: inward }
    assert.equal(alignWallFurniture(legacy, room).wall_face, 'exterior')
    assert.deepEqual(alignWallFurniture(legacy, room).wall_normal, outward)
  }
})
