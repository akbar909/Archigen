import { Component, useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { Html, useGLTF } from '@react-three/drei'
import { Sparkles } from 'lucide-react'

// ── Blender Headless GLB Model Component with Error Boundary ─────────
export class BlenderErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error) {
    console.warn('[Viewer3D] Error loading Blender GLB model:', error)
    if (this.props.onError) {
      this.props.onError(error)
    }
  }
  render() {
    if (this.state.hasError) {
      return (
        <Html center>
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.95)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: 14,
              padding: '20px 26px',
              textAlign: 'center',
              color: '#f87171',
              maxWidth: 320,
              boxShadow: '0 16px 48px rgba(0,0,0,0.7)',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 6 }}>
              3D Model Loading Error
            </div>
            <div style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.7)', lineHeight: 1.45, marginBottom: 14 }}>
              The 3D model could not be loaded or is unavailable in the cloud. Click below to regenerate it.
            </div>
            {this.props.onRetry && (
              <button
                type="button"
                onClick={this.props.onRetry}
                style={{
                  background: '#0284c7',
                  border: 'none',
                  borderRadius: 8,
                  color: 'white',
                  padding: '8px 16px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                Regenerate 3D Model
              </button>
            )}
          </div>
        </Html>
      )
    }
    return this.props.children
  }
}

// ── Loading Fallback (Clean GLB Rendering Status) ─────────────────────
export function BlenderLoadingFallback() {
  return (
    <Html center>
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.94)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(56, 189, 248, 0.4)',
          borderRadius: 16,
          padding: '20px 28px',
          color: '#38bdf8',
          boxShadow: '0 16px 48px rgba(0,0,0,0.7)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          whiteSpace: 'nowrap',
          zIndex: 50,
          minWidth: 260,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 600, fontSize: '0.9rem' }}>
          <Sparkles size={18} className="animate-spin text-sky-400" />
          <span>Loading 3D Model…</span>
        </div>

        <div style={{ fontSize: '0.74rem', color: 'rgba(255,255,255,0.7)' }}>
          Rendering 3D architecture in viewport
        </div>
      </div>
    </Html>
  )
}

// ── Model Loader (Single Self-Contained GLB Binary) ───────────────────
export function BlenderHouseModel({ url, onRoomsDetected }) {
  const { scene } = useGLTF(url)

  useEffect(() => {
    if (!scene || !onRoomsDetected) return
    const detected = []
    scene.traverse((child) => {
      if (child.isMesh && (child.name.startsWith('floor_') || child.name.startsWith('floor'))) {
        const box = new THREE.Box3().setFromObject(child)
        const center = new THREE.Vector3()
        const size = new THREE.Vector3()
        box.getCenter(center)
        box.getSize(size)
        detected.push({
          name: child.name,
          meshId: child.name.replace(/^floor_?/, ''),
          center: { x: center.x, y: center.y, z: center.z },
          size: { x: size.x, y: size.y, z: size.z },
        })
      }
    })
    if (detected.length > 0) {
      console.log('[Viewer3D] Detected 3D floor slabs from GLB model:', detected)
      onRoomsDetected(detected)
    }
  }, [scene, onRoomsDetected])

  const clonedScene = useMemo(() => {
    if (!scene) return null
    const clone = scene.clone(true)
    clone.traverse((child) => {
      if (child.isLight) {
        child.visible = false
        child.intensity = 0
      }

      // Filter out boolean cutters and temporary construction helpers
      const name = String(child.name || '')
      if (
        name.startsWith('cutter_') ||
        name.startsWith('_boolean_cutter_') ||
        name.startsWith('_frame_cutter_') ||
        name.startsWith('_wframe_cutter_')
      ) {
        child.visible = false
        return
      }

      if (child.isMesh) {
        child.castShadow = true
        child.receiveShadow = true
        if (child.material) {
          child.material = child.material.clone()
          if (name.startsWith('wall_')) {
            child.material.polygonOffset = true
            child.material.polygonOffsetFactor = 1
            child.material.polygonOffsetUnits = 1
          } else if (name.startsWith('floor_')) {
            child.material.polygonOffset = true
            child.material.polygonOffsetFactor = -1
            child.material.polygonOffsetUnits = -1
          }
        }
      }
    })
    return clone
  }, [scene])

  if (!clonedScene) return null
  return <primitive object={clonedScene} position={[0, 0, 0]} />
}

// Preload utility for snappy scene loads
BlenderHouseModel.preload = (url) => {
  if (url) {
    useGLTF.preload(url)
  }
}

