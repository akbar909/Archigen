import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { findEditableSurface } from '../src/utils/sceneEditing'
export default function PlacementProbe({ onSelect, onModeChange }) {
  const { camera, scene } = useThree()
  useEffect(() => {
    window.placementCamera = () => camera.position.toArray()
    window.setPlacementCamera = (position) => camera.position.fromArray(position)
    window.setTestViewMode = onModeChange
  }, [camera, onModeChange])
  useEffect(() => {
    window.selectExteriorTestSurface = (name) => {
      const object = scene.getObjectByName(name)
      if (!object || !onSelect) return false
      const surface = findEditableSurface(object, scene)
      if (!surface) return false
      const box = new THREE.Box3().setFromObject(object)
      onSelect({ ...surface, source: 'blender', roomId: 'exterior_ground', wallId: surface.type === 'wall' ? surface.id : null,
        hitPoint: surface.type === 'wall' ? { x: -0.075, y: 1, z: -3 } : { x: -5, y: -0.22, z: 4 },
        surfaceNormal: surface.type === 'wall' ? { x: -1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 },
        boundaryBounds: surface.exterior ? { minX: box.min.x, maxX: box.max.x, minY: -box.max.z, maxY: -box.min.z, base: box.min.y, height: box.max.y - box.min.y } : null })
      return true
    }
  }, [scene, onSelect])
  return null
}
