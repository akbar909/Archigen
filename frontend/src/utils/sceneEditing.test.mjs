import assert from 'node:assert/strict'
import test from 'node:test'
import * as THREE from 'three'
import { editorViewportOffset, findEditableSurface, installSurfaceTexture, isVisibleInHierarchy, setSubtreePickable } from './sceneEditing.js'
import { canApplyAccentColor, prepareAssetModel } from './assetModel.js'

test('wall faces keep separate finishes, including after another edit and rotation', () => {
  const wall = new THREE.Group()
  wall.rotation.y = Math.PI / 2
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(3, 3, 0.2), new THREE.MeshStandardMaterial())
  wall.add(mesh)
  const bedroom = new THREE.Texture(), bathroom = new THREE.Texture(), revised = new THREE.Texture()
  installSurfaceTexture(wall, bedroom, 1.8, { x: 1, y: 0, z: 0 })
  installSurfaceTexture(wall, bathroom, 1.8, { x: -1, y: 0, z: 0 })
  installSurfaceTexture(wall, revised, 1.8, { x: 1, y: 0, z: 0 })
  const matrix = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld)
  for (const group of mesh.geometry.groups) {
    const normal = new THREE.Vector3().fromBufferAttribute(mesh.geometry.attributes.normal, group.start).applyNormalMatrix(matrix)
    const map = mesh.material[group.materialIndex].map
    assert.equal(map, normal.x > 0.75 ? revised : normal.x < -0.75 ? bathroom : null)
  }
  assert.equal(mesh.material.length, 3, 'repeated finishes reuse the face material slot')
})

test('accent color is available only for models whose visible materials support recoloring', () => {
  const model = new THREE.Group()
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial())
  model.add(mesh)
  assert.equal(canApplyAccentColor(model), true)
  const item = { dimensions: { width: 1, height: 1, depth: 1 }, color: '#4a6fa5' }
  const prepared = prepareAssetModel(model, item)
  assert.equal(prepared.object.children[0].children[0].material.color.getHexString(), '4a6fa5')
  mesh.material.map = new THREE.Texture()
  assert.equal(canApplyAccentColor(model), false)
  const textured = prepareAssetModel(model, item)
  assert.equal(textured.object.children[0].children[0].material.color.getHexString(), 'ffffff')
  assert.equal(canApplyAccentColor(null), false)
  mesh.material.map = null
  mesh.material.vertexColors = true
  assert.equal(canApplyAccentColor(model), false)
})

test('hidden original cannot be selected at its previous position after replacement moves', () => {
  const scene = new THREE.Scene()
  const original = new THREE.Group()
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial())
  original.add(mesh)
  scene.add(original)
  const replacement = mesh.clone()
  replacement.position.x = 2
  scene.add(replacement)
  original.visible = false
  setSubtreePickable(original, false)
  scene.updateMatrixWorld(true)
  const ray = new THREE.Raycaster(new THREE.Vector3(0, 0, 5), new THREE.Vector3(0, 0, -1))
  assert.equal(ray.intersectObjects(scene.children, true).length, 0)
  assert.equal(isVisibleInHierarchy(mesh), false)
  ray.ray.origin.x = 2
  assert.ok(ray.intersectObjects(scene.children, true).length > 0)
  original.visible = true
  setSubtreePickable(original, true)
  ray.ray.origin.x = 0
  assert.ok(ray.intersectObjects(scene.children, true).length > 0)
})

test('selecting a wall primitive resolves the entire stable wall root', () => {
  const scene = new THREE.Scene()
  const wall = new THREE.Group()
  wall.name = 'Wall_L0_dining_north'
  wall.userData.archgen_wall_id = 'dining:north'
  const face = new THREE.Mesh(new THREE.BoxGeometry(3, 3, 0.2), new THREE.MeshStandardMaterial())
  face.name = 'Wall_L0_dining_north_1'
  wall.add(face)
  scene.add(wall)
  assert.equal(findEditableSurface(face, scene).object, wall)
  assert.equal(findEditableSurface(face, scene).id, 'dining:north')
})

for (const kind of ['wall', 'floor', 'ground']) {
  test(`${kind} texture replaces every split material and generates usable UVs`, () => {
    const root = new THREE.Group()
    const source = new THREE.MeshStandardMaterial({ color: '#222222', vertexColors: true })
    source.normalMap = new THREE.Texture()
    for (let i = 0; i < 2; i++) {
      const geometry = new THREE.BoxGeometry(3, 2, 0.1)
      geometry.deleteAttribute('uv')
      const mesh = new THREE.Mesh(geometry, i ? [source, source] : source)
      mesh.rotation.x = kind === 'wall' ? 0 : -Math.PI / 2
      root.add(mesh)
    }
    const texture = new THREE.Texture()
    assert.equal(installSurfaceTexture(root, texture), 2)
    root.children.forEach((mesh) => {
      assert.ok(new Set(mesh.geometry.attributes.uv.array).size > 2)
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        assert.equal(material.map, texture)
        assert.equal(material.color.getHexString(), 'ffffff')
        assert.equal(material.vertexColors, false)
        assert.equal(material.normalMap, null)
      }
    })
    assert.notEqual(source.map, texture)
  })
}

test('editor projection puts selection in unobscured desktop and mobile viewport without moving camera', () => {
  for (const drawer of [
    { left: 650, top: 50, width: 340, height: 700 },
    { left: 0, top: 450, width: 1000, height: 350 },
  ]) {
    const rect = { left: 0, top: 0, right: 1000, bottom: 800, width: 1000, height: 800 }
    const offset = editorViewportOffset(rect, drawer)
    const camera = new THREE.PerspectiveCamera(44, 1000 / 800, 0.1, 100)
    camera.position.set(0, 0, 5)
    camera.lookAt(0, 0, 0)
    camera.updateMatrixWorld(true)
    camera.setViewOffset(1000, 800, offset.x, offset.y, 1000, 800)
    const projected = new THREE.Vector3().project(camera)
    const x = (projected.x + 1) * 500, y = (1 - projected.y) * 400
    assert.ok(x < drawer.left || y < drawer.top)
    assert.deepEqual(camera.position.toArray(), [0, 0, 5])
  }
})
