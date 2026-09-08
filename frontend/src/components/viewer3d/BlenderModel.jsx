import { Component, useEffect, useMemo, useState } from 'react'
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
    console.warn('[Viewer3D] Error loading Blender GLB model, switching to CAD view:', error)
    if (this.props.onError) {
      this.props.onError(error)
    }
  }
  render() {
    if (this.state.hasError) {
      return this.props.fallback || null
    }
    return this.props.children
  }
}

// ── Loading Fallback with Auto-Timeout & Manual Bypass ───────────────
export function BlenderLoadingFallback({ onFallbackToCad }) {
  const [secondsRemaining, setSecondsRemaining] = useState(6)

  useEffect(() => {
    const interval = setInterval(() => {
      setSecondsRemaining((s) => {
        if (s <= 1) {
          clearInterval(interval)
          console.warn('[Viewer3D] Blender GLB load timed out (6s). Switching to CAD View.')
          onFallbackToCad?.()
          return 0
        }
        return s - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [onFallbackToCad])

  return (
    <Html center>
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.92)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(56, 189, 248, 0.35)',
          borderRadius: 16,
          padding: '16px 24px',
          color: '#38bdf8',
          boxShadow: '0 16px 48px rgba(0,0,0,0.7)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          whiteSpace: 'nowrap',
          zIndex: 50,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 600, fontSize: '0.88rem' }}>
          <Sparkles size={16} className="animate-spin" />
          <span>Loading Photorealistic 3D Model ({secondsRemaining}s)...</span>
        </div>
        <button
          type="button"
          onClick={onFallbackToCad}
          style={{
            background: 'var(--accent)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 999,
            padding: '6px 16px',
            fontSize: '0.78rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          Switch to CAD View
        </button>
      </div>
    </Html>
  )
}

// ── Model Loader ─────────────────────────────────────────────────────
export function BlenderHouseModel({ url }) {
  const { scene } = useGLTF(url)
  const clonedScene = useMemo(() => {
    if (!scene) return null
    const clone = scene.clone(true)
    clone.traverse((child) => {
      if (child.isLight) {
        child.visible = false
        child.intensity = 0
      }

      // Filter out exploded beams from legacy parented caps/baseboards and boolean cutters
      const name = String(child.name || '')
      if (
        name.startsWith('cap_') ||
        name.startsWith('baseboard_') ||
        name.startsWith('cutter_') ||
        name.startsWith('_boolean_cutter_') ||
        name.startsWith('_frame_cutter_') ||
        name.startsWith('_wframe_cutter_')
      ) {
        child.visible = false
        return
      }

      // Filter out duplicate plain foundation/deck from Blender to let Three.js lush grounds shine
      if (
        name === 'Architectural_Foundation_Podium' ||
        name === 'Outdoor_Teak_Patio_Deck'
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
            child.material.color = new THREE.Color('#f1f5f9')
            child.material.roughness = 0.85
            child.material.polygonOffset = true
            child.material.polygonOffsetFactor = 1
            child.material.polygonOffsetUnits = 1
          } else if (name.startsWith('floor_')) {
            child.material.roughness = 0.55
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
