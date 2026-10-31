import assert from 'node:assert/strict'
import test from 'node:test'
import * as THREE from 'three'
import { roofEditingView } from '../src/utils/cameraLook.js'

function roofSelection({ width = 12, depth = 8, position = [15, 6, -23], rotation = [0, 0, 0], scale = [1, 1, 1], ceiling = false } = {}) {
  const parent = new THREE.Group()
  parent.position.fromArray(position)
  parent.rotation.set(...rotation)
  parent.scale.fromArray(scale)
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, 0.3, depth), new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }))
  parent.add(mesh)
  parent.updateWorldMatrix(true, true)
  const normal = new THREE.Vector3(0, ceiling ? -1 : 1, 0)
    .applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld))
  const hitPoint = mesh.localToWorld(new THREE.Vector3(width * 0.4, ceiling ? -0.15 : 0.15, -depth * 0.4))
  return { type: ceiling ? 'ceiling' : 'roof', id: 'roof', object: parent, surfaceObject: mesh, surfaceNormal: normal, hitPoint }
}

for (const [name, shape] of [
  ['flat roof away from origin', {}],
  ['large roof on an upper floor', { width: 80, depth: 45, position: [-100, 27, 35] }],
  ['sloped roof under a rotated, non-uniformly scaled parent', { rotation: [0.4, 1.1, -0.15], scale: [2.2, 0.7, 1.4] }],
  ['narrow rotated roof', { width: 3, depth: 22, rotation: [-0.35, -0.8, 0] }],
  ['steeply pitched roof', { rotation: [1.15, -0.4, 0], position: [-4, 10, 6] }],
]) {
  for (const [width, height, offset] of [[1200, 800, { x: 184, y: 0 }], [390, 844, { x: 0, y: 190 }]]) {
    test(`${name} is centered and visible with a ${width}×${height} editor`, () => {
      const selection = roofSelection(shape)
      const camera = new THREE.PerspectiveCamera(44, width / height, 0.05, 2000)
      camera.position.copy(selection.hitPoint).add(new THREE.Vector3(-20, 10, 14))
      const before = camera.position.clone(), matrix = selection.object.matrixWorld.clone()
      const view = roofEditingView(selection, camera, { width, height }, offset)
      assert.ok(view)
      assert.ok(view.position.clone().sub(view.target).dot(view.normal) > 0, 'camera stays on the selected exterior face')
      assert.ok(view.position.y > view.bounds.max.y, 'camera is above the roof, outside the house')
      assert.ok(Math.abs(view.target.clone().sub(selection.hitPoint).dot(view.normal)) < 1e-5, 'target is on the clicked face')
      assert.ok(view.target.distanceTo(selection.hitPoint) > 0.5, 'edge clicks focus the face, not the edge')
      assert.ok(camera.position.equals(before), 'planning a view does not mutate the camera')
      assert.ok(selection.object.matrixWorld.equals(matrix), 'planning a view does not alter the model')
      camera.position.copy(view.position)
      camera.lookAt(view.target)
      camera.setViewOffset(width, height, offset.x, offset.y, width, height)
      camera.updateMatrixWorld(true)
      for (const x of [view.bounds.min.x, view.bounds.max.x]) for (const y of [view.bounds.min.y, view.bounds.max.y]) {
        for (const z of [view.bounds.min.z, view.bounds.max.z]) {
          const projected = new THREE.Vector3(x, y, z).project(camera)
          const px = (projected.x + 1) * width / 2, py = (1 - projected.y) * height / 2
          assert.ok(px > 0 && px < width - offset.x * 2, `roof corner remains outside sidebar: ${px}`)
          assert.ok(py > 0 && py < height - offset.y * 2, `roof corner remains above bottom sheet: ${py}`)
          assert.ok(projected.z > -1 && projected.z < 1)
        }
      }
    })
  }
}

