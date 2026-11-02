import assert from 'node:assert/strict'
import test from 'node:test'
import { createNavigationModel, moveWithElevation, nearestWalkablePosition, walkableSurface } from './navigation.js'
import { roomPlacement } from '../components/viewer3d/viewerUtils.js'

function fixture(type = 'u_shaped', across = false) {
  const dimensions = type === 'straight' ? { width: 1.1, depth: 5.5, height: 3 }
    : type === 'l_shaped' ? { width: 3.25, depth: 3.25, height: 3 }
      : across ? { width: 3.25, depth: 2.2, height: 3 } : { width: 2.2, depth: 3.25, height: 3 }
  const stair = { id: 'stairs', type, run_axis: across ? 'x' : 'y', position: { x: 1, y: 1, z: 0 }, dimensions,
    clear_width: 1, landing_depth: 1, steps: 18, floor_level: 0 }
  const rooms = [0, 1].map(level => ({ id: `lobby${level}`, x: 4, z: -4, y: level * 3, w: 8, l: 8, level }))
  const model = createNavigationModel({ rooms, stairs: [stair] })
  const world = (u, v) => ({ x: across ? 1 + dimensions.width - v : 1 + u, z: -(across ? 1 + u : 1 + v) })
  let path
  if (type === 'straight') path = [[.55, -.5], [.55, 4.5], [.55, 6]]
  else if (type === 'l_shaped') path = [[.5, -.5], [.5, 2.75], [3.75, 2.75]]
  else path = [[.51, -.5], [.51, 2.75], [1.69, 2.75], [1.69, -.5]]
  return { model, stair, path: path.map(([u, v]) => world(u, v)), world }
}

for (const [type, across] of [['u_shaped', false], ['u_shaped', true], ['straight', false], ['l_shaped', false]]) {
  test(`${type} ${across ? 'across plot' : ''}: walk both flights and landing up and down without teleporting`, () => {
    const { model, path } = fixture(type, across)
    let position = { ...path[0], y: 0, level: 0 }
    for (const destination of path.slice(1)) {
      position = moveWithElevation(model, position, destination.x - position.x, destination.z - position.z)
      assert.ok(Math.hypot(position.x - destination.x, position.z - destination.z) < .001, JSON.stringify(position))
    }
    assert.equal(position.level, 1)
    assert.ok(Math.abs(position.y - 3) < .001)
    for (const destination of path.slice(0, -1).reverse()) {
      position = moveWithElevation(model, position, destination.x - position.x, destination.z - position.z)
      assert.ok(Math.hypot(position.x - destination.x, position.z - destination.z) < .001, JSON.stringify(position))
    }
    assert.equal(position.level, 0)
    assert.ok(Math.abs(position.y) < .001)
  })
}

test('U stair blocks crossing the centre gap, climbing from the side and walking into an upper void', () => {
  const { model, world } = fixture()
  const left = world(.51, 1)
  const position = moveWithElevation(model, { ...left, y: 1 / 2.25 * 1.5, level: 0 }, 1.18, 0)
  assert.ok(position.x < 1.8)
  assert.equal(walkableSurface(model, ...Object.values(world(1.1, 1)), 1, 3), null)
  const side = world(-.3, 1)
  assert.ok(moveWithElevation(model, { ...side, y: 0, level: 0 }, 1, 0).x < 1.1)
  const entry = world(.51, -.5)
  const aboveLowerFlight = moveWithElevation(model, { ...entry, y: 3, level: 1 }, 0, -2)
  assert.ok(aboveLowerFlight.z > -1.01)
})

test('stair-room selection finds a real floor landing, not the void or a distant room', () => {
  const { model } = fixture('u_shaped', true)
  const safe = nearestWalkablePosition(model, 2, -2, 1, 3)
  assert.equal(safe.y, 3)
  assert.equal(safe.level, 1)
  assert.ok(!safe.stairId)
  assert.ok(walkableSurface(model, safe.x, safe.z, 1, 3))
})

test('a slab piece around the stair hole does not shrink or move the navigation room', () => {
  const room = { id: 'lobby', floor_level: 1, position: { x: 1, y: 2, z: 3 }, dimensions: { width: 4.6, depth: 2.6 } }
  const detected = [{ roomId: 'lobby', level: 1, center: { x: 5, y: 3, z: -3.3 }, size: { x: 1.2, y: .1, z: 2.6 } }]
  const result = roomPlacement(room, detected, 3, -1)
  assert.equal(result.w, 4.6)
  assert.equal(result.x, 3.3)
  assert.equal(result.y, 3.05)
})
