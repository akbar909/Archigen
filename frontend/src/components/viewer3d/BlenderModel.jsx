/* eslint-disable react/prop-types, react/no-unknown-property */
import { Component, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Html, useGLTF, useProgress } from '@react-three/drei'
import { Sparkles, RotateCw } from 'lucide-react'
import { saveModelToCache } from '../../utils/modelCache'
import { canApplyAccentColor, prepareAssetModel } from '../../utils/assetModel'
import { clone as cloneSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { applySurfaceTexture, findEditableSurface as findSurfaceRoot, isVisibleInHierarchy, setSubtreePickable } from '../../utils/sceneEditing'
import { isSelectionClick } from '../../utils/selectionGesture'
import { canonicalOpenings, collectOpeningRoots, openingFromObject, resolveOpeningAsset } from '../../utils/openingEditing'
import OpeningAsset from './OpeningAsset'

// Enable Draco decompression via local WASM decoders or Google CDN fallback
const DRACO_DECODER_PATH = '/draco/gltf/'

// Only self-contained GLB files are safe to load from signed S3 URLs.
const isBrowserModel = (path) => (
  typeof path === 'string' && path.trim() && path.split('?')[0].toLowerCase().endsWith('.glb')
)

const normalizedToken = (value) => String(value || '')
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '_')
  .replace(/^_+|_+$/g, '')

function furnitureIdForObject(object, furnitureIds) {
  const metadataId = object?.userData?.archgen_instance_id
  if (metadataId !== undefined && metadataId !== null) {
    const exact = furnitureIds.find((id) => String(id) === String(metadataId))
    if (exact) return exact
  }
  const name = normalizedToken(object?.name)
  if (!name.includes('furniture')) return null
  return furnitureIds.find((id) => name.includes(normalizedToken(id))) || null
}

function findFurnitureRoot(hitObject, sceneRoot, furnitureIds) {
  let current = hitObject
  let nameMatch = null
  while (current && current !== sceneRoot.parent) {
    const id = furnitureIdForObject(current, furnitureIds)
    if (id) {
      if (current.userData?.archgen_instance_id !== undefined || current.userData?.archgen_asset_root) {
        return { id, object: current }
      }
      nameMatch = { id, object: current }
    }
    if (current === sceneRoot) break
    current = current.parent
  }
  return nameMatch
}

function roomForSurface(match, point, rooms, cameraPoint) {
  if (match.roomId) return rooms.find((room) => String(room.id) === String(match.roomId)) || null
  const connected = String(match.object?.userData?.archgen_connected_rooms || '')
    .split(',').map((value) => value.trim()).filter(Boolean)
  const candidates = connected.length
    ? rooms.filter((room) => connected.includes(String(room.id)))
    : rooms
  const contains = (room, target, pad = 0) => {
    const position = room.position || room.bounds || {}
    const dimensions = room.dimensions || room.bounds || {}
    const x0 = Number(position.x) || 0
    const y0 = Number(position.y) || 0
    const x1 = x0 + (Number(dimensions.width ?? room.width) || 0)
    const y1 = y0 + (Number(dimensions.depth ?? room.length) || 0)
    const y = -target.z
    const floorZ = Number(position.z) || 0
    return target.x >= x0 - pad && target.x <= x1 + pad && y >= y0 - pad && y <= y1 + pad
      && target.y >= floorZ - 0.1 && target.y <= floorZ + (Number(dimensions.height) || 3) + 0.1
  }
  // On a shared wall choose the room on the viewer's side, never the first
  // connected room in the GLB metadata.
  if (cameraPoint) {
    const towardCamera = cameraPoint.clone().sub(point).normalize().multiplyScalar(0.25).add(point)
    const sideRoom = candidates.find((room) => contains(room, towardCamera))
    if (sideRoom) return sideRoom
  }
  return candidates.find((room) => contains(room, point, 0.15))
    || (['roof', 'ceiling'].includes(match.type) ? candidates.find((room) => contains(room, new THREE.Vector3(point.x, point.y - 0.3, point.z), 0.15)) : null)
    || null
}

