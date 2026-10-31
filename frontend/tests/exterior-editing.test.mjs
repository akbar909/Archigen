import test from 'node:test'
import assert from 'node:assert/strict'
import * as THREE from 'three'
import { findEditableSurface, installSurfaceTexture } from '../src/utils/sceneEditing.js'
import { clampFurniturePosition, addFurnitureToRoom, updateFurnitureById, clampMountHeight } from '../src/utils/designEditing.js'
import { createBoundaryDecor } from '../src/utils/exteriorEditing.js'

test('legacy boundary segments and exported metadata use stable editable wall IDs', () => {
  const scene = new THREE.Group(), wall = new THREE.Group()
  wall.name = 'Exterior_Boundary_Wall_2'
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.15, 1.8, 8), new THREE.MeshStandardMaterial())
  wall.add(mesh); scene.add(wall)
  for (const metadata of [{}, { archgen_wall_id: wall.name, archgen_exterior_feature: 'boundary_wall' }]) {
    wall.userData = metadata
    const selection = findEditableSurface(mesh, scene)
    assert.equal(selection.type, 'wall')
    assert.equal(selection.exterior, true)
    assert.equal(selection.id, wall.name)
    assert.equal(selection.roomId, 'exterior_ground')
  }
  installSurfaceTexture(wall, new THREE.Texture(), 1.8, { x: 1, y: 0, z: 0 })
  assert.ok(mesh.material.some((material) => material.userData.surfaceFaceKey === 'px'))
  assert.ok(mesh.geometry.groups.some((group) => group.materialIndex === 0), 'other faces keep their finish')
})

test('outdoor movement and rotation retain positions outside plot on actual ground', () => {
  const room = { id: 'exterior_ground', position: { x: 0, y: 0, z: 0 }, dimensions: { width: 10, depth: 10, height: 3 } }
  const item = { room_id: room.id, dimensions: { width: 1, depth: 1, height: 1 }, position: { x: -8, y: -5, z: -0.22 } }
  for (const rotation of [0, 45, 90, 180]) {
    const target = { ...item.position, x: -7.9 }
    assert.deepEqual(clampFurniturePosition({ ...item, rotation }, room, target), target)
    assert.deepEqual(clampFurniturePosition({ ...item, rotation, placement_bounds: { minX: -20, maxX: 30, minY: -20, maxY: 30 } }, room, target), target)
  }
  const edge = clampFurniturePosition({ ...item, placement_bounds: { minX: -20, maxX: 30, minY: -20, maxY: 30 } }, room, { x: -50, y: -5, z: -0.22 })
  assert.equal(edge.x, -19.5)
  assert.equal(edge.z, -0.22)
})

test('boundary decor stays on either selected face and persists as an exterior asset', () => {
  const asset = { id: 'panel', name: 'Panel', category: 'wall_panel', group: 'wall_panel', model_path: '/panel.glb', dimensions: { width: 0.8, height: 1, depth: 0.1 } }
  for (const sign of [-1, 1]) {
    const selection = { wallId: 'Exterior_Boundary_Wall_1', surfaceNormal: { x: sign, y: 0, z: 0 },
      hitPoint: { x: sign * 0.075, y: 1.4, z: -3 }, boundaryBounds: { minX: -0.075, maxX: 0.075, minY: 0, maxY: 8, base: 0, height: 1.8 } }
    const item = createBoundaryDecor(asset, selection, 'panel')
    assert.ok(item.position.x * sign > 0.075)
    assert.ok(item.mount_height + item.dimensions.height <= 1.8)
    const moved = clampFurniturePosition(item, { id: 'exterior_ground' }, { x: 4, y: 6, z: 0 })
    assert.equal(moved.y, 6)
    assert.ok(Math.abs(moved.x - item.position.x) < 1e-8)
    assert.ok(clampMountHeight(item, null, 50) <= 0.8)
    const design = {}
    addFurnitureToRoom(design, 'exterior_ground', item)
    updateFurnitureById(design, 'panel', { position: moved })
    assert.equal(JSON.parse(JSON.stringify(design)).exterior.assets[0].wall_id, selection.wallId)
    assert.equal(design.furniture, undefined)
  }
})
