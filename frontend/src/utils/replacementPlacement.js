import * as THREE from 'three'
import { clampFurniturePosition } from './designEditing.js'

export function replacementPlacement(item, asset, original, room) {
  const rotation = new THREE.Euler().setFromQuaternion(original.getWorldQuaternion(new THREE.Quaternion()),'YXZ')
  const box = new THREE.Box3().setFromObject(original,true)
  const center = box.getCenter(new THREE.Vector3())
  // Catalog dimensions describe an asset's default size. The saved layout size
  // governs this instance; substituting defaults can move a bed through a wall.
  const next = { ...item, dimensions:item.dimensions || asset.dimensions,
    rotation:Number.isFinite(Number(item.rotation ?? item.rotation_y)) ? Number(item.rotation ?? item.rotation_y) : THREE.MathUtils.radToDeg(rotation.y),
    position:item.client_edited_3d || item.wall_mounted ? item.position : {
      x:center.x,y:-center.z,z:box.min.y,
    } }
  next.position=clampFurniturePosition(next,room,next.position)
  return next
}
