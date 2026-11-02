import test from 'node:test'
import assert from 'node:assert/strict'
import { addFurnitureToRoom, addExteriorAsset, removeFurnitureById } from './designEditing.js'
import { reconcileDraftDesign } from './draftReconciliation.js'

const fixture = () => ({ glb_url:'saved.glb',rooms:[{id:'room',position:{x:0,y:0,z:0}}],
  floors:[{id:'floor',rooms:[{id:'room',position:{x:0,y:0,z:0}}]}] })
const asset = id => ({id,room_id:'room',category:'chair',position:{x:1,y:1,z:0},dimensions:{width:.5,depth:.5,height:1}})
const add = (baseline,id='new') => addFurnitureToRoom(structuredClone(baseline),'room',asset(id))

test('adding then deleting an unsaved interior asset restores the exact saved document',()=>{
  const saved=fixture(),previous=add(saved),next=removeFurnitureById(structuredClone(previous),'new')
  const source=structuredClone(next)
  const result=reconcileDraftDesign(previous,next,saved)
  assert.equal(result.isDirty,false)
  assert.deepEqual(result.design,saved)
  assert.deepEqual(next,source,'Caller-owned drafts/history must not be mutated during reconciliation')
})

test('canceling the first exterior asset also removes its lazily created empty exterior container',()=>{
  const saved=fixture(),previous=addExteriorAsset(structuredClone(saved),{...asset('urn'),room_id:'exterior_ground'})
  const result=reconcileDraftDesign(previous,removeFurnitureById(structuredClone(previous),'urn'),saved)
  assert.equal(result.isDirty,false)
  assert.deepEqual(result.design,saved)
})

test('deleting saved furniture keeps its required tombstone and remains dirty',()=>{
  const saved=add(fixture(),'persisted')
  const result=reconcileDraftDesign(saved,removeFurnitureById(structuredClone(saved),'persisted'),saved)
  assert.equal(result.isDirty,true)
  assert.deepEqual(result.design.deleted_furniture_ids,['persisted'])
})

test('canceling a newly added asset preserves another deletion and unrelated room edits',()=>{
  const saved=add(fixture(),'persisted')
  let previous=removeFurnitureById(add(saved),'persisted')
  previous.rooms[0].name='Renamed room'
  const result=reconcileDraftDesign(previous,removeFurnitureById(structuredClone(previous),'new'),saved)
  assert.equal(result.isDirty,true)
  assert.deepEqual(result.design.deleted_furniture_ids,['persisted'])
  assert.equal(result.design.rooms[0].name,'Renamed room')
})

test('previously saved and unknown embedded-model tombstones are never discarded',()=>{
  const saved={...fixture(),deleted_furniture_ids:['old_embedded']},previous=add(saved)
  const next=removeFurnitureById(structuredClone(previous),'new')
  next.deleted_furniture_ids.push('unlisted_embedded')
  const result=reconcileDraftDesign(previous,next,saved)
  assert.equal(result.isDirty,true)
  assert.deepEqual(result.design.deleted_furniture_ids,['old_embedded','unlisted_embedded'])
})

test('removing a temporary support table preserves the real change to a saved tabletop object',()=>{
  const saved=add(fixture(),'clock')
  const previous=add(saved,'temporary_table')
  previous.furniture.find(item=>item.id==='clock').support_id='temporary_table'
  previous.furniture.find(item=>item.id==='clock').position.z=.7
  const result=reconcileDraftDesign(previous,removeFurnitureById(structuredClone(previous),'temporary_table'),saved)
  assert.equal(result.isDirty,true)
  assert.equal(result.design.furniture.find(item=>item.id==='clock').support_id,undefined)
  assert.equal(result.design.furniture.find(item=>item.id==='clock').position.z,0)
  assert.equal(result.design.furniture.find(item=>item.id==='clock').client_edited_3d,true)
})

test('canceling one newly added asset retains other additions',()=>{
  const saved=fixture(),previous=add(add(saved,'one'),'two')
  const result=reconcileDraftDesign(previous,removeFurnitureById(structuredClone(previous),'one'),saved)
  assert.equal(result.isDirty,true)
  assert.deepEqual(result.design.furniture.map(item=>item.id),['two'])
  assert.equal(result.design.deleted_furniture_ids,undefined)
})
