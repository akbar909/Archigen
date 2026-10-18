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
              The saved 3D model could not be loaded. Click below to request a fresh download link without regenerating it.
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
                Reload Saved 3D Model
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
export function BlenderHouseModel({ url, onRoomsDetected, onDoorsDetected, onLoaded, showRoof = true, activeFloorLevel = null }) {
  const { scene } = useGLTF(url)

  useEffect(() => {
    if (scene && onLoaded) {
      onLoaded()
    }
  }, [scene, onLoaded])

  useEffect(() => {
    if (!scene) return
    scene.updateMatrixWorld(true)

    const detected = []
    const detectedDoors = []

    scene.traverse((child) => {
      if (!child.isMesh) return

      const rawName = child.name || ''
      const parentName = child.parent?.name || ''
      const effectiveName = rawName.toLowerCase().startsWith('floor')
        ? rawName
        : (parentName.toLowerCase().startsWith('floor') ? parentName : rawName)
      const lowerName = effectiveName.toLowerCase()

      // ── Detect room floor slabs ──
      if (lowerName.startsWith('floor')) {
        // Exclude site elements, whole-house foundation/podium, lawns, intermediate slabs, and cutters
        if (
          lowerName.includes('podium') ||
          lowerName.includes('foundation') ||
          lowerName.includes('lawn') ||
          lowerName.includes('garden') ||
          lowerName.includes('ground') ||
          lowerName.includes('intermediate') ||
          lowerName.includes('cutter') ||
          lowerName.includes('stair')
        ) {
          return
        }

        const box = new THREE.Box3().setFromObject(child)
        const center = new THREE.Vector3()
        const size = new THREE.Vector3()
        box.getCenter(center)
        box.getSize(size)

        // Ignore micro or non-floor meshes
        if (size.x < 0.6 || size.z < 0.6) return

        const explicitLevel = child.userData?.archgen_floor_level
          ?? child.parent?.userData?.archgen_floor_level
          ?? child.userData?.floor_level
          ?? child.parent?.userData?.floor_level

        let level = 0
        if (explicitLevel !== undefined && explicitLevel !== null && explicitLevel !== '') {
          const parsed = Number(explicitLevel)
          if (Number.isFinite(parsed)) level = parsed
        } else {
          const match = effectiveName.match(/(?:^|_)l(\d+)(?:_|$)/i)
          if (match) {
            level = Number(match[1])
          } else {
            // Three.js center.y is elevation in meters: 0m -> level 0, ~3m -> level 1, etc.
            level = Math.max(0, Math.round(center.y / 3.0))
          }
        }

        const roomId = child.userData?.archgen_room_id
          || child.parent?.userData?.archgen_room_id
          || ''

        const meshId = effectiveName.replace(/^floor(?:_L\d+)?_?/i, '')

        detected.push({
          name: effectiveName,
          meshId,
          roomId,
          level,
          center: { x: center.x, y: center.y, z: center.z },
          size: { x: size.x, y: size.y, z: size.z },
        })
      }

      // ── Detect 3D doors for physical doorway passage ──
      const doorName = (
        rawName.toLowerCase().startsWith('door')
          ? rawName
          : (parentName.toLowerCase().startsWith('door') ? parentName : '')
      ).toLowerCase()
      if (doorName && !doorName.includes('cutter') && !doorName.includes('frame')) {
        const box = new THREE.Box3().setFromObject(child)
        const center = new THREE.Vector3()
        const size = new THREE.Vector3()
        box.getCenter(center)
        box.getSize(size)
        const level = Math.max(0, Math.round(center.y / 3.0))
        detectedDoors.push({
          name: rawName || parentName,
          worldX: center.x,
          worldZ: center.z,
          width: Math.max(size.x, size.z, 0.9),
          floorLevel: level,
        })
      }
    })

    if (detected.length > 0 && onRoomsDetected) {
      console.log('[Viewer3D] Detected 3D floor slabs from GLB model:', detected)
      onRoomsDetected(detected)
    }

    if (detectedDoors.length > 0 && onDoorsDetected) {
      console.log('[Viewer3D] Detected 3D doors from GLB model:', detectedDoors)
      onDoorsDetected(detectedDoors)
    }
  }, [scene, onRoomsDetected, onDoorsDetected])

  const clonedScene = useMemo(() => {
    if (!scene) return null
    const clone = scene.clone(true)
    clone.updateMatrixWorld(true)

    // Old exports could contain parapet children that inherited the already
    // scaled roof slab transform. Keep those cached GLBs usable by rejecting
    // only roof meshes that are implausibly larger than the actual house.
    const structuralBounds = new THREE.Box3()
    const ownWorldBounds = (object) => {
      if (!object?.isMesh || !object.geometry) return null
      if (!object.geometry.boundingBox) object.geometry.computeBoundingBox()
      return object.geometry.boundingBox?.clone().applyMatrix4(object.matrixWorld) || null
    }
    clone.traverse((child) => {
      const lowerName = String(child.name || '').toLowerCase()
      if (child.isMesh && (lowerName.startsWith('wall_') || lowerName.startsWith('floor_'))) {
        const bounds = ownWorldBounds(child)
        if (bounds) structuralBounds.union(bounds)
      }
    })
    const structuralSize = new THREE.Vector3()
    if (!structuralBounds.isEmpty()) structuralBounds.getSize(structuralSize)

    const ownFloorLevel = (object) => {
      const metadataLevel = object?.userData?.archgen_floor_level
        ?? object?.userData?.floor_level
      if (metadataLevel !== undefined && metadataLevel !== null && metadataLevel !== '') {
        const parsed = Number(metadataLevel)
        if (Number.isFinite(parsed)) return parsed
      }
      const objectName = String(object?.name || '').toLowerCase()
      const canonical = objectName.match(/(?:^|_)l(\d+)(?:_|$)/)
      if (canonical) return Number(canonical[1])
      const legacy = objectName.match(/(?:floor|level)_(\d+)/)
      return legacy ? Number(legacy[1]) : null
    }

    const inheritedFloorLevels = (object) => {
      let current = object
      const levels = new Set()
      while (current && current !== clone.parent) {
        const level = ownFloorLevel(current)
        if (level !== null) levels.add(level)
        const upperLevel = Number(current?.userData?.archgen_upper_floor_level)
        if (Number.isFinite(upperLevel)) levels.add(upperLevel)
        if (current === clone) break
        current = current.parent
      }
      return levels
    }

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
        lowerName.startsWith('_stairopening_') ||
        lowerName.startsWith('_frame_cutter_') ||
        lowerName.startsWith('_wframe_cutter_') ||
        child.userData?.archgen_stair_opening === true
      ) {
        child.visible = false
        return
      }

      // Roof visibility toggle — also hide in cut-away floor view since roof
      // sits above every storey.
      if (lowerName.startsWith('roof') || lowerName.includes('_roof_') || lowerName.startsWith('roof_')) {
        const bounds = ownWorldBounds(child)
        const size = new THREE.Vector3()
        if (bounds) bounds.getSize(size)
        const malformedLegacyRoof = (
          structuralSize.x > 0 && structuralSize.z > 0
          && (size.x > structuralSize.x * 1.35 || size.z > structuralSize.z * 1.35)
        )
        const isCutAway = activeFloorLevel !== null && activeFloorLevel !== undefined
        child.visible = showRoof && !malformedLegacyRoof && !isCutAway
      }

      // Cut-away view: show the selected floor AND everything below it.
      // Hide objects that belong exclusively to floors ABOVE the active level.
      // Unlevelled site objects (ground, terrain, etc.) always remain visible.
      if (activeFloorLevel !== null && activeFloorLevel !== undefined && activeFloorLevel >= 0) {
        const explicitLevels = inheritedFloorLevels(child)
        const activeLvl = Number(activeFloorLevel)

        if (explicitLevels.size > 0) {
          // Object has explicit floor metadata — hide if ALL its levels are above the active level
          const allAbove = [...explicitLevels].every((lvl) => lvl > activeLvl)
          if (allAbove) {
            child.visible = false
          }
        } else {
          // No explicit metadata — use legacy name heuristics for upper floors
          const legacyMatch = lowerName.match(/(?:floor|level)[_]?(\d+)/)
          const inferredLevel = legacyMatch ? Number(legacyMatch[1]) : null
          if (inferredLevel !== null && inferredLevel > activeLvl) {
            child.visible = false
          }
          // Also hide objects with "upper_" prefix when viewing ground floor
          if (activeLvl === 0 && lowerName.includes('upper_')) {
            child.visible = false
          }
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

BlenderHouseModel.clear = (url) => {
  if (url) {
    useGLTF.clear(url)
  }
}
