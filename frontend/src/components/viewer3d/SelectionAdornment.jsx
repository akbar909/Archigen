/* eslint-disable react/prop-types, react/no-unknown-property */
import { useEffect, useMemo, useRef } from 'react'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { Move3D, RotateCw, Trash2 } from 'lucide-react'

export function SelectionBox({ object }) {
  const helper = useMemo(() => (
    object ? new THREE.BoxHelper(object, '#22d3ee') : null
  ), [object])

  useFrame(() => helper?.update())
  useEffect(() => () => helper?.dispose(), [helper])
  return helper ? <primitive object={helper} raycast={() => null} /> : null
}

export function SelectionQuickActions({ object, mode, onModeChange, onRotate, onDelete, allowRotation = true }) {
  const anchorRef = useRef(null)
  const bounds = useMemo(() => new THREE.Box3(), [])
  const center = useMemo(() => new THREE.Vector3(), [])

  useFrame(() => {
    if (!object || !anchorRef.current) return
    bounds.setFromObject(object)
    bounds.getCenter(center)
    anchorRef.current.position.set(center.x, bounds.max.y + 0.35, center.z)
  })

  if (!object) return null
  return (
    <group ref={anchorRef}>
      <Html center style={{ pointerEvents: 'auto' }}>
        <div className="scene-quick-actions" onPointerDown={(event) => event.stopPropagation()}>
          <button
            type="button"
            className={mode === 'translate' ? 'active' : ''}
            onClick={() => onModeChange('translate')}
            title="Move object"
          >
            <Move3D size={14} />
          </button>
          <button
            type="button"
            className={mode === 'rotate' ? 'active' : ''}
            onClick={() => onModeChange('rotate')}
            title="Rotate with gizmo"
            disabled={!allowRotation}
          >
            <RotateCw size={14} />
          </button>
          <button type="button" onClick={onRotate} title="Rotate 90 degrees" disabled={!allowRotation}>
            90°
          </button>
          <button type="button" className="danger" onClick={onDelete} title="Delete furniture">
            <Trash2 size={14} />
          </button>
        </div>
      </Html>
    </group>
  )
}
