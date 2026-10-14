import { Component, useEffect, useMemo, useState } from 'react'
import * as THREE from 'three'
import { Html, useGLTF, useProgress } from '@react-three/drei'
import { Sparkles, RotateCw } from 'lucide-react'

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
        <Html center style={{ pointerEvents: 'auto', transform: 'translate3d(-50%, -80px, 0)' }}>
          <div
            style={{
              background: 'rgba(18, 18, 18, 0.95)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: 14,
              padding: '20px 26px',
              textAlign: 'center',
              color: '#f87171',
              maxWidth: 320,
              boxShadow: '0 16px 48px rgba(0,0,0,0.8)',
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
                  background: '#10a37f',
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

// ── Loading Fallback with Real-time Progress Bar ──────────────────────
export function BlenderLoadingFallback({ onRetry }) {
  const { progress } = useProgress()
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setElapsed((prev) => prev + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  const percent = Math.min(Math.round(progress || 0), 100)

  return (
    <Html center style={{ pointerEvents: 'auto', transform: 'translate3d(-50%, -100px, 0)' }}>
      <div
        style={{
          background: 'rgba(18, 18, 18, 0.96)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(16, 163, 127, 0.4)',
          borderRadius: 16,
          padding: '20px 28px',
          color: '#10a37f',
          boxShadow: '0 20px 50px rgba(0,0,0,0.8), 0 0 25px rgba(16, 163, 127, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          minWidth: 290,
          zIndex: 100,
          textAlign: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 700, fontSize: '0.92rem', color: '#f8fafc' }}>
          <Sparkles size={18} className="animate-spin text-emerald-400" />
          <span>{percent > 0 ? `Loading 3D Model (${percent}%)` : 'Initializing 3D Model…'}</span>
        </div>

        {/* Real-time download progress bar */}
        <div style={{ width: '100%', height: 6, background: 'rgba(255,255,255,0.12)', borderRadius: 999, overflow: 'hidden' }}>
          <div
            style={{
              width: `${Math.max(percent, 4)}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #10a37f, #34d399)',
              transition: 'width 0.2s ease',
            }}
          />
        </div>

        <div style={{ fontSize: '0.74rem', color: 'rgba(255,255,255,0.72)', lineHeight: 1.4 }}>
          {percent < 100
            ? 'Downloading architecture, textures, and assets…'
            : 'Rendering 3D architecture into viewport…'}
        </div>

        {/* Retry option if taking more than 15 seconds */}
        {elapsed >= 15 && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            style={{
              marginTop: 4,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: 'rgba(16, 163, 127, 0.2)',
              border: '1px solid rgba(16, 163, 127, 0.5)',
              borderRadius: 8,
              padding: '6px 14px',
              fontSize: '0.75rem',
              color: '#34d399',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            <RotateCw size={13} />
            <span>Taking longer than expected? Reload</span>
          </button>
        )}
      </div>
    </Html>
  )
}

// ── Model Loader (Single Self-Contained GLB Binary) ───────────────────
export function BlenderHouseModel({ url, onRoomsDetected, onLoaded, showRoof = true, activeFloorLevel = null }) {
  const { scene } = useGLTF(url)

  useEffect(() => {
    if (scene && onLoaded) {
      onLoaded()
    }
  }, [scene, onLoaded])

  useEffect(() => {
    if (!scene || !onRoomsDetected) return
    const detected = []
    scene.traverse((child) => {
      const lowerName = String(child.name || '').toLowerCase()
      if (child.isMesh && lowerName.startsWith('floor')) {
        const box = new THREE.Box3().setFromObject(child)
        const center = new THREE.Vector3()
        const size = new THREE.Vector3()
        box.getCenter(center)
        box.getSize(size)
        detected.push({
          name: child.name,
          meshId: child.name.replace(/^floor(?:_L\d+)?_?/i, ''),
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
      const lowerName = name.toLowerCase()
      if (
        lowerName.startsWith('cutter_') ||
        lowerName.startsWith('_boolean_cutter_') ||
        lowerName.startsWith('_frame_cutter_') ||
        lowerName.startsWith('_wframe_cutter_')
      ) {
        child.visible = false
        return
      }

      // Roof visibility toggle (showRoof = true / false)
      if (lowerName.startsWith('roof') || lowerName.includes('_roof_') || lowerName.startsWith('roof_')) {
        child.visible = showRoof
      }

      // Floor cutaway filtering if activeFloorLevel is specified (e.g. 0 for ground floor only)
      if (activeFloorLevel !== null && activeFloorLevel !== undefined && activeFloorLevel >= 0) {
        const levelMatch = lowerName.match(/_l(\d+)_/)
        const explicitLevel = levelMatch ? Number(levelMatch[1]) : null
        const legacyUpper = lowerName.includes('floor_1') || lowerName.includes('floor_2') || lowerName.includes('level_1') || lowerName.includes('upper_')
        if ((explicitLevel !== null && explicitLevel > activeFloorLevel) || (explicitLevel === null && activeFloorLevel === 0 && legacyUpper)) {
          child.visible = false
        }
      }

      if (child.isMesh) {
        child.castShadow = true
        child.receiveShadow = true
        if (child.material) {
          child.material = child.material.clone()
          const mats = Array.isArray(child.material) ? child.material : [child.material]
          mats.forEach((m) => {
            if (m.map) {
              m.map.wrapS = THREE.RepeatWrapping
              m.map.wrapT = THREE.RepeatWrapping
              m.map.needsUpdate = true
            }
            if (m.roughnessMap) {
              m.roughnessMap.wrapS = THREE.RepeatWrapping
              m.roughnessMap.wrapT = THREE.RepeatWrapping
            }
            if (m.normalMap) {
              m.normalMap.wrapS = THREE.RepeatWrapping
              m.normalMap.wrapT = THREE.RepeatWrapping
            }
          })
          if (lowerName.startsWith('wall_')) {
            child.material.polygonOffset = true
            child.material.polygonOffsetFactor = 1
            child.material.polygonOffsetUnits = 1
          } else if (lowerName.startsWith('floor_')) {
            child.material.polygonOffset = true
            child.material.polygonOffsetFactor = -1
            child.material.polygonOffsetUnits = -1
          }
        }
      }
    })
    return clone
  }, [scene, showRoof, activeFloorLevel])

  if (!clonedScene) return null
  return <primitive object={clonedScene} position={[0, 0, 0]} />
}

// Preload utility for snappy scene loads
BlenderHouseModel.preload = (url) => {
  if (url) {
    useGLTF.preload(url)
  }
}
