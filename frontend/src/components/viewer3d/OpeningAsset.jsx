/* eslint-disable react/prop-types, react/no-unknown-property */
import { Component, Suspense, useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useGLTF } from '@react-three/drei'
import { toast } from 'react-hot-toast'
import { prepareOpeningModel } from '../../utils/openingEditing'
import { isSelectionClick } from '../../utils/selectionGesture'
import { setSubtreePickable } from '../../utils/sceneEditing'

class OpeningBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { toast.error('This model could not be loaded. The original opening is still shown.') }
  render() { return this.state.failed ? null : this.props.children }
}

function LoadedOpening({ asset, opening, originals = [], visible = true, onSelect, selection, onObjectReady, selected }) {
  const { scene } = useGLTF(asset.model_path, '/draco/gltf/')
  const yaw = asset.canonical_yaw_offset_deg || 0
  const pitch = asset.canonical_pitch_offset_deg || 0
  const { width, height, depth } = opening
  const model = useMemo(() => {
    const prepared = prepareOpeningModel(scene, { ...asset, canonical_yaw_offset_deg: yaw, canonical_pitch_offset_deg: pitch }, { width, height, depth })
    const infill = prepared.object.getObjectByName('Arch_wall_infill')
    if (infill && originals.length) {
      let house = originals[0]
      while (house.parent && house.parent.type !== 'Scene') house = house.parent
      const point = new THREE.Vector3(...opening.position)
      point.y += height / 2
      let closest = Infinity, material = null
      house.traverse((object) => {
        if (!object.isMesh) return
        let wall = object
        while (wall && wall !== house && !wall.userData?.archgen_wall_id && !/^wall_/i.test(wall.name)) wall = wall.parent
        if (!wall || wall === house) return
        const distance = new THREE.Box3().setFromObject(object).distanceToPoint(point)
        if (distance < closest) { closest = distance; material = Array.isArray(object.material) ? object.material[0] : object.material }
      })
      if (material) { infill.material.dispose(); infill.material = material.clone() }
    }
    return prepared
  }, [scene, asset, yaw, pitch, width, height, depth, originals, opening.position])
  const root = useRef(null)
  useEffect(() => () => model.object.traverse((object) => {
    if (!object.isMesh) return
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) material?.dispose()
  }), [model])
  useLayoutEffect(() => {
    const previous = originals.map((object) => object.visible)
    originals.forEach((object) => { object.visible = false; setSubtreePickable(object, false) })
    return () => originals.forEach((object, index) => {
      object.visible = previous[index]; setSubtreePickable(object, previous[index])
    })
  }, [originals])
  useLayoutEffect(() => { if (root.current) setSubtreePickable(root.current, visible) }, [visible, model])
  useLayoutEffect(() => {
    if (!selected || !onObjectReady) return undefined
    const frame = requestAnimationFrame(() => onObjectReady({ ...selection, object: root.current }))
    return () => cancelAnimationFrame(frame)
  }, [selected, onObjectReady, selection, model])
  return <group ref={root} visible={visible} position={opening.position} rotation={[0, opening.rotation || 0, 0]}
    userData={{ entityType: selection?.type, entityId: selection?.id, source: 'opening-replacement' }}
    onClick={(event) => {
      if (!visible || !onSelect || !isSelectionClick(event)) return
      event.stopPropagation()
      onSelect({ ...selection, object: root.current, cameraPoint: event.ray.origin.clone(),
        hitPoint: { x: event.point.x, y: event.point.y, z: event.point.z } })
    }}>
    <group scale={model.scale}><primitive object={model.object} /></group>
  </group>
}

export default function OpeningAsset(props) {
  if (!props.asset?.model_path) return null
  return <OpeningBoundary key={props.asset.model_path}>
    <Suspense fallback={null}><LoadedOpening {...props} /></Suspense>
  </OpeningBoundary>
}