test('interior ceiling focus stays on its underside without lowering the viewer through the floor', () => {
  const selection = roofSelection({ width: 5, depth: 4, position: [8, 3, -5], ceiling: true })
  const camera = new THREE.PerspectiveCamera(60, 1.5, 0.05, 350)
  camera.position.set(9, 1.65, -4)
  const view = roofEditingView(selection, camera, { width: 1200, height: 800 })
  assert.ok(view.position.y >= camera.position.y - 1e-6)
  assert.ok(view.position.y < view.target.y)
  assert.ok(view.position.clone().sub(view.target).dot(view.normal) > 0)
  assert.ok(view.fov >= camera.fov && view.fov <= 100)
})

test('legacy roof selections infer the face normal from transformed geometry', () => {
  const selection = roofSelection({ rotation: [0.3, 0.9, -0.1], scale: [1.4, 2, 0.7] })
  delete selection.surfaceNormal
  delete selection.hitPoint
  const camera = new THREE.PerspectiveCamera(44, 1.5, 0.05, 350)
  camera.position.set(30, 20, 20)
  const view = roofEditingView(selection, camera, { width: 1200, height: 800 })
  assert.ok(view.normal.y > 0)
  assert.ok(view.position.y > view.bounds.max.y)
})

test('a pitched ceiling never lowers the camera to frame a lower part of the surface', () => {
  const selection = roofSelection({ rotation: [1.1, 0.4, 0], position: [8, 6, -5], ceiling: true })
  const camera = new THREE.PerspectiveCamera(60, 1.5, 0.05, 350)
  camera.position.copy(selection.hitPoint).addScaledVector(selection.surfaceNormal, 1.3)
  const view = roofEditingView(selection, camera, { width: 1200, height: 800 })
  assert.ok(view.position.y >= camera.position.y - 1e-6)
  assert.ok(view.position.clone().sub(view.target).dot(view.normal) > 0)
})

test('roof focus leaves walls, floors, and furniture on their existing camera path', () => {
  const camera = new THREE.PerspectiveCamera()
  for (const type of ['wall', 'floor', 'ground', 'furniture', 'window', 'door']) {
    assert.equal(roofEditingView({ type, object: new THREE.Object3D() }, camera, { width: 1200, height: 800 }), null)
  }
})

test('a shared ceiling frames the living room rather than the bedroom at the slab center', () => {
  const selection = roofSelection({ width: 20, depth: 8, position: [10, 3, -4], ceiling: true })
  selection.hitPoint.set(3, 2.85, -4)
  const camera = new THREE.PerspectiveCamera(60, 1.5, 0.05, 350)
  camera.position.set(2.5, 1.65, -3.5)
  const living = { x: 3, z: -4, w: 6, l: 8 }
  const view = roofEditingView(selection, camera, { width: 1200, height: 800 }, { x: 184, y: 0 }, camera.fov, living)
  assert.deepEqual(view.position.toArray(), camera.position.toArray(), 'ceiling focus cannot cross a room wall')
  assert.ok(Math.abs(view.target.x - living.x) < 1e-6)
  assert.ok(Math.abs(view.target.z - living.z) < 1e-6)
  assert.ok(Math.abs(view.target.y - 2.85) < 1e-6)
  assert.ok(view.target.x < 6, 'target stays outside the bedroom at the shared slab center')
})

test('a ceiling without room metadata keeps the clicked location and the camera position', () => {
  const selection = roofSelection({ width: 25, depth: 16, ceiling: true })
  const camera = new THREE.PerspectiveCamera(60, 1.5, 0.05, 350)
  camera.position.copy(selection.hitPoint).add(new THREE.Vector3(0.2, -1.4, 0.3))
  const view = roofEditingView(selection, camera, { width: 1200, height: 800 })
  assert.deepEqual(view.position.toArray(), camera.position.toArray())
  assert.ok(view.target.distanceTo(selection.hitPoint) < 1e-6)
})