function wallSideAtPoint(room, point) {
  if (!room) return 'front'
  const position = room.position || room.bounds || {}
  const dimensions = room.dimensions || room.bounds || {}
  const x0 = Number(position.x) || 0
  const y0 = Number(position.y) || 0
  const x1 = x0 + (Number(dimensions.width ?? room.width) || 0)
  const y1 = y0 + (Number(dimensions.depth ?? room.length) || 0)
  const canonicalY = -point.z
  return [
    [Math.abs(point.x - x0), 'left'], [Math.abs(point.x - x1), 'right'],
    [Math.abs(canonicalY - y0), 'back'], [Math.abs(canonicalY - y1), 'front'],
  ].sort((a, b) => a[0] - b[0])[0][1]
}

function applyUploadedTexture(object, url, repeat = 2, normal = null) {
  return applySurfaceTexture(object, url, repeat, normal).catch((error) => console.warn('[Viewer3D] Finish loading failed:', error))
}

class AssetLoadBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error) { console.warn('[Viewer3D] Asset replacement unavailable:', error.message) }
  render() { return this.state.failed ? null : this.props.children }
}

function BlenderReplacementAsset({ item, visible, isSelected, onSelect, onObjectReady, onReady }) {
  const rootRef = useRef(null)
  const { scene } = useGLTF(item.model_path, DRACO_DECODER_PATH)
  const normalized = useMemo(() => {
    return prepareAssetModel(scene, item)
  }, [scene, item])
  const position = item.position || {}
  const elevation = Number(position.z) || 0
  const isRug = /rug|carpet/.test(String(item.category || item.asset || item.name || '').toLowerCase())
  const floorOffset = isRug ? 0.008 : 0
  const mountHeight = item.wall_mounted ? Math.max(0, Number(item.mount_height) || 0) : 0
  const ceilingOffset = item.ceiling_mounted
    ? (Number(item.dimensions?.height) || 0.8) - normalized.dimensions.height : 0
  const rotation = THREE.MathUtils.degToRad(-(Number(item.rotation ?? item.rotation_y) || 0))

  useEffect(() => { onReady?.() }, [onReady])
  useEffect(() => {
    if (rootRef.current) setSubtreePickable(rootRef.current, visible)
  }, [visible, normalized])

  useEffect(() => {
    if (!isSelected || !rootRef.current || !onObjectReady) return undefined
    // Keep parent selection state updates outside the asset render/effect
    // transaction. This avoids React's cross-component update warning while
    // Suspense is resolving a replacement GLB.
    const object = rootRef.current
    const frame = requestAnimationFrame(() => onObjectReady(object))
    return () => cancelAnimationFrame(frame)
  }, [isSelected, onObjectReady])

  return (
    <group
      ref={rootRef}
      visible={visible}
      position={[Number(position.x) || 0, elevation + mountHeight + ceilingOffset + floorOffset, -(Number(position.y) || 0)]}
      rotation={[0, rotation, 0]}
      scale={[item.flip_x ? -1 : 1, 1, item.flip_y ? -1 : 1]}
      userData={{
        isSelectable: true,
        entityType: 'furniture',
        entityId: item.id,
        roomId: item.room_id || item.roomId,
        source: 'blender-replacement',
        asset_info: {
          model_path: item.model_path, s3_key: item.s3_key,
          model_id: item.model_id, asset_id: item.asset_id,
          canonical_yaw_offset_deg: item.canonical_yaw_offset_deg,
          canonical_pitch_offset_deg: item.canonical_pitch_offset_deg,
          mounting: item.mounting,
          wall_orientation_version: item.wall_orientation_version,
          dimensions: item.dimensions,
        },
      }}
      onClick={(event) => {
        if (!visible || !isSelectionClick(event)) return
        event.stopPropagation()
        onSelect?.({
          type: 'furniture',
          id: item.id,
          roomId: item.room_id || item.roomId,
          object: rootRef.current,
          source: 'blender',
        })
      }}
    >
      <group scale={normalized.scale}>
        <primitive object={normalized.object} />
      </group>
    </group>
  )
}

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
  // Loader notifications can fire synchronously during a Suspense render.
  // Poll after commit so they cannot update a different rendering component.
  const [progress, setProgress] = useState(0)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const update = () => setProgress(useProgress.getState().progress || 0)
    update()
    const timer = setInterval(update, 150)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const timer = setInterval(() => setElapsed((prev) => prev + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  const percent = Math.min(Math.round(progress || 0), 100)

  return (
    <Html center wrapperClass="viewer-loading-anchor" className="viewer-loading-content" style={{ pointerEvents: 'auto', transform: 'translate3d(-50%, -100px, 0)' }}>
      <div
        className="viewer-loading-card"
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

export function BlenderHouseModel({
  url,
  onRoomsDetected,
  onDoorsDetected,
  onLoaded,
  showRoof = true,
  activeFloorLevel = null,
  viewMode = 'dollhouse',
  editingEnabled = false,
  furnitureItems = [],
  rooms = [],
  design = null,
  uploadedAssets = [],
  hiddenFurnitureIds = [],
  selectedEntity = null,
  onSelectEntity,
  onSelectionObjectReady,
}) {
  // Pass DRACO_DECODER_PATH so Draco-compressed GLB meshes are decoded efficiently via WebAssembly
  const { scene } = useGLTF(url, DRACO_DECODER_PATH)
  const [replacementReady, setReplacementReady] = useState({})

  // Asynchronously cache downloaded GLB model in browser IndexedDB for 0ms repeat loads
  useEffect(() => {
    if (!url) return
    // Check if not already loaded from blob
    if (!url.startsWith('blob:')) {
      fetch(url)
        .then((res) => (res.ok ? res.blob() : null))
        .then((blob) => {
          if (blob) {
            saveModelToCache(url, blob)
          }
        })
        .catch(() => {
          // Non-blocking network fetch fail for cache
        })
    }
  }, [url])

  // Announce readiness after scene metadata effects and a rendered frame.
  useEffect(() => {
    if (!scene || !onLoaded) return undefined
    let frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(() => onLoaded(true))
    })
    return () => {
      cancelAnimationFrame(frame)
      onLoaded(false)
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

    })

    const seenDoors = new Set()
    scene.traverse((object) => {
      const data = object.userData || {}
      const name = String(object.name || '')
      const metadataDoor = data.archgen_opening_kind === 'door'
      const legacyRoot = /^door/i.test(name) && !/^door/i.test(object.parent?.name || '')
      if (!metadataDoor && !legacyRoot) return
      if (/cutter/i.test(name) || data.archgen_opening_kind === 'window') return
      const id = String(data.archgen_opening_id || name)
      if (seenDoors.has(id)) return
      seenDoors.add(id)
      const bounds = new THREE.Box3().setFromObject(object)
      if (bounds.isEmpty()) return
      const center = bounds.getCenter(new THREE.Vector3())
      const size = bounds.getSize(new THREE.Vector3())
      const floorHeight = Number(design?.building?.floor_height) || 3
      const levelMatch = name.match(/(?:^|_)L(\d+)(?:_|$)/i)
      const level = Number(data.archgen_floor_level ?? (levelMatch ? Number(levelMatch[1]) : Math.floor((bounds.min.y + 0.05) / floorHeight)))
      detectedDoors.push({ id, name, worldX: metadataDoor ? Number(data.archgen_opening_x) : center.x,
        worldZ: metadataDoor ? -Number(data.archgen_opening_y) : center.z,
        width: Number(data.archgen_opening_width) || Math.max(size.x, size.z), floorLevel: level,
        axis: metadataDoor ? (data.archgen_opening_vertical ? 'z' : 'x') : (size.x >= size.z ? 'x' : 'z'),
      })
    })

    if (detected.length > 0 && onRoomsDetected) {
      console.log('[Viewer3D] Detected 3D floor slabs from GLB model:', detected)
      onRoomsDetected(detected)
    }

    if (detectedDoors.length > 0 && onDoorsDetected) {
      console.log('[Viewer3D] Detected 3D doors from GLB model:', detectedDoors)
      onDoorsDetected(detectedDoors)
    }
  }, [scene, onRoomsDetected, onDoorsDetected, design?.building?.floor_height])

  const furnitureIdKey = useMemo(
    () => [...new Set([
      ...furnitureItems.map((item) => item?.id).filter(Boolean),
      ...hiddenFurnitureIds.filter(Boolean),
    ])].sort().join('|'),
    [furnitureItems, hiddenFurnitureIds],
  )
  const furnitureIds = useMemo(
    () => (furnitureIdKey ? furnitureIdKey.split('|') : []),
    [furnitureIdKey],
  )

  const cloneBundle = useMemo(() => {
    if (!scene) return null
    const clone = cloneSkeleton(scene)
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

      // Roof visibility toggle — respect showRoof directly
      if (lowerName.startsWith('roof') || lowerName.includes('_roof_') || lowerName.startsWith('roof_')) {
        const bounds = ownWorldBounds(child)
        const size = new THREE.Vector3()
        if (bounds) bounds.getSize(size)
        const malformedLegacyRoof = (
          structuralSize.x > 0 && structuralSize.z > 0
          && (size.x > structuralSize.x * 1.35 || size.z > structuralSize.z * 1.35)
        )
        child.userData.__malformedLegacyRoof = malformedLegacyRoof
        child.visible = !malformedLegacyRoof
      }

      // Cut-away view: show the selected floor AND everything below it.
      // Hide objects that belong exclusively to floors ABOVE the active level.
      // In walkthrough mode, the user is inside a specific room, so don't cut away the ceiling above them!
      if (viewMode !== 'walkthrough' && activeFloorLevel !== null && activeFloorLevel !== undefined && activeFloorLevel >= 0) {
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
          child.material = Array.isArray(child.material) ? child.material.map((m) => m.clone()) : child.material.clone()
          const mats = Array.isArray(child.material) ? child.material : [child.material]
          mats.forEach((m) => {
            // Render both sides on roof, ceilings, and slabs so looking up from inside renders the ceiling
            if (
              lowerName.startsWith('roof') ||
              lowerName.includes('slab') ||
              lowerName.includes('ceiling') ||
              lowerName.startsWith('floor_')
            ) {
              m.side = THREE.DoubleSide
            }
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
    const furnitureRoots = new Map()
    clone.traverse((child) => {
      // Discover removed instance IDs too: saved layers may reuse a GLB
      // exported before the deletion, including older versions without tombstones.
      const metadataId = child.userData?.archgen_instance_id
      const id = metadataId !== undefined && metadataId !== null
        ? String(metadataId) : furnitureIdForObject(child, furnitureIds)
      if (!id) return
      const current = furnitureRoots.get(id)
      if (!current || child.userData?.archgen_instance_id !== undefined || child.userData?.archgen_asset_root) {
        furnitureRoots.set(id, child)
      }
    })
    furnitureRoots.forEach((root) => {
      root.userData.__archgenEditorBaseVisible = root.visible
      root.userData.isSelectable = true
      root.userData.entityType = 'furniture'
    })
    return { scene: clone, furnitureRoots }
  }, [scene, activeFloorLevel, viewMode, furnitureIds])

  // Roof visibility toggle decoupled from scene cloning to prevent texture flickering
  useEffect(() => {
    if (!cloneBundle) return
    cloneBundle.scene.traverse((child) => {
      const lowerName = String(child.name || '').toLowerCase()
      if (lowerName.startsWith('roof') || lowerName.includes('_roof_') || lowerName.startsWith('roof_')) {
        child.visible = Boolean(showRoof) && !child.userData?.__malformedLegacyRoof
      }
    })
  }, [cloneBundle, showRoof])

  const replacementItems = useMemo(
    () => {
      const suppressed = new Set(furnitureItems.flatMap((item) => item.suppressed_furniture_ids || []))
      return furnitureItems.filter((item) => item?.id && !suppressed.has(item.id)).map((item) => {
        if (isBrowserModel(item.model_path)) return item
        const original = cloneBundle?.furnitureRoots.get(item.id)
        if (!original) return null
        const asset = uploadedAssets.find((entry) => entry.kind === 'model' && (
          entry.id === original.userData?.archgen_id
          || entry.s3_key?.split('/').pop() === original.userData?.archgen_source_file
        ))
        if (!asset?.model_path) return null
        const position = original.getWorldPosition(new THREE.Vector3())
        const rotation = new THREE.Euler().setFromQuaternion(original.getWorldQuaternion(new THREE.Quaternion()), 'YXZ')
        return { ...item, dimensions: asset.dimensions, model_path: asset.model_path,
          s3_key: asset.s3_key, model_id: asset.id, asset_id: asset.id,
          canonical_yaw_offset_deg: asset.canonical_yaw_offset_deg,
          canonical_pitch_offset_deg: asset.canonical_pitch_offset_deg,
          mounting: asset.mounting,
          position: item.client_edited_3d ? item.position : {
            x: position.x, y: -position.z,
            z: position.y - (item.wall_mounted ? Number(item.mount_height) || 0 : 0),
          },
          rotation: item.client_edited_3d ? item.rotation : -THREE.MathUtils.radToDeg(rotation.y) }
      }).filter(Boolean)
    },
    [furnitureItems, cloneBundle, uploadedAssets],
  )
  const openingLayoutKey = JSON.stringify(canonicalOpenings(design))
  const openingRoots = useMemo(() => cloneBundle
    ? collectOpeningRoots(cloneBundle.scene, JSON.parse(openingLayoutKey)) : new Map(), [cloneBundle, openingLayoutKey])
  const replacementKey = replacementItems.map((item) => item.id).sort().join('|')

  useEffect(() => {
    if (!cloneBundle || !design) return
    const urlByKey = new Map(uploadedAssets.flatMap((asset) => [asset.s3_key, ...(asset.alias_s3_keys || [])].map((key) => [key, asset.url])))
    const resolveFinishUrl = (finish) => urlByKey.get(finish?.s3_key) || finish?.texture_url || null
    const wallFinishes = new Map(Object.entries(design.surface_overrides || {}))
    const wallFaces = new Map(Object.entries(design.wall_face_overrides || {}))
    const floorFinishes = new Map()
    const collectFloor = (floor) => {
      const floorWalls = floor?.walls || []
      const floorRooms = floor?.rooms || []
      floorWalls.forEach((wall) => {
        if (wall?.id && wall?.material_override) wallFinishes.set(String(wall.id), wall.material_override)
        if (wall?.id && wall?.material_overrides) wallFaces.set(String(wall.id), wall.material_overrides)
      })
      floorRooms.forEach((room) => {
        const finish = room?.materials?.floor || room?.pbr_material?.floor
        if (room?.id && finish?.s3_key) floorFinishes.set(String(room.id), finish)
      })
    }
    const designWalls = design.walls || []
    const designRooms = design.rooms || []
    const designFloors = design.floors || []
    designWalls.forEach((wall) => {
      if (wall?.id && wall?.material_override) wallFinishes.set(String(wall.id), wall.material_override)
      if (wall?.id && wall?.material_overrides) wallFaces.set(String(wall.id), wall.material_overrides)
    })
    designRooms.forEach((room) => {
      const finish = room?.materials?.floor || room?.pbr_material?.floor
      if (room?.id && finish?.s3_key) floorFinishes.set(String(room.id), finish)
    })
    designFloors.forEach(collectFloor)
    const applied = new Set()
    cloneBundle.scene.traverse((object) => {
      const surface = findSurfaceRoot(object, cloneBundle.scene)
      if (!surface || applied.has(surface.object.uuid)) return
      const root = surface.object
      const wallId = surface.type === 'wall' ? surface.id : null
      let roomId = surface.roomId
      if (surface.type === 'floor' && !roomId) {
        const bounds = new THREE.Box3().setFromObject(root)
        const point = bounds.getCenter(new THREE.Vector3())
        point.y = bounds.max.y + 0.05
        roomId = roomForSurface(surface, point, rooms)?.id
      }
      let finish = null
      let repeat = 2
      if (wallId && wallFinishes.has(String(wallId))) {
        finish = wallFinishes.get(String(wallId))
        repeat = 1.8
      } else if (roomId && surface.type === 'floor' && floorFinishes.has(String(roomId))) {
        finish = floorFinishes.get(String(roomId))
        repeat = 2.5
      } else if (surface.type === 'ground') {
        finish = design.exterior?.ground_finish
        repeat = 3.5
      }
      const url = resolveFinishUrl(finish)
      applied.add(root.uuid)
      const base = url ? applyUploadedTexture(root, url, repeat) : Promise.resolve()
      // Legacy whole-wall edits load first. Each new face has an independent
      // request key so editing the bathroom cannot cancel the bedroom finish.
      if (wallId && wallFaces.has(String(wallId))) base.then(() => {
        Object.values(wallFaces.get(String(wallId))).forEach((face) => {
          const faceUrl = resolveFinishUrl(face)
          if (faceUrl && face.normal) applyUploadedTexture(root, faceUrl, 1.8, face.normal)
        })
      })
    })
  }, [cloneBundle, design, uploadedAssets, rooms])

  useEffect(() => {
    if (!cloneBundle) return
    const replacements = new Set(replacementItems.filter((item) => replacementReady[`${item.id}:${item.model_path}`]).map((item) => item.id))
    const hidden = new Set(hiddenFurnitureIds.map(String))
    const activeIds = new Set(furnitureItems.map((item) => String(item.id)))
    furnitureItems.forEach((item) => (item.suppressed_furniture_ids || []).forEach((id) => hidden.add(String(id))))
    cloneBundle.furnitureRoots.forEach((root, id) => {
      root.visible = Boolean(root.userData.__archgenEditorBaseVisible) && activeIds.has(String(id)) && !replacements.has(id) && !hidden.has(String(id))
      setSubtreePickable(root, root.visible)
    })
  }, [cloneBundle, hiddenFurnitureIds, replacementItems, replacementKey, furnitureItems, replacementReady])

  useEffect(() => {
    if (!cloneBundle) return
    furnitureItems.forEach((item) => {
      if (!item?.id || !item.client_edited_3d || item.model_path) return
      const root = cloneBundle.furnitureRoots.get(item.id)
      if (!root) return
      const position = item.position || {}
      const elevation = Number(position.z) || 0
      const mountHeight = item.wall_mounted ? Math.max(0, Number(item.mount_height) || 0) : 0
      root.position.set(Number(position.x) || 0, elevation + mountHeight, -(Number(position.y) || 0))
      root.rotation.y = THREE.MathUtils.degToRad(-(Number(item.rotation ?? item.rotation_y) || 0))
      root.scale.x = Math.abs(root.scale.x) * (item.flip_x ? -1 : 1)
      root.scale.z = Math.abs(root.scale.z) * (item.flip_y ? -1 : 1)
      if (item.color && canApplyAccentColor(root)) {
        root.traverse((child) => {
          if (!child.isMesh || !child.material) return
          const materials = Array.isArray(child.material) ? child.material : [child.material]
          materials.forEach((material) => material.color?.set(item.color))
        })
      }
      root.updateMatrixWorld(true)
    })
  }, [cloneBundle, furnitureItems])

  useEffect(() => {
    if (!selectedEntity?.id || selectedEntity.source !== 'blender' || !cloneBundle) return
    if (replacementItems.some((item) => item.id === selectedEntity.id)) return
    const object = cloneBundle.furnitureRoots.get(selectedEntity.id)
    if (object) {
      const item = furnitureItems.find((entry) => entry.id === selectedEntity.id)
      onSelectionObjectReady?.({
        type: 'furniture',
        id: selectedEntity.id,
        roomId: item?.room_id || item?.roomId || object.userData?.archgen_room_id,
        object,
        source: 'blender',
      })
    }
  }, [cloneBundle, furnitureItems, onSelectionObjectReady, replacementItems, selectedEntity?.id, selectedEntity?.source])

  if (!cloneBundle) return null
  return (
    <group>
      <primitive
        object={cloneBundle.scene}
        position={[0, 0, 0]}
        onClick={(event) => {
          if (!editingEnabled || !isSelectionClick(event) || !isVisibleInHierarchy(event.object)) return
          const match = findFurnitureRoot(event.object, cloneBundle.scene, furnitureIds)
          if (match) {
            event.stopPropagation()
            const item = furnitureItems.find((entry) => entry.id === match.id)
            onSelectEntity?.({
              type: 'furniture',
              id: match.id,
              roomId: item?.room_id || item?.roomId || match.object.userData?.archgen_room_id,
              object: match.object,
              source: 'blender',
            })
            return
          }
          const surface = findSurfaceRoot(event.object, cloneBundle.scene)
          if (!surface) return
          event.stopPropagation()
          let normal = event.face?.normal?.clone().applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(event.object.matrixWorld))
          if (surface.type === 'roof' || surface.type === 'ceiling') {
            // Double-sided slabs may be hit from behind their stored normal.
            // Keep the actual clicked side, including imported/rotated meshes.
            if (normal?.dot(event.ray.direction) > 0) normal.negate()
            surface.type = normal?.y < -1e-5 ? 'ceiling' : 'roof'
          }
          const cameraRoom = surface.type === 'ceiling'
            ? roomForSurface({ type: 'ceiling' }, event.ray.origin, rooms)
            : null
          const room = cameraRoom || roomForSurface(surface, event.point, rooms, event.ray.origin)
          const wallSurface = surface.type === 'wall' || surface.type === 'window'
          const wallSide = wallSurface && !surface.exterior ? wallSideAtPoint(room, event.point) : null
          const boundaryBox = surface.exterior ? new THREE.Box3().setFromObject(surface.object) : null
          if (surface.type === 'wall' && !surface.exterior && Math.abs(normal?.y || 0) > 0.5 && room) {
            const inward = { front: [0, 0, 1], back: [0, 0, -1], left: [1, 0, 0], right: [-1, 0, 0] }
            normal = new THREE.Vector3(...inward[wallSide])
          }
          onSelectEntity?.({
            ...surface,
            ...(['roof', 'ceiling'].includes(surface.type) ? { surfaceObject: event.object } : {}),
            boundaryBounds: boundaryBox ? { minX: boundaryBox.min.x, maxX: boundaryBox.max.x, minY: -boundaryBox.max.z, maxY: -boundaryBox.min.z, base: boundaryBox.min.y, height: boundaryBox.max.y - boundaryBox.min.y } : null,
            opening: openingFromObject(surface.object),
            roomId: surface.type === 'ceiling' ? room?.id || null
              : surface.type === 'ground' ? 'exterior_ground' : (surface.roomId || room?.id || null),
            wallId: wallSurface ? (surface.type === 'wall' ? surface.id : null) : null,
            wallSide,
            surfaceNormal: normal ? { x: normal.x, y: normal.y, z: normal.z } : null,
            hitPoint: { x: event.point.x, y: event.point.y, z: event.point.z },
            source: 'blender',
          })
        }}
      />
      {[...openingRoots].map(([key, entry]) => {
        const asset = resolveOpeningAsset(design?.opening_overrides?.[key], uploadedAssets)
        if (!asset) return null
        const { opening, originals } = entry
        const point = new THREE.Vector3(...opening.position)
        const room = roomForSurface({}, point, rooms)
        const selection = { type: opening.type, id: opening.id, opening, source: 'blender',
          roomId: selectedEntity?.type === opening.type && selectedEntity.id === opening.id
            ? selectedEntity.roomId : room?.id,
          wallSide: selectedEntity?.type === opening.type && selectedEntity.id === opening.id
            ? selectedEntity.wallSide : wallSideAtPoint(room, point),
          surfaceNormal: selectedEntity?.type === opening.type && selectedEntity.id === opening.id
            ? selectedEntity.surfaceNormal : null }
        return <OpeningAsset key={key} asset={asset} opening={opening} originals={originals}
          visible={entry.visible}
          selection={selection} onSelect={editingEnabled ? (entity) => {
            const hit = new THREE.Vector3(entity.hitPoint.x, entity.hitPoint.y, entity.hitPoint.z)
            const hitRoom = roomForSurface({}, hit, rooms, entity.cameraPoint)
            const wallSide = wallSideAtPoint(hitRoom, hit)
            onSelectEntity?.({ ...entity, roomId: hitRoom?.id, wallSide, surfaceNormal: null })
          } : null}
          selected={selectedEntity?.type === opening.type && selectedEntity.id === opening.id}
          onObjectReady={onSelectionObjectReady} />
      })}
      {replacementItems.map((item) => {
        const original = cloneBundle.furnitureRoots.get(item.id)
        const visible = original
          ? Boolean(original.userData.__archgenEditorBaseVisible)
          : true
        return (
          <AssetLoadBoundary key={`${item.id}:${item.model_path}`}>
          <Suspense fallback={null}>
            <BlenderReplacementAsset
              item={item}
              visible={visible}
              onReady={() => setReplacementReady((current) => {
                const key = `${item.id}:${item.model_path}`
                return current[key] ? current : { ...current, [key]: true }
              })}
              isSelected={selectedEntity?.type === 'furniture' && selectedEntity.id === item.id}
              onSelect={onSelectEntity}
              onObjectReady={(object) => onSelectionObjectReady?.({
                type: 'furniture',
                id: item.id,
                roomId: item.room_id || item.roomId,
                object,
                source: 'blender',
              })}
            />
          </Suspense>
          </AssetLoadBoundary>
        )
      })}
    </group>
  )
}

// Preload utility for snappy scene loads with Draco decoder support
BlenderHouseModel.preload = (url) => {
  if (url) {
    useGLTF.preload(url, DRACO_DECODER_PATH)
  }
}

BlenderHouseModel.clear = (url) => {
  if (url) {
    useGLTF.clear(url)
  }
}
