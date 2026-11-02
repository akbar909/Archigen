import test from 'node:test'
import assert from 'node:assert/strict'
import * as THREE from 'three'
import { mountWallFixture } from './fixtureMounting.js'
import { replacementPlacement } from './replacementPlacement.js'
import { createAssetPlacement } from './assetPlacement.js'

const room={id:'bathroom',position:{x:0,y:0,z:0},dimensions:{width:3,depth:3,height:3}}
const shower={id:'shower_set_02',category:'shower',mounting:{surface:'wall',default_height:.95,orientation_version:1},dimensions:{width:.527,depth:.827,height:1.35}}
test('legacy floor shower becomes a wall fixture with a sensible height and preserves saved height nudges',()=>{
  const item={id:'shower',asset_id:shower.id,category:'shower',anchor_wall:'north',position:{x:1.5,y:2.5,z:0},dimensions:{width:1,depth:1,height:2.1}}
  const mounted=mountWallFixture(item,room,shower)
  assert.equal(mounted.wall_mounted,true)
  assert.equal(mounted.wall_side,'front')
  assert.equal(mounted.mount_height,.95)
  assert.equal(mounted.dimensions.height,1.35)
  assert.equal(item.wall_mounted,undefined)
  assert.equal(mountWallFixture({...mounted,mount_height:1.05},room,shower).mount_height,1.05)
  assert.equal(mountWallFixture({...mounted,mount_height:9},room,shower).mount_height,1.5499999999999998)
})
test('catalog replacement preserves the compact bed dimensions and fits its saved bedroom',()=>{
  const bedroom={id:'bedroom',position:{x:0,y:0,z:0},dimensions:{width:3,depth:3,height:3}}
  const original=new THREE.Group()
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(1.2,.7,1.8))
  mesh.position.set(.2,.35,0);original.add(mesh);original.position.set(2.1,0,-1.5);original.updateMatrixWorld(true)
  const item={id:'bed',category:'bed',dimensions:{width:1.2,depth:1.8,height:.7},position:{x:2.1,y:1.5,z:0}}
  const replacement=replacementPlacement(item,{dimensions:{width:2.4,depth:2.5,height:1.4}},original,bedroom)
  assert.deepEqual(replacement.dimensions,item.dimensions)
  assert.ok(replacement.position.x+replacement.dimensions.width/2<3)
  assert.ok(replacement.position.x>=2.1)
})

test('explicit shower wall overrides the center-nearest wall and discards the previous wall anchor',()=>{
  const item=createAssetPlacement({...shower,group:'furniture',model_path:'shower.glb'},room,'new_shower',{wallSide:'right'})
  assert.equal(item.wall_side,'right')
  assert.equal(item.anchor_wall,'east')
  assert.equal(item.wall_normal.x,-1)
  assert.ok(item.position.x>2.4)
  const changed=mountWallFixture({...item,wall_anchor:{x:3,y:1.5},wall_id:'east_wall'},room,shower,{wallSide:'left'})
  assert.equal(changed.wall_side,'left')
  assert.equal(changed.wall_anchor,null)
  assert.equal(changed.wall_id,null)
  assert.ok(changed.position.x<.6)
  assert.equal(changed.mount_height,item.mount_height)
})
