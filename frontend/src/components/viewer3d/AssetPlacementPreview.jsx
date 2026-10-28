/* eslint-disable react/prop-types, react/no-unknown-property */
import { Component, Suspense, useEffect, useMemo, useRef } from 'react'
import { useGLTF } from '@react-three/drei'
import { prepareAssetModel } from '../../utils/assetModel'
import { setSubtreePickable } from '../../utils/sceneEditing'

class PreviewBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onStatus(this.props.id, 'error') }
  render() { return this.state.failed ? null : this.props.children }
}

function PreviewModel({ item, onStatus, onObjectReady }) {
  const root = useRef(null)
  const { scene } = useGLTF(item.model_path, '/draco/gltf/')
  const prepared = useMemo(() => {
    const result = prepareAssetModel(scene, item)
    result.object.traverse((mesh) => {
      if (!mesh.isMesh) return
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        material.transparent = true
        material.opacity = 0.65
        material.depthWrite = false
      }
    })
    setSubtreePickable(result.object, false)
    return result
  }, [scene, item])
  useEffect(() => { onStatus(item.id, 'ready') }, [item.id, onStatus])
  useEffect(() => {
    onObjectReady?.(root.current)
    return () => onObjectReady?.(null)
  }, [onObjectReady])
  useEffect(() => () => prepared.object.traverse((mesh) => {
    if (mesh.isMesh) (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach((material) => material.dispose())
  }), [prepared])
  const ceilingOffset = item.ceiling_mounted ? item.dimensions.height - prepared.dimensions.height : 0
  return <group ref={root} position={[item.position.x, item.position.z + ceilingOffset + (item.asset_group === 'floor_overlay' ? 0.008 : 0), -item.position.y]}
    rotation={[0, -item.rotation * Math.PI / 180, 0]} scale={prepared.scale}>
    <primitive object={prepared.object} />
  </group>
}

export default function AssetPlacementPreview({ placement, onStatus, onObjectReady }) {
  if (!placement) return null
  return <PreviewBoundary key={placement.item.id} id={placement.item.id} onStatus={onStatus}>
    <Suspense fallback={null}><PreviewModel item={placement.item} onStatus={onStatus} onObjectReady={onObjectReady} /></Suspense>
  </PreviewBoundary>
}
