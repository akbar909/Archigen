import assert from 'node:assert/strict'
import test from 'node:test'
import { isAssetRecommendedForRoom } from './roomAssetLibrary.js'

for (const [room, category, unrelated] of [
  ['master_bedroom', 'nightstand', 'toilet'],
  ['kitchen', 'kitchen_cabinet', 'bed'],
  ['bathroom', 'bathroom_sink', 'sofa'],
  ['dining_room', 'dining_chair', 'bathtub'],
  ['living_room', 'coffee_table', 'refrigerator'],
  ['study', 'office_chair', 'shower'],
  ['garage', 'vehicle', 'bed'],
]) {
  test(`${room} recommends its uploaded categories without unrelated models`, () => {
    assert.equal(isAssetRecommendedForRoom({ category }, { type: room }), true)
    assert.equal(isAssetRecommendedForRoom({ category: unrelated }, { type: room }), false)
    assert.equal(isAssetRecommendedForRoom({ group: 'ceiling_asset' }, { type: room }), true)
  })
}

test('room names work without type metadata and unknown room types keep assets accessible', () => {
  assert.equal(isAssetRecommendedForRoom({ category: 'toilet' }, { name: 'Guest Bathroom' }), true)
  assert.equal(isAssetRecommendedForRoom({ category: 'bed' }, { name: 'Guest Bathroom' }), false)
  assert.equal(isAssetRecommendedForRoom({ category: 'custom_asset' }, { type: 'custom_room' }), true)
})
